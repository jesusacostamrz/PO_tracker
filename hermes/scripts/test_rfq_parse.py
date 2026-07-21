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

if len(sys.argv) > 1:  # live LLM smoke: python scripts/test_rfq_parse.py <rfq.xlsx|.png|.txt>
    from core.config import load_config
    from connectors.llm_client import LLMClient
    from core.rfq_parser import parse_rfq
    cfg = load_config(); llm = LLMClient.from_config(cfg)
    p = Path(sys.argv[1]); ext = p.suffix.lower()
    kind = "xlsx" if ext in (".xlsx", ".xlsm") else "image" if ext in (".png", ".jpg", ".jpeg") else "text"
    payload = p.read_bytes() if kind != "text" else p.read_text(encoding="utf-8", errors="replace")
    rfq = parse_rfq([(kind, p.name, payload)], llm, cfg.get("company", {}))
    print(f"customer={rfq.get('customer_name')}  ref={rfq.get('rfq_ref')}  lines={len(rfq['line_items'])}")
    for li in rfq["line_items"][:5]:
        print("  ", li)
