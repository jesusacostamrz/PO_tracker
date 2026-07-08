"""Self-contained Gantt HTML renderer. Draws PRE-POSITIONED rows (left/width in %),
so callers own layout: the template artifact positions via scheduler/CPM, the customer
tool positions via real Odoo dates. Theme-aware light/dark; horizontal-scroll safe."""
from __future__ import annotations

from dataclasses import dataclass, field

from uc.core.customer_view import CustomerPlan
from uc.core.internal_view import InternalPlan
from uc.core.palette import ACCENT

MONTHS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fmt_date(d) -> str:
    return f"{d.day} {MONTHS[d.month]}"


@dataclass
class Row:
    label: str
    kind: str                  # "phase" | "milestone"
    left: float
    width: float = 0.0
    color: str = "#8a99a8"
    progress: float = 0.0      # 0-100; draws an inner fill when > 0
    reached: bool = False      # milestone reached (customer)
    crit: bool = False         # critical path (template)
    lead: bool = False         # supplier lead-time (template)
    dur_label: str = ""
    wbs: str = ""              # WBS code shown before the name (template only)
    name_title: str = ""       # tooltip for the name span; defaults to label
    mark_title: str = ""       # tooltip for the bar/milestone mark; defaults to label
    # --- internal view only (all default so template/customer output is unchanged) ---
    row_class: str = ""        # extra class on the row div (e.g. "phase" | "step")
    indent: int = 0            # child-step indentation level
    variance_label: str = ""   # e.g. "+5d" | "-2d" | "±0" | "nuevo"
    variance_kind: str = ""    # "late" | "early" | "ontime" | "new" -> tag color
    baseline_end_left: float | None = None   # % position of a baseline end-tick


@dataclass
class Chart:
    title: str
    subtitle: str
    meta: str
    rows: list[Row] = field(default_factory=list)
    step: float = 0.0
    today_left: float | None = None
    total: int | None = None   # emits --total CSS var only when set (template)


# --- exact copy of the original <style> BODY (between <style> and </style>) ---
BASE_CSS = r"""
:root {
  --paper:#eef1f4; --panel:#ffffff; --ink:#161b22; --muted:#5b6b7c; --line:#d7dde3;
  --grid:#e4e9ee; --accent:#d97b12; --bar:#5b7f9c; --shadow:0 1px 2px rgba(20,30,45,.06);
  --sans: system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono: ui-monospace,"Cascadia Code","SFMono-Regular",Consolas,monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --paper:#0e1218; --panel:#161d26; --ink:#e6ecf2; --muted:#8a99a8; --line:#232c37;
    --grid:#1b232d; --bar:#6f93b0; --shadow:0 1px 2px rgba(0,0,0,.3); }
}
:root[data-theme="dark"] { --paper:#0e1218; --panel:#161d26; --ink:#e6ecf2; --muted:#8a99a8;
  --line:#232c37; --grid:#1b232d; --bar:#6f93b0; --shadow:0 1px 2px rgba(0,0,0,.3); }
:root[data-theme="light"] { --paper:#eef1f4; --panel:#ffffff; --ink:#161b22; --muted:#5b6b7c;
  --line:#d7dde3; --grid:#e4e9ee; --bar:#5b7f9c; --shadow:0 1px 2px rgba(20,30,45,.06); }
* { box-sizing:border-box; }
body { margin:0; }
.wrap { max-width:1120px; margin:0 auto; padding:40px 24px 64px; background:var(--paper);
  color:var(--ink); font-family:var(--sans); line-height:1.5; }
.eyebrow { font-family:var(--mono); font-size:12px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--accent); margin:0 0 6px; }
h1 { font-size:clamp(26px,4vw,38px); margin:0 0 8px; letter-spacing:-.02em; text-wrap:balance; }
.lede { color:var(--muted); max-width:64ch; margin:0 0 22px; }
.stats { display:flex; flex-wrap:wrap; gap:10px; margin:0 0 26px; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:10px 14px;
  box-shadow:var(--shadow); }
.stat b { font-family:var(--mono); font-size:19px; display:block; }
.stat span { color:var(--muted); font-size:12.5px; }
.legend { display:flex; flex-wrap:wrap; gap:14px 20px; align-items:center; padding:14px 16px;
  background:var(--panel); border:1px solid var(--line); border-radius:10px; margin:0 0 30px;
  font-size:12.5px; box-shadow:var(--shadow); }
.legend .grp { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
.lg { display:inline-flex; align-items:center; gap:6px; color:var(--muted); white-space:nowrap; }
.dot { width:11px; height:11px; border-radius:3px; display:inline-block; flex:none; }
.swatch-bar { width:26px; height:11px; border-radius:3px; background:var(--bar); display:inline-block; }
.swatch-bar.crit { background:transparent; box-shadow:inset 0 0 0 2px var(--accent); }
.swatch-lead { width:26px; height:11px; border-radius:3px; display:inline-block; background:var(--bar);
  background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.28) 0 3px,transparent 3px 6px); }
.swatch-ms { width:11px; height:11px; background:var(--ink); transform:rotate(45deg); display:inline-block; }
.sep { width:1px; height:16px; background:var(--line); }
.chart { margin:0 0 34px; }
.chart-head h2 { font-size:20px; margin:0 0 2px; letter-spacing:-.01em; }
.chart-head .sub { color:var(--muted); margin:0 0 3px; font-size:13.5px; }
.chart-head .meta { font-family:var(--mono); font-size:12.5px; color:var(--muted); margin:0 0 12px; }
.chart-head .meta b { color:var(--accent); }
.gantt-scroll { overflow-x:auto; border:1px solid var(--line); border-radius:12px; background:var(--panel);
  box-shadow:var(--shadow); }
.gantt { min-width:760px; }
.row { display:grid; grid-template-columns:320px 1fr; align-items:center; border-top:1px solid var(--line);
  min-height:30px; }
.row:first-child { border-top:none; }
.rlabel { display:flex; align-items:center; gap:8px; padding:5px 12px; min-width:0; }
.rlabel .wbs { font-family:var(--mono); font-size:11.5px; color:var(--muted); flex:none; min-width:34px; }
.rlabel .tname { font-size:12.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.track { position:relative; height:30px; border-left:1px solid var(--line);
  background:repeating-linear-gradient(to right, var(--grid) 0 1px, transparent 1px var(--step)); }
.bar { position:absolute; top:7px; height:16px; border-radius:4px; background:var(--c);
  display:flex; align-items:center; justify-content:flex-end; padding-right:5px; min-width:5px; }
.bar.crit { box-shadow:0 0 0 2px var(--accent), 0 0 0 3px rgba(217,123,18,.25); }
.bar.lead { background-image:repeating-linear-gradient(45deg,rgba(0,0,0,.30) 0 3px,transparent 3px 7px); }
.durlbl { font-family:var(--mono); font-size:10px; color:#fff; opacity:.9; }
.ms { position:absolute; top:9px; width:12px; height:12px; margin-left:-6px; background:var(--ink);
  transform:rotate(45deg); border-radius:2px; }
.ms.crit { background:var(--accent); box-shadow:0 0 0 2px rgba(217,123,18,.25); }
footer { color:var(--muted); font-size:12px; margin-top:26px; border-top:1px solid var(--line); padding-top:14px; }
footer b { color:var(--ink); }
"""


def _row_html(r: Row) -> str:
    dot = f'<span class="dot" style="background:{r.color}"></span>'
    wbs = f'<span class="wbs">{esc(r.wbs)}</span>' if r.wbs else ""
    name_title = esc(r.name_title) if r.name_title else esc(r.label)
    label = f'{dot}{wbs}<span class="tname" title="{name_title}">{esc(r.label)}</span>'
    mark_title = esc(r.mark_title) if r.mark_title else esc(r.label)
    tick = (f'<span class="btick" style="left:{r.baseline_end_left:.3f}%"></span>'
            if r.baseline_end_left is not None else "")
    vtag = (f'<span class="vtag {r.variance_kind}">{esc(r.variance_label)}</span>'
            if r.variance_label else "")
    if r.kind == "milestone":
        cls = "ms" + (" crit" if r.crit else "") + (" reached" if r.reached else "")
        mark = f'<span class="{cls}" style="left:{r.left:.3f}%" title="{mark_title}"></span>'
        track = f'<div class="track">{tick}{mark}{vtag}</div>'
    else:
        cls = "bar" + (" crit" if r.crit else "") + (" lead" if r.lead else "")
        fill = (f'<i class="fill" style="width:{max(0.0, min(r.progress, 100)):.1f}%"></i>'
                if r.progress > 0 else "")
        inlabel = f'<span class="durlbl">{esc(r.dur_label)}</span>' if r.dur_label else ""
        bar = (f'<div class="{cls}" style="left:{r.left:.3f}%;width:{r.width:.3f}%;--c:{r.color}" '
               f'title="{mark_title}">{fill}{inlabel}</div>')
        track = f'<div class="track">{tick}{bar}{vtag}</div>'
    row_cls = f"row {r.row_class}" if r.row_class else "row"
    rlabel_attr = f' style="padding-left:{12 + r.indent * 20}px"' if r.indent else ""
    return f'<div class="{row_cls}"><div class="rlabel"{rlabel_attr}>{label}</div>{track}</div>'


def render_chart(chart: Chart) -> str:
    rows = "\n".join(_row_html(r) for r in chart.rows)
    total_var = f"--total:{chart.total};" if chart.total is not None else ""
    today_line = (f'<div class="todayline" style="left:{chart.today_left:.3f}%"></div>\n          '
                  if chart.today_left is not None else "")
    return f"""
    <section class="chart">
      <div class="chart-head">
        <h2>{esc(chart.title)}</h2>
        <p class="sub">{esc(chart.subtitle)}</p>
        <p class="meta">{chart.meta}</p>
      </div>
      <div class="gantt-scroll">
        <div class="gantt" style="{total_var}--step:{chart.step:.4f}%">
          {today_line}{rows}
        </div>
      </div>
    </section>"""


def render_page(header_html: str, body_html: str, extra_css: str = "",
                title: str = "Plantillas de Cronograma PMI — Unicontrol") -> str:
    return (f"<title>{esc(title)}</title>\n"
            f"<style>{BASE_CSS}{extra_css}</style>\n"
            f'<div class="wrap">\n{header_html}\n  {body_html}\n</div>')


EXTRA_CSS_CUSTOMER = r"""
.bar .fill { position:absolute; left:0; top:0; height:100%; border-radius:4px;
  background:rgba(255,255,255,.35); }
.ms.reached { background:var(--accent); box-shadow:0 0 0 2px rgba(217,123,18,.25); }
.todayline { position:absolute; top:0; bottom:0; width:2px; background:var(--accent);
  opacity:.55; z-index:3; }
.gantt { position:relative; }
"""


def _pct(day, dmin, span_days: int) -> float:
    return (day - dmin).days / span_days * 100


def plan_to_chart(plan: CustomerPlan) -> Chart:
    span = max((plan.date_max - plan.date_min).days, 1)
    # Phases and milestones share one chronological order: a milestone that marks the
    # end of a phase sits right after that phase's bar. Sort key is the row's date;
    # ties keep the phase bar above the milestone diamond (kind rank 0 vs 1).
    items: list[tuple] = []
    for ph in plan.phases:
        left = _pct(ph.start, plan.date_min, span)
        width = max(_pct(ph.end, plan.date_min, span) - left, 0.9)
        items.append((ph.start, 0, Row(label=ph.name, kind="phase", left=left, width=width,
                                        color=ph.color, progress=ph.progress)))
    for m in plan.milestones:
        items.append((m.day, 1, Row(label=f"{m.name}  ({fmt_date(m.day)})", kind="milestone",
                                     left=_pct(m.day, plan.date_min, span), color=ACCENT,
                                     reached=m.reached)))
    items.sort(key=lambda it: (it[0], it[1]))
    rows: list[Row] = [it[2] for it in items]
    today_left = (_pct(plan.as_of, plan.date_min, span)
                  if plan.date_min <= plan.as_of <= plan.date_max else None)
    step = 7 / span * 100
    meta = (f"Avance <b>{plan.overall_progress:.0f}%</b> · {len(plan.phases)} fases · "
            f"{len(plan.milestones)} hitos · al {fmt_date(plan.as_of)} {plan.as_of.year}")
    return Chart(title=plan.project_name,
                 subtitle="Cronograma del proyecto — fases y fechas clave.",
                 meta=meta, rows=rows, step=step, today_left=today_left)


def render_customer_page(plan: CustomerPlan) -> str:
    chart = plan_to_chart(plan)
    header = (
        '  <p class="eyebrow">Unicontrol · Avance de proyecto</p>\n'
        f'  <h1>{esc(plan.project_name)}</h1>\n'
        f'  <p class="lede">Fases principales y fechas clave. Avance general '
        f'<b>{plan.overall_progress:.0f}%</b> al {fmt_date(plan.as_of)} {plan.as_of.year}.</p>\n'
        '  <div class="legend"><div class="grp">'
        '<span class="lg"><span class="swatch-bar"></span>Fase</span>'
        '<span class="lg"><span class="swatch-ms"></span>Hito pendiente</span>'
        '<span class="lg"><span class="swatch-ms" style="background:var(--accent)"></span>'
        'Hito cumplido</span></div></div>'
    )
    return render_page(header, render_chart(chart), extra_css=EXTRA_CSS_CUSTOMER,
                       title=plan.project_name)


# ------------------------------- internal view -------------------------------

EXTRA_CSS_INTERNAL = r"""
.bar .fill { position:absolute; left:0; top:0; height:100%; border-radius:4px;
  background:rgba(255,255,255,.35); }
.ms.reached { background:var(--accent); box-shadow:0 0 0 2px rgba(217,123,18,.25); }
.todayline { position:absolute; top:0; bottom:0; width:2px; background:var(--accent);
  opacity:.55; z-index:3; }
.gantt { position:relative; }
.row.phase .rlabel .tname { font-weight:600; }
.row.step .rlabel .dot { width:8px; height:8px; opacity:.75; }
.row.step .rlabel .tname { color:var(--muted); font-size:12px; }
.btick { position:absolute; top:4px; bottom:4px; width:2px; margin-left:-1px;
  background:var(--muted); opacity:.45; z-index:2; }
.vtag { position:absolute; right:6px; top:7px; height:16px; display:inline-flex;
  align-items:center; padding:0 6px; border-radius:4px; font-family:var(--mono);
  font-size:10.5px; z-index:4; background:var(--panel); border:1px solid var(--line);
  color:var(--muted); }
.vtag.late { color:#c0392b; border-color:rgba(192,57,43,.4); }
.vtag.early { color:#2f7d4f; border-color:rgba(47,125,79,.4); }
.vtag.ontime { opacity:.55; }
.vtag.new { color:var(--accent); border-color:rgba(217,123,18,.4); }
.badge-int { display:inline-block; font-family:var(--mono); font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:#fff; background:var(--accent); border-radius:5px;
  padding:2px 8px; margin-left:8px; vertical-align:middle; }
.swatch-tick { width:2px; height:14px; background:var(--muted); opacity:.6; display:inline-block; }
"""


def _variance_tag(v: int | None) -> tuple[str, str]:
    """(label, kind) for a variance in calendar days. None = no baseline entry."""
    if v is None:
        return ("nuevo", "new")
    if v > 0:
        return (f"+{v}d", "late")
    if v < 0:
        return (f"{v}d", "early")
    return ("±0", "ontime")


def _overall_variance_text(v: int | None) -> str:
    if v is None:
        return "sin línea base"
    if v > 0:
        return f"Atraso de <b>{v} d</b> vs. plan aprobado"
    if v < 0:
        return f"Adelanto de <b>{-v} d</b> vs. plan aprobado"
    return "En plan vs. lo aprobado"


def internal_plan_to_chart(plan: InternalPlan) -> Chart:
    span = max((plan.date_max - plan.date_min).days, 1)
    rows: list[Row] = []
    for r in plan.rows:
        left = _pct(r.start, plan.date_min, span)
        vlabel, vkind = _variance_tag(r.variance_days)
        btick = (_pct(r.baseline_end, plan.date_min, span)
                 if r.baseline_end and plan.date_min <= r.baseline_end <= plan.date_max
                 else None)
        if r.kind == "milestone":
            rows.append(Row(label=f"{r.name}  ({fmt_date(r.start)})", kind="milestone",
                            left=left, color=ACCENT, reached=r.reached, row_class="milestone",
                            variance_label=vlabel, variance_kind=vkind, baseline_end_left=btick))
        else:
            width = max(_pct(r.end, plan.date_min, span) - left, 0.9)
            rows.append(Row(label=r.name, kind="phase", left=left, width=width, color=r.color,
                            progress=r.progress, row_class=r.kind, indent=r.indent,
                            variance_label=vlabel, variance_kind=vkind, baseline_end_left=btick))
    today_left = (_pct(plan.as_of, plan.date_min, span)
                  if plan.date_min <= plan.as_of <= plan.date_max else None)
    step = 7 / span * 100
    n_phases = sum(1 for r in plan.rows if r.kind == "phase")
    n_steps = sum(1 for r in plan.rows if r.kind == "step")
    var = _overall_variance_text(plan.overall_variance_days).replace("<b>", "").replace("</b>", "")
    meta = (f"Avance <b>{plan.overall_progress:.0f}%</b> · {n_phases} fases · {n_steps} pasos · "
            f"{var} · al {fmt_date(plan.as_of)} {plan.as_of.year}")
    return Chart(title=plan.project_name,
                 subtitle="Plan completo — fases, pasos e hitos contra la línea base aprobada.",
                 meta=meta, rows=rows, step=step, today_left=today_left)


def render_internal_page(plan: InternalPlan) -> str:
    chart = internal_plan_to_chart(plan)
    approved = (f" · Línea base aprobada {fmt_date(plan.approved_on)} {plan.approved_on.year}"
                if plan.approved_on else "")
    header = (
        '  <p class="eyebrow">Unicontrol · Seguimiento interno'
        '<span class="badge-int">Uso interno</span></p>\n'
        f'  <h1>{esc(plan.project_name)}</h1>\n'
        f'  <p class="lede">Plan completo contra la línea base. Avance '
        f'<b>{plan.overall_progress:.0f}%</b> · {_overall_variance_text(plan.overall_variance_days)}'
        f'{approved}.</p>\n'
        '  <div class="legend"><div class="grp">'
        '<span class="lg"><span class="swatch-bar"></span>Fase / paso</span>'
        '<span class="lg"><span class="swatch-ms"></span>Hito</span>'
        '<span class="lg"><span class="swatch-tick"></span>Fin línea base</span>'
        '</div><span class="sep"></span><div class="grp">'
        '<span class="lg"><span class="vtag late" style="position:static">+d</span>Atraso</span>'
        '<span class="lg"><span class="vtag early" style="position:static">−d</span>Adelanto</span>'
        '</div></div>'
    )
    return render_page(header, render_chart(chart), extra_css=EXTRA_CSS_INTERNAL,
                       title=f"{plan.project_name} — interno")
