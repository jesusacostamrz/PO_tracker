"""Parse a customer RFQ (component list) into structured line items via the LLM.

Inputs arrive in mixed formats — Excel/CSV attachments, images/photos, or a table
pasted in the email body. Everything is normalized to text (or image data-URLs)
and pushed through ONE extraction prompt, so all formats yield the same JSON.
"""
from __future__ import annotations

import base64
import io

_MAX_TEXT_CHARS = 15000


def xlsx_to_text(data: bytes) -> str:
    """All sheets -> TSV-ish text. Header detection is the LLM's job, not ours."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        lines.append(f"=== SHEET {ws.title} ===")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells))
    wb.close()
    return "\n".join(lines).strip()


def _system_prompt(company: dict) -> str:
    aka = ", ".join(company.get("aka", []) or [])
    who = f'Our company is the SUPPLIER named "{company.get("legal_name", "")}"'
    if aka:
        who += f" (aka {aka})"
    return f"""You extract a Request For Quotation (RFQ) — a list of components a customer wants priced.

{who}. The RFQ is sent BY a customer TO us; the customer is the requesting company, never our own.

Return ONLY a JSON object (null where absent):
{{
  "customer_name": string,   // the requesting company, if identifiable; else null
  "rfq_ref": string,         // the customer's RFQ/requisition number, if any; else null
  "line_items": [
    {{"part_number": string,  // manufacturer part number / catalog code; null if only a description
      "description": string,  // what the item is, as written
      "quantity": number}}    // requested quantity; default 1 if truly absent
  ]
}}

Rules:
- Extract EVERY requested item; never invent items; never drop rows.
- part_number is a catalog/manufacturer code (e.g. "6204-2RS", "1SVR405613R3100") — not a line number.
- Numbers: dot decimal, no thousands separators; quantity must be a number.
- Content may be Spanish/English or both. Ignore signatures, disclaimers, prices the customer typed.
- Output JSON only — no prose, no code fences."""


def _img_data_url(img_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(img_bytes).decode("ascii")


def parse_rfq(sources: list[tuple[str, str, bytes | str]], llm, company: dict) -> dict:
    """sources: [(kind, filename, payload)] with kind in {'xlsx','image','text'}.

    Text-ish sources are concatenated into one prompt; images go to the vision
    model. If both exist, text wins (cheaper, usually the authoritative list).
    """
    system = _system_prompt(company)
    texts: list[str] = []
    image_urls: list[str] = []
    for kind, filename, payload in sources:
        if kind == "xlsx":
            texts.append(f"--- ATTACHMENT {filename} ---\n{xlsx_to_text(payload)}")
        elif kind == "text":
            texts.append(f"--- EMAIL BODY ---\n{payload}")
        elif kind == "image":
            image_urls.append(_img_data_url(payload, filename))

    if texts:
        blob = "\n\n".join(texts)[:_MAX_TEXT_CHARS]
        result = llm.chat_json(system=system, user="RFQ content:\n\n" + blob, max_tokens=3000)
        result["_source"] = "text"
    elif image_urls:
        result = llm.vision_json(system=system, user_text="Extract the RFQ from the attached image(s).",
                                 image_data_urls=image_urls[:4], max_tokens=3000)
        result["_source"] = "vision"
    else:
        result = {"customer_name": None, "rfq_ref": None, "line_items": [], "_source": "empty"}

    result.setdefault("line_items", [])
    # normalize lines defensively — downstream indexes these keys
    for li in result["line_items"]:
        li["part_number"] = (li.get("part_number") or None)
        li["description"] = str(li.get("description") or "")
        try:
            li["quantity"] = float(li.get("quantity") or 1)
        except (TypeError, ValueError):
            li["quantity"] = 1.0
    return result
