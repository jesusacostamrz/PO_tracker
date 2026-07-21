"""Action layer for RFQs: (rfq, line matches) -> Odoo draft quotation + Tracker rows.

Mirrors core/actions.py doctrine: honors runtime.dry_run; idempotency keyed on the
Gmail message id in the Quotes tab (a live row blocks, a dry-run row is upserted);
human-owned cells (Quotes col K) are never overwritten. Pricing Queue rows are only
written on LIVE runs — a dry-run logs intent to Audit instead. NEVER confirms or
sends anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from connectors.odoo_client import OdooClient
from connectors.sheets_client import SheetsClient
from core.actions import _now
from core.product_matcher import LineMatch

# Quotes tab column indices (0-based). Lockstep with QUOTES_HEADERS in setup_sheet.py.
Q_STATUS, Q_GMAIL_MSG = 8, 9


@dataclass
class QuoteOutcome:
    dry_run: bool
    status: str
    order_id: int | None = None
    order_name: str = ""
    auto_priced: int = 0
    queued: int = 0
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.notes.append(msg)


def _find_partner(odoo: OdooClient, name: str, threshold: int) -> dict | None:
    if not name:
        return None
    cands = odoo.find_partners(name, limit=10)
    best, best_score = None, 0
    for c in cands:
        s = max(fuzz.token_set_ratio(name.lower(), (c.get(k) or "").lower())
                for k in ("name", "display_name"))
        if s > best_score:
            best, best_score = c, s
    return best if best and best_score >= threshold else None


def _find_existing(sheets: SheetsClient, tab: str, msg_id: str):
    """(row_1based, is_dry) for a prior Quotes row with this Gmail msg id, else None."""
    if not msg_id:
        return None
    rows = sheets.read(f"{tab}!A2:K")
    for i, r in enumerate(rows):
        if len(r) > Q_GMAIL_MSG and r[Q_GMAIL_MSG] == msg_id:
            return (i + 2, (r[Q_STATUS] if len(r) > Q_STATUS else "") == "Dry-run")
    return None


def apply_rfq(odoo, sheets, cfg, rfq: dict, matches: list[LineMatch],
              gmail_msg_id: str = "", dry_run: bool | None = None) -> QuoteOutcome:
    dry = cfg.get("runtime", {}).get("dry_run", True) if dry_run is None else dry_run
    tabs = cfg["sheets"]["tabs"]
    quotes_tab, pq_tab, audit_tab = tabs["quotes"], tabs["pricing_queue"], tabs["audit"]
    run_mode = "dry-run" if dry else "live"
    rfq_ref = rfq.get("rfq_ref") or ""
    customer = rfq.get("customer_name") or ""
    audit: list[list] = []

    def _audit(action, detail, result):
        audit.append([_now(), rfq_ref or customer, action, detail, result, run_mode])

    def _flush(out):
        for a in audit:
            sheets.append_row(audit_tab, a)
        return out

    auto = [m for m in matches if m.status == "matched"]
    queue = [m for m in matches if m.status == "queue"]
    out = QuoteOutcome(dry_run=dry, status="Dry-run" if dry else "Draft Created",
                       auto_priced=len(auto), queued=len(queue))

    # --- idempotency ---
    existing = _find_existing(sheets, quotes_tab, gmail_msg_id)
    existing_row = None
    if existing:
        existing_row, was_dry = existing
        if not was_dry:
            out.skipped = True
            out.log("RFQ already tracked (live Quotes row) — skipped.")
            _audit("sheet_upsert", f"RFQ msg {gmail_msg_id} already tracked (row {existing_row})", "skipped")
            return _flush(out)

    # --- customer partner ---
    partner = _find_partner(odoo, customer, cfg["rfq"]["match"].get("partner_threshold", 85))
    if not partner:
        out.status = "Needs Review"
        out.log(f"Customer '{customer or '?'}' not found in Odoo — no draft created.")
        _audit("needs_review", f"no Odoo partner for '{customer}'", "ok")
    else:
        lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"]}
                 for m in auto]  # no price_unit: Odoo prices from the pricelist
        if dry:
            _audit("odoo_create_quote",
                   f"would create draft quote for {partner['name']}: {len(lines)} auto line(s), "
                   f"{len(queue)} queued", "dry-run")
        else:
            out.order_id = odoo.create_draft_quote(partner["id"], lines, client_ref=rfq_ref)
            out.order_name = odoo.read_field("sale.order", out.order_id, "name") or ""
            out.status = "Pending Pricing" if queue else "Draft Created"
            _audit("odoo_create_quote",
                   f"created draft {out.order_name} for {partner['name']} "
                   f"({len(lines)} auto, {len(queue)} queued)", "ok")

    # --- Pricing Queue rows (LIVE only; dry-run just audits intent) ---
    if queue and not dry and partner:
        for m in queue:
            sheets.append_row(pq_tab, [
                _now(), customer, rfq_ref, out.order_name, out.order_id or "",
                m.line.get("part_number") or "", m.line.get("description") or "",
                m.line.get("quantity") or "",
                (m.product or {}).get("name") or "", (m.product or {}).get("id") or "",
                m.reason, "Pending", "", "", "", "",
            ])
        _audit("sheet_upsert", f"queued {len(queue)} line(s) in Pricing Queue", "ok")
    elif queue and dry:
        for m in queue[:5]:
            _audit("needs_pricing", f"would queue: {m.line.get('part_number') or m.line.get('description')}"
                                     f" — {m.reason}", "dry-run")
        if len(queue) > 5:
            _audit("needs_pricing", f"... and {len(queue) - 5} more line(s)", "dry-run")

    # --- Quotes row (lockstep with QUOTES_HEADERS) ---
    quotes_row = [
        _now(), customer, rfq_ref, len(matches),
        out.auto_priced, out.queued,
        out.order_name or ("Dry-run" if dry and partner else ""), out.order_id or "",
        out.status, gmail_msg_id,
        "",  # K Human Notes (human-owned)
    ]
    if existing_row:  # upsert prior dry-run row; preserve K
        sheets.update_range(f"{quotes_tab}!A{existing_row}:J{existing_row}", [quotes_row[0:10]])
        _audit("sheet_upsert", f"updated Quotes row {existing_row}", "ok")
    else:
        sheets.append_row(quotes_tab, quotes_row)
        _audit("sheet_upsert", "appended Quotes row", "ok")
    return _flush(out)
