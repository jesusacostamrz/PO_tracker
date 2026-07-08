"""Delay Watch — internal delay early-warning. Reads Odoo projects, computes at-risk tasks,
and posts INTERNAL alerts (assignees + project manager + HIGH escalation). Never contacts clients.

DEFAULTS TO DRY-RUN (runtime.dry_run). Dry-run posts nothing and marks no state. --live posts.

    python scripts/delay_watch.py [--live]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_UC_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_UC_ROOT))

from uc.core.config import load_config, add_hermes_to_path  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402
from uc.core.risk import assess  # noqa: E402
from uc.core.alerts import load_alert_log, save_alert_log  # noqa: E402
from uc.core.actions import apply_alerts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="post alerts to Odoo (override dry_run)")
    args = ap.parse_args()

    cfg = load_config()
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    odoo = ProjectOdooClient.from_config(cfg)
    projs = odoo.active_projects()
    tasks = odoo.load_tasks([p["id"] for p in projs], cfg["odoo_project"])
    _, risks = assess(
        tasks,
        near_deadline_days=cfg["risk"]["near_deadline_days"],
        min_progress=cfg["risk"]["min_progress"],
    )

    state_dir = cfg.get("state", {}).get("dir", "./state")
    state_path = (_UC_ROOT / state_dir / "alerts_sent.json") if not Path(state_dir).is_absolute() \
        else Path(state_dir) / "alerts_sent.json"
    log = load_alert_log(state_path)

    out = apply_alerts(odoo, cfg, tasks, risks, log, dry_run=dry)
    if not dry:
        save_alert_log(state_path, log)

    print(f"Delay Watch [{'DRY-RUN' if dry else 'LIVE'}]: {len(projs)} project(s), "
          f"{len(tasks)} task(s), {len(risks)} risk(s), {out.skipped} already-alerted today")
    for line in out.lines:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
