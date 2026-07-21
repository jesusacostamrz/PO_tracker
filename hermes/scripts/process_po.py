"""Process one PO end-to-end: parse -> match -> act (Odoo writes + Tracker rows).

Honors runtime.dry_run from the config. Pass --live to actually write to Odoo for
this run; pass --odoo-db to target a duplicate test database instead of production.

Usage:
  python scripts/process_po.py <path-to-po.pdf> [--live] [--odoo-db NAME] [--gmail-msg-id ID]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.po_parser import parse_po  # noqa: E402
from core.pipeline import candidate_quotes, match_po_to_quotes  # noqa: E402
from core.actions import apply_match  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402
from connectors.odoo_client import OdooClient, OdooError  # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--live", action="store_true", help="actually write to Odoo (override dry_run)")
    ap.add_argument("--odoo-db", default=None, help="target a different Odoo database (e.g. a test copy)")
    ap.add_argument("--gmail-msg-id", default="", help="source Gmail message id (idempotency)")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"not found: {pdf_path}")
        return 2

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    llm = LLMClient.from_config(cfg)
    pdf_bytes = pdf_path.read_bytes()
    po = parse_po(pdf_bytes, llm, cfg.get("company", {}))
    doc_type = po.get("doc_type") or "purchase_order"
    if doc_type != "purchase_order":
        print(f"NOT A PO — document classified as '{doc_type}' "
              f"({po.get('customer_name')}, ref {po.get('po_number') or '-'}). Nothing written.")
        return 3
    print(f"Parsed PO {po.get('po_number')} — {po.get('customer_name')} "
          f"({po.get('subtotal')} {po.get('currency')})")

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1

    quotes = candidate_quotes(odoo, cfg)
    res = match_po_to_quotes(odoo, cfg, po, quotes)
    print(f"Match: {res.status.upper()} (confidence {res.confidence}) — {res.reason}")

    print(f"\nApplying actions  [db={cfg['odoo']['db']}]  [mode={'DRY-RUN' if dry else 'LIVE'}]")
    out = apply_match(odoo, sheets, cfg, po, res, pdf_bytes,
                      filename=pdf_path.name, gmail_msg_id=args.gmail_msg_id, dry_run=dry)

    if out.skipped:
        print("  SKIPPED (already in Tracker).")
    else:
        tag = "DRY-RUN" if out.dry_run else "LIVE"
        print(f"  SO            : {out.so_name or '-'} (id {out.so_id or '-'})")
        print(f"  Ref written   : {out.ref_written}")
        print(f"  PDF attached  : {out.pdf_attached}" + (f" (attachment id {out.attachment_id})" if out.attachment_id else ""))
        print(f"  Chatter posted: {out.chatter_posted}")
        print(f"  Terms updated : {out.terms_updated}")
        print(f"  Tracker row + Audit log written ({tag}).")
    for n in out.notes:
        print(f"    - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
