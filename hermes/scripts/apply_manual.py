"""Manual-match resolver: close the loop on human-resolved Tracker rows.

When Hermes couldn't confidently match a PO (Needs Review / No Match), a human
picks the right quotation in Odoo and types its number into the Orders tab's
"Manual SO #" column (K). This script applies what an automatic match would have
done: re-downloads the PO PDF from Gmail (via the stored Gmail Msg ID), performs
the same narrow Odoo writes (client_order_ref, terms, PDF attachment, chatter
note — it NEVER confirms the SO), and updates the row: Match Status becomes
"Matched (manual)" and Odoo SO ID (col L) is filled — that SO ID is the
idempotency marker, so resolved rows are never picked up again.

Honors runtime.dry_run: in dry-run nothing is written to Odoo or the Orders row
(so a later --live run still fires); intended actions go to the console and the
Audit tab. Timer-friendly one-shot, same as intake.py.

Usage:  python scripts/apply_manual.py [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.actions import ActionOutcome, annotate_odoo, _now  # noqa: E402
from connectors.gmail_client import GmailClient, GmailError  # noqa: E402
from connectors.odoo_client import OdooClient, OdooError  # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

# Orders column indices (0-based, col A = 0). Must stay in lockstep with
# ORDERS_HEADERS in scripts/setup_sheet.py.
PO_NUM, STATUS, MANUAL_SO, SO_ID, GMAIL_MSG = 1, 7, 10, 11, 18
RESOLVED_STATUS = "Matched (manual)"


def _cell(row: list, idx: int) -> str:
    return (row[idx] if len(row) > idx else "").strip()


def _resolve_so(odoo: OdooClient, so_name: str) -> dict | None:
    """Find exactly one sale.order for the human-typed number; None if 0 or 2+."""
    fields = ["name", "user_id", "invoice_status", "state"]
    recs = odoo.search_read("sale.order", [["name", "=", so_name]], fields, limit=2)
    if not recs:
        recs = odoo.search_read("sale.order", [["name", "ilike", so_name]], fields, limit=2)
    return recs[0] if len(recs) == 1 else None


def _fetch_pdf(gm: GmailClient, msg_id: str, po_number: str) -> tuple[str, bytes, dict]:
    """Re-download the PO PDF and email headers for the chatter note.

    Returns (filename, pdf_bytes, email_meta); pdf_bytes is b"" when the message
    has no single unambiguous PDF (annotate_odoo then simply skips the attach).
    """
    full = gm.get_message(msg_id)
    h = gm.headers(full)
    meta = {"from": h.get("from", ""), "subject": h.get("subject", ""), "date": h.get("date", "")}
    pdfs = gm.pdf_attachments(full)
    if len(pdfs) == 1:
        return pdfs[0][0], pdfs[0][1], meta
    # ponytail: multi-PDF emails — pick by PO# in the filename, else skip the
    # attach; parsing every PDF to disambiguate can come later if it ever happens.
    for fn, data in pdfs:
        if po_number and po_number in fn:
            return fn, data, meta
    return "", b"", meta


def run_once(gm, odoo, sheets, cfg, dry) -> int:
    tabs = cfg["sheets"]["tabs"]
    orders_tab, audit_tab = tabs["orders"], tabs["audit"]
    write = cfg.get("write", {})
    run_mode = "dry-run" if dry else "live"
    rows = sheets.read(f"{orders_tab}!A2:V")

    applied = 0
    for i, r in enumerate(rows):
        rownum = i + 2
        manual_so = _cell(r, MANUAL_SO)
        # Idempotency keys on Odoo SO ID (col L), which only Hermes writes: an
        # auto-matched or already-resolved row has it, a human-typed status doesn't.
        if not manual_so or _cell(r, SO_ID):
            continue  # nothing to resolve, or already linked to an SO

        po_number = _cell(r, PO_NUM)
        msg_id = _cell(r, GMAIL_MSG)
        audit_rows: list[list] = []

        def _audit(action, detail, result):
            audit_rows.append([_now(), po_number, action, detail, result, run_mode])

        q = _resolve_so(odoo, manual_so)
        if not q:
            print(f"  row {rownum}: Manual SO '{manual_so}' not found (or ambiguous) in Odoo — skipped")
            _audit("error", f"manual SO '{manual_so}' not found or ambiguous (row {rownum})", "error")
            for a in audit_rows:
                sheets.append_row(audit_tab, a)
            continue

        filename, pdf_bytes, email_meta = ("", b"", {})
        if msg_id:
            try:
                filename, pdf_bytes, email_meta = _fetch_pdf(gm, msg_id, po_number)
            except Exception as exc:  # message gone/label moved — still do the other writes
                _audit("error", f"could not re-fetch PDF from Gmail msg {msg_id}: {exc}", "error")
        if not pdf_bytes:
            print(f"  row {rownum}: no PDF recovered for PO {po_number or '?'} — annotating without attachment")

        out = ActionOutcome(dry_run=dry, status=RESOLVED_STATUS, so_id=q["id"], so_name=q["name"])
        annotate_odoo(odoo, write, q, po_number, pdf_bytes, filename,
                      "manual", email_meta, dry, out, _audit)

        if dry:
            print(f"  row {rownum}: [SIM] PO {po_number or '?'} -> {q['name']} "
                  f"(ref/terms/pdf/chatter would be written)")
        else:
            salesperson = q["user_id"][1] if isinstance(q.get("user_id"), (list, tuple)) else ""
            invoice_status = q.get("invoice_status") or ""
            sheets.update_range(f"{orders_tab}!D{rownum}:E{rownum}", [[salesperson, q["name"]]])
            sheets.update_range(f"{orders_tab}!H{rownum}:I{rownum}", [[RESOLVED_STATUS, "manual"]])
            sheets.update_range(f"{orders_tab}!L{rownum}:R{rownum}", [[
                q["id"], out.ref_written, out.pdf_attached, out.chatter_posted,
                out.terms_updated, invoice_status, "Yes" if invoice_status == "invoiced" else "No",
            ]])
            _audit("sheet_upsert", f"row {rownum} resolved manually to {q['name']}", "ok")
            print(f"  row {rownum}: PO {po_number or '?'} -> {q['name']}  "
                  f"ref={out.ref_written} pdf={out.pdf_attached} chatter={out.chatter_posted} "
                  f"terms={out.terms_updated}")
        applied += 1
        for a in audit_rows:
            sheets.append_row(audit_tab, a)

    return applied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="write to Odoo and the Orders row (override dry_run)")
    ap.add_argument("--odoo-db", default=None, help="target a different Odoo database (e.g. a test copy)")
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

    print(f"Manual resolver  Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")
    n = run_once(gm, odoo, sheets, cfg, dry)
    print(f"  -> {n} row(s) {'simulated' if dry else 'resolved'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
