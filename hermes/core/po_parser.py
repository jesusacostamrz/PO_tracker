"""Parse a customer Purchase Order PDF into structured fields via the LLM.

Text-based PDFs are read with pdfplumber and sent as text (cheap). Scanned/image
PDFs (little extractable text) are rendered to images with pypdfium2 and sent to
the vision model. The same JSON schema comes back either way.

Critical detail: the PO is issued by our CUSTOMER. On the document our own company
appears as the "Proveedor/Supplier" — the parser is told who we are so it extracts
the *other* party as the customer.
"""
from __future__ import annotations

import base64
import io

import pdfplumber
import pypdfium2 as pdfium

# Skip generic legal pages so we don't waste tokens or distract the model.
_TC_MARKERS = ("terminos y condiciones", "terms and conditions")
# Below this many extracted chars we treat the PDF as scanned and use vision.
_TEXT_MIN_CHARS = 120
# Cap text sent to the model (cheap + plenty for the order pages).
_MAX_TEXT_CHARS = 15000


def extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        raw = [(i + 1, (p.extract_text() or "")) for i, p in enumerate(pdf.pages)]
    kept = [f"=== PAGE {n} ===\n{t}" for n, t in raw
            if not any(m in t.lower() for m in _TC_MARKERS)]
    if not kept:  # every page looked like T&C — keep them all rather than nothing
        kept = [f"=== PAGE {n} ===\n{t}" for n, t in raw]
    return "\n\n".join(kept).strip()


def render_pages_as_data_urls(pdf_bytes: bytes, max_pages: int = 2, scale: float = 2.0) -> list[str]:
    urls: list[str] = []
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        for i in range(min(len(doc), max_pages)):
            pil = doc[i].render(scale=scale).to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            urls.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
    finally:
        doc.close()
    return urls


def _system_prompt(company: dict) -> str:
    aka = ", ".join(company.get("aka", []) or [])
    who = f'Our company is the SUPPLIER named "{company.get("legal_name", "")}"'
    if aka:
        who += f" (aka {aka})"
    if company.get("rfc"):
        who += f", RFC {company['rfc']}"
    return f"""You extract structured data from a customer Purchase Order (PO).

{who}.
The PO is issued by our CUSTOMER (the buyer) and sent to us. On the document our company may be
labeled "Proveedor"/"Supplier"/"Vendor" — that is NOT the customer. The CUSTOMER is the buying
company that issued the PO (the letterhead/issuer at the top; labeled buyer/comprador).

Return ONLY a JSON object (use null where a field is absent):
{{
  "customer_name": string,            // the BUYER that issued the PO — never our own company
  "po_number": string,                // the BUYER's PO number (labeled "Orden de Compra"/"Purchase Order", often like "PO-290810") — NOT a supplier/proveedor account code
  "supplier_quote_ref": string,       // OUR quotation/cotización number the customer cites, if any (e.g. "S02946"); else null
  "po_date": "YYYY-MM-DD",
  "currency": string,                 // ISO code if shown (USD, MXN, ...)
  "subtotal": number,                 // untaxed amount
  "tax": number,                      // total tax
  "total": number,                    // grand total incl. tax
  "payment_terms": string,            // credit terms, e.g. "15 days"/"Net 30" (labeled Forma de pago/Payment terms) — prefer this over a payment method like "Transferencia"
  "incoterm": string,
  "buyer_contact": string,
  "ship_to": string,                  // delivery destination, condensed to one line
  "requested_delivery_date": "YYYY-MM-DD",
  "line_items": [
    {{"customer_item_code": string, "description": string, "quantity": number,
      "uom": string, "unit_price": number, "amount": number}}
  ]
}}

Rules:
- Dates -> ISO YYYY-MM-DD. Day-first (DD/MM/YYYY) is common on Mexican POs.
- Numbers: strip currency symbols and thousands separators; dot decimal; numeric fields must be numbers, not strings.
- The document may be bilingual (Spanish/English). Ignore generic Terms & Conditions / legal boilerplate.
- po_number is the BUYER's purchase-order number (often "PO-######"); never use a supplier/proveedor account number or code.
- supplier_quote_ref: only fill if the PO explicitly cites OUR quotation/cotización number; otherwise null. Never guess it.
- buyer_contact: capture the full name if shown (e.g. first + last).
- Extract every line item from the order table; never invent items.
- Output JSON only — no prose, no code fences."""


def parse_po(pdf_bytes: bytes, llm, company: dict) -> dict:
    """Return the structured PO dict. Adds '_source' = 'text' or 'vision'."""
    system = _system_prompt(company)
    text = extract_text(pdf_bytes)
    if len(text) >= _TEXT_MIN_CHARS:
        result = llm.chat_json(system=system, user="PO text:\n\n" + text[:_MAX_TEXT_CHARS], max_tokens=2000)
        result["_source"] = "text"
    else:
        images = render_pages_as_data_urls(pdf_bytes)
        result = llm.vision_json(
            system=system,
            user_text="Extract the PO from the attached image(s).",
            image_data_urls=images,
            max_tokens=2500,
        )
        result["_source"] = "vision"
    return result
