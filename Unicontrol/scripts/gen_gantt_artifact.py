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
from uc.core.scheduler import forward_schedule
from uc.templates import MACHINING, INTEGRATION

ETAPA_COLOR = {
    "Diseño": "#3f7cac",
    "Revisión de Diseño": "#6c8f3f",
    "Compras": "#c07a1e",
    "Maquinado": "#7a6cae",
    "Ensamble": "#2f938a",
    "Entrega": "#b5495b",
    "—": "#8a99a8",
}
_MONTHS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_BASE = date(2000, 1, 1)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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


def _rows_html(items, sched, critical, total):
    out = []
    for (w, name, etapa, dur, _preds, mile) in items:
        es, ef = sched[w]
        color = ETAPA_COLOR.get(etapa, "#8a99a8")
        crit = w in critical
        lead = name.strip().endswith("*")
        left = es / total * 100
        label = (f'<span class="dot" style="background:{color}"></span>'
                 f'<span class="wbs">{_esc(w)}</span>'
                 f'<span class="tname" title="{_esc(etapa)} · {_esc(name)}">{_esc(name)}</span>')
        if mile:
            mark = (f'<span class="ms{" crit" if crit else ""}" style="left:{left:.3f}%" '
                    f'title="Hito · {_esc(name)}"></span>')
            track = f'<div class="track">{mark}</div>'
        else:
            width = max(dur / total * 100, 0.9)
            cls = "bar" + (" crit" if crit else "") + (" lead" if lead else "")
            dur_lbl = f'<span class="durlbl">{dur}d</span>' if width > 6 else ""
            bar = (f'<div class="{cls}" style="left:{left:.3f}%;width:{width:.3f}%;--c:{color}" '
                   f'title="{_esc(name)} — {dur} días hábiles{" · ruta crítica" if crit else ""}">'
                   f'{dur_lbl}</div>')
            track = f'<div class="track">{bar}</div>'
        out.append(f'<div class="row"><div class="rlabel">{label}</div>{track}</div>')
    return "\n".join(out)


def _chart_html(title, subtitle, items):
    sched, critical, total = _schedule(items)
    step = 100 * 5 / total  # week gridline spacing (%)
    n_tasks = sum(1 for it in items if not it[5])
    n_ms = sum(1 for it in items if it[5])
    meta = (f"{n_tasks} tareas · {n_ms} hitos · ruta crítica "
            f"<b>{total} días hábiles</b> (~{round(total/5)} semanas)")
    return f"""
    <section class="chart">
      <div class="chart-head">
        <h2>{_esc(title)}</h2>
        <p class="sub">{_esc(subtitle)}</p>
        <p class="meta">{meta}</p>
      </div>
      <div class="gantt-scroll">
        <div class="gantt" style="--total:{total};--step:{step:.4f}%">
          {_rows_html(items, sched, critical, total)}
        </div>
      </div>
    </section>"""


def main() -> int:
    start = date(2026, 7, 13)
    start_lbl = f"lun {start.day} {_MONTHS[start.month]} {start.year}"
    charts = (
        _chart_html("Proyecto de Maquinado",
                    "Piezas / fixtures / herramentales a medida — línea base ~6 semanas.",
                    MACHINING)
        + _chart_html("Integración de Sistemas",
                      "Celda de automatización a medida (transportador + robot + control) — línea base ~16 semanas.",
                      INTEGRATION)
    )
    etapa_legend = "".join(
        f'<span class="lg"><span class="dot" style="background:{c}"></span>{_esc(k)}</span>'
        for k, c in ETAPA_COLOR.items() if k != "—"
    )
    print(f"""<title>Plantillas de Cronograma PMI — Unicontrol</title>
<style>
:root {{
  --paper:#eef1f4; --panel:#ffffff; --ink:#161b22; --muted:#5b6b7c; --line:#d7dde3;
  --grid:#e4e9ee; --accent:#d97b12; --bar:#5b7f9c; --shadow:0 1px 2px rgba(20,30,45,.06);
  --sans: system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono: ui-monospace,"Cascadia Code","SFMono-Regular",Consolas,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --paper:#0e1218; --panel:#161d26; --ink:#e6ecf2; --muted:#8a99a8; --line:#232c37;
    --grid:#1b232d; --bar:#6f93b0; --shadow:0 1px 2px rgba(0,0,0,.3); }}
}}
:root[data-theme="dark"] {{ --paper:#0e1218; --panel:#161d26; --ink:#e6ecf2; --muted:#8a99a8;
  --line:#232c37; --grid:#1b232d; --bar:#6f93b0; --shadow:0 1px 2px rgba(0,0,0,.3); }}
:root[data-theme="light"] {{ --paper:#eef1f4; --panel:#ffffff; --ink:#161b22; --muted:#5b6b7c;
  --line:#d7dde3; --grid:#e4e9ee; --bar:#5b7f9c; --shadow:0 1px 2px rgba(20,30,45,.06); }}
* {{ box-sizing:border-box; }}
body {{ margin:0; }}
.wrap {{ max-width:1120px; margin:0 auto; padding:40px 24px 64px; background:var(--paper);
  color:var(--ink); font-family:var(--sans); line-height:1.5; }}
.eyebrow {{ font-family:var(--mono); font-size:12px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--accent); margin:0 0 6px; }}
h1 {{ font-size:clamp(26px,4vw,38px); margin:0 0 8px; letter-spacing:-.02em; text-wrap:balance; }}
.lede {{ color:var(--muted); max-width:64ch; margin:0 0 22px; }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 26px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 14px;
  box-shadow:var(--shadow); }}
.stat b {{ font-family:var(--mono); font-size:19px; display:block; }}
.stat span {{ color:var(--muted); font-size:12.5px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px 20px; align-items:center; padding:14px 16px;
  background:var(--panel); border:1px solid var(--line); border-radius:10px; margin:0 0 30px;
  font-size:12.5px; box-shadow:var(--shadow); }}
.legend .grp {{ display:flex; flex-wrap:wrap; gap:12px; align-items:center; }}
.lg {{ display:inline-flex; align-items:center; gap:6px; color:var(--muted); white-space:nowrap; }}
.dot {{ width:11px; height:11px; border-radius:3px; display:inline-block; flex:none; }}
.swatch-bar {{ width:26px; height:11px; border-radius:3px; background:var(--bar); display:inline-block; }}
.swatch-bar.crit {{ background:transparent; box-shadow:inset 0 0 0 2px var(--accent); }}
.swatch-lead {{ width:26px; height:11px; border-radius:3px; display:inline-block; background:var(--bar);
  background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.28) 0 3px,transparent 3px 6px); }}
.swatch-ms {{ width:11px; height:11px; background:var(--ink); transform:rotate(45deg); display:inline-block; }}
.sep {{ width:1px; height:16px; background:var(--line); }}
.chart {{ margin:0 0 34px; }}
.chart-head h2 {{ font-size:20px; margin:0 0 2px; letter-spacing:-.01em; }}
.chart-head .sub {{ color:var(--muted); margin:0 0 3px; font-size:13.5px; }}
.chart-head .meta {{ font-family:var(--mono); font-size:12.5px; color:var(--muted); margin:0 0 12px; }}
.chart-head .meta b {{ color:var(--accent); }}
.gantt-scroll {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel);
  box-shadow:var(--shadow); }}
.gantt {{ min-width:760px; }}
.row {{ display:grid; grid-template-columns:320px 1fr; align-items:center; border-top:1px solid var(--line);
  min-height:30px; }}
.row:first-child {{ border-top:none; }}
.rlabel {{ display:flex; align-items:center; gap:8px; padding:5px 12px; min-width:0; }}
.rlabel .wbs {{ font-family:var(--mono); font-size:11.5px; color:var(--muted); flex:none; min-width:34px; }}
.rlabel .tname {{ font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.track {{ position:relative; height:30px; border-left:1px solid var(--line);
  background:repeating-linear-gradient(to right, var(--grid) 0 1px, transparent 1px var(--step)); }}
.bar {{ position:absolute; top:7px; height:16px; border-radius:4px; background:var(--c);
  display:flex; align-items:center; justify-content:flex-end; padding-right:5px; min-width:5px; }}
.bar.crit {{ box-shadow:0 0 0 2px var(--accent), 0 0 0 3px rgba(217,123,18,.25); }}
.bar.lead {{ background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.30) 0 3px,transparent 3px 7px); }}
.durlbl {{ font-family:var(--mono); font-size:10px; color:#fff; opacity:.9; }}
.ms {{ position:absolute; top:9px; width:12px; height:12px; margin-left:-6px; background:var(--ink);
  transform:rotate(45deg); border-radius:2px; }}
.ms.crit {{ background:var(--accent); box-shadow:0 0 0 2px rgba(217,123,18,.25); }}
footer {{ color:var(--muted); font-size:12px; margin-top:26px; border-top:1px solid var(--line); padding-top:14px; }}
footer b {{ color:var(--ink); }}
</style>
<div class="wrap">
  <p class="eyebrow">Unicontrol · Plantillas de proyecto (PMI/PMP)</p>
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
  </div>
  {charts}
  <footer>Generado desde <b>uc.templates</b> + el planificador con prueba unitaria · fechas
    programadas hacia adelante en días hábiles desde el inicio base · la ruta crítica se calcula con CPM.
    Detalle completo en <b>docs/schedule-templates.md</b>.</footer>
</div>""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
