"""Offline self-check: split POs always go to a human (no network).

  python scripts/test_split.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.actions import apply_match  # noqa: E402
from core.matcher import MatchResult, match_po  # noqa: E402


class FakeSheets:
    def __init__(self, rows):
        self.rows, self.appended = rows, []

    def read(self, _rng):
        return self.rows

    def append_row(self, tab, row):
        self.appended.append((tab, row))

    def update_range(self, *_a):
        pass


CFG = {"runtime": {"dry_run": True}, "write": {}, "sheets": {"tabs": {"orders": "Orders", "audit": "Audit"}}}
MATCHING = {"amount_tolerance_pct": 0.5, "confidence_threshold": 0.85}


def _quote(total):
    return {"id": 1, "name": "S03354", "partner_id": [1, "ACME SA DE CV"], "amount_untaxed": total,
            "_lines": [{"price_unit": 100.0}]}


def _po(subtotal, ref=None):
    return {"customer_name": "ACME", "subtotal": subtotal, "supplier_quote_ref": ref,
            "line_items": [{"unit_price": 100.0}]}


def main() -> int:
    # 1) PO far below the quote total -> review, even with 100% line-price match / explicit ref
    r = match_po(_po(2858), [_quote(33561.4)], MATCHING)
    assert r.status == "needs_review" and "split" in r.reason, r
    r = match_po(_po(2858, ref="S03354"), [_quote(33561.4)], MATCHING)
    assert r.status == "needs_review", r
    # 2) near-total PO (and a bigger-than-quote PO) still auto-match
    assert match_po(_po(33000), [_quote(33561.4)], MATCHING).status == "matched"
    assert match_po(_po(40000), [_quote(33561.4)], MATCHING).status == "matched"

    # 3) 2nd PO on a quote: status label, MatchResult and written row all say Needs Review
    row = [""] * 18
    row[0], row[3], row[11] = "PO-1", "S03354", "Yes"
    sh = FakeSheets([row])
    m = MatchResult("matched", 0.9, "Matched S03354", quote=_quote(33561.4))
    out = apply_match(None, sh, CFG, {**_po(33000), "po_number": "PO-2"}, m, b"", "f.pdf")
    assert m.status == "needs_review" and out.status == "Needs Review", (m.status, out.status)
    written = sh.appended[-1][1] if sh.appended[-1][0] == "Orders" else next(r for t, r in sh.appended if t == "Orders")
    assert written[7] == "Needs Review" and written[4] == "", written

    print("test_split: OK (5 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
