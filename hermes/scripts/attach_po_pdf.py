"""Attach a PO PDF to a sale order after the fact (when apply_manual couldn't
re-fetch it from Gmail) and repair the Tracker row: PDF Attached = Yes, plus
the Gmail Msg ID if given. Dry-run by default; --live writes.

Run:  python scripts/attach_po_pdf.py /tmp/105381_UNICONTROL.pdf S03259 --po 105381 [--gmail-msg-id ID] [--live]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.actions import _attachment_name  # noqa: E402
from connectors.odoo_client import OdooClient  # noqa: E402
from connectors.sheets_client import SheetsClient  # noqa: E402

PO_NUM, PDF_ATTACHED, GMAIL_MSG = 1, 13, 18  # Orders cols B, N, S (lockstep with setup_sheet.py)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("so", help="sale order name, e.g. S03259")
    ap.add_argument("--po", required=True, help="customer PO number (Tracker row key + attachment name)")
    ap.add_argument("--gmail-msg-id", default="")
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    odoo = OdooClient.from_config(cfg)
    recs = odoo.search_read("sale.order", [["name", "=", a.so]], ["name"], limit=2)
    if len(recs) != 1:
        print(f"{a.so}: {len(recs)} sale orders found — need exactly 1")
        return 1
    pdf_bytes = Path(a.pdf).read_bytes()
    name = _attachment_name(a.po, Path(a.pdf).name)

    sheets = SheetsClient.from_config(cfg)
    tab = cfg["sheets"]["tabs"]["orders"]
    rows = sheets.read(f"{tab}!A1:Z")
    rownum = next((i for i, r in enumerate(rows[1:], start=2)
                   if len(r) > PO_NUM and r[PO_NUM].strip() == a.po), None)

    print(f"attach {name} ({len(pdf_bytes)} bytes) to {a.so} (id {recs[0]['id']}); Tracker row {rownum or 'NOT FOUND'}")
    if not a.live:
        print("dry-run: nothing written (add --live)")
        return 0
    att = odoo.attach_pdf(recs[0]["id"], name, pdf_bytes)
    print(f"attached id={att}")
    if rownum:
        sheets.update_range(f"{tab}!N{rownum}", [["Yes"]])
        if a.gmail_msg_id:
            sheets.update_range(f"{tab}!S{rownum}", [[a.gmail_msg_id]])
        print("Tracker row updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
