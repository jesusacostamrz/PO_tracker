"""Odoo External API (XML-RPC) connector for Hermes.

Used narrowly: read quotations to match against, write the customer PO#
(``client_order_ref``) back to the Sales Order, attach the PO PDF, post a chatter
note, and read ``invoice_status``. It NEVER confirms a Sales Order.
"""
from __future__ import annotations

import base64
import re
import xmlrpc.client
from dataclasses import dataclass, field
from datetime import date, timedelta

_TAG_RE = re.compile(r"<[^>]+>")


class OdooError(RuntimeError):
    pass


@dataclass
class OdooClient:
    url: str
    db: str
    username: str
    api_key: str
    _common: xmlrpc.client.ServerProxy = field(init=False, repr=False)
    _models: xmlrpc.client.ServerProxy = field(init=False, repr=False)
    _uid: int | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        base = self.url.rstrip("/")
        self._common = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/common", allow_none=True)
        self._models = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/object", allow_none=True)

    # ---- auth ----
    @property
    def uid(self) -> int:
        if self._uid is None:
            try:
                self._uid = self._common.authenticate(self.db, self.username, self.api_key, {})
            except Exception as exc:  # network / endpoint problems
                raise OdooError(f"Could not reach Odoo at {self.url}: {exc}") from exc
            if not self._uid:
                raise OdooError(
                    "Odoo authentication failed. Check url/db/username/api_key, that the bot "
                    "user is active, and that External API access is enabled on your plan."
                )
        return self._uid

    def version(self) -> dict:
        return self._common.version()

    # ---- generic ORM ----
    def execute(self, model: str, method: str, *args, **kwargs):
        return self._models.execute_kw(
            self.db, self.uid, self.api_key, model, method, list(args), kwargs or {}
        )

    def search_read(self, model, domain=None, fields=None, limit=None, order=None) -> list[dict]:
        kw = {}
        if fields:
            kw["fields"] = fields
        if limit:
            kw["limit"] = limit
        if order:
            kw["order"] = order
        return self.execute(model, "search_read", domain or [], **kw)

    # ---- read helpers (matching) ----
    def candidate_quotes(self, states=("draft", "sent"), lookback_days=120, limit=50) -> list[dict]:
        since = (date.today() - timedelta(days=lookback_days)).isoformat()
        domain = [["state", "in", list(states)], ["date_order", ">=", since]]
        fields = [
            "name", "partner_id", "user_id", "amount_untaxed", "amount_total", "currency_id",
            "date_order", "client_order_ref", "state", "invoice_status",
        ]
        return self.search_read("sale.order", domain, fields, limit=limit, order="date_order desc")

    def find_partners(self, name, limit=10) -> list[dict]:
        domain = ["|", ["name", "ilike", name], ["display_name", "ilike", name]]
        return self.search_read("res.partner", domain, ["name", "display_name", "email"], limit=limit)

    def order_lines(self, order_id) -> list[dict]:
        return self.search_read(
            "sale.order.line",
            [["order_id", "=", order_id]],
            ["product_id", "name", "product_uom_qty", "price_unit", "price_subtotal"],
        )

    def order_lines_bulk(self, order_ids) -> dict[int, list[dict]]:
        """Fetch lines for many orders in one call; returns {order_id: [lines]}."""
        if not order_ids:
            return {}
        rows = self.search_read(
            "sale.order.line",
            [["order_id", "in", list(order_ids)]],
            ["order_id", "product_id", "name", "product_uom_qty", "price_unit", "price_subtotal"],
        )
        by_order: dict[int, list[dict]] = {}
        for r in rows:
            oid = r["order_id"][0] if isinstance(r["order_id"], (list, tuple)) else r["order_id"]
            by_order.setdefault(oid, []).append(r)
        return by_order

    def invoice_status(self, order_id) -> str | None:
        rec = self.execute("sale.order", "read", [order_id], ["invoice_status"])
        return rec[0]["invoice_status"] if rec else None

    # ---- write path (confident match only; never confirms the SO) ----
    def set_client_order_ref(self, order_id, po_number: str) -> bool:
        return self.execute("sale.order", "write", [order_id], {"client_order_ref": po_number})

    def attach_pdf(self, order_id, filename: str, pdf_bytes: bytes) -> int:
        return self.execute(
            "ir.attachment",
            "create",
            {
                "name": filename,
                "datas": base64.b64encode(pdf_bytes).decode("ascii"),
                "res_model": "sale.order",
                "res_id": order_id,
                "mimetype": "application/pdf",
            },
        )

    def post_chatter(self, order_id, body_html: str) -> int:
        return self.execute(
            "sale.order", "message_post", [order_id], body=body_html, message_type="comment"
        )

    def read_field(self, model: str, rid: int, fname: str):
        rec = self.execute(model, "read", [rid], [fname])
        return rec[0].get(fname) if rec else None

    def set_terms_po(self, order_id, po_number: str, label: str = "PO Cliente") -> bool:
        """Append 'PO Cliente: <po#>' to the quote's Terms & Conditions (``note``).

        Appends (never overwrites existing terms) and is idempotent — if the PO# is
        already present in the note it does nothing. Returns True if it wrote.
        """
        if not po_number:
            return False
        current = self.read_field("sale.order", order_id, "note")
        current = "" if current in (False, None) else str(current)
        stripped = _TAG_RE.sub(" ", current)
        if po_number.lower() in stripped.lower():
            return False
        line = f"{label}: {po_number}"
        new = f"{current}<p>{line}</p>" if current.strip() else f"<p>{line}</p>"
        self.execute("sale.order", "write", [order_id], {"note": new})
        return True

    # ---- products & quotations (Hermes Quotes) ----
    def all_products(self, limit=10000) -> list[dict]:
        return self.search_read(
            "product.product", [["sale_ok", "=", True]],
            ["default_code", "name", "list_price"], limit=limit,
        )

    def create_draft_quote(self, partner_id: int, lines: list[dict], client_ref: str = "") -> int:
        """Create a DRAFT sale.order. Never confirms it. Omit price_unit in a line
        to let Odoo price it from the pricelist."""
        vals = {"partner_id": partner_id, "order_line": [(0, 0, l) for l in lines]}
        if client_ref:
            vals["client_order_ref"] = client_ref
        return self.execute("sale.order", "create", vals)

    def add_quote_lines(self, order_id: int, lines: list[dict]) -> bool:
        return self.execute("sale.order", "write", [order_id],
                            {"order_line": [(0, 0, l) for l in lines]})

    def create_product(self, name: str, default_code: str = "", list_price: float = 0.0) -> int:
        vals = {"name": name, "sale_ok": True, "list_price": list_price}
        if default_code:
            vals["default_code"] = default_code
        return self.execute("product.product", "create", vals)

    def product_tmpl_id(self, product_id: int) -> int:
        rec = self.execute("product.product", "read", [product_id], ["product_tmpl_id"])
        v = rec[0]["product_tmpl_id"]
        return v[0] if isinstance(v, (list, tuple)) else v

    def ensure_vendor(self, name: str) -> int:
        recs = self.search_read("res.partner", [["name", "=", name]], ["name"], limit=1)
        if recs:
            return recs[0]["id"]
        return self.execute("res.partner", "create", {"name": name, "is_company": True})

    def upsert_supplierinfo(self, tmpl_id: int, partner_id: int, price: float) -> None:
        dom = [["product_tmpl_id", "=", tmpl_id], ["partner_id", "=", partner_id]]
        recs = self.search_read("product.supplierinfo", dom, ["price"], limit=1)
        if recs:
            self.execute("product.supplierinfo", "write", [recs[0]["id"]], {"price": price})
        else:
            self.execute("product.supplierinfo", "create",
                         {"product_tmpl_id": tmpl_id, "partner_id": partner_id, "price": price})

    # ---- factory ----
    @classmethod
    def from_config(cls, cfg: dict) -> "OdooClient":
        import os
        odoo = cfg["odoo"]
        api_key = os.environ.get(odoo["api_key_env"], "")
        if not api_key:
            raise OdooError(f"Missing {odoo['api_key_env']} in .secrets/.env")
        return cls(odoo["url"], odoo["db"], odoo["username"], api_key)
