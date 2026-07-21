"""Action layer: turn a (PO, match-result) into Odoo writes + Tracker rows.

Honors ``runtime.dry_run``. In dry-run nothing is written to Odoo; the intended
actions are logged to the Audit tab (Run Mode = dry-run) and the Orders row records
the statuses as "Dry-run" so a human can see exactly what *would* have happened.

Odoo writes are narrow and reversible: set ``client_order_ref``, attach the PO PDF,
post a chatter note. It NEVER confirms the Sales Order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.utils import parseaddr

from connectors.odoo_client import OdooClient
from connectors.sheets_client import SheetsClient
from core.matcher import MatchResult

_STATUS_LABEL = {"matched": "Matched", "needs_review": "Needs Review", "no_match": "No Match"}


@dataclass
class ActionOutcome:
    dry_run: bool
    status: str                       # Match Status label written to the sheet
    so_id: int | None = None
    so_name: str = ""
    ref_written: str = "No"           # Yes | No | Dry-run
    pdf_attached: str = "No"
    chatter_posted: str = "No"
    terms_updated: str = "No"
    attachment_id: int | None = None
    skipped: bool = False             # idempotency hit
    notes: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.notes.append(msg)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _yn(b: bool) -> str:
    return "Yes" if b else "No"


def _attachment_name(po_number: str, fallback: str) -> str:
    """Name the Odoo attachment after the PO# (e.g. 'PO-290810.pdf').

    Falls back to the source filename when there's no usable PO number.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (po_number or "").strip()).strip("._-")
    return f"{safe}.pdf" if safe else fallback


def _decode_mime(s: str) -> str:
    """Decode RFC 2047 encoded-words (e.g. accented sender names) to plain text."""
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s


def _sender_line(email_from: str) -> str:
    """Turn a raw From header into 'Name <addr>' / 'addr' / '' for the chatter note."""
    name, addr = parseaddr(email_from or "")
    name = _decode_mime(name)
    if name and addr and name != addr:
        return f"{name} <{addr}>"
    return addr or name


def _find_existing(sheets: SheetsClient, orders_tab: str, po_number: str, msg_id: str):
    """Locate a prior Orders row for this PO# / Gmail msg id.

    Returns (row_number_1based, is_dry_run) or None. A *dry-run* row is a simulation
    and does NOT block a later real run — the live run upserts (overwrites) it in place.
    """
    if not (po_number or msg_id):
        return None
    rows = sheets.read(f"{orders_tab}!B2:S")  # window starts at col B: r[0]=PO#, r[17]=Gmail Msg ID
    for i, r in enumerate(rows):
        existing_po = r[0] if len(r) > 0 else ""
        existing_msg = r[17] if len(r) > 17 else ""
        if (po_number and existing_po == po_number) or (msg_id and existing_msg and existing_msg == msg_id):
            # cols M/N/O/P (Ref/PDF/Chatter/Terms) are at window indices 11/12/13/14
            is_dry = any((r[j] if len(r) > j else "") == "Dry-run" for j in (11, 12, 13, 14))
            return (i + 2, is_dry)
    return None


def annotate_odoo(
    odoo: OdooClient,
    write: dict,
    q: dict,
    po_number: str,
    pdf_bytes: bytes,
    filename: str,
    confidence: str,
    email_meta: dict | None,
    dry: bool,
    out: ActionOutcome,
    audit,
) -> None:
    """The four narrow Odoo writes on quote ``q`` (or their dry-run simulation).

    Shared by the automatic matched path (apply_match) and the manual resolver
    (scripts/apply_manual.py). Never confirms the Sales Order. ``audit`` is a
    callable(action, detail, result).
    """
    oid = q["id"]
    if write.get("customer_ref_field") and po_number:
        if dry:
            out.ref_written = "Dry-run"
            audit("odoo_write_ref", f"would set client_order_ref={po_number} on {q['name']}", "dry-run")
        else:
            odoo.set_client_order_ref(oid, po_number)
            out.ref_written = "Yes"
            audit("odoo_write_ref", f"set client_order_ref={po_number} on {q['name']}", "ok")

    if write.get("po_in_terms") and po_number:
        if dry:
            out.terms_updated = "Dry-run"
            audit("odoo_set_terms", f"would append 'PO Cliente: {po_number}' to T&C of {q['name']}", "dry-run")
        else:
            wrote = odoo.set_terms_po(oid, po_number)
            out.terms_updated = "Yes" if wrote else "No"
            audit("odoo_set_terms",
                  f"{'appended' if wrote else 'already present:'} 'PO Cliente: {po_number}' in T&C of {q['name']}",
                  "ok")

    if write.get("attach_pdf") and pdf_bytes:
        attach_name = _attachment_name(po_number, filename)  # save as PO-<#>.pdf
        if dry:
            out.pdf_attached = "Dry-run"
            audit("odoo_attach_pdf", f"would attach as {attach_name} ({len(pdf_bytes)} bytes) to {q['name']}", "dry-run")
        else:
            out.attachment_id = odoo.attach_pdf(oid, attach_name, pdf_bytes)
            out.pdf_attached = "Yes"
            audit("odoo_attach_pdf", f"attached as {attach_name} (id={out.attachment_id}) to {q['name']}", "ok")

    if write.get("post_chatter_note"):
        # Plain text (no HTML): Odoo escapes a str body and converts newlines to
        # <br>, so tags would render literally — see read-back of stored body.
        meta = email_meta or {}
        lines = [
            f"Hermes: linked customer PO {po_number or '(no #)'} to this quotation "
            f"(match confidence {confidence})."
        ]
        sender = _sender_line(meta.get("from", ""))
        if sender:
            lines.append(f"Received from: {sender}.")
        if meta.get("subject"):
            lines.append(f'Email subject: "{meta["subject"]}".')
        if out.pdf_attached in ("Yes", "Dry-run"):
            lines.append("PDF attached.")
        lines.append("Not confirmed — for the salesperson to review.")
        body = "\n".join(lines)
        if dry:
            out.chatter_posted = "Dry-run"
            audit("odoo_chatter", f"would post chatter note on {q['name']}", "dry-run")
        else:
            odoo.post_chatter(oid, body)
            out.chatter_posted = "Yes"
            audit("odoo_chatter", f"posted chatter note on {q['name']}", "ok")


def apply_match(
    odoo: OdooClient,
    sheets: SheetsClient,
    cfg: dict,
    po: dict,
    match: MatchResult,
    pdf_bytes: bytes,
    filename: str,
    gmail_msg_id: str = "",
    dry_run: bool | None = None,
    email_meta: dict | None = None,
) -> ActionOutcome:
    dry = cfg.get("runtime", {}).get("dry_run", True) if dry_run is None else dry_run
    write = cfg.get("write", {})
    tabs = cfg["sheets"]["tabs"]
    orders_tab, audit_tab = tabs["orders"], tabs["audit"]
    run_mode = "dry-run" if dry else "live"

    po_number = (po.get("po_number") or "").strip()
    status = _STATUS_LABEL.get(match.status, "Needs Review")
    out = ActionOutcome(dry_run=dry, status=status)
    audit: list[list] = []

    def _audit(action: str, detail: str, result: str) -> None:
        audit.append([_now(), po_number, action, detail, result, run_mode])

    # --- idempotency: a real (non-dry-run) row blocks; a dry-run row gets upserted ---
    existing = _find_existing(sheets, orders_tab, po_number, gmail_msg_id)
    existing_row = None
    if existing:
        existing_row, was_dry = existing
        if not was_dry:
            out.skipped = True
            out.log("Already in Tracker (live row) — skipped (idempotency on PO# / Gmail msg id).")
            _audit("sheet_upsert", f"PO {po_number} already tracked (row {existing_row})", "skipped")
            for row in audit:
                sheets.append_row(audit_tab, row)
            return out

    q = match.quote
    matched = match.status == "matched"
    # Only record the linked SO when we're actually confident. A needs_review / no_match
    # "best guess" must NOT populate Quote/SO #, Odoo SO ID or Salesperson — that leaked a
    # wrong/random order into the sheet.
    if q and matched:
        out.so_id = q["id"]
        out.so_name = q.get("name", "")

    # --- confident match: perform (or simulate) the Odoo writes ---
    if match.status == "matched" and q:
        annotate_odoo(odoo, write, q, po_number, pdf_bytes, filename,
                      match.confidence, email_meta, dry, out, _audit)
    else:
        _audit("needs_review", match.reason, "ok")

    # --- Tracker: append the Orders row ---
    salesperson = ""
    invoice_status = ""
    if q and matched:
        if q.get("user_id"):
            salesperson = q["user_id"][1] if isinstance(q["user_id"], (list, tuple)) else str(q["user_id"])
        invoice_status = q.get("invoice_status") or ""
    invoiced_suggested = "Yes" if invoice_status == "invoiced" else "No"

    # Column order must match scripts/setup_sheet.py ORDERS_HEADERS. Human-owned cells
    # are Manual SO # (idx 10 / col K) and Human Verified / Invoiced (Confirmed) /
    # Human Notes (idx 19-21 / cols T:V) — written blank on a brand-new row, but never
    # overwritten on an upsert (see below).
    orders_row = [
        _now(),                                   # 0  A  Received At
        po_number,                                # 1  B  PO #
        po.get("customer_name") or "",            # 2  C  Customer
        salesperson,                              # 3  D  Salesperson
        out.so_name,                              # 4  E  Quote/SO #
        po.get("subtotal") or "",                 # 5  F  PO Amount (untaxed)
        po.get("currency") or "",                 # 6  G  Currency
        status,                                   # 7  H  Match Status
        match.confidence,                         # 8  I  Confidence
        match.reason,                             # 9  J  Match Notes
        "",                                       # 10 K  Manual SO # (human-owned)
        out.so_id or "",                          # 11 L  Odoo SO ID
        out.ref_written,                          # 12 M  Ref Written
        out.pdf_attached,                         # 13 N  PDF Attached
        out.chatter_posted,                       # 14 O  Chatter Posted
        out.terms_updated,                        # 15 P  Terms Updated
        invoice_status,                           # 16 Q  Invoice Status
        invoiced_suggested,                       # 17 R  Invoiced (Suggested)
        gmail_msg_id,                             # 18 S  Gmail Msg ID
        "",                                       # 19 T  Human Verified (human-owned)
        "",                                       # 20 U  Invoiced (Confirmed) (human-owned)
        "",                                       # 21 V  Human Notes (human-owned)
    ]
    if existing_row:  # overwrite the prior dry-run sim, but PRESERVE human-owned cells
        sheets.update_range(f"{orders_tab}!A{existing_row}:J{existing_row}", [orders_row[0:10]])
        sheets.update_range(f"{orders_tab}!L{existing_row}:S{existing_row}", [orders_row[11:19]])
        _audit("sheet_upsert", f"updated Orders row {existing_row} for PO {po_number}", "ok")
    else:
        sheets.append_row(orders_tab, orders_row)
        _audit("sheet_upsert", f"appended Orders row for PO {po_number}", "ok")

    for row in audit:
        sheets.append_row(audit_tab, row)

    return out
