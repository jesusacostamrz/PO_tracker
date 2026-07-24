"""Pricing-queue resolver: apply human pricing decisions back to Odoo drafts.

Intake now auto-creates a product (price 0) and adds a line for EVERY RFQ line up
front, so the order usually already carries a 0-priced line for this product. For
each Pricing Queue row a human resolved (Sale Price + a product id — "Use Product
ID" if set, else create if "Create Product? = Yes", else the intake-suggested
product id in col J):
  1. create the product if asked (name = Description, code = Part #, price = Sale Price)
  2. price the existing 0-priced order line if one exists (write price_unit + qty),
     else add a new line (explicit price_unit = human's price)
  3. mark the row Resolved; refresh the Quotes row (Queued count, Status -> Complete at 0)

Idempotency: only rows with Status == "Pending" are touched; Resolved rows never re-apply.
Honors runtime.dry_run (simulate + audit only). NEVER confirms the order.

Usage:  python scripts/apply_quotes.py [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config          # noqa: E402
from core.actions import _now                # noqa: E402
from connectors.odoo_client import OdooClient, OdooError        # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

# Pricing Queue column indices (0-based). Lockstep with PQ_HEADERS in setup_sheet.py.
PQ_ORDER_NAME, PQ_ORDER_ID, PQ_PART, PQ_DESC, PQ_QTY = 3, 4, 5, 6, 7
PQ_SUGG_ID, PQ_STATUS, PQ_PRICE, PQ_USE_ID, PQ_CREATE = 9, 11, 12, 13, 14
# Quotes tab indices. Lockstep with QUOTES_HEADERS.
Q_QUEUED, Q_ORDER_ID, Q_STATUS = 5, 7, 8


def _cell(row, idx) -> str:
    return str(row[idx] if len(row) > idx else "").strip()


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _refresh_quotes_row(sheets, quotes_tab, pq_rows, order_id) -> None:
    # Error rows still need human attention — a quote is only Complete when none remain.
    pending = sum(1 for r in pq_rows
                  if _cell(r, PQ_ORDER_ID) == str(order_id)
                  and _cell(r, PQ_STATUS) in ("Pending", "Error"))
    qrows = sheets.read(f"{quotes_tab}!A2:K")
    for i, r in enumerate(qrows):
        if _cell(r, Q_ORDER_ID) == str(order_id):
            status = "Complete" if pending == 0 else "Pending Pricing"
            sheets.update_range(f"{quotes_tab}!F{i + 2}", [[pending]])
            sheets.update_range(f"{quotes_tab}!I{i + 2}", [[status]])
            return


def run_once(odoo, sheets, cfg, dry) -> int:
    tabs = cfg["sheets"]["tabs"]
    pq_tab, quotes_tab, audit_tab = tabs["pricing_queue"], tabs["quotes"], tabs["audit"]
    run_mode = "dry-run" if dry else "live"
    rows = sheets.read(f"{pq_tab}!A2:S")

    applied, touched_orders = 0, set()
    for i, r in enumerate(rows):
        rownum = i + 2
        if _cell(r, PQ_STATUS) != "Pending":
            continue
        price = _num(_cell(r, PQ_PRICE))
        use_id = _cell(r, PQ_USE_ID)
        # An explicit product id wins over a stray Create?=Yes — never duplicate a product.
        create = _cell(r, PQ_CREATE).lower() == "yes" and not use_id
        # Intake now auto-creates a product for every unmatched line — fall back to its
        # suggested id so the human only has to type Sale Price.
        suggested_id = _cell(r, PQ_SUGG_ID)
        if price is None or not (use_id or create or suggested_id):
            continue  # human hasn't finished this row

        order_id = _num(_cell(r, PQ_ORDER_ID))
        desc, part = _cell(r, PQ_DESC), _cell(r, PQ_PART)
        qty_raw = _num(_cell(r, PQ_QTY))
        qty = 1.0 if qty_raw is None else qty_raw

        def _audit(action, detail, result):
            sheets.append_row(audit_tab, [_now(), part or desc[:30], action, detail, result, run_mode])

        if order_id is None:
            _audit("error", f"PQ row {rownum} has no Odoo Quote ID", "error")
            if not dry:
                sheets.update_range(f"{pq_tab}!L{rownum}", [["Error"]])
            continue

        if dry:
            what = (f"create product '{desc[:40]}'" if create
                   else f"use product {use_id}" if use_id else f"use suggested product {suggested_id}")
            print(f"  row {rownum}: [SIM] {what}, price order {int(order_id)} @ {price} x {qty:g}")
            _audit("apply_quote_line", f"would {what} on order {int(order_id)} @ {price}", "dry-run")
            applied += 1
            continue

        try:
            if create:
                product_id = odoo.create_product(part or desc, list_price=price,
                                                 description=desc if part else "")
                _audit("odoo_create_product", f"created product {product_id} '{(part or desc)[:40]}'", "ok")
            elif use_id:
                product_id = int(float(use_id))
            else:
                product_id = int(float(suggested_id))
            # Intake usually already added a 0-priced line for this product — price it
            # in place instead of adding a duplicate.
            existing_line = odoo.find_quote_line(int(order_id), product_id)
            if existing_line:
                odoo.update_quote_line(existing_line["id"], {"price_unit": price, "product_uom_qty": qty})
                _audit("apply_quote_line",
                      f"priced existing line for product {product_id} on order {int(order_id)} @ {price}", "ok")
            else:
                odoo.add_quote_lines(int(order_id), [{
                    "product_id": product_id, "product_uom_qty": qty, "price_unit": price,
                }])
                _audit("apply_quote_line", f"added product {product_id} to order {int(order_id)} @ {price}", "ok")
            sheets.update_range(f"{pq_tab}!L{rownum}", [["Resolved"]])
            touched_orders.add(int(order_id))
            applied += 1
            print(f"  row {rownum}: product {product_id} -> order {int(order_id)} @ {price} x {qty:g}")
        except Exception as exc:
            sheets.update_range(f"{pq_tab}!L{rownum}", [["Error"]])
            _audit("error", f"PQ row {rownum}: {type(exc).__name__}: {exc}", "error")
            touched_orders.add(int(order_id))  # refresh its Quotes row too
            print(f"  row {rownum}: ERROR {exc}")

    if not dry and touched_orders:
        fresh = sheets.read(f"{pq_tab}!A2:S")
        for oid in touched_orders:
            _refresh_quotes_row(sheets, quotes_tab, fresh, oid)
    return applied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg, key="quotes_spreadsheet_id")
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1

    print(f"Quote resolver  Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")
    n = run_once(odoo, sheets, cfg, dry)
    print(f"  -> {n} line(s) {'simulated' if dry else 'applied'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
