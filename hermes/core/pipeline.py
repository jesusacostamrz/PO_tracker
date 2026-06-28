"""Shared parse->match orchestration used by both the single-PO runner and the
Gmail intake batch.

Keeping the candidate-quote fetch here means a batch can pull the quote pool ONCE
and reuse it across many POs, and the two entry points (scripts/process_po.py and
scripts/intake.py) can never drift in how they pick/score candidates.
"""
from __future__ import annotations

from core.matcher import MatchResult, match_po, _cust_sim
from connectors.odoo_client import OdooClient

_CUST_MIN_SIM = 0.80  # customer must fuzzy-match at least this before a quote is a candidate


def candidate_quotes(odoo: OdooClient, cfg: dict) -> list[dict]:
    """The draft/sent quote pool to match against. Fetch once, reuse per PO in a batch."""
    m = cfg["matching"]
    return odoo.candidate_quotes(
        states=tuple(m["candidate_states"]),
        lookback_days=m["lookback_days"],
        limit=500,
    )


def match_po_to_quotes(odoo: OdooClient, cfg: dict, po: dict, quotes: list[dict]) -> MatchResult:
    """Filter the quote pool to this PO's customer, attach order lines, and match.

    ``quotes`` is mutated in place: each quote's ``_lines`` is (re)set for THIS po —
    candidates get their real lines, everything else gets ``[]`` — so reusing the same
    pool list across POs never leaks stale line data between them.
    """
    cust = po.get("customer_name") or ""
    ids = [
        q["id"]
        for q in quotes
        if q.get("partner_id") and _cust_sim(cust, q["partner_id"][1]) >= _CUST_MIN_SIM
    ]
    lines = odoo.order_lines_bulk(ids)
    for q in quotes:
        q["_lines"] = lines.get(q["id"], [])
    return match_po(po, quotes, cfg["matching"])
