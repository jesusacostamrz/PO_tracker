"""Purchase requisition built FROM a Sales Order's quantities + a supplier quote.

A salesperson's SO already carries (a) the line quantities and (b) the supplier's
quotation PDF (attached next to the customer's own PO PDF). This module builds the
draft purchase RFQ(s) from the SO lines and prices them from the supplier quote,
matching lines by part number (or a MODELO: code inside the line description).

Two triggers call ``from_sales_order``: an email subject "REQ <SO> [<vendor>]"
(scripts/intake_req.py) and an Odoo chatter mention "@Unicontrolbot req ..."
(scripts/intake_mentions.py).
"""
from __future__ import annotations

import base64
from html import escape

from core.rfq_parser import parse_rfq
from scripts.order_shortage import key, compute
from scripts.order_purchasing import plan_rfqs

VENDOR_MIN_SCORE = 80

# Told to the RFQ parser: this document is what OUR SUPPLIER quoted us, not a
# customer request — flip customer_name/unit_cost semantics accordingly, and
# bail out (empty line_items) if it turns out to be a PO addressed to us instead.
_QUOTE_HINT = (
    "SUPPLIER-QUOTE MODE — this document is OUR SUPPLIER's quotation TO US, not a "
    "customer RFQ: every line's unit price is OUR COST -> unit_cost (with "
    "cost_currency/currency as shown); supplier_name = the company that ISSUED the "
    "quotation (its letterhead). If the document is instead a PURCHASE ORDER "
    "addressed TO US (we appear on it as the supplier/proveedor), return "
    "line_items: [] — it is not a supplier quote."
)


def resolve_vendor(odoo, name: str | None, live: bool,
                   create: bool = True) -> tuple[int, str] | None:
    """Odoo partner for a named vendor; created (live) when unknown unless
    ``create`` is False (then None — a free-text hint may not become a partner)."""
    if not name:
        return None
    from core.quote_actions import _name_score
    hits = odoo.find_partners(name, limit=10)  # name ilike -> every hit CONTAINS the typed name
    if len(hits) == 1:  # "bluestar" -> the one BLUESTARLAM MEXICO; a unique containment is the vendor
        return hits[0]["id"], hits[0]["name"]
    words = name.split()
    if not hits and len(words) > 2:  # punctuation/legal-suffix drift ("SKS Welding Systems S. de R.L."
        hits = odoo.find_partners(" ".join(words[:2]), limit=10)  # vs "..., S. de R.L. de C.V.")
    scored = sorted(((_name_score(name.lower(), p["name"].lower()), p) for p in hits),
                    key=lambda t: t[0], reverse=True)
    best = scored[0] if scored else None
    if best and best[0] >= VENDOR_MIN_SCORE:
        tie = len(scored) > 1 and scored[1][0] == best[0]
        if tie and not create:  # "sks" = SKS Inc AND SKS S. de R.L.: a hint can't pick, the quote will
            return None
        return best[1]["id"], best[1]["name"]
    if not create:
        return None
    vname = name.title() if name.islower() else name
    return (odoo.ensure_vendor(vname) if live else 0), vname


def _modelo_key(text: str) -> str | None:
    for line in str(text or "").splitlines():
        s = line.strip()
        if s.upper().startswith("MODELO:"):
            return key(s.split(":", 1)[1])
    return None


def _quote_pdfs(odoo, so_id: int, client_order_ref: str | None) -> list[tuple[str, bytes]]:
    """SO's PDF attachments, skipping the customer's own PO (name matches the ref)."""
    ref_key = key(client_order_ref) if client_order_ref else None
    atts = odoo.search_read(
        "ir.attachment",
        [["res_model", "=", "sale.order"], ["res_id", "=", so_id],
         ["mimetype", "=", "application/pdf"]],
        ["name", "datas"],
    )
    out = []
    for a in atts:
        if ref_key and ref_key in key(a.get("name")):
            continue  # this is the customer's PO, not the supplier's quote
        out.append((a["name"], base64.b64decode(a["datas"])))
    return out


def _parse_quotes(sources: list[tuple[str, bytes]], llm, cfg) -> list[dict]:
    """Parse each candidate PDF as a supplier quote; keep only real ones (>=1 costed line).
    Each kept parse carries its source file as ``_file`` = (name, bytes)."""
    quotes = []
    for name, data in sources:
        rfq = parse_rfq([("text", "req-instructions", _QUOTE_HINT), ("pdf", name, data)],
                        llm, cfg.get("company", {}))
        if any((li.get("unit_cost") or 0) > 0 for li in rfq.get("line_items") or []):
            rfq["_file"] = (name, data)
            quotes.append(rfq)
    return quotes


def _line_keys(line: dict) -> list[str]:
    """Candidate match keys for one SO line, in priority order."""
    ks = []
    name = str(line.get("name") or "")
    first = name.splitlines()[0] if name else ""
    if first.strip():
        ks.append(key(first))
    pid = line.get("product_id")
    pname = pid[1] if isinstance(pid, (list, tuple)) else None
    if pname:
        ks.append(key(pname))
    mk = _modelo_key(name)
    if mk:
        ks.append(mk)
    return ks


def _quote_cost_map(quotes: list[dict]) -> list[dict[str, tuple[float, str | None]]]:
    """Per quote: {part key -> (unit_cost, currency)}."""
    maps = []
    for q in quotes:
        m = {}
        for li in q.get("line_items") or []:
            if (li.get("unit_cost") or 0) <= 0:
                continue
            pn = li.get("part_number") or li.get("description")
            if not pn:
                continue
            m[key(pn)] = (li["unit_cost"], li.get("cost_currency") or q.get("currency"))
        maps.append(m)
    return maps


def _link_note(odoo, rfq_id: int, so_id: int, so_name: str, customer: str, detail: str) -> None:
    """Provenance on the RFQ: link back to the SO it was built from (every RFQ gets one)."""
    odoo.post_chatter(
        rfq_id,
        f"<p>Hermes creó esta solicitud a partir de la orden de venta "
        f"<a href=\"/odoo/sales/{so_id}\">{escape(so_name)}</a>"
        f"{' (' + escape(customer) + ')' if customer else ''}, {detail}</p>",
        model="purchase.order")


def from_sales_order(odoo, llm, cfg, so_name: str, *, vendor_hint: str | None = None,
                     extra_sources=(), shortage: bool = False, live: bool = False,
                     out=print) -> list[tuple[int, str, str]]:
    orders = odoo.search_read("sale.order", [["name", "=", so_name]],
                              ["id", "name", "partner_id", "client_order_ref", "state"], limit=1)
    if not orders:
        raise RuntimeError(f"No Sales Order named {so_name!r} in Odoo.")
    order = orders[0]
    so_id = order["id"]

    if shortage:
        _, report, _ = compute(cfg, odoo, so_name)
        buy_rows = [r for r in report if r.get("buy", 0) > 0]
        lines = [{"product_id": r["product_id"], "name": r["part"], "product_uom_qty": r["buy"]}
                 for r in buy_rows]
    else:
        # qty 0 = down-payment ("Anticipo") / note lines — nothing to buy
        lines = [l for l in odoo.order_lines(so_id)
                 if l.get("product_id") and (l.get("product_uom_qty") or 0) > 0]

    quote_sources = list(extra_sources) or _quote_pdfs(odoo, so_id, order.get("client_order_ref"))
    quotes = _parse_quotes(quote_sources, llm, cfg)
    cost_maps = _quote_cost_map(quotes)

    # {quote_idx: [to_buy rows]}; None key = uncovered (no quote matched)
    by_quote: dict[int | None, list[dict]] = {}
    for l in lines:
        pid = l["product_id"]
        product_id = pid[0] if isinstance(pid, (list, tuple)) else pid
        pname = pid[1] if isinstance(pid, (list, tuple)) else l.get("name", "")
        row = {"product_id": product_id, "part": pname, "buy": l["product_uom_qty"]}
        hit = None
        for k in _line_keys(l):
            for qi, m in enumerate(cost_maps):
                if k in m:
                    hit = qi
                    break
            if hit is not None:
                break
        if hit is not None:
            cost, cur = cost_maps[hit][next(k for k in _line_keys(l) if k in cost_maps[hit])]
            row["cost"] = cost
            row["_currency"] = cur
        by_quote.setdefault(hit, []).append(row)

    uncovered = by_quote.pop(None, [])
    created: list[tuple[int, str, str]] = []
    uncovered_report: list[dict] = []

    if len(quotes) == 1 and uncovered:
        # one supplier quote: fold uncovered lines onto it at cost 0, flagged
        for r in uncovered:
            r["cost"] = 0.0
            uncovered_report.append(r)
        by_quote.setdefault(0, []).extend(uncovered)
        uncovered = []
    else:
        uncovered_report = uncovered  # several/no quotes: no-vendor path handles them

    chatter_rows: list[str] = []  # "name (vendor) — N lines, total X CUR" per created RFQ
    customer = order["partner_id"][1] if isinstance(order.get("partner_id"), (list, tuple)) else ""

    for qi, rows in by_quote.items():
        quote = quotes[qi]
        # a typed hint must name an EXISTING partner; else the quote's issuer (may be created)
        vendor = (resolve_vendor(odoo, vendor_hint, live, create=False)
                  or resolve_vendor(odoo, quote.get("supplier_name"), live))
        currency = next((r.get("_currency") for r in rows if r.get("_currency")), None) or quote.get("currency")
        to_buy = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
        batch, _ = plan_rfqs(odoo, so_name, to_buy, live=live, out=out,
                             vendor=vendor, currency=currency)
        created.extend(batch)
        qname, qdata = quote.get("_file") or ("", b"")
        for rfq_id, name, rvname in batch:
            total = sum(r["buy"] * r.get("cost", 0.0) for r in rows)
            chatter_rows.append(f"{name} ({rvname}) — {len(rows)} línea(s), "
                                f"total {total:,.2f} {currency or ''}".strip())
            # provenance on the RFQ: link back to the SO + the supplier quote it was priced from
            _link_note(odoo, rfq_id, so_id, so_name, customer,
                       f"con cantidades de la orden y costos de la cotización del proveedor {escape(qname)}.")
            if qdata:
                odoo.attach_pdf(rfq_id, qname, qdata, model="purchase.order")
        if live and vendor:
            tmpl_map = odoo.product_tmpl_map([r["product_id"] for r in rows if r.get("cost")])
            for r in rows:
                if r.get("cost") and r["product_id"] in tmpl_map:
                    odoo.upsert_supplierinfo(tmpl_map[r["product_id"]], vendor[0], r["cost"])

    if uncovered:  # multiple quotes and still-uncovered lines: no vendor, placeholder path
        to_buy = [{k: v for k, v in r.items() if not k.startswith("_")} for r in uncovered]
        batch, _ = plan_rfqs(odoo, so_name, to_buy, live=live, out=out, vendor=None, currency=None)
        created.extend(batch)
        for rfq_id, name, rvname in batch:
            chatter_rows.append(f"{name} ({rvname}) — {len(uncovered)} línea(s), sin costo")
            if live:
                _link_note(odoo, rfq_id, so_id, so_name, customer,
                           "con las cantidades de la orden. No hay cotización de proveedor que cubra "
                           "estas partidas: asignar proveedor y costos.")

    if live:
        if not quotes:
            body = "<p>Hermes: no se encontró una cotización de proveedor utilizable para esta requisición.</p>"
            if chatter_rows:
                body += "<p>Solicitud(es) en borrador creadas sin costo:</p><ul>"                         + "".join(f"<li>{escape(r)}</li>" for r in chatter_rows) + "</ul>"
        elif chatter_rows:
            body = "<p>Hermes creó las siguientes solicitudes de compra en borrador:</p><ul>" \
                  + "".join(f"<li>{escape(r)}</li>" for r in chatter_rows) + "</ul>"
        else:
            body = "<p>Hermes: la(s) cotización(es) de proveedor no generaron ninguna solicitud nueva " \
                  "(ya existían para esta orden).</p>"
        if uncovered_report:
            items = ", ".join(r["part"] for r in uncovered_report)
            body += f"<p>Sin costo en la cotización: {escape(items)}.</p>"
        odoo.post_chatter(so_id, body, model="sale.order")

    return created
