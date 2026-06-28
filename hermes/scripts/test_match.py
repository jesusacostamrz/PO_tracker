"""Parse a PO and try to match it to an Odoo quotation (read-only; writes nothing).

Usage:  python scripts/test_match.py <path-to-po.pdf>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from core.po_parser import parse_po  # noqa: E402
from core.matcher import match_po, _cust_sim  # noqa: E402
from connectors.llm_client import LLMClient  # noqa: E402
from connectors.odoo_client import OdooClient, OdooError  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/test_match.py <path-to-po.pdf>")
        return 2
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"not found: {pdf_path}")
        return 2

    cfg = load_config()
    llm = LLMClient.from_config(cfg)

    po = parse_po(pdf_path.read_bytes(), llm, cfg.get("company", {}))
    print("Parsed PO:")
    print(f"  customer   : {po.get('customer_name')}")
    print(f"  PO #       : {po.get('po_number')}")
    print(f"  quote ref  : {po.get('supplier_quote_ref')}")
    print(f"  untaxed    : {po.get('subtotal')} {po.get('currency')}")
    for li in po.get("line_items") or []:
        print(f"  line       : {li.get('quantity')} x {li.get('unit_price')}  {li.get('description')}")

    try:
        odoo = OdooClient.from_config(cfg)
        m = cfg["matching"]
        quotes = odoo.candidate_quotes(states=tuple(m["candidate_states"]),
                                       lookback_days=m["lookback_days"], limit=500)
        # attach line items for the customer-matched candidates only (lean)
        cust = po.get("customer_name") or ""
        ids = [q["id"] for q in quotes
               if q.get("partner_id") and _cust_sim(cust, q["partner_id"][1]) >= 0.80]
        lines = odoo.order_lines_bulk(ids)
        for q in quotes:
            q["_lines"] = lines.get(q["id"], [])
    except OdooError as exc:
        print(f"\nFAILED (Odoo): {exc}")
        return 1

    print(f"\nPulled {len(quotes)} quotes; {len(ids)} match the customer (lines fetched). "
          f"tolerance={m['amount_tolerance_pct']}%")

    res = match_po(po, quotes, m)
    print(f"\n=== RESULT: {res.status.upper()}  (confidence {res.confidence}) ===")
    print(res.reason)
    if res.quote:
        q = res.quote
        partner = q["partner_id"][1] if q.get("partner_id") else "?"
        print(f"  -> {q['name']}  {partner}  untaxed={q.get('amount_untaxed')}  [{q.get('state')}]")
        for ln in q.get("_lines") or []:
            print(f"       line: {ln.get('product_uom_qty')} x {ln.get('price_unit')}  {ln.get('name','')[:40]}")
    if res.candidates and not res.quote:
        print("  Near candidates:")
        for q in res.candidates:
            partner = q["partner_id"][1] if q.get("partner_id") else "?"
            print(f"   - {q['name']:<14} {partner:<30} untaxed={q.get('amount_untaxed')} [{q.get('state')}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
