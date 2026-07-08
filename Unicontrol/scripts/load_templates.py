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
from uc.templates import TEMPLATES  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402


def _next_monday(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def _load_one(odoo, fmap, name, items, start):
    sched = forward_schedule([(w, dur, preds) for (w, _n, _e, dur, preds, _m) in items])
    pid = odoo.create_project(name)
    wbs2id: dict[str, int] = {}
    for (w, tname, _etapa, dur, _preds, mile) in items:
        es, ef = sched[w]
        begin = add_working_days(start, es)
        end = add_working_days(start, (ef - 1) if dur > 0 else es)
        vals = {
            "name": f"{'★ ' if mile else ''}{w}  {tname}",
            "project_id": pid,
            fmap["planned_start"]: f"{begin.isoformat()} 08:00:00",
            fmap["deadline"]: f"{end.isoformat()} 17:00:00",
        }
        wbs2id[w] = odoo.create_task(vals)
    # second pass: dependencies ("Blocked by")
    for (w, _n, _e, _d, preds, _m) in items:
        pred_ids = [wbs2id[p] for p in preds if p in wbs2id]
        if pred_ids:
            odoo.write_task(wbs2id[w], {fmap["depends_on"]: [(6, 0, pred_ids)]})
    return pid, len(wbs2id)


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
