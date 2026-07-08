# uc/core/internal_view.py
"""Turn a live Odoo project into the FULL internal plan: every phase, its child steps, and
milestones — each carrying schedule variance against the approved baseline.

INTERNAL USE ONLY. Unlike customer_view (which hides children), this exposes the whole WBS.
Pure logic — no Odoo, no HTML. Variance = current_end - baseline_end in calendar days, where
current_end is the actual end for done tasks, else the live planned end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from uc.core.baseline import Baseline
from uc.core.customer_view import (
    clean_name,
    clean_phase_name,
    is_milestone,
    weighted_progress,
)
from uc.core.models import Task
from uc.core.palette import PHASE_PALETTE


def current_end(t: Task) -> date | None:
    """Where the task actually ends now: its actual end if done, else the live planned end."""
    return t.actual_end if (t.done and t.actual_end) else t.planned_end


def _variance(cur: date | None, base_end: date | None) -> int | None:
    if cur is None or base_end is None:
        return None
    return (cur - base_end).days


@dataclass
class InternalRow:
    name: str
    kind: str                    # "phase" | "step" | "milestone"
    indent: int                  # 0 phase/milestone, 1 step
    start: date
    end: date
    progress: float
    color: str
    done: bool
    reached: bool = False        # milestone reached (done or actual end <= as_of)
    variance_days: int | None = None      # None => no baseline entry ("nuevo")
    baseline_end: date | None = None


@dataclass
class InternalPlan:
    project_name: str
    rows: list[InternalRow] = field(default_factory=list)
    date_min: date | None = None
    date_max: date | None = None
    as_of: date | None = None
    overall_progress: float = 0.0
    overall_variance_days: int | None = None
    approved_on: date | None = None


def build(tasks: list[Task], project_name: str, baseline: Baseline | None,
          as_of: date | None = None) -> InternalPlan:
    as_of = as_of or date.today()
    children: dict[int, list[Task]] = {}
    for t in tasks:
        if t.parent_id is not None:
            children.setdefault(t.parent_id, []).append(t)
    tops = [t for t in tasks if t.parent_id is None]

    def base_end(t: Task) -> date | None:
        return baseline.end_of(t.id) if baseline else None

    def has_base(t: Task) -> bool:
        return baseline.has(t.id) if baseline else False

    # --- assign palette colors to phases in timeline order (milestones get ACCENT later) ---
    phase_tasks = [t for t in tops if not is_milestone(t)]
    def phase_start(t: Task) -> date | None:
        kids = [c for c in children.get(t.id, []) if c.planned_start]
        return t.planned_start or (min(c.planned_start for c in kids) if kids else None)
    dated_phases = sorted((t for t in phase_tasks if phase_start(t)), key=phase_start)
    color_of = {t.id: PHASE_PALETTE[i % len(PHASE_PALETTE)] for i, t in enumerate(dated_phases)}

    # --- build a top-level sequence: phases (by start) + milestones (by day), then drop each
    #     phase's children in right after it ------------------------------------------------
    seq: list[tuple[date, int, Task]] = []
    for t in phase_tasks:
        s = phase_start(t)
        if s:
            seq.append((s, 0, t))
    for t in tops:
        if is_milestone(t):
            day = t.planned_end or t.planned_start
            if day:
                seq.append((day, 1, t))
    seq.sort(key=lambda it: (it[0], it[1]))

    rows: list[InternalRow] = []
    for _, _, t in seq:
        if is_milestone(t):
            day = current_end(t) or t.planned_end or t.planned_start
            reached = t.done or (t.actual_end is not None and t.actual_end <= as_of)
            rows.append(InternalRow(
                name=clean_name(t.name), kind="milestone", indent=0,
                start=day, end=day, progress=100.0 if reached else 0.0,
                color="", done=t.done, reached=reached,
                variance_days=_variance(day, base_end(t)) if has_base(t) else None,
                baseline_end=base_end(t),
            ))
            continue

        kids = children.get(t.id, [])
        members = kids or [t]
        dated = [x for x in members if x.planned_start and x.planned_end]
        start = t.planned_start or (min(x.planned_start for x in dated) if dated else None)
        p_end = t.planned_end or (max(x.planned_end for x in dated) if dated else None)
        if not (start and p_end):
            continue
        # phase current end = latest current end across members; baseline end = phase's own
        # baseline if present, else latest child baseline.
        member_cur_ends = [current_end(x) for x in members if current_end(x)]
        cur_end = max(member_cur_ends) if member_cur_ends else p_end
        phase_base = base_end(t)
        if phase_base is None:
            kid_bases = [base_end(k) for k in kids if base_end(k)]
            phase_base = max(kid_bases) if kid_bases else None
        rows.append(InternalRow(
            name=clean_phase_name(t.name), kind="phase", indent=0,
            start=start, end=p_end, progress=weighted_progress(members),
            color=color_of.get(t.id, PHASE_PALETTE[0]), done=all(x.done for x in members),
            variance_days=_variance(cur_end, phase_base), baseline_end=phase_base,
        ))
        # child steps, indented, in start order
        for c in sorted((k for k in kids if k.planned_start and k.planned_end),
                        key=lambda x: x.planned_start):
            c_cur = current_end(c)
            rows.append(InternalRow(
                name=clean_name(c.name), kind="step", indent=1,
                start=c.planned_start, end=c.planned_end,
                progress=100.0 if c.done else float(c.progress),
                color=color_of.get(t.id, PHASE_PALETTE[0]), done=c.done,
                variance_days=_variance(c_cur, base_end(c)) if has_base(c) else None,
                baseline_end=base_end(c),
            ))

    # --- overall metrics -----------------------------------------------------------------
    all_work = [x for t in phase_tasks for x in (children.get(t.id, []) or [t])]
    overall = weighted_progress(all_work) if all_work else 0.0
    work_cur = [current_end(x) for x in all_work if current_end(x)]
    work_base = [base_end(x) for x in all_work if base_end(x)]
    overall_var = (_variance(max(work_cur), max(work_base))
                   if work_cur and work_base else None)

    days = [r.start for r in rows] + [r.end for r in rows]
    date_min = min(days) if days else None
    date_max = max(days) if days else None
    return InternalPlan(project_name, rows, date_min, date_max, as_of, overall,
                        overall_var, baseline.approved_on if baseline else None)
