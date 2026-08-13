"""Offline self-check for core/pricebook.py + pricebook pricing. No network."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.pricebook import Pricebook, apply_pricebook, load_pricebooks  # noqa: E402
from core.product_matcher import LineMatch                              # noqa: E402
from core.quote_actions import _pricebook_sale                          # noqa: E402

FCFG = {"vendor_name": "Phoenix Contact", "currency": "USD", "mxn_fx_surcharge": 0.5,
        "header_row": 1,
        "columns": {"item": "Item number", "type": "Type description",
                    "list": "2026 PL", "cost": "2026 Distribuidor"}}

ROWS = [["706016", "DFK-2,8", 2.22, 1.37],
        ["706029", "DFK-2,8 BU", 2.30, 1.42],
        ["1234567", "UT 2,5", 100.0, 61.7]]


def _lm(part=None, desc="", status="queue"):
    return LineMatch({"part_number": part, "description": desc, "quantity": 1},
                     status, None, 0.0, "no product above match threshold")


def main() -> int:
    pb = Pricebook("phoenix", FCFG, ROWS)

    # lookup: by item number, by type (comma/dash-insensitive), by desc token
    assert pb.lookup("706016")["type"] == "DFK-2,8"
    assert pb.lookup("dfk-2,8")["item"] == "706016"
    assert pb.lookup("DFK 2,8 BU")["item"] == "706029"
    assert pb.lookup(None, "TERMINAL PHOENIX 1234567 PARA RIEL")["type"] == "UT 2,5"
    assert pb.lookup("999999") is None
    # two different catalog hits in one description -> ambiguous -> None
    assert pb.lookup(None, "706016 o 706029") is None

    # apply_pricebook: hit stashes _pricebook; existing catalog product is reused
    cfg = {"pricebook": {"files": {}}}  # loaded books injected below via monkey-ish path
    matches = [_lm("706016"), _lm("999999", "no match"), _lm("UT 2,5")]
    products = [{"id": 7, "name": "UT 2,5", "default_code": "", "list_price": 90.0}]
    import core.pricebook as mod
    orig = mod.load_pricebooks
    mod.load_pricebooks = lambda _cfg: [pb]
    try:
        hits = apply_pricebook(matches, products, cfg)
    finally:
        mod.load_pricebooks = orig
    assert hits == 2
    assert matches[0].status == "queue" and matches[0].line["_pricebook"]["list"] == 2.22
    assert matches[0].line["manufacturer"] == "Phoenix Contact"
    assert matches[1].line.get("_pricebook") is None
    assert matches[2].status == "matched" and matches[2].product["id"] == 7  # reused, no duplicate

    # pricing: list as-is; discount x(1-d); margin /(1-m); MXN fx already surcharged by caller
    rec = {"list": 100.0}
    assert _pricebook_sale(rec, 1.0, None, None) == 100.0
    assert _pricebook_sale(rec, 1.0, 10, None) == 90.0            # 10% discount -> x0.9
    assert _pricebook_sale(rec, 1.0, None, 30) == 142.86          # margin on selling price
    assert _pricebook_sale(rec, 17.8, None, None) == 1780.0       # 17.3 official + 0.5
    assert _pricebook_sale(rec, None, None, None) is None         # unknown fx -> refuse
    assert _pricebook_sale({"list": 0}, 1.0, None, None) is None  # no list price -> queue

    # xlsx round-trip through load_pricebooks (incl. the JSON cache)
    with tempfile.TemporaryDirectory() as td:
        from openpyxl import Workbook
        path = Path(td) / "pl.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append(["Item number", "Type description", "BU", "2026 PL", "2026 Distribuidor"])
        ws.append(["706016", "DFK-2,8", "AA", 2.22, 1.37])
        ws.append(["", "", "", None, None])              # junk row skipped
        wb.save(path)
        cfg2 = {"pricebook": {"files": {"phx": {**FCFG, "path": str(path)}}}}
        for _ in range(2):  # 2nd pass reads the cache
            books = load_pricebooks(cfg2)
            assert len(books) == 1 and books[0].lookup("706016")["list"] == 2.22
        assert path.with_suffix(".xlsx.cache.json").exists()

    print("test_pricebook: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
