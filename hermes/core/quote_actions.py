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

import json
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from connectors.odoo_client import OdooClient
from connectors.sheets_client import SheetsClient
from core.actions import _now
from core.product_matcher import LineMatch, norm_code

# Quotes tab column indices (0-based). Lockstep with QUOTES_HEADERS in setup_sheet.py.
Q_ORDER_ID, Q_STATUS, Q_GMAIL_MSG = 8, 4, 9

_UNSPSC_NOUN_SYSTEM = (
    "For each industrial product, give ONE Spanish singular noun naming what the product "
    "IS. Use the most GENERIC base noun, without accents, never a compound term — "
    "electrovalvula -> valvula, niple -> conector, manifold -> colector, racor -> conector "
    "(e.g. valvula, conector, cilindro, bomba, manguera, filtro, regulador, silenciador, "
    "tuberia). Return ONLY JSON: {\"nouns\": [{\"id\": <product id>, \"noun\": \"...\"}]}. "
    "Omit products you cannot identify."
)

_UNSPSC_PICK_SYSTEM = (
    "You assign UNSPSC categories for Mexican CFDI. Each product comes with a list of "
    "candidate categories {code, name} taken from the real catalog — you MUST pick from "
    "that product's own candidates, choosing the most specific match. Return ONLY JSON: "
    '{"codes": [{"id": <product id>, "code": "########"}]}. Omit a product when none of '
    "its candidates fits — a missing code is fine, a wrong one is not."
)


def product_extra_vals(odoo, cfg, audit) -> dict:
    """Accounting defaults (POR COBRAR / POR PAGAR accounts) for every product
    Hermes creates — looked up by account code; a missing account is audited,
    never fatal."""
    pdef = cfg["rfq"].get("product_defaults") or {}
    extra: dict = {}
    for fld, key in (("property_account_income_id", "income_account"),
                     ("property_account_expense_id", "expense_account")):
        code = pdef.get(key)
        if not code:
            continue
        try:
            aid = odoo.account_id(str(code))
        except Exception:
            aid = None
        if aid:
            extra[fld] = aid
        else:
            audit("product_defaults", f"account {code} not found in Odoo — skipped", "error")
    return extra


def set_unspsc(odoo, llm, created: list[tuple], audit, fallback: str = "") -> None:
    """Catalog-grounded UNSPSC classification for freshly created products.

    The LLM never invents a code: it names the product type (one Spanish noun),
    the real Odoo UNSPSC catalog is searched for that noun, and the LLM then
    picks only among those real candidates — so a valve can only land in a
    valve-family category. Anything unresolvable gets the `fallback` code
    (e.g. 20121445 Accesorios y partes) when configured, else stays empty.
    """
    items = [{"id": pid, "part": part, "description": desc, "brand": mfr}
             for pid, _name, part, desc, mfr in created]
    resp = llm.chat_json(system=_UNSPSC_NOUN_SYSTEM,
                         user=json.dumps(items, ensure_ascii=False), max_tokens=2000)
    nouns = {int(r["id"]): str(r.get("noun") or "").strip().lower()
             for r in (resp or {}).get("nouns") or [] if r.get("id")}

    cand_by_noun: dict[str, list[dict]] = {}
    for noun in set(nouns.values()):
        if not noun:
            continue
        recs = odoo.search_read("product.unspsc.code",
                                [["name", "ilike", noun]], ["code", "name"], limit=60)
        cand_by_noun[noun] = [{"code": r["code"], "name": r["name"]} for r in recs]

    ask = []
    for it in items:
        cands = cand_by_noun.get(nouns.get(it["id"], ""), [])
        if cands:
            ask.append({**it, "candidates": cands})
        else:
            audit("unspsc", f"product {it['id']}: no catalog match for "
                            f"'{nouns.get(it['id'], '?')}'", "skipped")
    written: set[int] = set()
    if ask:
        resp = llm.chat_json(system=_UNSPSC_PICK_SYSTEM,
                             user=json.dumps(ask, ensure_ascii=False), max_tokens=3000)
        allowed = {it["id"]: {c["code"] for c in it["candidates"]} for it in ask}
        for row in (resp or {}).get("codes") or []:
            pid, code = row.get("id"), str(row.get("code") or "").strip()
            if not pid or code not in allowed.get(int(pid), set()):
                continue  # outside the product's own candidate list -> refuse
            uid = odoo.unspsc_id(code)
            if uid:
                odoo.execute("product.product", "write", [int(pid)], {"unspsc_code_id": uid})
                audit("unspsc", f"product {pid}: UNSPSC {code}", "ok")
                written.add(int(pid))

    # anything still unclassified gets the configured generic fallback
    fb_uid = odoo.unspsc_id(fallback) if fallback else None
    if fb_uid:
        for it in items:
            if it["id"] not in written:
                odoo.execute("product.product", "write", [it["id"]], {"unspsc_code_id": fb_uid})
                audit("unspsc", f"product {it['id']}: fallback {fallback}", "ok")


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
    price_flags: list[str] = field(default_factory=list)  # PO-vs-quoted discrepancies (PO flow)

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


def _cost_sale_price(m: LineMatch, margin_pct, default_pct, fx: float = 1.0) -> float | None:
    """Supplier-quote mode: the RFQ email attached OUR SUPPLIER's quote and the
    body instructed a profit margin — sale price = our cost * fx * (1 + margin),
    where fx converts the document's currency into the quote's currency."""
    c = m.line.get("unit_cost")
    if not c or c <= 0:  # 0.00 / "SIN COSTO" lines must still reach the human queue
        return None
    pct = default_pct if margin_pct is None else margin_pct
    return round(c * fx * (1 + pct / 100.0), 2)


def _quote_currency(odoo: OdooClient, partner_id: int) -> str | None:
    """The currency the customer's draft quote will use = their Odoo pricelist's."""
    p = odoo.search_read("res.partner", [["id", "=", partner_id]], ["property_product_pricelist"])
    plist = (p or [{}])[0].get("property_product_pricelist")
    if not plist:
        return None
    pl = odoo.search_read("product.pricelist", [["id", "=", plist[0]]], ["currency_id"])
    cur = (pl or [{}])[0].get("currency_id")
    return cur[1] if cur else None


def _fx_factor(odoo: OdooClient, doc_ccy: str | None, quote_ccy: str | None) -> float | None:
    """Multiplier turning document-currency amounts into quote-currency amounts.
    None = cannot determine safely (unknown doc currency / missing Odoo rate)."""
    if not doc_ccy or not quote_ccy:
        return None
    if doc_ccy == quote_ccy:
        return 1.0
    rates = {r["name"]: r["rate"] for r in odoo.search_read(
        "res.currency", [["name", "in", [doc_ccy, quote_ccy]]], ["name", "rate"])}
    if rates.get(doc_ccy) and rates.get(quote_ccy):
        return rates[quote_ccy] / rates[doc_ccy]
    return None


def _trusted(m: LineMatch) -> bool:
    """Only a TRUSTED match (exact part-number, or unambiguous fuzzy >= threshold)
    may reuse an existing product — the matcher also attaches weak below-threshold/
    ambiguous guesses to m.product as FYI, and quoting those put an ALTECH locknut
    on an MHL-4 valve line."""
    return m.product is not None and m.reason.startswith(("exact part-number match", "fuzzy match"))


def _line_name(m: LineMatch) -> str | None:
    # customer's own wording on the line so the salesperson (and the
    # customer PDF) see what was asked for, not just our catalog name
    part = m.line.get("part_number") or ""
    desc = m.line.get("description") or ""
    return f"[{part}] {desc}".strip() if part and desc else (desc or part or None)


def _create_missing_products(odoo: OdooClient, cfg: dict, matches: list[LineMatch],
                             audit, price_of=None) -> tuple[list[tuple], set[int]]:
    """Auto-create a product for every match without a trusted catalog product
    (dedup by part#, else description) and set m.product in place. Returns
    (created_products for UNSPSC, created product ids). ``price_of(m)`` sets the
    new product's sale price (RFQ flow: unknown -> 0; PO flow: the PO's price)."""
    extra_vals = product_extra_vals(odoo, cfg, audit)
    created_products: list[tuple[int, str, str, str, str]] = []  # (id, name, part, desc, mfr)
    created_by_key: dict[str, tuple[int, str]] = {}
    for m in matches:
        if _trusted(m):
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
            pid = odoo.create_product(name, list_price=(price_of(m) if price_of else 0.0),
                                      description=desc if part else "", extra=extra_vals)
            created_by_key[key] = (pid, name)
            created_products.append((pid, name, part, desc, m.line.get("manufacturer") or ""))
            audit("odoo_create_product", f"created product {pid} '{name[:40]}' (part {part or '-'})", "ok")
        m.product = {"id": pid, "name": name}
    return created_products, {pid for pid, _ in created_by_key.values()}


def _image_candidates(odoo: OdooClient, matches: list[LineMatch],
                      created_ids: set[int]) -> dict[int, tuple[str, str, str]]:
    """pid -> (part, desc, mfr) for quote products still needing an image:
    auto-created ones always, existing catalog products only when image_128 is empty."""
    cand: dict[int, tuple[str, str, str]] = {}
    for m in matches:
        pid = (m.product or {}).get("id")
        if pid and pid not in cand:
            cand[pid] = (m.line.get("part_number") or "",
                         m.line.get("description") or "",
                         m.line.get("manufacturer") or "")
    existing_ids = [p for p in cand if p not in created_ids]
    have_img = {rec["id"] for rec in odoo.search_read(
        "product.product", [["id", "in", existing_ids]], ["image_128"])
        if rec.get("image_128")} if existing_ids else set()
    return {pid: v for pid, v in cand.items() if pid not in have_img}


def _attach_images(odoo: OdooClient, img_cand: dict, search, audit,
                   offer_urls: dict | None = None) -> None:
    """Best-effort product images; a failure here must never fail the pipeline."""
    if not img_cand or search is None:
        return
    try:
        from core.product_images import find_image_bytes
    except ImportError:
        return
    for pid, (part, desc, mfr) in img_cand.items():
        try:
            img = find_image_bytes(part, mfr, desc, search, page_url=(offer_urls or {}).get(pid))
            if img and odoo.set_product_image(pid, img):
                audit("product_image", f"attached image to product {pid}", "ok")
        except Exception as exc:
            audit("product_image", f"product {pid}: {type(exc).__name__}: {exc}", "error")


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
              search=None, llm=None,
              attachments: list[tuple[str, bytes]] | None = None) -> QuoteOutcome:
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

    fx_map: dict = {}  # cost currency -> quote-currency factor, filled once the partner is known

    def _ccy(m):  # a line's own currency wins; documents can mix USD and MXN lines
        return m.line.get("cost_currency") or rfq.get("currency")

    def sale_of(m):
        f = fx_map.get(_ccy(m), 1.0)
        if f is None:  # unknown currency/rate — refuse to price blind
            return None
        return _cost_sale_price(m, rfq.get("margin_pct"),
                                cfg.get("pricebook", {}).get("default_markup_pct", 25), f)

    auto = [m for m in matches if m.status == "matched"]
    # a queue-status line WITH a supplier cost is priceable (cost*margin) — it goes
    # straight onto the draft instead of the Pricing Queue
    queue = [m for m in matches if m.status == "queue" and sale_of(m) is None]
    costed = [m for m in matches if m.status == "queue" and sale_of(m) is not None]
    out = QuoteOutcome(dry_run=dry, status="Dry-run" if dry else "Draft Created",
                       auto_priced=len(auto) + len(costed), queued=len(queue))

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
                               f"({out.auto_priced} auto, {out.queued} unpriced line(s) on hold)", "ok")
    else:
        # explicit body instruction "take the prices from <site>" — a validated
        # offer from THAT site becomes the line's cost (sale = price * fx *
        # (1 + margin), same machinery as supplier-quote mode); lines the site
        # can't price stay on the human Pricing Queue as usual
        site = rfq.get("price_source_site")
        if site and queue and search is not None and llm is not None:
            from core.web_pricing import research_price
            for m in queue:
                label = m.line.get("part_number") or m.line.get("description")
                try:
                    offer = research_price(m.line, llm, search, only_site=site)
                except Exception as exc:  # best-effort: an un-priced line just queues
                    offer = None
                    _audit("web_pricing", f"{label}: {type(exc).__name__}: {exc}", "error")
                if not offer:
                    continue
                m.line["_web_offer"] = offer  # Pricing Queue / image reuse — no second search
                if offer.get("price") is not None:
                    m.line["unit_cost"] = offer["price"]
                    m.line["cost_currency"] = (offer.get("currency") or "").strip().upper() or None
                    _audit("web_pricing", f"{label}: {offer['price']} {offer.get('currency') or '?'} "
                                          f"from {offer.get('url')}", "ok")
            priced = [m for m in queue if sale_of(m) is not None]
            if priced:
                costed, queue = costed + priced, [m for m in queue if sale_of(m) is None]
                out.auto_priced, out.queued = len(auto) + len(costed), len(queue)
                _audit("web_pricing", f"priced {len(priced)}/{len(priced) + len(queue)} line(s) "
                                      f"from {site} (explicit instruction)", "ok")
        # AUTO lines can carry a supplier cost too (their price_unit override
        # below uses sale_of) — their currencies need converting just like costed
        cost_ccys = {_ccy(m) for m in auto + costed if m.line.get("unit_cost")}
        if cost_ccys:
            # supplier costs are in the DOCUMENT's currency (possibly mixed per
            # line); the quote uses the customer's pricelist currency — convert
            # each line, or refuse to price the ones we can't convert
            quote_ccy = _quote_currency(odoo, partner["id"])
            for c in cost_ccys:
                fx_map[c] = _fx_factor(odoo, c, quote_ccy)
                if fx_map[c] not in (None, 1.0):
                    _audit("currency", f"supplier costs {c} -> {quote_ccy} at rate {fx_map[c]:.6f}", "ok")
            bad = [m for m in costed if sale_of(m) is None]
            if bad:
                _audit("currency", f"can't convert supplier costs to quote currency ({quote_ccy or '?'}) "
                                   f"— {len(bad)} line(s) queued unpriced", "error")
                queue, costed = queue + bad, [m for m in costed if sale_of(m) is not None]
                out.auto_priced, out.queued = len(auto) + len(costed), len(queue)
        # an explicit cost+margin instruction overrides the catalog price
        auto_lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"],
                       **({"price_unit": p} if (p := sale_of(m)) is not None else {})}
                     for m in auto]  # no price_unit: Odoo prices from the pricelist
        if dry:
            _audit("odoo_create_quote",
                   f"would create draft quote for {partner['name']}: {len(auto_lines)} auto line(s), "
                   f"{len(costed)} cost+margin, {len(queue)} queued", "dry-run")
        else:
            # Every RFQ line lands on the draft now: trusted matches reuse their
            # product, the rest get one auto-created (see _trusted /
            # _create_missing_products) at cost*margin when known, else price 0.
            pdef = cfg["rfq"].get("product_defaults") or {}
            created_products, created_ids = _create_missing_products(
                odoo, cfg, queue + costed, _audit, price_of=lambda m: sale_of(m) or 0.0)
            for m in costed:  # a web-priced line's product page doubles as its image source
                pid = (m.product or {}).get("id")
                url = (m.line.get("_web_offer") or {}).get("url")
                if pid and url:
                    offer_urls.setdefault(pid, url)

            costed_lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"],
                            "price_unit": sale_of(m),
                            **({"name": n} if (n := _line_name(m)) else {})} for m in costed]
            queue_lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"],
                           "price_unit": 0.0,
                           **({"name": n} if (n := _line_name(m)) else {})} for m in queue]
            lines = auto_lines + costed_lines + queue_lines
            out.order_id = odoo.create_draft_quote(partner["id"], lines, client_ref=rfq_ref)
            out.order_name = odoo.read_field("sale.order", out.order_id, "name") or ""
            out.status = "Pending Pricing" if queue else "Draft Created"
            _audit("odoo_create_quote",
                   f"created draft {out.order_name} for {partner['name']} "
                   f"({len(auto_lines)} auto, {len(costed_lines)} cost+margin, "
                   f"{len(queue_lines)} at price 0, "
                   f"{len(created_products)} product(s) auto-created)", "ok")

            # source document(s) (e.g. the supplier's quote PDF) onto the draft,
            # so they're at hand when the quote is confirmed — best-effort
            for fn, data in (attachments or []):
                try:
                    odoo.attach_pdf(out.order_id, fn, data)
                    _audit("attach_pdf", f"attached {fn} to {out.order_name}", "ok")
                except Exception as exc:
                    _audit("attach_pdf", f"{fn}: {type(exc).__name__}: {exc}", "error")

            # UNSPSC classification for new products (best-effort, one LLM call)
            if created_products and llm is not None and pdef.get("unspsc", True):
                try:
                    set_unspsc(odoo, llm, created_products, _audit,
                               fallback=str(pdef.get("unspsc_fallback") or ""))
                except Exception as exc:
                    _audit("unspsc", f"{type(exc).__name__}: {exc}", "error")

            # Product image candidates (attached AFTER the pricing pass below, so
            # a price-research source page can double as the image source).
            if search is not None:
                img_cand.update(_image_candidates(odoo, auto + costed + queue, created_ids))

    # --- Pricing Queue rows (LIVE only; dry-run just audits intent) ---
    if queue and not dry and partner:
        try:
            from core.web_pricing import research_price
        except ImportError:
            research_price = None
        for m in queue:
            web_price = web_currency = web_source = ""
            offer = m.line.get("_web_offer")  # already researched by the explicit-site pass
            if offer is None and research_price and search is not None and llm is not None:
                try:
                    offer = research_price(m.line, llm, search,
                                           preferred_sites=cfg["rfq"].get("preferred_supplier_sites") or ())
                except Exception as exc:  # best-effort: never block the queue row
                    offer = None
                    _audit("web_pricing", f"{m.line.get('part_number') or m.line.get('description')}: "
                                          f"{type(exc).__name__}: {exc}", "error")
            if offer:  # fresh OR cached — either way the human gets the researched link
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

    # --- product images: after pricing so the validated price-research page
    # doubles as the image source (one web search per product) ---
    _attach_images(odoo, img_cand, search, _audit, offer_urls=offer_urls)

    # --- Quotes row (lockstep with QUOTES_HEADERS) ---
    quotes_row = [
        _now(), customer, rfq_ref,
        out.order_name or ("Dry-run" if dry and partner else ""),
        out.status, len(matches), out.auto_priced, out.queued,
        out.order_id or "", gmail_msg_id,
        "", "",  # K Quote Status, L Human Notes (human-owned; blank = Not Sent)
    ]
    if existing_row:  # upsert prior dry-run row; preserve human K:L
        sheets.update_range(f"{quotes_tab}!A{existing_row}:J{existing_row}", [quotes_row[0:10]])
        _audit("sheet_upsert", f"updated Quotes row {existing_row}", "ok")
    else:
        sheets.append_row(quotes_tab, quotes_row)
        _audit("sheet_upsert", "appended Quotes row", "ok")
    return _flush(out)


# ---- new quote FROM a customer PO (human types NEW in the Tracker's Manual SO #) ----

def po_lines(po: dict) -> list[dict]:
    """PO line_items -> matcher-shaped lines (customer_item_code is the part#)."""
    out = []
    for li in po.get("line_items") or []:
        if not (li.get("customer_item_code") or li.get("description")):
            continue
        out.append({"part_number": li.get("customer_item_code") or "",
                    "description": li.get("description") or "",
                    "quantity": li.get("quantity") or 0,
                    "unit_price": li.get("unit_price")})
    return out


def _po_price(m: LineMatch) -> float:
    try:
        return float(m.line.get("unit_price") or 0)
    except (TypeError, ValueError):
        return 0.0


def _last_quoted_prices(odoo: OdooClient, partner_id: int,
                        product_ids: set[int]) -> dict[int, tuple[float, str]]:
    """{product id -> (unit price, order name)} from the MOST RECENT sale.order
    line for this customer. ponytail: newest by line id, one bulk read; per-order
    date ordering can come later if edits ever make id-order wrong."""
    if not product_ids:
        return {}
    rows = odoo.search_read(
        "sale.order.line",
        [["order_partner_id", "=", partner_id], ["product_id", "in", list(product_ids)]],
        ["product_id", "price_unit", "order_id"], order="id desc", limit=500)
    out: dict[int, tuple[float, str]] = {}
    for r in rows:
        pid = r["product_id"][0] if isinstance(r["product_id"], (list, tuple)) else r["product_id"]
        if pid not in out:
            oname = r["order_id"][1] if isinstance(r["order_id"], (list, tuple)) else ""
            out[pid] = (r["price_unit"] or 0.0, oname)
    return out


def check_po_prices(odoo: OdooClient, partner_id: int, matches: list[LineMatch],
                    created_ids: set[int]) -> list[str]:
    """Check & balance: the PO's unit prices vs what this customer was last
    quoted in Odoo. Returns one flag string per discrepancy — a price that moved,
    a product never quoted to this customer, or a brand-new product."""
    prior = _last_quoted_prices(odoo, partner_id,
                                {m.product["id"] for m in matches
                                 if m.product and m.product["id"] not in created_ids})
    flags: list[str] = []
    for m in matches:
        pid = (m.product or {}).get("id")
        if not pid:
            continue
        label = m.product.get("name") or m.line.get("part_number") or str(pid)
        po_p = _po_price(m)
        if pid in created_ids:
            flags.append(f"{label}: new product — no prior quoted price")
        elif pid not in prior:
            flags.append(f"{label}: never quoted to this customer")
        else:
            quoted, oname = prior[pid]
            # ponytail: 0.5% tolerance for rounding; make it config if it ever needs tuning
            if abs(quoted - po_p) > max(0.01, 0.005 * quoted):
                flags.append(f"{label}: PO price {po_p:g} vs quoted {quoted:g} ({oname or 'prior quote'})")
    return flags


def quote_from_po(odoo: OdooClient, cfg: dict, po: dict, matches: list[LineMatch],
                  audit, llm=None, search=None, dry: bool = False) -> QuoteOutcome:
    """Create a DRAFT quotation from a customer PO's own lines.

    Every line is priced from the PO itself (the PO states unit prices — no
    Pricing Queue involved); a line with no trusted catalog match gets its
    product auto-created at the PO price, same conventions as apply_rfq
    (part# as name, accounting defaults, UNSPSC, image best-effort).
    order_id stays None when the customer has no Odoo partner (status
    'Needs Review' — human fixes the partner/alias and retries) or on dry-run.
    NEVER confirms or sends anything. Audit/sheet rows are the caller's job.
    """
    customer = po.get("customer_name") or ""
    out = QuoteOutcome(dry_run=dry, status="Dry-run" if dry else "Draft Created",
                       auto_priced=len(matches))
    partner = _find_partner(odoo, customer, cfg["rfq"]["match"].get("partner_threshold", 85),
                            aliases=cfg["rfq"].get("customer_aliases") or {})
    if not partner:
        out.status = "Needs Review"
        out.log(f"Customer '{customer or '?'}' not found in Odoo — no draft created.")
        audit("needs_review", f"no Odoo partner for '{customer}' (new-quote request)", "ok")
        return out
    to_create = sum(1 for m in matches if not _trusted(m))
    if dry:
        audit("odoo_create_quote",
              f"would create draft quote for {partner['name']} from PO {po.get('po_number') or '?'}: "
              f"{len(matches)} line(s) at PO prices, {to_create} product(s) would be auto-created",
              "dry-run")
        return out

    pdef = cfg["rfq"].get("product_defaults") or {}
    created_products, created_ids = _create_missing_products(odoo, cfg, matches, audit,
                                                             price_of=_po_price)
    lines = []
    for m in matches:
        l = {"product_id": m.product["id"], "product_uom_qty": m.line.get("quantity") or 0,
             "price_unit": _po_price(m)}
        if m.product["id"] in created_ids and (n := _line_name(m)):
            l["name"] = n
        lines.append(l)
    # Check & balance BEFORE creating (the draft's own lines must not count as
    # "prior quotes"): PO prices vs what this customer was last quoted.
    out.price_flags = check_po_prices(odoo, partner["id"], matches, created_ids)

    out.order_id = odoo.create_draft_quote(partner["id"], lines,
                                           client_ref=po.get("po_number") or "")
    out.order_name = odoo.read_field("sale.order", out.order_id, "name") or ""
    audit("odoo_create_quote",
          f"created draft {out.order_name} for {partner['name']} from PO "
          f"({len(lines)} line(s) at PO prices, {len(created_products)} product(s) auto-created)", "ok")
    if out.price_flags:
        out.status = "Price Review"
        odoo.post_chatter(out.order_id,
                          "Hermes: price check vs this customer's previous quotes found "
                          "discrepancies — review before confirming:\n- "
                          + "\n- ".join(out.price_flags))
        audit("price_review", f"{len(out.price_flags)} line(s) flagged: "
                              + "; ".join(out.price_flags)[:300], "ok")

    if created_products and llm is not None and pdef.get("unspsc", True):
        try:
            set_unspsc(odoo, llm, created_products, audit,
                       fallback=str(pdef.get("unspsc_fallback") or ""))
        except Exception as exc:
            audit("unspsc", f"{type(exc).__name__}: {exc}", "error")
    if search is not None:
        _attach_images(odoo, _image_candidates(odoo, matches, created_ids), search, audit)
    return out
