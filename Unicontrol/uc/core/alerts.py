"""Alert recipient resolution + per-day idempotency. Deterministic; no Odoo I/O.

Recipients (INTERNAL ONLY — never clients): a task's assignees + the project Manager,
always; plus a configured escalation list when severity is HIGH.

Idempotency: an alert is identified by (day, task_id, kind) so re-running Delay Watch the
same day never re-notifies people for the same problem.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def resolve_recipient_user_ids(
    assignee_ids, project_manager_id, escalation_ids, severity: str
) -> list[int]:
    """Internal recipients for one risk item. Assignees + manager always; escalation on HIGH."""
    ids: set[int] = set(assignee_ids or [])
    if project_manager_id:
        ids.add(project_manager_id)
    if severity == "high":
        ids.update(escalation_ids or [])
    return sorted(ids)


def alert_key(task_id: int, kind: str, day: date) -> str:
    return f"{day.isoformat()}|{task_id}|{kind}"


class AlertLog:
    def __init__(self, sent=None):
        self.sent: set[str] = set(sent or [])

    def already_sent(self, task_id: int, kind: str, day: date) -> bool:
        return alert_key(task_id, kind, day) in self.sent

    def mark(self, task_id: int, kind: str, day: date) -> None:
        self.sent.add(alert_key(task_id, kind, day))


def load_alert_log(path: str | Path) -> AlertLog:
    p = Path(path)
    if not p.exists():
        return AlertLog()
    data = json.loads(p.read_text(encoding="utf-8"))
    return AlertLog(data.get("sent", []))


def save_alert_log(path: str | Path, log: AlertLog) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"sent": sorted(log.sent)}, indent=2), encoding="utf-8")
