"""Gmail intake batch: poll unread PO emails -> parse -> match -> act -> label.

Wraps the same parse/match/act pipeline as scripts/process_po.py, but drives it
from the inbox instead of a single PDF on disk.

One-shot by default (systemd-timer-friendly): it processes every currently-unread
PO message once, then exits. Pass --watch N to keep polling every N seconds.

Honors runtime.dry_run. In dry-run NOTHING is written to Odoo AND no Gmail label is
applied, so the inbox is left untouched and a dry run is fully repeatable. A live run
(--live) performs the narrow Odoo writes (via core.actions.apply_match) and labels
each message:
    all PDFs matched        -> Hermes/Processed
    any needs-review/error  -> Hermes/NeedsReview
    no PDF found            -> Hermes/NeedsReview

Tracker/Odoo idempotency (PO# / Gmail msg id) is enforced inside apply_match, so a
re-poll never double-writes; the labels just keep handled mail out of the poll query.

Usage:
  python scripts/intake.py [--live] [--odoo-db NAME] [--max N] [--watch SECONDS] [--mark-read]
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.po_parser import parse_po  # noqa: E402
from core.pipeline import candidate_quotes, match_po_to_quotes  # noqa: E402
from core.actions import apply_match  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402
from connectors.gmail_client import GmailClient, GmailError  # noqa: E402
from connectors.odoo_client import OdooClient, OdooError  # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402


@dataclass
class BatchStats:
    messages: int = 0
    pdfs: int = 0
    matched: int = 0
    needs_review: int = 0
    skipped: int = 0          # idempotency hits (already a live Tracker row)
    errored: int = 0
    labeled: list[str] = field(default_factory=list)  # human-readable per-message lines


def _process_message(gm, odoo, sheets, cfg, llm, quotes, msg_id, dry, mark_read, st):
    """Parse every PDF on one message, act on each, then label the message."""
    labels = cfg["gmail"]["labels"]
    full = gm.get_message(msg_id)
    h = gm.headers(full)
    subj = (h.get("subject") or "(no subject)")[:50]
    pdfs = gm.pdf_attachments(full)

    if not pdfs:
        st.needs_review += 1
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        st.labeled.append(f"  [{('SIM' if dry else 'NeedsReview')}] {subj} — no PDF attachment")
        return

    email_meta = {"from": h.get("from", ""), "subject": h.get("subject", ""), "date": h.get("date", "")}
    results = []  # (po_number-or-filename, match_status, outcome-or-None)
    for filename, pdf_bytes in pdfs:
        st.pdfs += 1
        po = parse_po(pdf_bytes, llm, cfg.get("company", {}))
        doc_type = po.get("doc_type") or "purchase_order"  # missing field -> assume PO (fail open)
        if doc_type != "purchase_order":
            results.append((filename, f"ignored ({doc_type})", None))
            continue
        res = match_po_to_quotes(odoo, cfg, po, quotes)
        out = apply_match(
            odoo, sheets, cfg, po, res, pdf_bytes,
            filename=filename, gmail_msg_id=msg_id, dry_run=dry, email_meta=email_meta,
        )
        results.append((po.get("po_number") or "?", res.status, out))
        if out.skipped:
            st.skipped += 1

    # Non-PO attachments (quotes, invoices, ...) don't count against the email —
    # but an email whose PDFs are ALL non-PO has nothing to track: needs review.
    po_statuses = [status for _, status, out in results if out is not None]
    all_matched = bool(po_statuses) and all(status == "matched" for status in po_statuses)
    if all_matched:
        st.matched += 1
        target = labels["processed"]
    else:
        st.needs_review += 1
        target = labels["needs_review"]

    if not dry:
        gm.apply_label(msg_id, target, mark_read=mark_read)

    tag = "SIM" if dry else target.split("/")[-1]
    detail = ", ".join(f"{po}:{status}" for po, status, _ in results)
    st.labeled.append(f"  [{tag}] {subj} — {detail}")


def run_once(gm, odoo, sheets, cfg, llm, dry, max_msgs, mark_read) -> BatchStats:
    st = BatchStats()
    query = cfg["gmail"]["poll_query"]
    msgs = gm.search(query, max_results=max_msgs)
    st.messages = len(msgs)
    if not msgs:
        return st

    quotes = candidate_quotes(odoo, cfg)  # fetch the quote pool once for the whole batch
    for m in msgs:
        try:
            _process_message(gm, odoo, sheets, cfg, llm, quotes, m["id"], dry, mark_read, st)
        except Exception as exc:  # one bad message must not kill the batch
            st.errored += 1
            if not dry:
                try:
                    gm.apply_label(m["id"], cfg["gmail"]["labels"]["needs_review"], mark_read=mark_read)
                except Exception:
                    pass
            st.labeled.append(f"  [ERROR] msg {m['id']} — {type(exc).__name__}: {exc}")
    return st


def _print_stats(st: BatchStats, dry: bool) -> None:
    mode = "DRY-RUN (mailbox untouched)" if dry else "LIVE"
    print(f"\nIntake batch [{mode}]: {st.messages} message(s), {st.pdfs} PDF(s)")
    for line in st.labeled:
        print(line)
    print(f"  -> matched={st.matched}  needs_review={st.needs_review}  "
          f"skipped={st.skipped}  errored={st.errored}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write to Odoo AND apply Gmail labels (override dry_run)")
    ap.add_argument("--odoo-db", default=None, help="target a different Odoo database (e.g. a test copy)")
    ap.add_argument("--max", type=int, default=25, help="max messages to pull per poll")
    ap.add_argument("--watch", type=int, default=0, help="keep polling every N seconds (0 = run once)")
    ap.add_argument("--mark-read", action="store_true", help="also clear UNREAD on handled messages (live only)")
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    try:
        gm = GmailClient.from_config(cfg)
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (GmailError, OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"Gmail: {gm.account}   Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")

    if args.watch > 0:
        print(f"Watching every {args.watch}s — Ctrl-C to stop.")
        try:
            while True:
                try:
                    st = run_once(gm, odoo, sheets, cfg, llm, dry, args.max, args.mark_read)
                    _print_stats(st, dry)
                except Exception as exc:  # keep the long-running service alive across transient errors
                    print(f"[watch] poll failed: {type(exc).__name__}: {exc}")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
    else:
        st = run_once(gm, odoo, sheets, cfg, llm, dry, args.max, args.mark_read)
        _print_stats(st, dry)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
