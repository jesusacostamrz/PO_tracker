# uc/core/customer_view.py
"""Turn a live Odoo project's task hierarchy into a customer-safe plan: phase bars
(top-level parent tasks) + milestones (top-level ★ tasks), with child-rolled-up progress.
Pure logic — no Odoo, no HTML. Children (internal steps) are never exposed."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from uc.core.models import Task
from uc.core.palette import PHASE_PALETTE

_WBS = re.compile(r"^(M\d+|\d+(?:\.\d+)*)\s+")


def is_milestone(task: Task) -> bool:
    return (task.name or "").lstrip().startswith("★")


def clean_name(name: str) -> str:
    s = (name or "").lstrip()
    if s.startswith("★"):
        s = s[1:].lstrip()
    m = _WBS.match(s)
    if m:
        s = s[m.end():]
    return s.strip()


def clean_phase_name(name: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", name or "").strip()


def weighted_progress(tasks: list[Task]) -> float:
    total = sum(max(t.duration_days, 1) for t in tasks)
    if not total:
        return 0.0
    acc = sum((100.0 if t.done else float(t.progress)) * max(t.duration_days, 1) for t in tasks)
    return round(acc / total, 1)


def is_hierarchical(tasks: list[Task]) -> bool:
    """True when the project has real phase/child structure (some task has a parent).

    Leak-safety depends on it: in a hierarchical project only top-level parents become
    customer-visible phase rows and children stay hidden. A FLAT project (no parent set)
    would turn every internal leaf into a top-level 'phase' and expose its name, so the
    customer CLI refuses one that isn't hierarchical.
    """
    return any(t.parent_id is not None for t in tasks)


@dataclass
class PhaseBar:
    name: str
    color: str
    start: date
    end: date
    progress: float
    done: bool


@dataclass
class MilestoneMark:
    name: str
    day: date
    reached: bool


@dataclass
class CustomerPlan:
    project_name: str
    phases: list[PhaseBar] = field(default_factory=list)
    milestones: list[MilestoneMark] = field(default_factory=list)
    date_min: date | None = None
    date_max: date | None = None
    as_of: date | None = None
    overall_progress: float = 0.0


def build(tasks: list[Task], project_name: str, as_of: date | None = None) -> CustomerPlan:
    as_of = as_of or date.today()
    children: dict[int, list[Task]] = {}
    for t in tasks:
        if t.parent_id is not None:
            children.setdefault(t.parent_id, []).append(t)
    tops = [t for t in tasks if t.parent_id is None]

    phases: list[PhaseBar] = []
    for t in tops:
        if is_milestone(t):
            continue
        members = children.get(t.id, []) or [t]
        dated = [x for x in members if x.planned_start and x.planned_end]
        start = t.planned_start or (min(x.planned_start for x in dated) if dated else None)
        end = t.planned_end or (max(x.planned_end for x in dated) if dated else None)
        if not (start and end):
            continue
        phases.append(PhaseBar(
            name=clean_phase_name(t.name), color="",  # color assigned after sort
            start=start, end=end,
            progress=weighted_progress(members),
            done=all(x.done for x in members),
        ))
    phases.sort(key=lambda p: p.start)
    for i, p in enumerate(phases):
        p.color = PHASE_PALETTE[i % len(PHASE_PALETTE)]

    # Milestones are expected to be TOP-LEVEL tasks (the loader never nests a ★ task).
    # A ★ task nested as a child would be treated as phase progress, not shown here.
    milestones: list[MilestoneMark] = []
    for t in tops:
        if not is_milestone(t):
            continue
        day = t.planned_end or t.planned_start
        if not day:
            continue
        reached = t.done or (t.actual_end is not None and t.actual_end <= as_of)
        milestones.append(MilestoneMark(clean_name(t.name), day, reached))
    milestones.sort(key=lambda m: m.day)

    all_work = [x for t in tops if not is_milestone(t) for x in (children.get(t.id, []) or [t])]
    overall = weighted_progress(all_work) if all_work else 0.0
    days = ([p.start for p in phases] + [p.end for p in phases]
            + [m.day for m in milestones])
    date_min = min(days) if days else None
    date_max = max(days) if days else None
    return CustomerPlan(project_name, phases, milestones, date_min, date_max, as_of, overall)
