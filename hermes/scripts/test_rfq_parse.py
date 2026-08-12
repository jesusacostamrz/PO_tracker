"""Offline: xlsx_to_text. Optional live: parse a real RFQ file if passed as argv[1]."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.rfq_parser import xlsx_to_text

from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["Part Number", "Descripcion", "Cant"])
ws.append(["6204-2RS", "Rodamiento sellado", 12])
ws.append([None, "Cable 14 AWG rojo", 100])
buf = io.BytesIO(); wb.save(buf)

text = xlsx_to_text(buf.getvalue())
assert "6204-2RS" in text and "Cable 14 AWG rojo" in text and "12" in text
print("OK xlsx_to_text")

# routing: any image -> vision (text included as context); text-only -> chat
from core.rfq_parser import parse_rfq

class _FakeLLM:
    def chat_json(self, **kw):
        return {"line_items": [], "_via": "chat", "_user": kw.get("user")}
    def vision_json(self, **kw):
        return {"line_items": [], "_via": "vision", "_user": kw.get("user_text")}

r = parse_rfq([("image", "a.png", b"png"), ("text", "email-body", "From: nsoto@abc-aluminum.com")],
              _FakeLLM(), {})
assert r["_via"] == "vision" and "abc-aluminum" in r["_user"] and r["_source"] == "vision+text"
r = parse_rfq([("text", "email-body", "hola")], _FakeLLM(), {})
assert r["_via"] == "chat" and r["_source"] == "text"
print("OK parse_rfq routing")

# pdf routing: text PDF -> chat as text; scanned PDF -> rendered pages -> vision
import core.po_parser as pp
_orig = pp.extract_text, pp.render_pages_as_data_urls
pp.extract_text = lambda b: "COT-1234\nVALVULA SMC VX21 x2" + " " * pp._TEXT_MIN_CHARS
r = parse_rfq([("pdf", "cot.pdf", b"%PDF")], _FakeLLM(), {})
assert r["_via"] == "chat" and "VALVULA SMC" in r["_user"]
pp.extract_text = lambda b: ""  # scanned: no text layer
pp.render_pages_as_data_urls = lambda b, **kw: ["data:image/png;base64,AAAA"]
r = parse_rfq([("pdf", "scan.pdf", b"%PDF")], _FakeLLM(), {})
assert r["_via"] == "vision" and r["_source"] == "vision"
pp.extract_text, pp.render_pages_as_data_urls = _orig
print("OK pdf routing")

# supplier-quote mode: margin_pct + unit_cost normalized; sale = cost / (1 - margin)
class _CostLLM:
    def chat_json(self, **kw):
        return {"customer_name": "ABC", "margin_pct": "40", "currency": "mxn",
                "line_items": [{"description": "valvula", "quantity": 2, "unit_cost": "118.50",
                                "cost_currency": "usd"},
                               {"description": "cable", "quantity": 1}]}
r = parse_rfq([("text", "email-body", "quote for ABC +40%")], _CostLLM(), {})
assert r["margin_pct"] == 40.0 and r["line_items"][0]["unit_cost"] == 118.5
assert r["line_items"][1]["unit_cost"] is None
assert r["currency"] == "MXN" and r["line_items"][0]["cost_currency"] == "USD"
assert r["line_items"][1]["cost_currency"] is None

from core.quote_actions import _cost_sale_price, _fx_factor
class _M:  # minimal LineMatch stand-in: only .line is read
    def __init__(self, line): self.line = line
# margin is on the SELLING price: sale = cost / (1 - margin)
assert _cost_sale_price(_M({"unit_cost": 1000.0}), 40.0, 25) == 1666.67  # user's example
assert _cost_sale_price(_M({"unit_cost": 100.0}), None, 30) == 142.86    # default margin /0.7
assert _cost_sale_price(_M({"unit_cost": None}), 40.0, 25) is None
assert _cost_sale_price(_M({"unit_cost": 0.0}), 40.0, 25) is None        # SIN COSTO -> queue
assert _cost_sale_price(_M({"unit_cost": 100.0}), 100.0, 25) is None     # absurd margin -> queue
assert _cost_sale_price(_M({"unit_cost": 100.0}), 40.0, 25, fx=0.1) == 16.67

class _FxOdoo:  # rates relative to company currency (USD=1)
    def search_read(self, model, dom, fields, **kw):
        return [{"name": "MXN", "rate": 17.0}, {"name": "USD", "rate": 1.0}]
assert abs(_fx_factor(_FxOdoo(), "MXN", "USD") - 1 / 17.0) < 1e-9
assert _fx_factor(_FxOdoo(), "USD", "USD") == 1.0
assert _fx_factor(_FxOdoo(), None, "USD") is None
assert _fx_factor(_FxOdoo(), "EUR", "USD") is None  # no rate returned -> refuse
print("OK supplier-quote pricing")

# instruction override: the subject/body second pass beats the document's parse
class _TwoPassLLM:
    def chat_json(self, system, user, max_tokens=0):
        if '"line_items"' in system:  # main extraction prompt carries the schema
            return {"customer_name": "Industrial Magza",  # document letterhead slip
                    "line_items": [{"description": "reductor", "quantity": 1, "unit_cost": 100}]}
        return {"customer_name": "abc", "margin_pct": "40",
                "price_source_site": "https://www.AutomationDirect.com/adc"}

r = parse_rfq([("text", "email-subject", "EMAIL SUBJECT: rfq abc"),
               ("text", "email-body", "quote for abc with 40% margin")], _TwoPassLLM(), {})
assert r["customer_name"] == "abc", r["customer_name"]
assert r["margin_pct"] == 40.0 and r["price_source_site"] == "automationdirect.com"
assert r["line_items"][0]["unit_cost"] == 100.0  # line items untouched by the override
print("OK salesperson-instruction override beats document parse")

if len(sys.argv) > 1:  # live LLM smoke: python scripts/test_rfq_parse.py <rfq.xlsx|.png|.txt>
    from core.config import load_config
    from connectors.llm_client import LLMClient
    from core.rfq_parser import parse_rfq
    cfg = load_config(); llm = LLMClient.from_config(cfg)
    p = Path(sys.argv[1]); ext = p.suffix.lower()
    kind = ("xlsx" if ext in (".xlsx", ".xlsm") else "image" if ext in (".png", ".jpg", ".jpeg")
            else "pdf" if ext == ".pdf" else "text")
    payload = p.read_bytes() if kind != "text" else p.read_text(encoding="utf-8", errors="replace")
    rfq = parse_rfq([(kind, p.name, payload)], llm, cfg.get("company", {}))
    print(f"customer={rfq.get('customer_name')}  ref={rfq.get('rfq_ref')}  lines={len(rfq['line_items'])}")
    for li in rfq["line_items"][:5]:
        print("  ", li)
