"""Web price research for a Pricing Queue line, via SearchClient + LLMClient.

Advisory only (see CLAUDE.md): the result is a suggestion shown to the human
pricer, never written straight to a quote. Any failure (no search client, no
usable search result, no trustworthy offer) degrades to None — callers treat
that exactly like "no suggestion available".
"""
from __future__ import annotations

_SYSTEM = """You extract the single best CURRENT purchase offer for one exact part
from raw web-search results. Prefer Mexican vendors when available. Only exact
part-number matches count — do not substitute an equivalent or generic part.
If no trustworthy offer with a real price is present, return price null.

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

    prompt = (
        f"Busca ofertas de compra actuales para esta pieza exacta: {subject}. "
        f"Descripcion: {desc}. Cantidad requerida: {line.get('quantity', 1)}. "
        "Prioriza proveedores que vendan y envien dentro de Mexico. "
        "Si no hay disponibilidad en Mexico, lista ofertas internacionales. "
        "Para cada oferta incluye: precio, moneda, proveedor y URL del producto."
    )

    try:
        result = search.web_search(prompt, country="MX")
        if not result or not result.get("text"):
            return None

        user = result["text"] + "\n\nSources:\n" + "\n".join(result.get("sources") or [])
        offer = llm.chat_json(system=_SYSTEM, user=user, max_tokens=400)

        price = offer.get("price")
        if price is None:
            return None
        offer["price"] = float(price)
        return offer
    except Exception as e:
        print(f"WARN web_pricing: {e}")
        return None
