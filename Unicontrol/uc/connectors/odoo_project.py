"""Odoo Project extension of the Hermes OdooClient.

Read path for Delay Watch (reads project.project / project.task and normalizes tasks to
uc.core.models.Task). Field names come from config `odoo_project.fields` (confirmed by
scripts/test_project.py), never hardcoded — so a version rename is a config change.

Only fields that actually exist on the model are requested (some, e.g. `progress`, may be
absent on a plain project.task), so search_read never errors on an unknown field.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling hermes package importable when this module is used as a library.
_HERMES = Path(__file__).resolve().parents[2].parent / "hermes"
if _HERMES.exists() and str(_HERMES) not in sys.path:
    sys.path.insert(0, str(_HERMES))

from connectors.odoo_client import OdooClient  # noqa: E402

from uc.core.models import Task  # noqa: E402


class ProjectOdooClient(OdooClient):
    """OdooClient + project.task reads. Inherits from_config (auth) unchanged."""

    def existing_fields(self, model: str) -> set[str]:
        return set(self.execute(model, "fields_get", []).keys())

    def active_projects(self, limit: int = 100) -> list[dict]:
        return self.search_read(
            "project.project", [["active", "=", True]], ["id", "name"], limit=limit, order="name"
        )

    def load_tasks(self, project_ids: list[int], oproj_cfg: dict) -> list[Task]:
        """Read active tasks for the given projects and map them to Task objects."""
        if not project_ids:
            return []
        fmap = oproj_cfg["fields"]
        done_states = oproj_cfg.get("done_states", [])
        wanted = {"id", "name", "project_id", *fmap.values()}
        existing = self.existing_fields("project.task")
        req = sorted(f for f in wanted if f in existing)
        rows = self.search_read(
            "project.task",
            [["project_id", "in", list(project_ids)], ["active", "=", True]],
            req, order="id",
        )
        return [Task.from_odoo(r, fmap, done_states) for r in rows]

    # ---- recipients ----
    def project_manager_id(self, project_id: int) -> int | None:
        """The project's Manager (project.user_id) — the task lead's superior."""
        rec = self.execute("project.project", "read", [project_id], ["user_id"])
        uid = rec[0].get("user_id") if rec else None
        return uid[0] if isinstance(uid, (list, tuple)) and uid else None

    def partner_ids_for_users(self, user_ids: list[int]) -> list[int]:
        """Map res.users ids → their partner ids (needed to notify via message_post)."""
        if not user_ids:
            return []
        rows = self.search_read("res.users", [["id", "in", list(user_ids)]], ["partner_id"])
        out = []
        for r in rows:
            pid = r.get("partner_id")
            if isinstance(pid, (list, tuple)) and pid:
                out.append(pid[0])
        return out

    # ---- write path (narrow, reversible) ----
    def write_task(self, task_id: int, vals: dict) -> bool:
        """Write vals onto one project.task. Mirrors OdooClient.set_client_order_ref."""
        return self.execute("project.task", "write", [task_id], vals)

    def create_project(self, name: str) -> int:
        return self.execute("project.project", "create", {"name": name})

    def create_task(self, vals: dict) -> int:
        return self.execute("project.task", "create", vals)

    def notify_task(self, task_id: int, body: str, partner_ids: list[int]) -> int:
        """Post an internal note on the task and notify the given partners (Odoo emails them).

        INTERNAL ONLY — partner_ids are Unicontrol users, never customers.
        """
        return self.execute(
            "project.task", "message_post", [task_id],
            body=body, partner_ids=list(partner_ids),
            message_type="comment", subtype_xmlid="mail.mt_comment",
        )
