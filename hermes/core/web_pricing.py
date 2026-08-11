"""Web price research for a Pricing Queue line, via SearchClient + LLMClient.

Advisory only (see CLAUDE.md): the result is a suggestion shown to the human
pricer, never written straight to a quote. Any failure (no search client, no
usable search result, no trustworthy offer) degrades to None — callers treat
that exactly like "no suggestion available".
"""
from __future__ import annotations

import re

_SYSTEM = """You extract the single best CURRENT purchase offer for one exact part
from raw web-search results. Prefer Mexican vendors when available. STRICT rule:
the offer's own part number must be EXACTLY the requested one (same prefix, same
suffix, same digits) — a near-miss variant, a different series, or a lookalike
SKU does NOT count; when in doubt return price null. The url MUST be copied
verbatim from the provided Sources list and must be the page of that exact part.
If no trustworthy offer with a real price exists, return price null but still
set url to the most relevant source (a catalog or vendor page for the part) and
say why in note.

Return ONLY a JSON object:
{"price": number|null, "currency": "MXN"|"USD"|..., "vendor": string, "url": string, "note": string}"""


def research_price(line: dict, llm, search, preferred_sites: tuple | list = ()) -> dict | None:
    if search is None:
        return None
    part = (line.get("part_number") or "").strip()
    mfr = (line.get("manufacturer") or "").strip()
    desc = (line.get("description") or "").strip()
    subject = f"{part} {mfr}".strip() if part else desc
    if not subject:
        return None

    try:
        if getattr(search, "kind", "") == "serper":
            # Query ladder, stop at the first tier with validated results:
            # 1) bare part number, exactly what a human types — Google ranks the
            #    exact-SKU page first; extra words pull in lookalikes
            # 2) part + brand — long/generic part numbers sometimes need the
            #    brand to rank; safe because must_contain still requires the
            #    exact part in every surviving result
            # Each tier tries MX first, then US (MX-localized Google often
            # lacks US-catalog parts entirely). Last resort: vendors often list
            # a part WITHOUT its letter prefix (Bimba "C-7030-DXP-00MC" is sold
            # as "7030-DXP-00MC"), so retry accepting the prefix-stripped form —
            # the extractor's exact-part rule still blocks a variant PRICE, so
            # this can only add reference links/images, never bad prices.
            # 0) preferred supplier catalogs first (config rfq.preferred_supplier_sites)
            queries = [f"site:{s} {part or desc}" for s in preferred_sites]
            queries.append(part or desc)
            if part and mfr:
                queries.append(f"{part} {mfr}")
            keys = [part] if part else [None]
            stripped = re.sub(r"^[A-Za-z]+[-\s]+", "", part)
            if part and stripped != part and len(re.sub(r"[^a-zA-Z0-9]", "", stripped)) >= 6:
                keys.append(stripped)
            result = None
            for key in keys:
                for q in queries:
                    for country in ("MX", "US"):
                        result = search.web_search(q, country=country, must_contain=key)
                        if result:
                            break
                    if result:
                        break
                if result:
                    break
        else:
            prompt = (
                f"Busca ofertas de compra actuales para esta pieza exacta: {subject}. "
                f"Descripcion: {desc}. Cantidad requerida: {line.get('quantity', 1)}. "
                "Prioriza proveedores que vendan y envien dentro de Mexico. "
                "Si no hay disponibilidad en Mexico, lista ofertas internacionales. "
                "Para cada oferta incluye: precio, moneda, proveedor y URL del producto."
            )
            result = search.web_search(prompt, country="MX")
        if not result or not result.get("text"):
            return None

        user = result["text"] + "\n\nSources:\n" + "\n".join(result.get("sources") or [])
        offer = llm.chat_json(system=_SYSTEM, user=user, max_tokens=400)

        price = offer.get("price")
        if price is None:
            # no trustworthy offer — still hand the human a reference link
            url = offer.get("url") or ((result.get("sources") or [None])[0])
            if not url:
                return None
            return {"price": None, "currency": "", "vendor": offer.get("vendor") or "",
                    "url": url, "note": offer.get("note") or "no trustworthy offer found"}
        offer["price"] = float(price)
        return offer
    except Exception as e:
        print(f"WARN web_pricing: {e}")
        return None
