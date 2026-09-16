"""Diagnose why a PO email was (or wasn't) processed: find it by Gmail query,
save its first PDF to /tmp, and print the extracted text + parser verdict.
Read-only (no Odoo/Sheet writes, no labels).

Run:  python scripts/inspect_po_email.py "subject:105381 has:attachment"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.po_parser import extract_text, parse_po  # noqa: E402
from connectors.gmail_client import GmailClient  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "subject:105381 has:attachment"
    cfg = load_config()
    gm = GmailClient.from_config(cfg)
    msgs = gm.search(query, 5)
    print("MSGS", msgs)
    if not msgs:
        return 1
    full = gm.get_message(msgs[0]["id"])
    print("HEADERS", {k: v for k, v in gm.headers(full).items() if k in ("from", "subject", "date")})
    pdfs = gm.pdf_attachments(full)
    print("PDFS", [(fn, len(b)) for fn, b in pdfs])
    if not pdfs:
        return 1
    fn, b = pdfs[0]
    out = Path("/tmp") / fn.replace(" ", "_")
    out.write_bytes(b)
    print("SAVED", out)
    text = extract_text(b)
    print("TEXTCHARS", len(text))
    print(text[:2000])
    po = parse_po(b, LLMClient.from_config(cfg), cfg.get("company", {}))
    keys = ("doc_type", "_source", "customer_name", "po_number", "supplier_quote_ref", "subtotal", "currency")
    print("PARSED", json.dumps({k: po.get(k) for k in keys}, ensure_ascii=False))
    print("LINES", len(po.get("line_items") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
