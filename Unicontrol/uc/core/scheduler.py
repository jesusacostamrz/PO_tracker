"""Forward-schedule a WBS (durations + Finish-to-Start deps) into working-day offsets,
and map working-day offsets to calendar dates (Mon–Fri). Used to date the Odoo template
tasks and to lay out the Gantt artifact.
"""
from __future__ import annotations

from collections import deque
from datetime import date, timedelta


def add_working_days(start: date, n: int) -> date:
    """Date `n` working days (Mon–Fri) after `start`. If `start` is a weekend it first
    rolls forward to Monday; n=0 then returns that working day."""
    d = start
    while d.weekday() >= 5:      # Sat=5, Sun=6
        d += timedelta(days=1)
    steps = n
    while steps > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            steps -= 1
    return d


def forward_schedule(items) -> dict:
    """items: iterable of (id, duration, preds). Returns {id: (es, ef)} as earliest
    start/finish offsets in working days. Raises ValueError on a dependency cycle."""
    items = list(items)
    ids = {i for i, _, _ in items}
    dur = {i: d for i, d, _ in items}
    preds = {i: [p for p in ps if p in ids] for i, _, ps in items}
    succ: dict = {i: [] for i, _, _ in items}
    for i, _, ps in items:
        for p in preds[i]:
            succ[p].append(i)

    indeg = {i: len(preds[i]) for i in ids}
    q = deque(sorted((i for i in ids if indeg[i] == 0), key=str))
    order: list = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(order) != len(ids):
        raise ValueError("Cycle detected in WBS dependencies")

    ES: dict = {}
    EF: dict = {}
    for n in order:
        ES[n] = max((EF[p] for p in preds[n]), default=0)
        EF[n] = ES[n] + dur[n]
    return {i: (ES[i], EF[i]) for i in ids}
