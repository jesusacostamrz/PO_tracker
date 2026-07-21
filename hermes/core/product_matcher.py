"""Match RFQ line items to Odoo products. Pure logic — no I/O.

Signal order: exact (normalized) part-number == default_code beats everything;
then fuzzy description-vs-name. Ambiguity (top-2 too close) or a hit without a
sale price goes to the Pricing Queue — Hermes never guesses a product or quotes 0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

_CODE_JUNK = re.compile(r"[\s‐-―_./]+")  # spaces, unicode dashes, separators


def norm_code(s) -> str:
    if not s:
        return ""
    return _CODE_JUNK.sub("", str(s)).replace("-", "").upper()


@dataclass
class LineMatch:
    line: dict
    status: str            # "matched" | "queue"
    product: dict | None
    score: float
    reason: str


def _best_two(line: dict, products: list[dict]) -> list[tuple[float, dict]]:
    """Top-2 (score, product) by fuzzy similarity of code+description vs code+name."""
    want = f"{line.get('part_number') or ''} {line.get('description') or ''}".strip()
    scored = []
    for p in products:
        have = f"{p.get('default_code') or ''} {p.get('name') or ''}".strip()
        scored.append((fuzz.token_set_ratio(want.lower(), have.lower()), p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:2]


def _decide(product: dict, score: float, how: str) -> "LineMatch | None":
    """Matched only if the product is actually quotable (has a sale price)."""
    if (product.get("list_price") or 0) > 0:
        return ("matched", product, score, how)
    return ("queue", product, score, f"{how}, but product has no sale price")


def match_lines(lines: list[dict], products: list[dict], mcfg: dict) -> list[LineMatch]:
    threshold = mcfg.get("fuzzy_threshold", 88)
    margin = mcfg.get("ambiguity_margin", 3)
    by_code = {norm_code(p.get("default_code")): p for p in products if p.get("default_code")}

    out: list[LineMatch] = []
    for line in lines:
        code = norm_code(line.get("part_number"))
        if code and code in by_code:
            status, prod, score, why = _decide(by_code[code], 100.0, "exact part-number match")
            out.append(LineMatch(line, status, prod, score, why))
            continue

        top2 = _best_two(line, products)
        if not top2 or top2[0][0] < threshold:
            best = top2[0][1] if top2 and top2[0][0] >= 60 else None
            score = top2[0][0] if top2 else 0.0
            out.append(LineMatch(line, "queue", best, score, "no product above match threshold"))
            continue
        if len(top2) == 2 and (top2[0][0] - top2[1][0]) < margin:
            out.append(LineMatch(line, "queue", top2[0][1], top2[0][0],
                                 f"ambiguous: two products within {margin} pts"))
            continue
        status, prod, score, why = _decide(top2[0][1], top2[0][0],
                                           f"fuzzy match {top2[0][0]:.0f}")
        out.append(LineMatch(line, status, prod, score, why))
    return out
