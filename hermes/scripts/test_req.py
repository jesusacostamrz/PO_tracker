"""Offline requisition intake self-check (no network)."""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import intake_req as req
from scripts.order_purchasing import PLACEHOLDER_VENDOR


class Odoo:
    def __init__(self):
        self.products = [{"id": 1, "name": "221-412", "list_price": 0}]
        self.orders, self.created, self.notes, self.new = [], [], [], []
        self.fetches = 0

    def all_products(self):
        self.fetches += 1
        return list(self.products)

    def product_tmpl_map(self, ids):
        assert all(ids)  # dry-run placeholders must never be read from Odoo
        return {pid: pid + 10 for pid in ids}

    def supplierinfo_by_tmpl(self, ids):
        return {11: {"partner_id": [7, "WAGO"], "price": 2.5}}

    def purchase_orders_by_origin(self, origin):
        return [p for p in self.orders if p["origin"] == origin]

    def ensure_vendor(self, name):
        assert name == PLACEHOLDER_VENDOR
        return 9

    def account_id(self, code):
        return 500

    def create_product(self, name, list_price=0.0, description="", extra=None):
        self.new.append(dict(name=name, list_price=list_price, description=description, extra=extra))
        self.products.append({"id": 2, "name": name, "list_price": list_price})
        return 2

    def create_draft_rfq(self, partner, origin, lines):
        rid = len(self.orders) + 10
        self.created.append((partner, origin, lines))
        self.orders.append(dict(id=rid, name=f"P{rid}", partner_id=[partner, "Vendor"],
                                origin=origin, state="draft"))
        return rid

    def read_field(self, model, rid, field):
        assert (model, field) == ("purchase.order", "name")
        return f"P{rid}"

    def post_chatter(self, rid, body, *, model):
        assert model == "purchase.order" and "buyer&lt;x&gt;" in body and "REQ parts" in body
        self.notes.append(rid)


cfg = {"req": {"poll_query": "subject:req", "labels": {"processed": "P", "needs_review": "R"}},
       "rfq": {"match": {}, "product_defaults": {"unspsc": False, "expense_account": "502"}}}
gm = Mock()
gm.search.return_value = [{"id": "msg"}]
gm.headers.return_value = {"subject": " REQ parts ", "from": "buyer<x>"}
gm.attachments_by_ext.return_value = []
gm.body_text.return_value = "items"
items = [{"part_number": p, "description": "", "quantity": q}
         for p, q in [("221-412", 3), ("ZZ-9", 2), ("ZZ9", 1)]]
odoo = Odoo()
with patch.object(req, "parse_rfq", return_value={"line_items": items}):
    req.run_once(gm, odoo, cfg, None, True, 25, True)
    assert not odoo.created and not odoo.new and not gm.apply_label.called
    req.run_once(gm, odoo, cfg, None, False, 25, True)
    assert len(odoo.new) == 1 and odoo.new[0] == dict(
        name="ZZ-9", description="", list_price=0.0, extra={"property_account_expense_id": 500})
    by_vendor = {vendor: lines for vendor, origin, lines in odoo.created if origin == "REQ parts #msg"}
    assert by_vendor[7] == [dict(product_id=1, name="221-412", product_qty=3, price_unit=2.5)]
    assert [l["product_id"] for l in by_vendor[9]] == [2, 2] and len(odoo.notes) == 2
    req.run_once(gm, odoo, cfg, None, False, 25, True)
    assert len(odoo.created) == 2 and len(odoo.new) == 1 and odoo.fetches == 3
    gm.apply_label.assert_called_with("msg", "P", mark_read=True)
with patch.object(req, "parse_rfq", return_value={"line_items": []}):
    req.run_once(gm, odoo, cfg, None, False, 25, True)
    gm.apply_label.assert_called_with("msg", "R", mark_read=True)
print("test_req: OK")
