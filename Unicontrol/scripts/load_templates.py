"""Create the two PMI/PMP schedule templates as Odoo Projects (tasks + dependencies +
back-scheduled dates). WRITES to Odoo (authorized). Idempotent: skips a template whose
project name already exists.

    python scripts/load_templates.py [--start YYYY-MM-DD]

Default start = the next Monday. Duplicate the created project per real job and re-date it.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core.config import load_config, add_hermes_to_path  # noqa: E402
from uc.core.scheduler import add_working_days, forward_schedule  # noqa: E402
from uc.templates import PHASE_NAMES, TEMPLATES, phase_groups  # noqa: E402
from uc.core.palette import ETAPA_TAG_COLOR  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402


def _next_monday(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def _load_one(odoo, fmap, name, items, start):
    sched = forward_schedule([(w, dur, preds) for (w, _n, _e, dur, preds, _m) in items])
    pid = odoo.create_project(name)

    # tag ids per etapa (find-or-create once)
    tag_ids: dict[str, int] = {}

    def tag_for(etapa: str) -> list:
        if etapa not in tag_ids:
            tag_ids[etapa] = odoo.tag_id(etapa, ETAPA_TAG_COLOR.get(etapa, 0))
        return [(6, 0, [tag_ids[etapa]])]

    # 1) parent phase tasks
    groups = phase_groups(items, PHASE_NAMES.get(name, {}))
    parent_of: dict[str, int] = {}   # major -> parent task id
    parent_id_by_major: dict[str, int] = {}
    for g in groups:
        vals = {"name": g["name"], "project_id": pid, fmap["tag_ids"]: tag_for(g["etapa"])}
        parent_id_by_major[g["major"]] = odoo.create_task(vals)

    # 2) leaf + milestone tasks
    row = {w: (n, e, dur, preds, mile) for (w, n, e, dur, preds, mile) in items}
    wbs2id: dict[str, int] = {}
    for (w, tname, etapa, dur, _preds, mile) in items:
        es, ef = sched[w]
        begin = add_working_days(start, es)
        end = add_working_days(start, (ef - 1) if dur > 0 else es)
        vals = {
            "name": f"{'★ ' if mile else ''}{w}  {tname}",
            "project_id": pid,
            fmap["planned_start"]: f"{begin.isoformat()} 08:00:00",
            fmap["deadline"]: f"{end.isoformat()} 17:00:00",
            fmap["tag_ids"]: tag_for(etapa),
        }
        if not mile:
            vals[fmap["parent"]] = parent_id_by_major[w.split(".")[0]]
        wbs2id[w] = odoo.create_task(vals)

    # 3) leaf dependencies ("Blocked by")
    for (w, _n, _e, _d, preds, _m) in items:
        pred_ids = [wbs2id[p] for p in preds if p in wbs2id]
        if pred_ids:
            odoo.write_task(wbs2id[w], {fmap["depends_on"]: [(6, 0, pred_ids)]})

    # 4) roll up parent dates from children
    for g in groups:
        child_ids = [wbs2id[w] for w in g["leaves"]]
        begins = add_working_days(start, min(sched[w][0] for w in g["leaves"]))
        ends = add_working_days(start, max((sched[w][1] - 1) for w in g["leaves"]))
        odoo.write_task(parent_id_by_major[g["major"]], {
            fmap["planned_start"]: f"{begins.isoformat()} 08:00:00",
            fmap["deadline"]: f"{ends.isoformat()} 17:00:00",
        })
    return pid, len(wbs2id) + len(groups)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None, help="project start date YYYY-MM-DD (default: next Monday)")
    args = ap.parse_args()

    cfg = load_config()
    fmap = cfg["odoo_project"]["fields"]
    start = date.fromisoformat(args.start) if args.start else _next_monday(date.today())

    odoo = ProjectOdooClient.from_config(cfg)
    existing = {p["name"] for p in odoo.active_projects()}
    print(f"Start date: {start.isoformat()}")
    for name, items in TEMPLATES.items():
        if name in existing:
            print(f"  SKIP (exists): {name}")
            continue
        pid, n = _load_one(odoo, fmap, name, items, start)
        print(f"  CREATED [{pid}] {name} — {n} tasks")
    print("\nDone. Open Odoo → Project to review; duplicate per job and re-date as needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
