"""Gmail RFQ intake: poll RFQ emails -> parse -> match products -> draft quote -> label.

Mirrors scripts/intake.py. One-shot (timer-friendly); --watch N to keep polling.
Dry-run: nothing written to Odoo, no labels applied, Quotes row logged as Dry-run.
Live: draft quotation created, Pricing Queue populated, message labeled
Hermes/Processed (all lines auto-priced) or Hermes/NeedsReview (anything queued,
customer unknown, or error). Idempotency on Gmail msg id inside apply_rfq.

Usage:  python scripts/intake_rfq.py [--live] [--odoo-db NAME] [--max N] [--watch SECONDS] [--mark-read]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.rfq_parser import parse_rfq                  # noqa: E402
from core.product_matcher import match_lines           # noqa: E402
from core.quote_actions import apply_rfq               # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.gmail_client import GmailClient, GmailError      # noqa: E402
from connectors.odoo_client import OdooClient, OdooError         # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError   # noqa: E402

XLSX_EXTS = (".xlsx", ".xlsm")
IMG_EXTS = (".png", ".jpg", ".jpeg")


def _sources_from_message(gm: GmailClient, full: dict) -> list[tuple[str, str, bytes | str]]:
    """Collect RFQ content: spreadsheets first, then images, then the email body."""
    sources: list[tuple[str, str, bytes | str]] = []
    for fn, data in gm.attachments_by_ext(full, XLSX_EXTS):
        sources.append(("xlsx", fn, data))
    for fn, data in gm.attachments_by_ext(full, IMG_EXTS):
        sources.append(("image", fn, data))
    body = gm.body_text(full)
    if body and not any(k == "xlsx" for k, _, _ in sources):
        sources.append(("text", "email-body", body))
    return sources


def _process_message(gm, odoo, sheets, cfg, llm, products, msg_id, dry, mark_read, lines_out):
    labels = cfg["rfq"]["labels"]
    full = gm.get_message(msg_id)
    subj = (gm.headers(full).get("subject") or "(no subject)")[:50]

    sources = _sources_from_message(gm, full)
    if not sources:
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        lines_out.append(f"  [{'SIM' if dry else 'NeedsReview'}] {subj} — no usable content")
        return

    rfq = parse_rfq(sources, llm, cfg.get("company", {}))
    if not rfq["line_items"]:
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        lines_out.append(f"  [{'SIM' if dry else 'NeedsReview'}] {subj} — no line items extracted")
        return

    matches = match_lines(rfq["line_items"], products, cfg["rfq"]["match"])
    out = apply_rfq(odoo, sheets, cfg, rfq, matches, gmail_msg_id=msg_id, dry_run=dry)

    clean = out.queued == 0 and out.status in ("Draft Created", "Dry-run") and not out.skipped
    if not dry:
        gm.apply_label(msg_id, labels["processed"] if clean else labels["needs_review"],
                       mark_read=mark_read)
    tag = "SIM" if dry else ("Processed" if clean else "NeedsReview")
    lines_out.append(f"  [{tag}] {subj} — {out.status}: quote={out.order_name or '-'} "
                     f"auto={out.auto_priced} queued={out.queued}"
                     + (" (skipped: already tracked)" if out.skipped else ""))


def run_once(gm, odoo, sheets, cfg, llm, dry, max_msgs, mark_read) -> list[str]:
    lines_out: list[str] = []
    msgs = gm.search(cfg["rfq"]["poll_query"], max_results=max_msgs)
    if not msgs:
        return lines_out
    products = odoo.all_products()  # fetch the pool once per batch
    for m in msgs:
        try:
            _process_message(gm, odoo, sheets, cfg, llm, products, m["id"], dry, mark_read, lines_out)
        except Exception as exc:  # one bad message must not kill the batch
            if not dry:
                try:
                    gm.apply_label(m["id"], cfg["rfq"]["labels"]["needs_review"], mark_read=mark_read)
                except Exception:
                    pass
            lines_out.append(f"  [ERROR] msg {m['id']} — {type(exc).__name__}: {exc}")
    return lines_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--watch", type=int, default=0)
    ap.add_argument("--mark-read", action="store_true")
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
    print(f"RFQ intake  Gmail: {gm.account}  Odoo db: {cfg['odoo']['db']}  "
          f"mode: {'DRY-RUN' if dry else 'LIVE'}")

    while True:
        try:
            for line in run_once(gm, odoo, sheets, cfg, llm, dry, args.max, args.mark_read) or ["  (no RFQ messages)"]:
                print(line)
        except Exception as exc:
            print(f"[poll] failed: {type(exc).__name__}: {exc}")
        if args.watch <= 0:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
