"""Web price research for a Pricing Queue line, via SearchClient + LLMClient.

Advisory only (see CLAUDE.md): the result is a suggestion shown to the human
pricer, never written straight to a quote. Any failure (no search client, no
usable search result, no trustworthy offer) degrades to None — callers treat
that exactly like "no suggestion available".
"""
from __future__ import annotations

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


def research_price(line: dict, llm, search) -> dict | None:
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
            # bare part number, exactly what a human types — Google ranks the
            # exact-SKU page first; extra words (brand, "precio comprar") pull
            # in lookalikes. Results that never mention the part are dropped
            # BEFORE extraction, so a junk hit can't become the fallback link.
            result = search.web_search(part or desc, country="MX",
                                       must_contain=part or None)
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
