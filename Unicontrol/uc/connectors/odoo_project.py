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
