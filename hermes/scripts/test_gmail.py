"""Read-only Gmail connectivity check.

Authenticates with the stored token, prints the account, runs the poll query,
and lists a few matching messages and whether each carries a PDF. It marks
nothing read and deletes nothing.

Run:  python scripts/test_gmail.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.gmail_client import GmailClient, GmailError  # noqa: E402


def main() -> int:
    cfg = load_config()
    try:
        gm = GmailClient.from_config(cfg)
        print(f"Connected to Gmail as {gm.account}")

        query = cfg["gmail"]["poll_query"]
        msgs = gm.search(query, max_results=10)
        print(f"\nQuery: {query!r}")
        print(f"Found {len(msgs)} matching message(s) (showing up to 10):")
        for m in msgs:
            full = gm.get_message(m["id"])
            h = gm.headers(full)
            pdfs = gm.pdf_attachments(full)
            subj = (h.get("subject") or "(no subject)")[:48]
            frm = (h.get("from") or "?")[:30]
            print(f"  - {subj:<48}  from {frm:<30}  pdf x{len(pdfs)}")
        if not msgs:
            print("  (none — try sending a test PO email to the inbox, or adjust poll_query)")
        print("\nOK — Gmail read path works.")
        return 0
    except GmailError as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
