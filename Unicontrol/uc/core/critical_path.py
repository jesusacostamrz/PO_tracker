"""Critical Path Method over a task-dependency network (activity-on-node).

Odoo stores dependencies and planned dates but does NOT compute a critical path or
slack — this does. Durations come from each task's planned span (fallback 1 day).
Forward pass → earliest start/finish; backward pass → latest start/finish; slack =
latest−earliest; critical tasks have zero slack.

Simplification: uses planned *durations* chained by dependency, not the literal
calendar gaps between tasks. For a back-to-back internal plan (what Plan Builder
produces) the two agree; revisit if plans carry large idle gaps between etapas.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .models import Task


@dataclass
class CPMResult:
    slack: dict[int, int]       # task_id → slack in days
    critical: set[int]          # task_ids on the critical path (zero slack)
    project_length: int         # earliest finish of the whole network, in days
    order: list[int]            # topological order used


def _topo(tasks: list[Task]):
    ids = {t.id for t in tasks}
    preds = {t.id: [p for p in t.depends_on if p in ids] for t in tasks}
    succ: dict[int, list[int]] = {t.id: [] for t in tasks}
    for t in tasks:
        for p in preds[t.id]:
            succ[p].append(t.id)
    indeg = {tid: len(preds[tid]) for tid in ids}
    q = deque(sorted(tid for tid in ids if indeg[tid] == 0))
    order: list[int] = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(order) != len(ids):
        raise ValueError("Cycle detected in task dependencies")
    return order, preds, succ


def compute_cpm(tasks: list[Task]) -> CPMResult:
    if not tasks:
        return CPMResult({}, set(), 0, [])
    order, preds, succ = _topo(tasks)
    dur = {t.id: t.duration_days for t in tasks}

    ES: dict[int, int] = {}
    EF: dict[int, int] = {}
    for n in order:
        ES[n] = max((EF[p] for p in preds[n]), default=0)
        EF[n] = ES[n] + dur[n]
    project_length = max(EF.values())

    LF: dict[int, int] = {}
    LS: dict[int, int] = {}
    for n in reversed(order):
        LF[n] = min((LS[s] for s in succ[n]), default=project_length)
        LS[n] = LF[n] - dur[n]

    slack = {n: LS[n] - ES[n] for n in order}
    critical = {n for n in order if slack[n] == 0}
    return CPMResult(slack=slack, critical=critical, project_length=project_length, order=order)
