"""Match a parsed PO to an Odoo quotation.

Signals, strongest first:
  1. The customer cites OUR quotation number on the PO -> near-certain.
  2. Line-item UNIT PRICES match a quote's lines        -> strong & quantity-independent
     (customers often order more/fewer units than quoted, so totals drift but the
      per-unit price stays put).
  3. Untaxed totals agree within amount_tolerance_pct   -> corroboration only.
Customer name must fuzzy-match. If nothing is clearly unique -> needs_review.

Quotes may carry pre-fetched lines on q['_lines'] (sale.order.line dicts with
'price_unit'); without them the line signal is treated as absent.
"""
from __future__ import annotations

from dataclasses import dataclass

import re
import unicodedata

from rapidfuzz import fuzz

_CUST_MIN = 0.80          # min customer-name similarity to consider a quote
_PRICE_TOL = 0.01         # 1% tolerance comparing unit prices
_AMBIGUOUS_MARGIN = 0.05  # if top two scores are this close -> ambiguous


@dataclass
class MatchResult:
    status: str               # 'matched' | 'needs_review'
    confidence: float
    reason: str
    quote: dict | None = None
    candidates: list | None = None


# Legal-form / filler tokens that differ between a PO letterhead and the Odoo
# partner name ("Volex de México, S.A. de C.V." vs "VOLEX DE MEXICO").
_NAME_NOISE = {"sa", "cv", "sapi", "srl", "rl", "s", "a", "c", "v", "de", "del", "la",
               "inc", "corp", "corporation", "co", "ltd", "llc", "sc", "cia"}


def _norm_name(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    toks = re.sub(r"[^a-z0-9 ]+", " ", plain.lower()).split()
    return " ".join(t for t in toks if t not in _NAME_NOISE) or plain.lower()


def _cust_sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(_norm_name(a), _norm_name(b)) / 100.0


def _price_overlap(po_items, quote_lines) -> float:
    po_prices = [li.get("unit_price") for li in (po_items or []) if li.get("unit_price")]
    q_prices = [ln.get("price_unit") for ln in (quote_lines or []) if ln.get("price_unit")]
    if not po_prices or not q_prices:
        return 0.0
    hits = sum(1 for p in po_prices
               if any(abs(p - qp) <= max(p, qp) * _PRICE_TOL for qp in q_prices))
    return hits / len(po_prices)


def _amount_close(po_amount, q_amount) -> tuple[float, float]:
    if not po_amount or not q_amount:
        return 0.0, 100.0
    diff_pct = abs(po_amount - q_amount) / max(q_amount, 1e-9) * 100.0
    return max(0.0, 1.0 - min(diff_pct / 10.0, 1.0)), diff_pct


def _split_gap(po_amount, q_amount, matching: dict) -> float:
    """% by which the PO total falls BELOW the quote total when that exceeds
    matching.split_gap_pct (default 50), else 0. A PO covering a fraction of a quote is
    probably one of several POs split from it -> human review (rule 2026-10-07)."""
    limit = float(matching.get("split_gap_pct", 50))
    if not po_amount or not q_amount or po_amount >= q_amount:
        return 0.0
    gap = (q_amount - po_amount) / q_amount * 100.0
    return gap if gap > limit else 0.0


def _split_review(q: dict, gap: float) -> MatchResult:
    return MatchResult("needs_review", 0.60,
        f"PO total is {gap:.1f}% below quote {q['name']} — likely a split/partial PO, needs a human.",
        quote=q, candidates=[q])


def match_po(po: dict, quotes: list[dict], matching: dict) -> MatchResult:
    tol = float(matching.get("amount_tolerance_pct", 0.5))
    threshold = float(matching.get("confidence_threshold", 0.85))
    customer = po.get("customer_name") or ""
    amount = po.get("subtotal")
    ref = (po.get("supplier_quote_ref") or "").strip().lower()

    cands = [(q, _cust_sim(customer, q["partner_id"][1] if q.get("partner_id") else ""))
             for q in quotes]
    cands = [(q, c) for q, c in cands if c >= _CUST_MIN]

    # 1) explicit quote-ref match wins outright
    if ref:
        for q, _ in cands:
            if (q.get("name") or "").strip().lower() == ref:
                gap = _split_gap(amount, q.get("amount_untaxed"), matching)
                if gap:
                    return _split_review(q, gap)
                return MatchResult("matched", 0.97, f"PO cites our quote {q['name']} directly.", quote=q)

    if not cands:
        return MatchResult("needs_review", 0.0, f"No quotation found for customer '{customer}'.")

    # 2/3) score by line-price overlap (+ amount corroboration)
    scored = []
    for q, cust in cands:
        overlap = _price_overlap(po.get("line_items"), q.get("_lines"))
        amt_close, diff_pct = _amount_close(amount, q.get("amount_untaxed"))
        score = round(0.45 * cust + 0.45 * overlap + 0.10 * amt_close, 3)
        scored.append((q, cust, overlap, diff_pct, score))
    scored.sort(key=lambda t: t[4], reverse=True)

    q, cust, overlap, diff_pct, score = scored[0]
    runner = scored[1] if len(scored) > 1 else None

    # require an identifying signal beyond customer+amount
    if overlap == 0.0 and diff_pct > tol:
        return MatchResult("needs_review", score,
            f"No line-price match and total off by {diff_pct:.2f}% (> {tol}%). Best guess {q['name']}.",
            quote=q, candidates=[t[0] for t in scored[:5]])

    if runner and (scored[0][4] - runner[4]) < _AMBIGUOUS_MARGIN:
        return MatchResult("needs_review", min(score, 0.60),
            f"Two quotes score nearly the same ({q['name']} vs {runner[0]['name']}) — ambiguous, needs a human.",
            quote=q, candidates=[t[0] for t in scored[:5]])

    gap = _split_gap(amount, q.get("amount_untaxed"), matching)
    if gap:
        return _split_review(q, gap)

    if score >= threshold:
        return MatchResult("matched", score,
            f"Matched {q['name']} (line prices {overlap:.0%} match, total off {diff_pct:.2f}%).", quote=q)

    return MatchResult("needs_review", score,
        f"Best candidate {q['name']} (score {score} < {threshold}).",
        quote=q, candidates=[t[0] for t in scored[:5]])
