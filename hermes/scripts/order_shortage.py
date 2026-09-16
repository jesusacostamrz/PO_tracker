"""Shortage report: what must be PURCHASED to fulfill one Sales Order.

Compares the order's lines (Odoo) against on-hand stock (the inventory
spreadsheet's Actualizacion tab) and prints the shortfall. READ-ONLY —
writes nothing to Odoo or Sheets.

Usage (from hermes/):
    python scripts/order_shortage.py S03107
    python scripts/order_shortage.py S03107 --part-col B --qty-col E   # override auto-detect

Requires sheets.inventory_spreadsheet_id in config (env
SHEETS_INVENTORY_SPREADSHEET_ID) and the workbook shared with the
service account (Viewer is enough for this script).
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.odoo_client import OdooClient  # noqa: E402
from connectors.sheets_client import SheetsClient  # noqa: E402

# Header-cell candidates for auto-detecting the two columns we need
# (case/accent-insensitive substring match).
PART_HEADERS = ["no. parte", "numero de parte", "num. parte", "parte", "part",
                "sku", "codigo", "modelo", "producto", "item", "articulo"]
QTY_HEADERS = ["existencia", "stock", "inventario", "disponible", "on hand",
               "cantidad", "qty", "piezas"]


def norm(s) -> str:
    """Accent-insensitive, case-insensitive, trimmed."""
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().lower()


def key(s) -> str:
    """Match key: norm + all whitespace removed — the sheet writes Phoenix-style
    part numbers with spaces ('32 09 53 6') that Odoo stores compact ('3209536')."""
    return "".join(norm(s).split())


def to_qty(cell) -> float:
    try:
        return float(str(cell).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def col_letter_to_idx(letter: str) -> int:
    idx = 0
    for c in letter.strip().upper():
        idx = idx * 26 + (ord(c) - ord("A") + 1)
    return idx - 1


def find_col(header_row: list, candidates: list[str]) -> int | None:
    cells = [norm(c) for c in header_row]
    for cand in candidates:  # candidate order = priority
        for i, cell in enumerate(cells):
            if cell and cand in cell:
                return i
    return None


def stock_map(rows: list[list], part_idxs: list[int], qty_idx: int) -> dict[str, float]:
    """part#/modelo -> on-hand qty. Duplicate rows (e.g. per location) are summed.
    Each row is indexed under every part column that has a value; an order line
    matches at most one of those keys, so quantities aren't double-counted."""
    out: dict[str, float] = {}
    for r in rows:
        qty = to_qty(r[qty_idx]) if len(r) > qty_idx else 0.0
        # distinct keys per row: part# and modelo holding the SAME value must
        # not double-count this row's qty
        keys = {key(r[pi]) for pi in part_idxs if len(r) > pi and str(r[pi]).strip()}
        for k in keys:
            out[k] = out.get(k, 0.0) + qty
    return out


def shortage(lines: list[dict], stock: dict[str, float]) -> list[dict]:
    """One row per order line: ordered vs on hand vs to-buy."""
    report = []
    for l in lines:
        pid = l.get("product_id")
        name = pid[1] if isinstance(pid, (list, tuple)) else (l.get("name") or "")
        ordered = float(l.get("product_uom_qty") or 0)
        k = key(name)
        in_sheet = k in stock
        on_hand = stock.get(k, 0.0)
        report.append({
            "product_id": pid[0] if isinstance(pid, (list, tuple)) else pid,
            "part": name,
            "ordered": ordered,
            "on_hand": on_hand,
            "buy": max(0.0, ordered - on_hand),
            "in_sheet": in_sheet,
        })
    return report


def fmt(n: float) -> str:
    return f"{n:g}"


def compute(cfg, odoo: OdooClient, so_name: str,
            part_col: str | None = None, qty_col: str | None = None):
    """(order, report_rows, stock_source_desc) for one Sales Order.
    Raises RuntimeError with a user-readable message on any lookup problem."""
    orders = odoo.search_read("sale.order", [["name", "=", so_name]],
                              ["name", "partner_id", "state"], limit=1)
    if not orders:
        raise RuntimeError(f"No Sales Order named {so_name!r} in Odoo.")
    order = orders[0]
    lines = odoo.order_lines(order["id"])
    # section/note lines have no product
    lines = [l for l in lines if l.get("product_id")]

    tab = cfg["sheets"]["tabs"].get("inventory", "Actualizacion")
    sheets = SheetsClient.from_config(cfg, key="inventory_spreadsheet_id")
    values = sheets.read(f"{tab}!A1:Z")
    if not values:
        raise RuntimeError(f"Tab {tab!r} is empty or missing in the inventory workbook.")
    header, rows = values[0], values[1:]

    part_idx = col_letter_to_idx(part_col) if part_col else find_col(header, PART_HEADERS)
    qty_idx = col_letter_to_idx(qty_col) if qty_col else find_col(header, QTY_HEADERS)
    if part_idx is None or qty_idx is None:
        raise RuntimeError(
            "Could not auto-detect the part/qty columns. Header row is:\n  "
            + " | ".join(f"{chr(65+i)}: {c}" for i, c in enumerate(header))
            + "\nRe-run with --part-col <letter> --qty-col <letter>."
        )
    part_idxs = [part_idx]
    modelo_idx = find_col(header, ["modelo"])
    if modelo_idx is not None and modelo_idx not in part_idxs:
        part_idxs.append(modelo_idx)

    report = shortage(lines, stock_map(rows, part_idxs, qty_idx))
    source = f"'{tab}' tab, part col {chr(65+part_idx)}, qty col {chr(65+qty_idx)}"
    return order, report, source


def main() -> int:
    ap = argparse.ArgumentParser(description="Purchasing shortage report for one Sales Order")
    ap.add_argument("so", help="Sales Order name, e.g. S03107")
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
    partner = order["partner_id"][1] if isinstance(order["partner_id"], (list, tuple)) else ""

    print(f"\nShortage report — {order['name']}  ({partner})  [state: {order['state']}]")
    print(f"Stock source: {source}\n")
    w = max([len(r["part"]) for r in report] + [12])
    print(f"{'Part':<{w}}  {'Ordered':>8}  {'On hand':>8}  {'BUY':>8}")
    print("-" * (w + 30))
    for r in report:
        note = "" if r["in_sheet"] else "   (not in inventory sheet)"
        print(f"{r['part']:<{w}}  {fmt(r['ordered']):>8}  {fmt(r['on_hand']):>8}  "
              f"{fmt(r['buy']):>8}{note}")
    print("-" * (w + 30))
    covered = len(report) - len(to_buy)
    print(f"{len(report)} lines: {covered} covered by stock, {len(to_buy)} need purchasing "
          f"({fmt(sum(r['buy'] for r in to_buy))} pcs total).")
    missing = [r for r in report if not r["in_sheet"]]
    if missing:
        print(f"NOTE: {len(missing)} part(s) not found in the inventory sheet — "
              f"counted as 0 on hand. Verify naming matches the Odoo product name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
