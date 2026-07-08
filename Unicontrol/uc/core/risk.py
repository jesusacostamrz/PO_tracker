"""At-risk detection over a project's tasks. Deterministic; no I/O.

Three rules, escalated when the task sits on the critical path:
  • overdue                     — planned end is in the past and the task isn't done
  • near_deadline_no_progress   — due within N days with progress below a floor
  • predecessor_slipped         — a critical task whose predecessor is overdue

The natural-language alert/email is drafted elsewhere (core.digest via the LLM); this
module only decides WHAT is at risk and how severe.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .critical_path import CPMResult, compute_cpm
from .models import Task

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class RiskItem:
    task_id: int
    task_name: str
    kind: str                 # overdue | near_deadline_no_progress | predecessor_slipped
    severity: str             # high | medium | low
    message: str              # human-readable (Spanish, salesperson-friendly)
    on_critical_path: bool


def _is_overdue(t: Task, today: date) -> bool:
    return (not t.done) and t.planned_end is not None and t.planned_end < today


def assess(
    tasks: list[Task],
    today: date | None = None,
    near_deadline_days: int = 3,
    min_progress: float = 10.0,
) -> tuple[CPMResult, list[RiskItem]]:
    today = today or date.today()
    cpm = compute_cpm(tasks)
    by_id = {t.id: t for t in tasks}
    risks: list[RiskItem] = []

    for t in tasks:
        crit = t.id in cpm.critical
        if _is_overdue(t, today):
            days = (today - t.planned_end).days
            risks.append(RiskItem(
                t.id, t.name, "overdue", "high" if crit else "medium",
                f"Atrasada {days} día(s): venció el {t.planned_end.isoformat()} y no está terminada.",
                crit,
            ))
            continue  # overdue supersedes near-deadline for the same task
        if (not t.done) and t.planned_end is not None:
            dleft = (t.planned_end - today).days
            if 0 <= dleft <= near_deadline_days and t.progress < min_progress:
                risks.append(RiskItem(
                    t.id, t.name, "near_deadline_no_progress", "high" if crit else "medium",
                    f"Vence en {dleft} día(s) ({t.planned_end.isoformat()}) con avance {t.progress:.0f}%.",
                    crit,
                ))

    for t in tasks:
        if t.id not in cpm.critical or t.done:
            continue
        for p in t.depends_on:
            pred = by_id.get(p)
            if pred and _is_overdue(pred, today):
                risks.append(RiskItem(
                    t.id, t.name, "predecessor_slipped", "high",
                    f"Su predecesora «{pred.name}» está atrasada y está en la ruta crítica.",
                    True,
                ))
                break

    risks.sort(key=lambda r: (_SEVERITY_ORDER[r.severity], r.task_id))
    return cpm, risks
