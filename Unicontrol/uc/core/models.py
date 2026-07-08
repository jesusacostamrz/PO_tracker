"""Normalized project/task models, decoupled from Odoo's raw field names.

Odoo `project.task` field names vary by version, so raw rows are mapped to these
dataclasses through the config `odoo_project.fields` map (confirmed by
scripts/test_project.py). The rest of the codebase only ever sees `Task`/`Project`,
never a raw Odoo dict — so a field rename is a one-line config change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


def parse_date(v) -> date | None:
    """Odoo returns 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', or False. → date | None."""
    if not v:
        return None
    if isinstance(v, date):
        return v
    s = str(v).split(" ")[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _m2o_id(v):
    """Odoo many2one comes back as [id, label] (or False)."""
    if isinstance(v, (list, tuple)) and v:
        return v[0]
    return None


def _m2o_label(v) -> str:
    if isinstance(v, (list, tuple)) and len(v) > 1:
        return v[1]
    return ""


@dataclass
class Task:
    id: int
    name: str
    depends_on: list[int] = field(default_factory=list)
    planned_start: date | None = None
    planned_end: date | None = None
    actual_end: date | None = None
    done: bool = False
    progress: float = 0.0          # 0–100
    stage: str = ""
    assignee_ids: list[int] = field(default_factory=list)   # res.users ids (task leaders)
    project_id: int | None = None
    project_name: str = ""

    @property
    def duration_days(self) -> int:
        """Planned duration in days; falls back to 1 when dates are missing."""
        if self.planned_start and self.planned_end:
            return max(0, (self.planned_end - self.planned_start).days)
        return 1

    @classmethod
    def from_odoo(cls, row: dict, fmap: dict, done_states: list[str]) -> "Task":
        """Build a Task from a raw project.task row using the config field map.

        `done` = task in a done/closed ``state`` (Odoo 17: '1_done'/'1_canceled') OR it
        has an actual end date. Field NAMES are confirmed by Step 0 (scripts/test_project.py).
        """
        def g(key):
            f = fmap.get(key)
            return row.get(f) if f else None

        state = g("state") or ""
        actual_end = parse_date(g("actual_end"))
        depends = g("depends_on") or []
        assignees = g("assignees") or []
        return cls(
            id=row["id"],
            name=row.get("name", ""),
            depends_on=[d for d in depends if isinstance(d, int)],
            planned_start=parse_date(g("planned_start")),
            planned_end=parse_date(g("planned_end")) or parse_date(g("deadline")),
            actual_end=actual_end,
            done=(state in done_states) or actual_end is not None,
            progress=float(g("progress") or 0.0),
            stage=_m2o_label(g("stage")),
            assignee_ids=[a for a in assignees if isinstance(a, int)],
            project_id=_m2o_id(row.get("project_id")),
            project_name=_m2o_label(row.get("project_id")),
        )


@dataclass
class Project:
    id: int
    name: str
    tasks: list[Task] = field(default_factory=list)
