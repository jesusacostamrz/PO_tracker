"""Offline self-check for the NEW-quote-from-PO path (no network).

Covers: PO line mapping, catalog matching (incl. the real part number hiding in
the description while the part# column holds a buyer's cost-center code), price
check & balance vs prior quotes, and quote_from_po's line building against a
fake Odoo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.product_matcher import match_lines  # noqa: E402
from core.quote_actions import po_lines, quote_from_po  # noqa: E402


class FakeOdoo:
    prior_lines: list[dict] = []  # canned sale.order.line history

    def __init__(self):
        self.next_pid = 100
        self.created_products = []
        self.draft = None
        self.chatter = []

    def find_partners(self, name, limit=10):
        return [{"id": 7, "name": "Acme Industrial", "display_name": "Acme Industrial"}]

    def search_read(self, model, domain=None, fields=None, limit=None, order=None):
        assert model == "sale.order.line", model
        return self.prior_lines

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

    def post_chatter(self, order_id, body):
        self.chatter.append(body)


PO = {
    "customer_name": "Acme Industrial",
    "po_number": "PO-1234",
    "line_items": [
        {"customer_item_code": "3209536", "description": "Valvula 3/2", "quantity": 4, "unit_price": 120.5},
        # buyer's cost center in the part# column; real part number leads the description
        {"customer_item_code": "9000514 MEJORAS AUTOMATIZACION",
         "description": 'M22-KC10 "Bloque de contacto N.O. para Botoneria"',
         "quantity": 10, "unit_price": 4.8},
        {"customer_item_code": "ZZZ-999", "description": "Conector especial", "quantity": 2, "unit_price": 33.0},
        {"customer_item_code": None, "description": None, "quantity": 1, "unit_price": 9.9},  # dropped
    ],
}
CATALOG = [{"id": 1, "name": "3209536", "default_code": "", "list_price": 250.0},
           {"id": 2, "name": "M22-KC10", "default_code": "", "list_price": 6.0}]
CFG = {"rfq": {"match": {"fuzzy_threshold": 88, "ambiguity_margin": 3, "partner_threshold": 85},
               "product_defaults": {}}}


def demo():
    lines = po_lines(PO)
    assert len(lines) == 3, lines  # the empty line is dropped
    assert lines[0]["part_number"] == "3209536" and lines[0]["unit_price"] == 120.5

    matches = match_lines(lines, CATALOG, CFG["rfq"]["match"])
    # cost-center part# didn't block the match: M22-KC10 found inside the description
    assert matches[1].product and matches[1].product["id"] == 2, matches[1]
    assert matches[1].reason.startswith("exact part-number match (in description)"), matches[1].reason

    audits = []
    odoo = FakeOdoo()
    # price history: 3209536 quoted at the SAME price, M22-KC10 quoted HIGHER (5.2)
    odoo.prior_lines = [
        {"product_id": [1, "3209536"], "price_unit": 120.5, "order_id": [9, "S03000"]},
        {"product_id": [2, "M22-KC10"], "price_unit": 5.2, "order_id": [9, "S03000"]},
    ]
    out = quote_from_po(odoo, CFG, PO, matches, lambda *a: audits.append(a))
    assert out.order_id == 55 and out.order_name == "S09999"
    assert odoo.draft["client_ref"] == "PO-1234"
    l1, l2, l3 = odoo.draft["lines"]
    # matched catalog product reused, priced from the PO (not our 250.0 list price)
    assert l1 == {"product_id": 1, "product_uom_qty": 4, "price_unit": 120.5}, l1
    assert l2 == {"product_id": 2, "product_uom_qty": 10, "price_unit": 4.8}, l2
    # unmatched line: product auto-created AT the PO price, customer wording on the line
    assert len(odoo.created_products) == 1
    cp = odoo.created_products[0]
    assert cp["name"] == "ZZZ-999" and cp["list_price"] == 33.0
    assert l3["product_id"] == cp["id"] and l3["price_unit"] == 33.0
    assert l3["name"] == "[ZZZ-999] Conector especial", l3
    # price check: same-price line silent; moved price + new product flagged; chatter posted
    assert out.status == "Price Review" and len(out.price_flags) == 2, out.price_flags
    assert any("4.8" in f and "5.2" in f for f in out.price_flags), out.price_flags
    assert any("new product" in f for f in out.price_flags), out.price_flags
    assert odoo.chatter and "discrepancies" in odoo.chatter[0]

    # all prices agree and nothing auto-created -> clean status, no chatter warning
    odoo4 = FakeOdoo()
    odoo4.prior_lines = [
        {"product_id": [1, "3209536"], "price_unit": 120.5, "order_id": [9, "S03000"]},
        {"product_id": [2, "M22-KC10"], "price_unit": 4.8, "order_id": [9, "S03000"]},
    ]
    po_clean = {**PO, "line_items": PO["line_items"][:2]}
    out4 = quote_from_po(odoo4, CFG, po_clean, match_lines(po_lines(po_clean), CATALOG, CFG["rfq"]["match"]),
                         lambda *a: audits.append(a))
    assert out4.status == "Draft Created" and not out4.price_flags and not odoo4.chatter

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

    # redo detection: NEW + cancelled/deleted linked SO unblocks; a live one doesn't
    from scripts.apply_manual import _so_redoable

    class SO(FakeOdoo):
        state: str | None = "cancel"

        def search_read(self, model, domain=None, fields=None, limit=None, order=None):
            assert model == "sale.order"
            return [{"state": self.state}] if self.state else []
    so = SO()
    assert _so_redoable(so, "3121")            # cancelled -> redo
    so.state = "draft"
    assert not _so_redoable(so, "3121")        # still standing -> blocked
    so.state = None
    assert _so_redoable(so, "999")             # deleted -> redo
    assert not _so_redoable(so, "garbage")     # unparseable id -> stay safe, blocked

    print("test_manual_new: OK")


if __name__ == "__main__":
    demo()
