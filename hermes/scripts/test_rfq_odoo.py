"""READ-ONLY smoke: product pool is reachable and shaped right. Writes nothing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import load_config
from connectors.odoo_client import OdooClient

cfg = load_config()
odoo = OdooClient.from_config(cfg)
prods = odoo.all_products(limit=5000)
print(f"OK — {len(prods)} sellable products")
with_code = sum(1 for p in prods if p.get("default_code"))
priced = sum(1 for p in prods if (p.get("list_price") or 0) > 0)
print(f"   with internal reference: {with_code}   with sale price > 0: {priced}")
for p in prods[:3]:
    print("  ", p)
