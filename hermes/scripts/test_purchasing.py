"""Offline self-check for order_purchasing.py clustering (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.order_purchasing import cluster  # noqa: E402

to_buy = [
    {"product_id": 1, "part": "221-412", "buy": 150.0},   # WAGO
    {"product_id": 2, "part": "221-413", "buy": 150.0},   # WAGO
    {"product_id": 3, "part": "M21-375-499", "buy": 5.0}, # Brady, min_qty 10 > buy
    {"product_id": 4, "part": "ZZ-9", "buy": 2.0},        # no vendor on file
    {"product_id": 5, "part": "XX-1", "buy": 1.0},        # template missing entirely
]
tmpl_map = {1: 11, 2: 12, 3: 13, 4: 14}  # 5 absent
sinfo = {
    11: {"partner_id": [7, "WAGO MX"], "price": 2.5, "min_qty": 0},
    12: {"partner_id": [7, "WAGO MX"], "price": 3.0, "min_qty": 0},
    13: {"partner_id": [9, "Brady"], "price": 40.0, "min_qty": 10},
    # 14 has no supplierinfo row
}

by_vendor, unassigned = cluster(to_buy, tmpl_map, sinfo)

assert set(by_vendor) == {(7, "WAGO MX"), (9, "Brady")}
wago = by_vendor[(7, "WAGO MX")]
assert [l["name"] for l in wago] == ["221-412", "221-413"]
assert wago[0]["product_qty"] == 150.0 and wago[0]["price_unit"] == 2.5
brady = by_vendor[(9, "Brady")][0]
assert brady["_min_qty_note"] == 10.0            # below vendor minimum -> flagged
assert [r["part"] for r in unassigned] == ["ZZ-9", "XX-1"]

print("test_purchasing: OK")
