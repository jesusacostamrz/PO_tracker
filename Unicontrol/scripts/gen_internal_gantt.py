# scripts/gen_internal_gantt.py
"""Generate the INTERNAL full-project Gantt for ONE live Odoo project (READ-ONLY).

    python scripts/gen_internal_gantt.py --project-id 8 [--as-of YYYY-MM-DD] > internal.html

Shows the whole WBS — phases, their child steps, and milestones — each with schedule
variance against the approved baseline (baselines/project-<id>.json). USO INTERNO: this
exposes internal task detail and must never be shared with a customer. Save the baseline
first with scripts/save_baseline.py.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core import baseline as bl  # noqa: E402
from uc.core.config import add_hermes_to_path, load_config  # noqa: E402
from uc.core.internal_view import build  # noqa: E402
from uc.render.gantt_html import render_internal_page  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", type=int, required=True)
    ap.add_argument("--as-of", default=None, help="status date YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    cfg = load_config()
    odoo = ProjectOdooClient.from_config(cfg)
    proj = odoo.project_by_id(args.project_id)
    if not proj:
        print(f"ERROR: no project with id {args.project_id}", file=sys.stderr)
        return 2

    tasks = odoo.load_tasks([args.project_id], cfg["odoo_project"])
    if not tasks:
        print(f"ERROR: project [{args.project_id}] {proj['name']} has no tasks", file=sys.stderr)
        return 2

    baseline = bl.load(args.project_id)
    if baseline is None:
        print(f"ERROR: no baseline for project {args.project_id}. Run "
              f"scripts/save_baseline.py --project-id {args.project_id} first.", file=sys.stderr)
        return 6

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    plan = build(tasks, project_name=proj["name"], baseline=baseline, as_of=as_of)
    if not plan.rows:
        print(f"ERROR: project [{args.project_id}] {proj['name']} has no planned dates — "
              "add planned_date_begin / date_deadline first.", file=sys.stderr)
        return 3

    print(render_internal_page(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
