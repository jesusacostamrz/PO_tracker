"""Offline check: _resolve_so tolerates short-typed SO numbers but stays unique-or-nothing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.apply_manual import _resolve_so  # noqa: E402


class FakeOdoo:
    def __init__(self, names):
        self.names = names

    def search_read(self, model, domain, fields, limit=2, **kw):
        field, op, val = domain[0]
        if op == "=":
            hits = [n for n in self.names if n == val]
        else:  # ilike
            hits = [n for n in self.names if val.lower() in n.lower()]
        return [{"name": n, "user_id": False, "invoice_status": "", "state": "draft"} for n in hits[:limit]]


def main():
    odoo = FakeOdoo(["S02996", "S02997", "S03060"])
    assert _resolve_so(odoo, "S02996")["name"] == "S02996"   # exact
    assert _resolve_so(odoo, "s02996")["name"] == "S02996"   # case via ilike
    assert _resolve_so(odoo, "S2996")["name"] == "S02996"    # missing zero -> digits fallback
    assert _resolve_so(odoo, "2996")["name"] == "S02996"     # bare number
    assert _resolve_so(odoo, "S0299") is None                # ambiguous (0299 -> 299 hits 96+97)
    assert _resolve_so(odoo, "S99999") is None               # nonexistent
    print("OK: exact, ilike, digits fallback, ambiguity guard")


if __name__ == "__main__":
    main()
