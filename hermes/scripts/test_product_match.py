"""Offline check of product matching rules (no network)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.product_matcher import match_lines, norm_code

MCFG = {"fuzzy_threshold": 88, "ambiguity_margin": 3}
PRODUCTS = [
    {"id": 1, "default_code": "6204-2RS", "name": "Rodamiento 6204 2RS sellado", "list_price": 45.0},
    {"id": 2, "default_code": "6205-2RS", "name": "Rodamiento 6205 2RS sellado", "list_price": 52.0},
    {"id": 3, "default_code": False, "name": "Cable THW 14 AWG rojo (m)", "list_price": 8.5},
    {"id": 4, "default_code": "REL-24V", "name": "Relevador 24VDC 2 polos", "list_price": 0.0},
]

assert norm_code(" 6204‑2rs ") == norm_code("6204-2RS")  # case/space/unicode-dash insensitive

def one(line):
    return match_lines([line], PRODUCTS, MCFG)[0]

# 1. exact code -> matched
m = one({"part_number": "6204-2rs", "description": "rodamiento", "quantity": 2})
assert m.status == "matched" and m.product["id"] == 1

# 2. matched product but price 0 -> queue (no price to quote)
m = one({"part_number": "REL-24V", "description": "relevador", "quantity": 1})
assert m.status == "queue" and m.product["id"] == 4 and "price" in m.reason.lower()

# 3. description-only fuzzy hit -> matched
m = one({"part_number": None, "description": "cable thw 14 awg rojo", "quantity": 100})
assert m.status == "matched" and m.product["id"] == 3

# 4. ambiguous (6204 vs 6205 close names, wrong/missing code) -> queue
m = one({"part_number": None, "description": "rodamiento 2RS sellado", "quantity": 1})
assert m.status == "queue"

# 5. nothing similar -> queue with no strong suggestion
m = one({"part_number": "ZZZ-999", "description": "valvula solenoide 3/4", "quantity": 1})
assert m.status == "queue"

print("OK test_product_match")
