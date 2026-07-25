"""Action layer for RFQs: (rfq, line matches) -> Odoo draft quotation + Tracker rows.

Mirrors core/actions.py doctrine: honors runtime.dry_run; idempotency keyed on the
Gmail message id in the Quotes tab (a row that created an Odoo order blocks;
dry-run and needs-review rows are upserted); human-owned cells (Quotes col K) are
never overwritten. On a LIVE run with a known partner, EVERY RFQ line lands on the
draft quotation immediately: auto-matched lines are priced from the pricelist,
queued lines land at price_unit 0 (a queued line with no suggested product gets
one auto-created at price 0, image attached best-effort) so nothing is left off
the quote. Pricing Queue rows are only written on LIVE runs — a dry-run logs
intent to Audit instead. Web-researched price suggestions (Pricing Queue cols
Q-S) are advisory only — a human still sets Sale Price before it reaches the
quote. NEVER confirms or sends anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from connectors.odoo_client import OdooClient
from connectors.sheets_client import SheetsClient
from core.actions import _now
from core.product_matcher import LineMatch, norm_code

# Quotes tab column indices (0-based). Lockstep with QUOTES_HEADERS in setup_sheet.py.
Q_ORDER_ID, Q_STATUS, Q_GMAIL_MSG = 7, 8, 9


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


def _find_partner(odoo: OdooClient, name: str, threshold: int,
                  aliases: dict | None = None) -> dict | None:
    if not name:
        return None
    # e.g. "ABC Aluminum" (email domain) -> "Aluminio de Baja California" (Odoo name)
    name = (aliases or {}).get(name.strip().lower(), name)
    cands = odoo.find_partners(name, limit=10)
    if not cands:  # ponytail: retry with the longest word — full extracted name often isn't a substring
        words = sorted((w for w in name.split() if len(w) >= 4), key=len, reverse=True)
        if words:
            cands = odoo.find_partners(words[0], limit=10)
    best, best_score = None, 0
    for c in cands:
        s = max(fuzz.token_set_ratio(name.lower(), (c.get(k) or "").lower())
                for k in ("name", "display_name"))
        if s > best_score:
            best, best_score = c, s
    return best if best and best_score >= threshold else None


def _find_existing(sheets: SheetsClient, tab: str, msg_id: str):
    """(row_1based, blocking) for a prior Quotes row with this Gmail msg id, else None.

    A row BLOCKS reprocessing only if it did real Odoo work — i.e. it has an Odoo
    Quote ID (written on live runs only). Dry-run rows and Needs-Review rows (no
    order created in either mode) are upserted in place by a later run.
    """
    if not msg_id:
        return None
    rows = sheets.read(f"{tab}!A2:K")
    for i, r in enumerate(rows):
        if len(r) > Q_GMAIL_MSG and r[Q_GMAIL_MSG] == msg_id:
            has_order = bool(str(r[Q_ORDER_ID] if len(r) > Q_ORDER_ID else "").strip())
            return (i + 2, has_order)
    return None


def apply_rfq(odoo, sheets, cfg, rfq: dict, matches: list[LineMatch],
              gmail_msg_id: str = "", dry_run: bool | None = None,
              search=None, llm=None) -> QuoteOutcome:
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
        existing_row, blocking = existing
        if blocking:
            out.skipped = True
            out.log("RFQ already tracked (live Quotes row) — skipped.")
            _audit("sheet_upsert", f"RFQ msg {gmail_msg_id} already tracked (row {existing_row})", "skipped")
            return _flush(out)

    # --- customer partner ---
    img_cand: dict[int, tuple[str, str, str]] = {}  # pid -> (part, desc, mfr), filled on live create
    offer_urls: dict[int, str] = {}                 # pid -> validated price-research page
    partner = _find_partner(odoo, customer, cfg["rfq"]["match"].get("partner_threshold", 85),
                            aliases=cfg["rfq"].get("customer_aliases") or {})
    if not partner:
        out.status = "Needs Review"
        out.log(f"Customer '{customer or '?'}' not found in Odoo — no draft created.")
        _audit("needs_review", f"no Odoo partner for '{customer}' "
                               f"({len(auto)} auto, {len(queue)} unpriced line(s) on hold)", "ok")
    else:
        auto_lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"]}
                     for m in auto]  # no price_unit: Odoo prices from the pricelist
        if dry:
            _audit("odoo_create_quote",
                   f"would create draft quote for {partner['name']}: {len(auto_lines)} auto line(s), "
                   f"{len(queue)} queued", "dry-run")
        else:
            # Every RFQ line lands on the draft now. Only a TRUSTED match (exact
            # part-number, or unambiguous fuzzy >= threshold) may reuse an existing
            # product — the matcher also attaches weak below-threshold/ambiguous
            # guesses to m.product as FYI for the Pricing Queue, and quoting those
            # put an ALTECH locknut on an MHL-4 valve line. Untrusted lines get a
            # product auto-created at price 0 (dedup by part#, else description).
            created_products: list[tuple[int, str, str, str, str]] = []  # (id, name, part, desc, mfr)
            created_by_key: dict[str, tuple[int, str]] = {}
            for m in queue:
                trusted = m.reason.startswith(("exact part-number match", "fuzzy match"))
                if m.product is not None and trusted:
                    continue
                part = m.line.get("part_number") or ""
                key = norm_code(part) if part else f"desc:{(m.line.get('description') or '').strip().lower()}"
                if key in created_by_key:
                    pid, name = created_by_key[key]
                else:
                    # Client catalog convention: product name = the part number alone
                    # (no default_code — Odoo would display "[code] name" and mix the
                    # Product/Description columns). Description goes to description_sale.
                    desc = m.line.get("description") or ""
                    name = part or desc or "Unknown item"
                    pid = odoo.create_product(name, list_price=0.0,
                                              description=desc if part else "")
                    created_by_key[key] = (pid, name)
                    created_products.append((pid, name, part, m.line.get("description") or "",
                                             m.line.get("manufacturer") or ""))
                    _audit("odoo_create_product", f"created product {pid} '{name[:40]}' (part {part or '-'})", "ok")
                m.product = {"id": pid, "name": name}

            def _line_name(m):
                # customer's own wording on the line so the salesperson (and the
                # customer PDF) see what was asked for, not just our catalog name
                part = m.line.get("part_number") or ""
                desc = m.line.get("description") or ""
                return f"[{part}] {desc}".strip() if part and desc else (desc or part or None)

            queue_lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"],
                           "price_unit": 0.0,
                           **({"name": n} if (n := _line_name(m)) else {})} for m in queue]
            lines = auto_lines + queue_lines
            out.order_id = odoo.create_draft_quote(partner["id"], lines, client_ref=rfq_ref)
            out.order_name = odoo.read_field("sale.order", out.order_id, "name") or ""
            out.status = "Pending Pricing" if queue else "Draft Created"
            _audit("odoo_create_quote",
                   f"created draft {out.order_name} for {partner['name']} "
                   f"({len(auto_lines)} auto, {len(queue_lines)} at price 0, "
                   f"{len(created_products)} product(s) auto-created)", "ok")

            # Product image candidates (attached AFTER the pricing pass below, so
            # a price-research source page can double as the image source):
            # every product on the quote that has no image yet — auto-created ones
            # always, existing catalog products only when image_128 is empty.
            if search is not None:
                created_ids = {pid for pid, _ in created_by_key.values()}
                cand: dict[int, tuple[str, str, str]] = {}
                for m in auto + queue:
                    pid = (m.product or {}).get("id")
                    if pid and pid not in cand:
                        cand[pid] = (m.line.get("part_number") or "",
                                     m.line.get("description") or "",
                                     m.line.get("manufacturer") or "")
                existing_ids = [p for p in cand if p not in created_ids]
                have_img = {rec["id"] for rec in odoo.search_read(
                    "product.product", [["id", "in", existing_ids]], ["image_128"])
                    if rec.get("image_128")} if existing_ids else set()
                img_cand.update({pid: v for pid, v in cand.items() if pid not in have_img})

    # --- Pricing Queue rows (LIVE only; dry-run just audits intent) ---
    if queue and not dry and partner:
        try:
            from core.web_pricing import research_price
        except ImportError:
            research_price = None
        for m in queue:
            web_price = web_currency = web_source = ""
            if research_price and search is not None and llm is not None:
                try:
                    offer = research_price(m.line, llm, search)
                except Exception as exc:  # best-effort: never block the queue row
                    offer = None
                    _audit("web_pricing", f"{m.line.get('part_number') or m.line.get('description')}: "
                                          f"{type(exc).__name__}: {exc}", "error")
                if offer:
                    web_price = offer.get("price") or ""
                    web_currency = offer.get("currency") or ""
                    web_source = offer.get("url") or ""
                    pid = (m.product or {}).get("id")
                    # only a PRICED offer guarantees an exact product page — a
                    # reference-only url may be a catalog page whose og:image
                    # is a site banner, not the product
                    if pid and web_source and offer.get("price") is not None:
                        offer_urls.setdefault(pid, web_source)
            sheets.append_row(pq_tab, [
                _now(), customer, rfq_ref, out.order_name, out.order_id or "",
                m.line.get("part_number") or "", m.line.get("description") or "",
                m.line.get("quantity") or "",
                (m.product or {}).get("name") or "", (m.product or {}).get("id") or "",
                m.reason, "Pending", "", "", "", "",
                web_price, web_currency, web_source,
                m.line.get("manufacturer") or "",
            ])
        _audit("sheet_upsert", f"queued {len(queue)} line(s) in Pricing Queue", "ok")
    elif queue and dry:
        for m in queue[:5]:
            _audit("needs_pricing", f"would queue: {m.line.get('part_number') or m.line.get('description')}"
                                     f" — {m.reason}", "dry-run")
        if len(queue) > 5:
            _audit("needs_pricing", f"... and {len(queue) - 5} more line(s)", "dry-run")

    # --- product images (best-effort; a failure here must never fail the RFQ) ---
    # Runs after pricing so the validated price-research page doubles as the
    # image source (one web search per product); search engines are the fallback.
    if img_cand:
        try:
            from core.product_images import find_image_bytes
        except ImportError:
            find_image_bytes = None
        if find_image_bytes:
            for pid, (part, desc, mfr) in img_cand.items():
                try:
                    img = find_image_bytes(part, mfr, desc, search, page_url=offer_urls.get(pid))
                    if img and odoo.set_product_image(pid, img):
                        _audit("product_image", f"attached image to product {pid}", "ok")
                except Exception as exc:
                    _audit("product_image", f"product {pid}: {type(exc).__name__}: {exc}", "error")

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
