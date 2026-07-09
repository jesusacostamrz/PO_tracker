# scripts/gantt.py
"""One launcher to render a Customer or Internal Gantt for ANY live Odoo project (READ-ONLY).

Interactive (no args) — lists your active projects and prompts:
    python scripts/gantt.py

Scriptable flags:
    python scripts/gantt.py --list
    python scripts/gantt.py --project-id 8 --view customer --open
    python scripts/gantt.py --project-id 8 --view internal --as-of 2026-09-15

Customer view = phases + milestones only (shareable). Internal view = full WBS + variance
vs. the approved baseline (USO INTERNO); if no baseline exists it offers to save one.
Output HTML is written under Unicontrol/out/ and (optionally) opened in your browser.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uc.core import baseline as bl  # noqa: E402
from uc.core.config import add_hermes_to_path, load_config  # noqa: E402
from uc.core.customer_view import build as build_customer, is_hierarchical  # noqa: E402
from uc.core.internal_view import build as build_internal  # noqa: E402
from uc.render.gantt_html import render_customer_page, render_internal_page  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402

OUT_DIR = ROOT / "out"
_VIEWS = {"c": "customer", "customer": "customer", "cliente": "customer",
          "i": "internal", "internal": "internal", "interno": "internal"}


def norm_view(s: str | None) -> str | None:
    """Map a user token (c/i/customer/interno/…) to 'customer'|'internal' or None."""
    return _VIEWS.get((s or "").strip().lower())


def out_path(view: str, pid: int) -> Path:
    return OUT_DIR / f"{view}_{pid}.html"


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(1)


def render_customer_html(odoo, cfg, pid, name, as_of) -> str:
    tasks = odoo.load_tasks([pid], cfg["odoo_project"])
    if not tasks:
        _fail(f"ERROR: [{pid}] {name} has no tasks.")
    if not is_hierarchical(tasks):
        _fail(f"ERROR: [{pid}] {name} is flat (no phase hierarchy) — customer view refused "
              "so internal task detail can't leak. Restructure into parent phases first.")
    plan = build_customer(tasks, project_name=name, as_of=as_of)
    if not plan.phases and not plan.milestones:
        _fail(f"ERROR: [{pid}] {name} has no planned dates.")
    return render_customer_page(plan)


def render_internal_html(odoo, cfg, pid, name, as_of, may_prompt) -> str:
    tasks = odoo.load_tasks([pid], cfg["odoo_project"])
    if not tasks:
        _fail(f"ERROR: [{pid}] {name} has no tasks.")
    baseline = bl.load(pid)
    if baseline is None:
        if may_prompt and _yes(f"  [{pid}] has no approved baseline. Save one now from the "
                               "current dates? (s/n): "):
            baseline = bl.snapshot(pid, name, tasks)
            print(f"  baseline saved -> {bl.save(baseline)}")
        else:
            _fail(f"ERROR: no baseline for [{pid}]. Run "
                  f"scripts/save_baseline.py --project-id {pid} first.")
    plan = build_internal(tasks, project_name=name, baseline=baseline, as_of=as_of)
    if not plan.rows:
        _fail(f"ERROR: [{pid}] {name} has no planned dates.")
    return render_internal_page(plan)


def _yes(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("s", "si", "sí", "y", "yes")


def _pick_project(projects: list[dict]) -> int:
    print("\nProyectos activos:")
    for p in projects:
        print(f"  [{p['id']:>3}]  {p['name']}")
    ids = {p["id"] for p in projects}
    while True:
        raw = input("> Elegir proyecto (id): ").strip()
        if raw.isdigit() and int(raw) in ids:
            return int(raw)
        print("  id inválido, intenta de nuevo.")


def _pick_view() -> str:
    while True:
        v = norm_view(input("> Vista (c=cliente / i=interno): "))
        if v:
            return v
        print("  escribe c o i.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a Customer or Internal Gantt.")
    ap.add_argument("--project-id", type=int)
    ap.add_argument("--view", help="customer|internal (or c|i)")
    ap.add_argument("--as-of", default=None, help="status date YYYY-MM-DD (default: today)")
    ap.add_argument("--out", default=None, help="output HTML path (default: out/<view>_<id>.html)")
    ap.add_argument("--open", dest="open_", action="store_true", help="open the HTML in a browser")
    ap.add_argument("--no-open", dest="open_", action="store_false")
    ap.add_argument("--list", action="store_true", help="list active projects and exit")
    ap.set_defaults(open_=None)
    args = ap.parse_args()

    cfg = load_config()
    odoo = ProjectOdooClient.from_config(cfg)
    projects = odoo.active_projects()
    by_id = {p["id"]: p["name"] for p in projects}

    if args.list:
        for p in projects:
            print(f"[{p['id']:>3}] {p['name']}")
        return 0

    interactive = args.project_id is None
    pid = args.project_id if args.project_id is not None else _pick_project(projects)
    if pid not in by_id:
        # allow ids that exist but are inactive/archived via a direct lookup
        proj = odoo.project_by_id(pid)
        if not proj:
            _fail(f"ERROR: no project with id {pid}.")
        by_id[pid] = proj["name"]
    name = by_id[pid]

    view = norm_view(args.view) or (_pick_view() if interactive else None)
    if not view:
        _fail("ERROR: --view must be customer|internal (or c|i).")

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()

    if view == "customer":
        html = render_customer_html(odoo, cfg, pid, name, as_of)
    else:
        html = render_internal_html(odoo, cfg, pid, name, as_of, may_prompt=interactive)

    dest = Path(args.out) if args.out else out_path(view, pid)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    print(f"  wrote {view} Gantt for [{pid}] {name} -> {dest}")

    do_open = args.open_ if args.open_ is not None else interactive
    if do_open:
        webbrowser.open(dest.resolve().as_uri())
        print("  opened in browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
