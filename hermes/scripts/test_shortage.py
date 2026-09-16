"""Offline self-check for order_shortage.py logic (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.order_shortage import find_col, shortage, stock_map, to_qty  # noqa: E402

# column auto-detect: accents/case ignored, priority order respected
hdr = ["Fecha", "No. Parte", "Descripción", "Existencia Física", "Ubicación"]
assert find_col(hdr, ["no. parte", "sku"]) == 1
assert find_col(hdr, ["existencia", "stock"]) == 3
assert find_col(hdr, ["nothing-here"]) is None

# stock map: duplicate part rows sum; blank/short rows skipped; commas parsed;
# spaced part numbers ('32 09 53 6') match compact ('3209536'); MODELO col indexed too
rows = [
    ["x", "RB38", "", "1,200"],
    ["x", "rb 38 ", "", "50"],      # same part, spaces/case -> summed
    ["x", "", "", "99"],            # blank part -> skipped
    ["x", "AB-1"],                  # row shorter than qty col -> qty 0
    ["32 09 53 6", "D-ST 4", "", "7"],
]
sm = stock_map(rows, part_idxs=[1], qty_idx=3)
assert sm["rb38"] == 1250.0
assert sm["ab-1"] == 0.0
sm = stock_map(rows, part_idxs=[0, 1], qty_idx=3)
assert sm["3209536"] == 7.0     # spaced part number, compact lookup
assert sm["d-st4"] == 7.0       # modelo column indexed under its own key
# part and modelo columns holding the SAME value must not double-count the row
assert stock_map([["3209536", "3209536", "", "7"]], part_idxs=[0, 1], qty_idx=3)["3209536"] == 7.0

# shortage: covered, partial, and not-in-sheet lines
lines = [
    {"product_id": [1, "RB38"], "product_uom_qty": 1000},   # covered
    {"product_id": [2, "AB-1"], "product_uom_qty": 5},      # in sheet, 0 on hand
    {"product_id": [3, "ZZ-9"], "product_uom_qty": 2},      # not in sheet
]
rep = shortage(lines, sm)
assert rep[0]["buy"] == 0 and rep[0]["in_sheet"]
assert rep[1]["buy"] == 5 and rep[1]["in_sheet"]
assert rep[2]["buy"] == 2 and not rep[2]["in_sheet"]

assert to_qty("1,234.5") == 1234.5 and to_qty("") == 0.0 and to_qty("n/a") == 0.0

print("test_shortage: OK")
