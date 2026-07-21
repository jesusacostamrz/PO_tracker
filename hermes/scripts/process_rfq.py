"""Process one local RFQ file (xlsx/csv/png/jpg/txt) -> parse, match, act.

DEFAULTS TO DRY-RUN (runtime.dry_run). --live creates the draft quotation and
writes Tracker rows. No Gmail involved — this is the test bench; idempotency is
skipped (no Gmail msg id), so repeated --live runs create repeated drafts.

Usage:  python scripts/process_rfq.py <file> [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.rfq_parser import parse_rfq                  # noqa: E402
from core.product_matcher import match_lines           # noqa: E402
from core.quote_actions import apply_rfq               # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.odoo_client import OdooClient, OdooError    # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

KINDS = {".xlsx": "xlsx", ".xlsm": "xlsx", ".png": "image", ".jpg": "image",
         ".jpeg": "image", ".txt": "text", ".csv": "text"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    p = Path(args.file)
    kind = KINDS.get(p.suffix.lower())
    if not kind:
        print(f"Unsupported file type: {p.suffix}")
        return 1
    payload = p.read_text(encoding="utf-8", errors="replace") if kind == "text" else p.read_bytes()

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"RFQ {p.name}   Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")

    rfq = parse_rfq([(kind, p.name, payload)], llm, cfg.get("company", {}))
    print(f"  customer: {rfq.get('customer_name')}   ref: {rfq.get('rfq_ref')}   "
          f"lines: {len(rfq['line_items'])}   source: {rfq.get('_source')}")

    products = odoo.all_products()
    matches = match_lines(rfq["line_items"], products, cfg["rfq"]["match"])
    for m in matches:
        tag = "AUTO " if m.status == "matched" else "QUEUE"
        want = m.line.get("part_number") or m.line.get("description", "")[:40]
        got = (m.product or {}).get("name", "-")
        print(f"  [{tag}] {want!r:45} -> {got[:45]!r}  ({m.score:.0f}) {m.reason}")

    out = apply_rfq(odoo, sheets, cfg, rfq, matches, dry_run=dry)
    print(f"  -> status={out.status}  quote={out.order_name or '-'}  "
          f"auto={out.auto_priced}  queued={out.queued}")
    for n in out.notes:
        print("     ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
