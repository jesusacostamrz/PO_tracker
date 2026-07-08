"""Turn RiskItems into INTERNAL Odoo alerts. dry_run default; idempotent per (task, kind, day).

In dry-run: nothing is posted to Odoo and the alert log is NOT marked (fully repeatable) —
the intended notifications are returned for logging. In live: posts an internal note on the
task notifying the resolved recipients (assignees + project manager + HIGH escalation), and
records the alert so it won't repeat the same day. NEVER notifies a customer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from uc.core.alerts import AlertLog, resolve_recipient_user_ids
from uc.core.models import Task
from uc.core.risk import RiskItem


@dataclass
class AlertOutcome:
    dry_run: bool
    lines: list[str] = field(default_factory=list)   # human-readable per-alert
    skipped: int = 0                                  # idempotency hits


def _body(task: Task, r: RiskItem) -> str:
    crit = "En ruta crítica. " if r.on_critical_path else ""
    return (
        f"Alerta de proyecto ({r.severity.upper()}) — {task.name}. "
        f"{r.message} {crit}"
        "Aviso interno automático de Unicontrol PM (no enviado al cliente)."
    )


def apply_alerts(odoo, cfg, tasks, risks, alert_log: AlertLog, today=None, dry_run=True) -> AlertOutcome:
    today = today or date.today()
    acfg = cfg.get("alerts", {})
    escalation = acfg.get("escalation_users", []) or []
    high_only = acfg.get("notify_high_only", False)

    by_id = {t.id: t for t in tasks}
    mgr_cache: dict[int, int | None] = {}
    out = AlertOutcome(dry_run=dry_run)

    for r in risks:
        if high_only and r.severity != "high":
            continue
        if alert_log.already_sent(r.task_id, r.kind, today):
            out.skipped += 1
            continue
        task = by_id.get(r.task_id)
        if task is None:
            continue

        pid = task.project_id
        if pid not in mgr_cache:
            mgr_cache[pid] = odoo.project_manager_id(pid) if pid else None
        recipients = resolve_recipient_user_ids(task.assignee_ids, mgr_cache[pid], escalation, r.severity)

        if dry_run:
            out.lines.append(
                f"[DRY] task {r.task_id} «{task.name}» {r.kind}/{r.severity} "
                f"-> users {recipients}: {r.message}"
            )
        else:
            partner_ids = odoo.partner_ids_for_users(recipients)
            odoo.notify_task(r.task_id, _body(task, r), partner_ids)
            alert_log.mark(r.task_id, r.kind, today)
            out.lines.append(
                f"[SENT] task {r.task_id} «{task.name}» {r.kind}/{r.severity} -> users {recipients}"
            )
    return out
