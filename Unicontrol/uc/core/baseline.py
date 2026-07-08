# uc/core/baseline.py
"""Freeze / read a project's APPROVED SCHEDULE as a local JSON snapshot.

Odoo has no native baseline field, so the internal Gantt compares live task dates against
a frozen copy taken when the plan was approved. One file per project —
``Unicontrol/baselines/project-<id>.json`` — keyed by Odoo task id (stable across
replanning). Pure file I/O: no Odoo, no HTML.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from uc.core.models import Task

BASELINE_DIR = Path(__file__).resolve().parents[2] / "baselines"


@dataclass
class Baseline:
    project_id: int
    project_name: str
    approved_on: date | None
    tasks: dict[int, tuple[date | None, date | None]]  # task_id -> (start, end)

    def end_of(self, task_id: int) -> date | None:
        entry = self.tasks.get(task_id)
        return entry[1] if entry else None

    def has(self, task_id: int) -> bool:
        return task_id in self.tasks


def baseline_path(project_id: int, base_dir: Path | None = None) -> Path:
    return (base_dir or BASELINE_DIR) / f"project-{project_id}.json"


def _d(v) -> date | None:
    return date.fromisoformat(v) if v else None


def snapshot(project_id: int, project_name: str, tasks: list[Task],
             approved_on: date | None = None) -> Baseline:
    """Build a Baseline from the CURRENT dates of live tasks (does not write anything)."""
    approved_on = approved_on or date.today()
    entries = {t.id: (t.planned_start, t.planned_end) for t in tasks}
    return Baseline(project_id, project_name, approved_on, entries)


def save(baseline: Baseline, base_dir: Path | None = None) -> Path:
    path = baseline_path(baseline.project_id, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": baseline.project_id,
        "project_name": baseline.project_name,
        "approved_on": baseline.approved_on.isoformat() if baseline.approved_on else None,
        "tasks": {
            str(tid): {"start": s.isoformat() if s else None,
                       "end": e.isoformat() if e else None}
            for tid, (s, e) in baseline.tasks.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load(project_id: int, base_dir: Path | None = None) -> Baseline | None:
    path = baseline_path(project_id, base_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = {int(tid): (_d(v.get("start")), _d(v.get("end")))
             for tid, v in data.get("tasks", {}).items()}
    return Baseline(int(data["project_id"]), data.get("project_name", ""),
                    _d(data.get("approved_on")), tasks)
