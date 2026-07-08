"""STEP 0 — read-only Odoo Project schema probe (writes nothing).

Confirms the REAL project.task field names + the "done" signal on your Odoo instance so
the connector isn't built on guessed names. Run from the Unicontrol/ directory:

    python scripts/test_project.py

Requires: Unicontrol/.secrets/.env with ODOO_USERNAME + ODOO_API_KEY, and the bot user
granted Project access. Reuses hermes/connectors/odoo_client.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # Unicontrol/ (for `uc`)

from uc.core.config import load_config, add_hermes_to_path      # noqa: E402

add_hermes_to_path()
from connectors.odoo_client import OdooClient, OdooError        # noqa: E402

# Fields we care about, incl. candidate "done" signals (kanban_state / state / is_closed).
_WANT = [
    "name", "project_id", "active",
    "planned_date_begin", "planned_date_end", "date_start", "date_deadline", "date_end",
    "depend_on_ids", "stage_id", "user_ids", "milestone_id",
    "kanban_state", "state", "is_closed",
]


def main() -> int:
    cfg = load_config()
    try:
        odoo = OdooClient.from_config(cfg)
        print("Odoo server:", odoo.version().get("server_version"))
    except OdooError as exc:
        print(f"FAILED (connect): {exc}")
        return 1

    projs = odoo.search_read("project.project", [], ["id", "name"], limit=20)
    print(f"\n{len(projs)} project(s) visible to the bot:")
    for p in projs:
        print(f"  [{p['id']}] {p['name']}")

    # Full metadata (no attributes filter — that returned empty dicts last time).
    fields = odoo.execute("project.task", "fields_get", [])
    print("\nproject.task field check (presence + type):")
    for f in _WANT:
        if f not in fields:
            print(f"  MISSING  {f}")
            continue
        m = fields[f]
        extra = ""
        if m.get("relation"):
            extra += f"  -> {m['relation']}"
        if m.get("type") == "selection" and m.get("selection"):
            extra += f"  selection={m['selection']}"
        print(f"  OK       {f:20s} {str(m.get('type')):10s} {m.get('string', '')}{extra}")

    # Task stages: a folded stage is the "closed/done" column — a done signal if no state field.
    stages = odoo.search_read("project.task.type", [], ["id", "name", "fold"], limit=50)
    print("\nproject.task.type stages (fold=True means a done/closed column):")
    for s in stages:
        print(f"  [{s['id']}] {s['name']!r:30s} fold={s['fold']}")

    if projs:
        pid = projs[0]["id"]
        avail = [f for f in _WANT if f in fields]
        tasks = odoo.search_read("project.task", [["project_id", "=", pid]], avail, limit=10)
        print(f"\nSample tasks from project [{pid}] (fields: {', '.join(avail)}):")
        for t in tasks:
            print("  ", t)

    print("\nNext: I lock the confirmed field names + done-signal into "
          "config/unicontrol.config.yaml, then build the Delay Watch connector.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
