"""Generate a self-contained one-page Gantt artifact for the two PMI templates.
Offline (no Odoo): uses uc.templates + scheduler + critical_path. Prints HTML to stdout.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core.critical_path import compute_cpm
from uc.core.models import Task
from uc.core.palette import ETAPA_COLOR
from uc.core.scheduler import forward_schedule
from uc.render.gantt_html import Chart, Row, MONTHS, esc, render_chart, render_page
from uc.templates import MACHINING, INTEGRATION

_BASE = date(2000, 1, 1)


def _schedule(items):
    sched = forward_schedule([(w, dur, preds) for (w, _n, _e, dur, preds, _m) in items])
    tasks = [
        Task(id=w, name=n, depends_on=preds,
             planned_start=_BASE + timedelta(days=sched[w][0]),
             planned_end=_BASE + timedelta(days=sched[w][1]))
        for (w, n, _e, dur, preds, _m) in items
    ]
    cpm = compute_cpm(tasks)
    total = max((ef for _es, ef in sched.values()), default=1) or 1
    return sched, cpm.critical, total


def _chart(title, subtitle, items) -> Chart:
    sched, critical, total = _schedule(items)
    step = 100 * 5 / total  # week gridline spacing (%)
    rows = []
    for (w, name, etapa, dur, _preds, mile) in items:
        es, ef = sched[w]
        color = ETAPA_COLOR.get(etapa, "#8a99a8")
        crit = w in critical
        lead = name.strip().endswith("*")
        left = es / total * 100
        name_title = f"{etapa} · {name}"
        if mile:
            rows.append(Row(label=name, kind="milestone", left=left, color=color, wbs=w,
                             crit=crit, name_title=name_title, mark_title=f"Hito · {name}"))
        else:
            width = max(dur / total * 100, 0.9)
            mark_title = f"{name} — {dur} días hábiles" + (" · ruta crítica" if crit else "")
            rows.append(Row(label=name, kind="phase", left=left, width=width, color=color, wbs=w,
                             crit=crit, lead=lead,
                             dur_label=(f"{dur}d" if width > 6 else ""),
                             name_title=name_title, mark_title=mark_title))
    n_tasks = sum(1 for it in items if not it[5])
    n_ms = sum(1 for it in items if it[5])
    meta = (f"{n_tasks} tareas · {n_ms} hitos · ruta crítica "
            f"<b>{total} días hábiles</b> (~{round(total/5)} semanas)")
    return Chart(title=title, subtitle=subtitle, meta=meta, rows=rows, step=step, total=total)


def main() -> int:
    start = date(2026, 7, 13)
    start_lbl = f"lun {start.day} {MONTHS[start.month]} {start.year}"
    charts = (
        render_chart(_chart("Proyecto de Maquinado",
                    "Piezas / fixtures / herramentales a medida — línea base ~6 semanas.",
                    MACHINING))
        + render_chart(_chart("Integración de Sistemas",
                      "Celda de automatización a medida (transportador + robot + control) — línea base ~16 semanas.",
                      INTEGRATION))
    )
    etapa_legend = "".join(
        f'<span class="lg"><span class="dot" style="background:{c}"></span>{esc(k)}</span>'
        for k, c in ETAPA_COLOR.items() if k != "—"
    )
    header_html = f"""  <p class="eyebrow">Unicontrol · Plantillas de proyecto (PMI/PMP)</p>
  <h1>Cronogramas base de proyecto</h1>
  <p class="lede">Dos líneas base reutilizables para derivar el plan interno de cada trabajo:
    WBS, hitos, dependencias Fin-a-Inicio y ruta crítica. Los tiempos de proveedor (marcados <b>*</b>)
    se definen al cotizar. Cargadas en Odoo Project — duplica por trabajo y re-fecha.</p>
  <div class="stats">
    <div class="stat"><b>2</b><span>plantillas</span></div>
    <div class="stat"><b>29</b><span>tareas · maquinado</span></div>
    <div class="stat"><b>46</b><span>tareas · integración</span></div>
    <div class="stat"><b>34 / 109</b><span>días hábiles ruta crítica</span></div>
    <div class="stat"><b>{start_lbl}</b><span>inicio base</span></div>
  </div>
  <div class="legend">
    <div class="grp">
      <span class="lg"><span class="swatch-bar"></span>Tarea</span>
      <span class="lg"><span class="swatch-bar crit"></span>Ruta crítica</span>
      <span class="lg"><span class="swatch-lead"></span>Tiempo de proveedor *</span>
      <span class="lg"><span class="swatch-ms"></span>Hito</span>
    </div>
    <span class="sep"></span>
    <div class="grp">{etapa_legend}</div>
  </div>"""
    body_html = charts + """
  <footer>Generado desde <b>uc.templates</b> + el planificador con prueba unitaria · fechas
    programadas hacia adelante en días hábiles desde el inicio base · la ruta crítica se calcula con CPM.
    Detalle completo en <b>docs/schedule-templates.md</b>.</footer>"""
    print(render_page(header_html, body_html))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
