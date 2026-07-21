"""Offline: brand-mapped xlsx -> normalized rows with computed sale price."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from scripts.import_pricelist import read_pricelist

wb = Workbook(); ws = wb.active
ws.append(["Part Number", "Description", "List", "Net Price"])
ws.append(["AB-100", "Contactor 3P 25A", 100.0, 60.0])
ws.append(["AB-200", "Contactor 3P 40A", 150.0, "  $95.50 "])
ws.append([None, "junk row", None, None])
buf = io.BytesIO(); wb.save(buf)

brand = {"vendor_name": "X", "markup_pct": 25, "header_row": 1,
         "columns": {"part": "Part Number", "description": "Description", "cost": "Net Price"}}
rows = read_pricelist(buf.getvalue(), brand)
assert len(rows) == 2
assert rows[0] == {"part": "AB-100", "description": "Contactor 3P 25A", "cost": 60.0, "sale_price": 75.0}
assert rows[1]["cost"] == 95.5 and rows[1]["sale_price"] == 119.38
print("OK test_pricelist")
