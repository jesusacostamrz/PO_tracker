"""Offline self-check for the NEW-quote-from-PO path (no network).

Covers: PO line mapping, catalog matching, and quote_from_po's line building
(PO prices everywhere, product auto-created for unmatched lines, customer
wording kept on created lines) against a fake Odoo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.product_matcher import match_lines  # noqa: E402
from core.quote_actions import po_lines, quote_from_po  # noqa: E402


class FakeOdoo:
    def __init__(self):
        self.next_pid = 100
        self.created_products = []
        self.draft = None

    def find_partners(self, name, limit=10):
        return [{"id": 7, "name": "Acme Industrial", "display_name": "Acme Industrial"}]

    def create_product(self, name, default_code="", list_price=0.0, description="", extra=None):
        self.next_pid += 1
        self.created_products.append({"id": self.next_pid, "name": name,
                                      "list_price": list_price, "description": description})
        return self.next_pid

    def create_draft_quote(self, partner_id, lines, client_ref=""):
        self.draft = {"partner_id": partner_id, "lines": lines, "client_ref": client_ref}
        return 55

    def read_field(self, model, rid, fname):
        return "S09999"


PO = {
    "customer_name": "Acme Industrial",
    "po_number": "PO-1234",
    "line_items": [
        {"customer_item_code": "3209536", "description": "Valvula 3/2", "quantity": 4, "unit_price": 120.5},
        {"customer_item_code": "ZZZ-999", "description": "Conector especial", "quantity": 2, "unit_price": 33.0},
        {"customer_item_code": None, "description": None, "quantity": 1, "unit_price": 9.9},  # dropped
    ],
}
CATALOG = [{"id": 1, "name": "3209536", "default_code": "", "list_price": 250.0}]
CFG = {"rfq": {"match": {"fuzzy_threshold": 88, "ambiguity_margin": 3, "partner_threshold": 85},
               "product_defaults": {}}}


def demo():
    lines = po_lines(PO)
    assert len(lines) == 2, lines  # the empty line is dropped
    assert lines[0]["part_number"] == "3209536" and lines[0]["unit_price"] == 120.5

    audits = []
    odoo = FakeOdoo()
    matches = match_lines(lines, CATALOG, CFG["rfq"]["match"])
    out = quote_from_po(odoo, CFG, PO, matches, lambda *a: audits.append(a))
    assert out.order_id == 55 and out.order_name == "S09999"
    assert odoo.draft["client_ref"] == "PO-1234"
    l1, l2 = odoo.draft["lines"]
    # matched catalog product reused, priced from the PO (not our 250.0 list price)
    assert l1 == {"product_id": 1, "product_uom_qty": 4, "price_unit": 120.5}, l1
    # unmatched line: product auto-created AT the PO price, customer wording on the line
    assert len(odoo.created_products) == 1
    cp = odoo.created_products[0]
    assert cp["name"] == "ZZZ-999" and cp["list_price"] == 33.0
    assert l2["product_id"] == cp["id"] and l2["price_unit"] == 33.0
    assert l2["name"] == "[ZZZ-999] Conector especial", l2

    # dry-run: nothing created, no order id
    odoo2 = FakeOdoo()
    out2 = quote_from_po(odoo2, CFG, PO, match_lines(po_lines(PO), CATALOG, CFG["rfq"]["match"]),
                         lambda *a: audits.append(a), dry=True)
    assert out2.order_id is None and odoo2.draft is None and not odoo2.created_products

    # unknown customer: no draft, status Needs Review
    class NoPartner(FakeOdoo):
        def find_partners(self, name, limit=10):
            return []
    out3 = quote_from_po(NoPartner(), CFG, PO, match_lines(po_lines(PO), CATALOG, CFG["rfq"]["match"]),
                         lambda *a: audits.append(a))
    assert out3.order_id is None and out3.status == "Needs Review"

    print("test_manual_new: OK")


if __name__ == "__main__":
    demo()
