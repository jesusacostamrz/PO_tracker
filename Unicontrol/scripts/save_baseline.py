# scripts/save_baseline.py
"""Freeze a live Odoo project's CURRENT schedule as its approved baseline (READ-ONLY on Odoo).

    python scripts/save_baseline.py --project-id 8 [--as-of YYYY-MM-DD] [--force]

Writes Unicontrol/baselines/project-<id>.json. Re-run only when a plan is formally
re-approved; it refuses to overwrite an existing baseline unless --force is given.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core import baseline as bl  # noqa: E402
from uc.core.config import add_hermes_to_path, load_config  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", type=int, required=True)
    ap.add_argument("--as-of", default=None, help="approval date YYYY-MM-DD (default: today)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing baseline")
    args = ap.parse_args()

    if bl.baseline_path(args.project_id).exists() and not args.force:
        print(f"ERROR: baseline for project {args.project_id} already exists at "
              f"{bl.baseline_path(args.project_id)}. Re-baselining discards the approved "
              "plan — pass --force if that is intended.", file=sys.stderr)
        return 5

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

    approved_on = date.fromisoformat(args.as_of) if args.as_of else date.today()
    snap = bl.snapshot(args.project_id, proj["name"], tasks, approved_on=approved_on)
    path = bl.save(snap)
    dated = sum(1 for s, e in snap.tasks.values() if s and e)
    print(f"Saved baseline for [{args.project_id}] {proj['name']} → {path}")
    print(f"  {len(snap.tasks)} tasks ({dated} dated), approved_on {approved_on.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
