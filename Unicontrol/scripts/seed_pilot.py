"""One-off DEMO seeder: give the pilot project realistic dates + dependencies so the
Delay Watch engine has something to schedule and flag.

WRITES to Odoo (authorized): sets planned_date_begin / date_deadline / state / depend_on_ids
on the pilot's tasks. The tasks started with empty dates and no dependencies, so this is
reversible (clear those fields to undo). Run from Unicontrol/:  python scripts/seed_pilot.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core.config import load_config, add_hermes_to_path  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402

# Scenario (today ~2026-07-07): task 1 done; task 2 overdue on the critical path;
# tasks 3 & 4 planned into the future and blocked by their predecessor.
_PLAN = [
    ("planificar idea",                 "2026-06-16 08:00:00", "2026-06-20 17:00:00", "1_done", None),
    ("generar plan de implementacion",  "2026-06-22 08:00:00", "2026-06-30 17:00:00", None,     "planificar idea"),
    ("generar agente hermes",           "2026-07-01 08:00:00", "2026-07-20 17:00:00", None,     "generar plan de implementacion"),
    ("generar codigo pyton",            "2026-07-11 08:00:00", "2026-07-25 17:00:00", None,     "generar agente hermes"),
]


def main() -> int:
    cfg = load_config()
    f = cfg["odoo_project"]["fields"]
    odoo = ProjectOdooClient.from_config(cfg)

    proj = next((p for p in odoo.active_projects() if p["name"].strip().lower() == "piloto"), None)
    if not proj:
        print("No project named 'piloto' found.")
        return 1
    rows = odoo.search_read("project.task", [["project_id", "=", proj["id"]]], ["id", "name"], order="id")
    name2id = {r["name"].strip(): r["id"] for r in rows}

    for name, start, end, state, blocked_by in _PLAN:
        tid = name2id.get(name)
        if not tid:
            print(f"  SKIP (not found): {name!r}")
            continue
        vals = {f["planned_start"]: start, f["planned_end"]: end}
        if state:
            vals[f["state"]] = state
        if blocked_by and name2id.get(blocked_by):
            vals[f["depends_on"]] = [(6, 0, [name2id[blocked_by]])]
        odoo.write_task(tid, vals)
        print(f"  updated [{tid}] {name!r}: {start[:10]}..{end[:10]} "
              f"state={state or '(unchanged)'} blocked_by={blocked_by or '-'}")
    print("\nDone. Now run: python scripts/verify_reads.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
