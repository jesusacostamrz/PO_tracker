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

# supplier-quote mode: margin_pct + unit_cost normalized; sale = cost * (1 + margin)
class _CostLLM:
    def chat_json(self, **kw):
        return {"customer_name": "ABC", "margin_pct": "40",
                "line_items": [{"description": "valvula", "quantity": 2, "unit_cost": "118.50"},
                               {"description": "cable", "quantity": 1}]}
r = parse_rfq([("text", "email-body", "quote for ABC +40%")], _CostLLM(), {})
assert r["margin_pct"] == 40.0 and r["line_items"][0]["unit_cost"] == 118.5
assert r["line_items"][1]["unit_cost"] is None

from core.quote_actions import _cost_sale_price
class _M:  # minimal LineMatch stand-in: only .line is read
    def __init__(self, line): self.line = line
assert _cost_sale_price(_M({"unit_cost": 100.0}), 40.0, 25) == 140.0
assert _cost_sale_price(_M({"unit_cost": 100.0}), None, 25) == 125.0
assert _cost_sale_price(_M({"unit_cost": None}), 40.0, 25) is None
print("OK supplier-quote pricing")

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
