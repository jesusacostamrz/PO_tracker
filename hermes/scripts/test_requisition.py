"""Offline self-check for core/requisition.py + intake_mentions.py (no network)."""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.requisition as requisition  # noqa: E402
from core.requisition import from_sales_order, resolve_vendor  # noqa: E402
from scripts.intake_mentions import parse_command, run_once  # noqa: E402


class FakeOdoo:
    def __init__(self, so, lines, attachments=None, partners=None):
        self.uid = 999
        self.so = so
        self.lines = lines
        self.attachments = attachments or []
        self.partners = partners or {}
        self.created = []       # (partner_id, origin, lines, currency)
        self.chatter = []       # (res_id, body, model)
        self.supplierinfo = []  # (tmpl_id, partner_id, price)
        self._next_rfq = 5000
        # intake_mentions state test fixtures
        self.messages = []

    # ---- sale.order / attachments ----
    def search_read(self, model, domain=None, fields=None, limit=None, order=None):
        if model == "sale.order":
            return [self.so] if domain[0][2] == self.so["name"] else []
        if model == "ir.attachment":
            return self.attachments
        if model == "mail.message":
            lo = next((v for f, op, v in domain if f == "id" and op == ">"), None)
            msgs = [m for m in self.messages if lo is None or m["id"] > lo]
            if order == "id desc":
                msgs = sorted(msgs, key=lambda m: -m["id"])
            return msgs[:limit] if limit else msgs
        raise AssertionError(f"unexpected search_read {model}")

    def order_lines(self, so_id):
        return self.lines

    def find_partners(self, name, limit=10):
        return self.partners.get(name.lower(), [])

    def ensure_vendor(self, name):
        return 9001

    def product_tmpl_map(self, ids):
        return {i: i + 100 for i in ids}

    def supplierinfo_by_tmpl(self, tmpl_ids):
        return {}

    def purchase_orders_by_origin(self, origin):
        return []

    def create_draft_rfq(self, partner_id, origin, lines, currency=None):
        self._next_rfq += 1
        self.created.append((partner_id, origin, lines, currency))
        return self._next_rfq

    def read_field(self, model, rid, fname):
        if model == "purchase.order" and fname == "name":
            return f"P{rid}"
        if model == "res.users" and fname == "partner_id":
            return [1, "Unicontrolbot"]
        if model == "sale.order" and fname == "name":
            return self.so["name"]
        raise AssertionError((model, fname))

    def post_chatter(self, res_id, body, model="sale.order"):
        self.chatter.append((res_id, body, model))
        return 1

    def upsert_supplierinfo(self, tmpl_id, partner_id, price):
        self.supplierinfo.append((tmpl_id, partner_id, price))

    def attach_pdf(self, res_id, filename, data, *, model="sale.order"):
        self.attached = getattr(self, "attached", []) + [(res_id, filename, model)]
        return 1


SO = {"id": 1, "name": "S03241", "partner_id": [2, "Cliente SA"],
      "client_order_ref": "PO-293737", "state": "sale"}

ATTACHMENTS = [
    {"name": "PO-293737.pdf", "datas": base64.b64encode(b"po-bytes").decode()},
    {"name": "Cotizacion ACME.pdf", "datas": base64.b64encode(b"quote-bytes").decode()},
]

LINES = [
    {"product_id": [1, "ABC-1"], "name": "ABC-1\nDescripcion del articulo", "product_uom_qty": 5.0},
    {"product_id": [2, "XYZ-9"], "name": "Otro articulo\nMODELO: DEF-2", "product_uom_qty": 3.0},
    {"product_id": [3, "NOPART"], "name": "NOPART", "product_uom_qty": 1.0},
]

parsed_calls = []


def fake_parse_rfq(sources, llm, company):
    parsed_calls.append(sources)
    pdf_name = next(fn for k, fn, p in sources if k == "pdf")
    assert "293737" not in pdf_name, "the customer's PO must never reach the parser"
    return {
        "line_items": [
            {"part_number": "ABC-1", "unit_cost": 10.0, "cost_currency": "USD"},
            {"part_number": "DEF-2", "unit_cost": 20.0, "cost_currency": "USD"},
        ],
        "supplier_name": "ACME SUPPLY",
        "currency": "USD",
    }


requisition.parse_rfq = fake_parse_rfq

odoo = FakeOdoo(SO, LINES, ATTACHMENTS,
               partners={"acme supply": [{"id": 77, "name": "ACME SUPPLY MX"}],
                         "bluestar": [{"id": 88, "name": "BLUESTAR MX"}]})

created = from_sales_order(odoo, llm=None, cfg={"company": {}}, so_name="S03241", live=True, out=lambda *a: None)

# (a) PO attachment skipped, only the supplier quote reached the parser
assert len(parsed_calls) == 1
assert all("293737" not in fn for src in parsed_calls for k, fn, p in src if k == "pdf")

# (b) SO qty used; part-number AND MODELO: matches both priced from the quote
assert len(odoo.created) == 1
partner_id, origin, rfq_lines, currency = odoo.created[0]
assert partner_id == 77 and origin == "S03241" and currency == "USD"
by_name = {l["name"]: l for l in rfq_lines}
assert by_name["ABC-1"]["product_qty"] == 5.0 and by_name["ABC-1"]["price_unit"] == 10.0
assert by_name["XYZ-9"]["product_qty"] == 3.0 and by_name["XYZ-9"]["price_unit"] == 20.0

# (c) the uncovered line (NOPART) folds onto the single quote at cost 0, chatter flags it
assert by_name["NOPART"]["product_qty"] == 1.0 and by_name["NOPART"]["price_unit"] == 0.0
assert odoo.chatter and "NOPART" in odoo.chatter[-1][1]

# supplierinfo upserted only for the covered (costed) lines
assert {t[2] for t in odoo.supplierinfo} == {10.0, 20.0}

print("test_requisition (a/b/c): OK")

# (d) shortage=True uses buy quantities from order_shortage.compute
parsed_calls.clear()
odoo2 = FakeOdoo(SO, LINES, ATTACHMENTS, partners={"acme supply": [{"id": 77, "name": "ACME SUPPLY MX"}]})


def fake_compute(cfg, odoo_, so_name):
    return SO, [{"product_id": 1, "part": "ABC-1", "buy": 2.0},
                {"product_id": 2, "part": "XYZ-9", "buy": 0.0}], "fake-sheet"


_orig_compute = requisition.compute
requisition.compute = fake_compute
try:
    from_sales_order(odoo2, llm=None, cfg={"company": {}}, so_name="S03241",
                     shortage=True, live=True, out=lambda *a: None)
finally:
    requisition.compute = _orig_compute

_, _, rfq_lines2, _ = odoo2.created[0]
names2 = {l["name"]: l["product_qty"] for l in rfq_lines2}
assert names2 == {"ABC-1": 2.0}  # XYZ-9 had buy=0 -> excluded before it ever reaches the RFQ
print("test_requisition (d) shortage: OK")

# (e) vendor_hint overrides the quote's supplier_name
parsed_calls.clear()
odoo3 = FakeOdoo(SO, LINES[:1], ATTACHMENTS,
                 partners={"acme supply": [{"id": 77, "name": "ACME SUPPLY MX"}],
                           "bluestar": [{"id": 88, "name": "BLUESTAR MX"}]})
from_sales_order(odoo3, llm=None, cfg={"company": {}}, so_name="S03241",
                 vendor_hint="Bluestar", live=True, out=lambda *a: None)
assert odoo3.created[0][0] == 88, "vendor_hint must beat the parsed supplier_name"
# the RFQ itself is annotated: chatter link to the SO + the supplier quote attached
assert any(m == "purchase.order" and "S0" in b for _, b, m in odoo3.chatter), odoo3.chatter
assert odoo3.attached and odoo3.attached[0][2] == "purchase.order", getattr(odoo3, "attached", None)
print("test_requisition (e) vendor_hint: OK")

# (e2) a hint that matches NO partner never creates one — the quote's supplier is used
odoo4 = FakeOdoo(SO, LINES[:1], ATTACHMENTS, partners=dict(odoo3.partners))
from_sales_order(odoo4, llm=None, cfg={"company": {}}, so_name="S03241",
                 vendor_hint="Antonio favor de procesar", live=True, out=lambda *a: None)
assert odoo4.created[0][0] == 77, "free-text hint must not become a new partner; quote issuer wins"
print("test_requisition (e2) unknown hint ignored: OK")

# (e3) an AMBIGUOUS hint (two equal partners) defers to the quote's issuer
odoo5 = FakeOdoo(SO, LINES[:1], ATTACHMENTS, partners={
    "sks": [{"id": 596, "name": "SKS Welding Systems Inc"},
            {"id": 533, "name": "SKS Welding Systems, S. de R.L. de C.V."}],
    "acme supply": [{"id": 77, "name": "ACME SUPPLY MX"}]})
from_sales_order(odoo5, llm=None, cfg={"company": {}}, so_name="S03241",
                 vendor_hint="sks", live=True, out=lambda *a: None)
assert odoo5.created[0][0] == 77, odoo5.created
print("test_requisition (e3) ambiguous hint defers to quote: OK")

from scripts.intake_mentions import parse_command as _pc  # noqa: E402
assert _pc("<a>@Unicontrolbot</a> req <a>@Antonio.Acosta</a> favor de procesar.") == (None, False)
assert _pc("@Unicontrolbot req SKS @Antonio.Acosta favor de procesar.") == ("SKS", False)
assert _pc("@Unicontrolbot req --shortage SKS, gracias") == ("SKS", True)
assert _pc('<a>@antonio.acosta</a> <a>@Unicontrolbot</a> req sks') == ("sks", False)  # bot not first
assert _pc("Has sido asignado al pedido") is None
print("test_requisition (f2) hint cut at mention/punctuation: OK")

# (f) mention command regex
assert parse_command("@Unicontrolbot req") == (None, False)
assert parse_command("Unicontrolbot: requisición SKS") == ("SKS", False)
cmd = parse_command("@Unicontrolbot req --shortage Bluestar")
assert cmd is not None and cmd[1] is True and cmd[0] == "Bluestar"
assert parse_command("@Unicontrolbot @antonio.acosta req SKS") == ("SKS", False)  # 2nd mention in between
assert parse_command("Has sido asignado a esta tarea por Juan") is None
print("test_requisition (f) mention regex: OK")

# (g) mentions state file initializes to the current max id, processing nothing
odoo4 = FakeOdoo(SO, [])
odoo4.messages = [{"id": 10, "res_id": 1, "body": "hola"}, {"id": 15, "res_id": 1, "body": "@Unicontrolbot req"}]
state_path = Path(__file__).resolve().parent / "_test_mentions_state.json"
if state_path.exists():
    state_path.unlink()
try:
    lines_out = run_once(odoo4, {"company": {}}, llm=None, dry=True, state_path=state_path)
    assert not odoo4.created and not odoo4.chatter  # nothing processed on first run
    state = json.loads(state_path.read_text())
    assert state["last_id"] == 15
    # second poll with a genuinely new message DOES process it
    odoo4.messages.append({"id": 16, "res_id": 1, "body": "@Unicontrolbot req"})
    requisition.parse_rfq = fake_parse_rfq
    lines_out2 = run_once(odoo4, {"company": {}}, llm=None, dry=True, state_path=state_path)
    state2 = json.loads(state_path.read_text())
    assert state2["last_id"] == 16
finally:
    if state_path.exists():
        state_path.unlink()
print("test_requisition (g) mentions state init: OK")

# (h) no supplier quote at all: the placeholder-vendor RFQ still carries the SO link note,
#     and the SO note names the RFQ it created
odoo5 = FakeOdoo(SO, LINES[:1], [], partners={})
created5 = from_sales_order(odoo5, llm=None, cfg={"company": {}}, so_name="S03241", live=True,
                            out=lambda *a: None)
assert created5, "no-quote requisition must still create the placeholder RFQ"
assert any(m == "purchase.order" and "S03241" in b and "/odoo/sales/" in b for _, b, m in odoo5.chatter), odoo5.chatter
so_notes = [b for _, b, m in odoo5.chatter if m == "sale.order"]
assert so_notes and created5[0][1] in so_notes[-1], (created5, so_notes)
print("test_requisition (h) no-quote RFQ provenance: OK")

print("test_requisition: OK")
