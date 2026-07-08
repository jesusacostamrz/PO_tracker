"""READ-ONLY end-to-end check: Odoo project.task -> uc.core.models.Task -> CPM + risk.

Writes NOTHING to Odoo. Proves the connector + field-map + engine work against real data.
Run from Unicontrol/ (with the venv):  python scripts/verify_reads.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core.config import load_config, add_hermes_to_path  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402
from uc.core.risk import assess  # noqa: E402


def main() -> int:
    cfg = load_config()
    odoo = ProjectOdooClient.from_config(cfg)
    print("Odoo:", odoo.version().get("server_version"))

    projs = odoo.active_projects()
    print(f"\nActive projects: {[(p['id'], p['name']) for p in projs]}")
    ids = [p["id"] for p in projs]

    tasks = odoo.load_tasks(ids, cfg["odoo_project"])
    print(f"\nLoaded {len(tasks)} task(s):")
    for t in tasks:
        print(f"  [{t.id}] {t.name!r} start={t.planned_start} end={t.planned_end} "
              f"deps={t.depends_on} done={t.done} stage={t.stage!r}")

    cpm, risks = assess(
        tasks,
        near_deadline_days=cfg["risk"]["near_deadline_days"],
        min_progress=cfg["risk"]["min_progress"],
    )
    print(f"\nCritical-path task ids: {sorted(cpm.critical)}  project_length={cpm.project_length}d")
    print(f"At-risk items: {len(risks)}")
    for r in risks:
        print(f"  {r.severity.upper():6s} [{r.task_id}] {r.task_name} — {r.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
