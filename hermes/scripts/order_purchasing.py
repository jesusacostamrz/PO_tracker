"""Vendor clustering + draft purchase RFQs for one Sales Order's shortage.

Extends order_shortage.py: whatever stock can't cover is clustered by each
product's vendor (``product.supplierinfo``, same records import_pricelist.py
maintains). Parts with a vendor on file become ONE DRAFT purchase RFQ per
vendor in Odoo; parts without a vendor go into one extra draft RFQ on the
placeholder vendor "Sin proveedor (asignar)" — purchasing changes the partner
or duplicates that RFQ to split it across vendors, right in Odoo.

Linking: each RFQ's Source Document (``origin``) is the customer SO name, so
in Odoo the requisition shows e.g. "S03107" and is searchable by it; a chatter
note on the SO lists the RFQs created.

DEFAULTS TO DRY-RUN (prints the clustering, writes nothing). --live creates
the draft RFQs — it NEVER confirms one and NEVER sends one to a vendor; a
human reviews and sends from Odoo. Idempotent per (SO, vendor): a vendor that
already has any RFQ citing this SO is skipped, so re-runs don't duplicate.

Usage (from hermes/):
    python scripts/order_purchasing.py S03107 [--live] [--part-col B --qty-col E]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.odoo_client import OdooClient  # noqa: E402
from scripts.order_shortage import compute, fmt  # noqa: E402

PLACEHOLDER_VENDOR = "Sin proveedor (asignar)"


def cluster(to_buy: list[dict], tmpl_map: dict[int, int],
            sinfo: dict[int, dict]) -> tuple[dict, list[dict]]:
    """Split shortage rows into ({(vendor_id, vendor_name): [rfq line]}, unassigned).
    RFQ line qty is the shortage; price is our last known cost for that vendor."""
    by_vendor: dict[tuple[int, str], list[dict]] = {}
    unassigned: list[dict] = []
    for r in to_buy:
        si = sinfo.get(tmpl_map.get(r["product_id"]))
        if not si or not si.get("partner_id"):
            unassigned.append(r)
            continue
        vid, vname = si["partner_id"][0], si["partner_id"][1]
        line = {"product_id": r["product_id"], "name": r["part"],
                "product_qty": r["buy"], "price_unit": float(si.get("price") or 0.0)}
        min_qty = float(si.get("min_qty") or 0.0)
        if min_qty > r["buy"]:
            line["_min_qty_note"] = min_qty  # surfaced in the report; human decides
        by_vendor.setdefault((vid, vname), []).append(line)
    return by_vendor, unassigned


def plan_rfqs(odoo, origin: str, to_buy: list[dict], live: bool,
              out=print) -> tuple[list[tuple[int, str, str]], bool]:
    """Plan vendor drafts. Returns (created (id, name, vendor) tuples — none in
    dry-run, whether any line had no vendor on file)."""
    tmpl_map = odoo.product_tmpl_map([r["product_id"] for r in to_buy if r["product_id"]])
    sinfo = odoo.supplierinfo_by_tmpl(set(tmpl_map.values()))
    by_vendor, unassigned = cluster(to_buy, tmpl_map, sinfo)
    if unassigned:
        # Lines with no vendor on file go into ONE draft RFQ on a placeholder
        # vendor: purchasing reassigns the partner (or duplicates the RFQ to
        # split it across vendors) from Odoo instead of losing the lines.
        pid = odoo.ensure_vendor(PLACEHOLDER_VENDOR) if live else 0
        by_vendor[(pid, PLACEHOLDER_VENDOR)] = [
            {"product_id": r["product_id"], "name": r["part"],
             "product_qty": r["buy"], "price_unit": 0.0} for r in unassigned]

    existing = odoo.purchase_orders_by_origin(origin)
    existing_by_partner: dict[int, dict] = {}
    for po in existing:
        pid = po["partner_id"][0] if isinstance(po["partner_id"], (list, tuple)) else po["partner_id"]
        existing_by_partner.setdefault(pid, po)

    mode = "LIVE" if live else "DRY-RUN (no writes; use --live to create the draft RFQs)"
    out(f"\nPurchasing plan — {origin}  [{mode}]")
    out(f"{len(to_buy)} lines to buy -> {len(by_vendor) - bool(unassigned)} vendor(s) on file, "
          f"{len(unassigned)} line(s) with no vendor (-> RFQ on {PLACEHOLDER_VENDOR!r}).\n")

    created: list[tuple[int, str, str]] = []
    for (vid, vname), lines in sorted(by_vendor.items(), key=lambda kv: kv[0][1]):
        subtotal = sum(l["product_qty"] * l["price_unit"] for l in lines)
        out(f"── {vname}  ({len(lines)} lines, est. cost {subtotal:,.2f})")
        for l in lines:
            note = ""
            if "_min_qty_note" in l:
                note = f"   [vendor min qty {fmt(l['_min_qty_note'])} — review]"
            price = f" @ {l['price_unit']:,.2f}" if l["price_unit"] else " @ cost unknown"
            out(f"   {l['name']:<32} x {fmt(l['product_qty']):>6}{price}{note}")
        prior = existing_by_partner.get(vid)
        if prior:
            out(f"   -> SKIPPED: {prior['name']} ({prior['state']}) already cites "
                  f"{origin} for this vendor.\n")
            continue
        if live:
            rfq_lines = [{k: v for k, v in l.items() if not k.startswith("_")} for l in lines]
            rfq_id = odoo.create_draft_rfq(vid, origin, rfq_lines)
            rfq_name = odoo.read_field("purchase.order", rfq_id, "name")
            created.append((rfq_id, rfq_name, vname))
            out(f"   -> created DRAFT RFQ {rfq_name} (origin: {origin}) — "
                  f"review and send from Odoo.\n")
        else:
            out(f"   -> would create 1 draft RFQ (origin: {origin}).\n")

    if unassigned:
        out(f"NOTE: the {PLACEHOLDER_VENDOR!r} RFQ holds the lines with no vendor on file — "
              "in Odoo change its vendor, or duplicate it per vendor and trim the lines.\n")

    return created, bool(unassigned)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Cluster a Sales Order's shortage by vendor; --live creates draft RFQs")
    ap.add_argument("so", help="Sales Order name, e.g. S03107")
    ap.add_argument("--live", action="store_true", help="actually create draft RFQs in Odoo")
    ap.add_argument("--part-col", help="inventory tab column letter holding the part number")
    ap.add_argument("--qty-col", help="inventory tab column letter holding on-hand qty")
    args = ap.parse_args()

    cfg = load_config()
    odoo = OdooClient.from_config(cfg)
    try:
        order, report, source = compute(cfg, odoo, args.so, args.part_col, args.qty_col)
    except RuntimeError as e:
        print(e)
        return 1

    to_buy = [r for r in report if r["buy"] > 0]
    if not to_buy:
        print(f"{order['name']}: stock covers every line — nothing to purchase.")
        return 0

    print(f"\nStock source: {source}")
    created, unassigned = plan_rfqs(odoo, order["name"], to_buy, args.live)

    if args.live and created:
        odoo.post_chatter(order["id"],
                          "<p>Hermes: requisiciones de compra (borrador) creadas para "
                          "cubrir faltantes de esta orden: " + ", ".join(f"{name} ({vendor})" for _, name, vendor in created) +
                          ". Revisar y enviar desde Compras."
                          + (f" La RFQ de '{PLACEHOLDER_VENDOR}' agrupa partidas sin proveedor: "
                             "cambiar el proveedor o duplicarla por proveedor." if unassigned else "")
                          + "</p>")
        print(f"Created {len(created)} draft RFQ(s); chatter note posted on {order['name']}. "
              f"Nothing was confirmed or sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
