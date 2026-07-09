# uc/service/gantt_service.py
"""Shared orchestration: (Odoo project + view) -> self-contained Gantt HTML.

One code path used by BOTH the CLI launcher (scripts/gantt.py) and the web app
(scripts/gantt_web.py) so they can't drift. READ-ONLY on Odoo. Raises RenderError
(with a stable code) instead of exiting, so callers choose how to report failures.
"""
from __future__ import annotations

from datetime import date

from uc.core import baseline as bl
from uc.core.customer_view import build as build_customer, is_hierarchical
from uc.core.internal_view import build as build_internal
from uc.render.gantt_html import render_customer_page, render_internal_page

VIEWS = {"c": "customer", "customer": "customer", "cliente": "customer",
         "i": "internal", "internal": "internal", "interno": "internal"}


class RenderError(Exception):
    """A user-facing failure. `code` mirrors the CLI exit codes:
    2=no tasks, 3=no dates, 4=flat (leak-unsafe), 6=no baseline."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.message = message
        self.code = code


def norm_view(s: str | None) -> str | None:
    """Map a token (c/i/customer/interno/…) to 'customer'|'internal' or None."""
    return VIEWS.get((s or "").strip().lower())


def render(odoo, cfg, pid: int, name: str, view: str, as_of: date | None = None,
          save_baseline_if_missing: bool = False) -> str:
    """Render one project's Gantt to HTML. `view` must be 'customer' or 'internal'."""
    as_of = as_of or date.today()
    tasks = odoo.load_tasks([pid], cfg["odoo_project"])
    if not tasks:
        raise RenderError(f"[{pid}] {name} no tiene tareas.", code=2)

    if view == "customer":
        if not is_hierarchical(tasks):
            raise RenderError(
                f"[{pid}] {name} es plano (sin jerarquía de fases). La vista de cliente se "
                "rechaza para no filtrar detalle interno. Reestructura en fases padre primero.",
                code=4)
        plan = build_customer(tasks, project_name=name, as_of=as_of)
        if not plan.phases and not plan.milestones:
            raise RenderError(f"[{pid}] {name} no tiene fechas planeadas.", code=3)
        return render_customer_page(plan)

    if view == "internal":
        baseline = bl.load(pid)
        if baseline is None:
            if save_baseline_if_missing:
                baseline = bl.snapshot(pid, name, tasks)
                bl.save(baseline)
            else:
                raise RenderError(
                    f"[{pid}] {name} no tiene línea base aprobada. Guárdala primero.", code=6)
        plan = build_internal(tasks, project_name=name, baseline=baseline, as_of=as_of)
        if not plan.rows:
            raise RenderError(f"[{pid}] {name} no tiene fechas planeadas.", code=3)
        return render_internal_page(plan)

    raise RenderError(f"vista desconocida: {view!r} (usa customer|internal).", code=1)


def has_baseline(pid: int) -> bool:
    return bl.load(pid) is not None
