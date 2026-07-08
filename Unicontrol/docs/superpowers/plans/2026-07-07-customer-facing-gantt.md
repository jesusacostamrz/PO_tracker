# Customer-Facing Live Gantt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a shareable, self-contained HTML Gantt for one live Odoo project that shows only milestones + synthesized phase bars (leak-safe) with gentle live progress.

**Architecture:** One shared HTML renderer (`uc/render/gantt_html.py`) draws pre-positioned rows; two callers feed it — the existing template artifact (positions via scheduler/CPM) and the new customer tool (positions via real Odoo dates). Phase grouping matches live tasks back to `uc/templates.py` for rich phase names+colors, falling back to generic "Fase N". All decision logic is pure and unit-tested; the CLI is a thin read-only Odoo wrapper.

**Tech Stack:** Python 3 stdlib only for logic/tests (`unittest`, `dataclasses`, `re`, `datetime`); reuses `uc.core.*`, `uc.templates`, and the Hermes `OdooClient` via `ProjectOdooClient`. No new dependencies.

## Global Constraints

- **Tests are stdlib `unittest`, no pytest.** Run from `Unicontrol/` with `python -m unittest discover -s tests -p "test_*.py"`. Test files import `from uc.core...` directly (cwd is on `sys.path`).
- **Read-only on Odoo.** The customer tool only reads (`search_read` / `load_tasks`). It MUST NOT write to Odoo.
- **Leak-safe:** never render an individual internal task row. Only phase bars + milestones reach output.
- **The template artifact's rendered output must stay byte-for-byte identical.** Enforced by a golden-file test. New renderer features are strictly *additive* — the extra markup/CSS is emitted ONLY when the customer-specific data is present, and customer-only CSS is passed as a separate `extra_css` string (empty for the template path).
- **No alarm colors** in customer output — behind-schedule stays neutral.
- **Spanish output**, matching existing artifact copy. No "ruta crítica" / "días hábiles" in the customer variant.
- **Field access via the config map**, never hardcoded Odoo field names. Map lives at `config/unicontrol.config.yaml` → `odoo_project.fields`.
- Commit after each task.

## File Structure

```
uc/core/palette.py            NEW. ETAPA_COLOR + ACCENT (moved out of gen_gantt_artifact).
uc/core/customer_view.py      NEW. Pure domain: parse WBS, detect milestones/phases,
                              template-match, roll up progress → CustomerPlan.
uc/render/gantt_html.py       NEW. Presentation: Row/Chart types, render_chart, render_page
                              (BASE_CSS), plan_to_chart + render_customer_page.
uc/connectors/odoo_project.py MODIFY. Add project_by_id() (read-only).
scripts/gen_customer_gantt.py NEW. Thin CLI: read live project → build → render → stdout.
scripts/gen_gantt_artifact.py MODIFY. Build Rows from scheduler/CPM, call shared renderer.
tests/fixtures/gantt_template_golden.html   NEW. Golden snapshot of current artifact output.
tests/test_template_golden.py     NEW. Asserts artifact output == golden.
tests/test_palette.py             NEW.
tests/test_customer_view.py       NEW.
tests/test_gantt_html.py          NEW.
```

---

### Task 1: Snapshot-lock the current template artifact

Locks today's `gen_gantt_artifact.py` output BEFORE any refactor so the shared-renderer extraction can't silently change it.

**Files:**
- Create: `tests/fixtures/gantt_template_golden.html`
- Create: `tests/test_template_golden.py`

**Interfaces:**
- Consumes: current `scripts/gen_gantt_artifact.py` (prints full HTML to stdout, deterministic — `main()` hardcodes `start = date(2026, 7, 13)`).
- Produces: a golden fixture + a test other tasks must keep green.

- [ ] **Step 1: Seed the golden fixture from current output**

Run from `Unicontrol/`:
```bash
python -c "import subprocess,sys,pathlib; out=subprocess.run([sys.executable,'scripts/gen_gantt_artifact.py'],capture_output=True,text=True,encoding='utf-8').stdout; pathlib.Path('tests/fixtures').mkdir(parents=True,exist_ok=True); pathlib.Path('tests/fixtures/gantt_template_golden.html').write_text(out.replace('\r\n','\n'),encoding='utf-8',newline='\n')"
```
Expected: file `tests/fixtures/gantt_template_golden.html` created, non-empty, starts with `<title>Plantillas de Cronograma PMI`.

- [ ] **Step 2: Write the golden test**

```python
# tests/test_template_golden.py
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "gantt_template_golden.html"


class TestTemplateArtifactGolden(unittest.TestCase):
    def test_output_matches_golden(self):
        out = subprocess.run(
            [sys.executable, "scripts/gen_gantt_artifact.py"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        produced = out.stdout.replace("\r\n", "\n")
        golden = GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(produced, golden)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it passes against unmodified code**

Run: `python -m unittest tests.test_template_golden -v`
Expected: PASS (1 test).

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/gantt_template_golden.html tests/test_template_golden.py
git commit -m "test: golden-lock template Gantt artifact output before refactor"
```

---

### Task 2: Extract the shared renderer + refactor the template artifact

Moves the CSS + row/section markup into `uc/render/gantt_html.py` behind `Row`/`Chart` types, refactors `gen_gantt_artifact.py` to build rows and call the renderer, and adds customer-only rendering features as strictly additive code. The golden test from Task 1 proves the template output is unchanged.

**Files:**
- Create: `uc/core/palette.py`
- Create: `uc/render/__init__.py` (empty)
- Create: `uc/render/gantt_html.py`
- Modify: `scripts/gen_gantt_artifact.py`
- Test: `tests/test_gantt_html.py`, and Task 1's `tests/test_template_golden.py` must stay green.

**Interfaces:**
- Produces (used by later tasks and the template artifact):
  - `uc.core.palette.ETAPA_COLOR: dict[str, str]`, `uc.core.palette.ACCENT: str`
  - `uc.render.gantt_html.Row` dataclass: `label: str`, `kind: str` (`"phase"` | `"milestone"`), `left: float`, `width: float`, `color: str`, `progress: float = 0.0`, `reached: bool = False`, `crit: bool = False`, `lead: bool = False`, `dur_label: str = ""`
  - `uc.render.gantt_html.Chart` dataclass: `title: str`, `subtitle: str`, `meta: str`, `rows: list[Row]`, `step: float = 0.0`, `today_left: float | None = None`
  - `render_chart(chart: Chart) -> str` — returns the `<section class="chart">…</section>` HTML
  - `render_page(header_html: str, body_html: str, extra_css: str = "") -> str` — wraps with `<title>`, `<style>BASE_CSS{extra_css}</style>`, and `<div class="wrap">…</div>`
  - `esc(s: str) -> str`, `MONTHS: list[str]`, `fmt_date(d) -> str` (e.g. `"24 jul"`)

- [ ] **Step 1: Create the palette module**

```python
# uc/core/palette.py
"""Phase (etapa) colors shared by the template artifact and the customer Gantt."""
from __future__ import annotations

ACCENT = "#d97b12"

ETAPA_COLOR = {
    "Diseño": "#3f7cac",
    "Revisión de Diseño": "#6c8f3f",
    "Compras": "#c07a1e",
    "Maquinado": "#7a6cae",
    "Ensamble": "#2f938a",
    "Entrega": "#b5495b",
    "—": "#8a99a8",
}
```

- [ ] **Step 2: Create `uc/render/__init__.py`**

Create an empty file `uc/render/__init__.py`.

- [ ] **Step 3: Create the shared renderer**

Move the existing `_esc`, the `<style>` contents, `_MONTHS`, and the row/section markup out of `gen_gantt_artifact.py` into this module, parameterized by `Row`/`Chart`. Preserve number formatting EXACTLY (`f"{left:.3f}%"`, `f"{width:.3f}%"`, `f"{step:.4f}%"`) so the golden test passes. New features (`progress` fill, `reached` class, `today_left` line) are emitted ONLY when truthy.

```python
# uc/render/gantt_html.py
"""Self-contained Gantt HTML renderer. Draws PRE-POSITIONED rows (left/width in %),
so callers own layout: the template artifact positions via scheduler/CPM, the customer
tool positions via real Odoo dates. Theme-aware light/dark; horizontal-scroll safe."""
from __future__ import annotations

from dataclasses import dataclass, field

MONTHS = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fmt_date(d) -> str:
    return f"{d.day} {MONTHS[d.month]}"


@dataclass
class Row:
    label: str
    kind: str                 # "phase" | "milestone"
    left: float
    width: float = 0.0
    color: str = "#8a99a8"
    progress: float = 0.0     # 0–100; draws an inner fill when > 0
    reached: bool = False      # milestone reached (customer)
    crit: bool = False         # critical path (template)
    lead: bool = False         # supplier lead-time (template)
    dur_label: str = ""


@dataclass
class Chart:
    title: str
    subtitle: str
    meta: str
    rows: list[Row] = field(default_factory=list)
    step: float = 0.0
    today_left: float | None = None


# --- exact copy of the original <style> BODY (between <style> and </style>) ---
BASE_CSS = r"""<PASTE THE EXISTING STYLE BODY VERBATIM FROM gen_gantt_artifact.py lines 113-177>"""


def _row_html(r: Row) -> str:
    dot = f'<span class="dot" style="background:{r.color}"></span>'
    label = (f'{dot}<span class="tname" title="{esc(r.label)}">{esc(r.label)}</span>'
             if r.kind == "phase" and False else "")  # replaced below
    # Label column: phase shows dot+name; milestone shows dot+name.
    label = f'{dot}<span class="tname" title="{esc(r.label)}">{esc(r.label)}</span>'
    if r.kind == "milestone":
        cls = "ms" + (" crit" if r.crit else "") + (" reached" if r.reached else "")
        mark = f'<span class="{cls}" style="left:{r.left:.3f}%" title="{esc(r.label)}"></span>'
        track = f'<div class="track">{mark}</div>'
    else:
        cls = "bar" + (" crit" if r.crit else "") + (" lead" if r.lead else "")
        fill = (f'<i class="fill" style="width:{max(0.0, min(r.progress,100)):.1f}%"></i>'
                if r.progress > 0 else "")
        inlabel = f'<span class="durlbl">{esc(r.dur_label)}</span>' if r.dur_label else ""
        bar = (f'<div class="{cls}" style="left:{r.left:.3f}%;width:{r.width:.3f}%;--c:{r.color}" '
               f'title="{esc(r.label)}">{fill}{inlabel}</div>')
        track = f'<div class="track">{bar}</div>'
    return f'<div class="row"><div class="rlabel">{label}</div>{track}</div>'


def render_chart(chart: Chart) -> str:
    rows = "\n".join(_row_html(r) for r in chart.rows)
    today = (f'<div class="todayline" style="left:{chart.today_left:.3f}%"></div>'
             if chart.today_left is not None else "")
    return f"""
    <section class="chart">
      <div class="chart-head">
        <h2>{esc(chart.title)}</h2>
        <p class="sub">{esc(chart.subtitle)}</p>
        <p class="meta">{chart.meta}</p>
      </div>
      <div class="gantt-scroll">
        <div class="gantt" style="--step:{chart.step:.4f}%">
          {today}
          {rows}
        </div>
      </div>
    </section>"""


def render_page(header_html: str, body_html: str, extra_css: str = "") -> str:
    return (f"<title>Plantillas de Cronograma PMI — Unicontrol</title>\n"
            f"<style>{BASE_CSS}{extra_css}</style>\n"
            f'<div class="wrap">\n{header_html}\n  {body_html}\n</div>')
```

> **IMPORTANT for the golden test:** the original renderer positions the `today` line and the `--total` variable differently. To keep byte-identity, match the ORIGINAL markup for the template path exactly: the original `.gantt` uses `style="--total:{total};--step:{step:.4f}%"` and has NO today line, NO `fill`, NO `reached`. Adjust `render_chart` so that when `today_left is None` the `{today}` slot and its surrounding newline are absent, and include `--total` only if the golden requires it. Iterate against `tests.test_template_golden` until it passes; that test is the source of truth for exactness. If matching `--total` is needed, add a `total: int | None = None` field to `Chart` and emit `--total:{chart.total};` only when set.

- [ ] **Step 4: Refactor `gen_gantt_artifact.py` to build Rows and call the renderer**

Replace its `_esc`, `_MONTHS`, `ETAPA_COLOR`, `_rows_html`, `_chart_html`, and the inline `<style>`/page string with: import from the renderer + palette, build `Row`/`Chart` from the scheduler/CPM results, and assemble the SAME header/stats/legend strings it emits today.

```python
# scripts/gen_gantt_artifact.py (key changes)
from uc.core.palette import ETAPA_COLOR
from uc.render.gantt_html import Chart, Row, render_chart, render_page, esc, MONTHS

def _chart(title, subtitle, items) -> Chart:
    sched, critical, total = _schedule(items)        # unchanged helper
    step = 100 * 5 / total
    rows = []
    for (w, name, etapa, dur, _preds, mile) in items:
        es, ef = sched[w]
        color = ETAPA_COLOR.get(etapa, "#8a99a8")
        left = es / total * 100
        if mile:
            rows.append(Row(label=name, kind="milestone", left=left, color=color,
                            crit=(w in critical)))
        else:
            width = max(dur / total * 100, 0.9)
            rows.append(Row(label=name, kind="phase", left=left, width=width, color=color,
                            crit=(w in critical), lead=name.strip().endswith("*"),
                            dur_label=(f"{dur}d" if width > 6 else "")))
    n_tasks = sum(1 for it in items if not it[5])
    n_ms = sum(1 for it in items if it[5])
    meta = (f"{n_tasks} tareas · {n_ms} hitos · ruta crítica "
            f"<b>{total} días hábiles</b> (~{round(total/5)} semanas)")
    return Chart(title=title, subtitle=subtitle, meta=meta, rows=rows, step=step)  # + total=total if needed
```

Then in `main()` build the two charts with `render_chart(_chart(...))`, keep the existing eyebrow/lede/stats/legend HTML verbatim as `header_html`, and emit `render_page(header_html, charts_html)`.

> Note: the original label column shows WBS + name (`<span class="wbs">…` + `<span class="tname">`). The customer path has no WBS. To stay golden-identical, keep the WBS span in the template path. Simplest: give `Row` an optional `wbs: str = ""` field and emit `<span class="wbs">{wbs}</span>` only when non-empty; template rows set it, customer rows leave it "". Add `wbs` to the `Row` dataclass and to `_row_html`'s label block.

- [ ] **Step 5: Write a focused renderer unit test (positioning + additive features)**

```python
# tests/test_gantt_html.py
import unittest

from uc.render.gantt_html import Chart, Row, esc, fmt_date, render_chart


class TestRenderChart(unittest.TestCase):
    def test_phase_bar_has_position_and_fill(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="Diseño", kind="phase", left=10.0, width=25.0, color="#3f7cac", progress=60)
        ])
        html = render_chart(chart)
        self.assertIn("left:10.000%", html)
        self.assertIn("width:25.000%", html)
        self.assertIn('class="fill"', html)
        self.assertIn("60.0%", html)

    def test_zero_progress_emits_no_fill(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="x", kind="phase", left=0, width=5, color="#000", progress=0)])
        self.assertNotIn('class="fill"', render_chart(chart))

    def test_reached_milestone_gets_class(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="Entrega", kind="milestone", left=80, reached=True)])
        self.assertIn("reached", render_chart(chart))

    def test_today_line_only_when_set(self):
        self.assertNotIn("todayline", render_chart(Chart("P", "s", "m", rows=[])))
        self.assertIn("todayline", render_chart(Chart("P", "s", "m", rows=[], today_left=50.0)))

    def test_helpers(self):
        from datetime import date
        self.assertEqual(fmt_date(date(2026, 7, 24)), "24 jul")
        self.assertEqual(esc("<a>"), "&lt;a&gt;")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6: Add the customer-only CSS constant (used later by the customer page)**

Append to `uc/render/gantt_html.py`:

```python
EXTRA_CSS_CUSTOMER = r"""
.bar .fill { position:absolute; left:0; top:0; height:100%; border-radius:4px;
  background:rgba(255,255,255,.35); }
.ms.reached { background:var(--accent); box-shadow:0 0 0 2px rgba(217,123,18,.25); }
.todayline { position:absolute; top:0; bottom:0; width:2px; background:var(--accent);
  opacity:.55; z-index:3; }
.gantt { position:relative; }
"""
```

- [ ] **Step 7: Run all tests — golden must still pass**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: all pass, INCLUDING `tests.test_template_golden` (proves the template artifact is byte-identical) and the new `tests.test_gantt_html`. Previously-passing suite count (41) + new tests, all OK.

- [ ] **Step 8: Commit**

```bash
git add uc/core/palette.py uc/render/__init__.py uc/render/gantt_html.py scripts/gen_gantt_artifact.py tests/test_gantt_html.py
git commit -m "refactor: extract shared Gantt renderer; template output byte-identical (golden-verified)"
```

---

### Task 3: WBS parsing + milestone detection (customer_view foundations)

Pure helpers for reading the WBS prefix baked into Odoo task names and telling milestones from work tasks.

**Files:**
- Create: `uc/core/customer_view.py`
- Test: `tests/test_customer_view.py`

**Interfaces:**
- Consumes: `uc.core.models.Task`.
- Produces:
  - `parse_wbs(name: str) -> str | None` — `"1.1  Foo"→"1.1"`, `"★ M1  Kickoff"→"M1"`, `"Random"→None`
  - `wbs_root(wbs: str) -> str` — `"1.1"→"1"`, `"M1"→"M1"`
  - `is_milestone(task: Task) -> bool` — name starts with `★` OR parsed WBS matches `^M\d+$`
  - `clean_name(name: str) -> str` — strips a leading `★` and WBS prefix for display

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_customer_view.py
import unittest
from datetime import date

from uc.core.models import Task
from uc.core import customer_view as cv


class TestWbsParsing(unittest.TestCase):
    def test_parse_dotted_wbs(self):
        self.assertEqual(cv.parse_wbs("1.1  Kickoff y revisión"), "1.1")

    def test_parse_milestone_wbs(self):
        self.assertEqual(cv.parse_wbs("★ M1  Kickoff completo"), "M1")

    def test_parse_no_wbs(self):
        self.assertIsNone(cv.parse_wbs("Comprar tornillos"))

    def test_wbs_root(self):
        self.assertEqual(cv.wbs_root("5.5"), "5")
        self.assertEqual(cv.wbs_root("M3"), "M3")

    def test_is_milestone_by_star(self):
        self.assertTrue(cv.is_milestone(Task(id=1, name="★ M2  Diseño aprobado")))

    def test_is_milestone_false_for_work(self):
        self.assertFalse(cv.is_milestone(Task(id=2, name="2.1  Modelar piezas")))

    def test_clean_name_strips_prefix(self):
        self.assertEqual(cv.clean_name("★ M5  Piezas entregadas"), "Piezas entregadas")
        self.assertEqual(cv.clean_name("7.2  Entrega al cliente"), "Entrega al cliente")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_customer_view -v`
Expected: FAIL (`module 'uc.core.customer_view' has no attribute ...`).

- [ ] **Step 3: Implement the helpers**

```python
# uc/core/customer_view.py
"""Turn a live Odoo project's tasks into a customer-safe plan: milestones + synthesized
phase bars with gentle progress. Pure logic — no Odoo, no HTML. Individual work tasks are
NEVER exposed; only phase rollups and milestones leave this module."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from uc.core.models import Task
from uc.core.palette import ACCENT, ETAPA_COLOR

_WBS_RE = re.compile(r"^\s*★?\s*(M\d+|\d+(?:\.\d+)*)")


def parse_wbs(name: str) -> str | None:
    m = _WBS_RE.match(name or "")
    return m.group(1) if m else None


def wbs_root(wbs: str) -> str:
    return wbs.split(".")[0]


def is_milestone(task: Task) -> bool:
    if (task.name or "").lstrip().startswith("★"):
        return True
    w = parse_wbs(task.name)
    return bool(w and re.fullmatch(r"M\d+", w))


def clean_name(name: str) -> str:
    s = (name or "").lstrip()
    if s.startswith("★"):
        s = s[1:].lstrip()
    w = parse_wbs(name)
    if w and s.startswith(w):
        s = s[len(w):]
    return s.strip()
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.test_customer_view -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add uc/core/customer_view.py tests/test_customer_view.py
git commit -m "feat: WBS parsing + milestone detection for customer view"
```

---

### Task 4: Template matching (rich phase names + colors)

Given the set of live WBS codes, decide whether the project is a known template instance and, if so, provide the `wbs → etapa` map. Coverage threshold 0.6.

**Files:**
- Modify: `uc/core/customer_view.py`
- Test: `tests/test_customer_view.py` (add a class)

**Interfaces:**
- Consumes: `uc.templates.TEMPLATES` (`{name: [(wbs, name, etapa, dur, preds, mile), ...]}`).
- Produces: `match_template(wbs_codes: set[str]) -> tuple[str | None, dict[str, str]]` — returns `(template_name, {wbs: etapa})` when a template covers ≥ 0.6 of the non-milestone codes, else `(None, {})`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_customer_view.py
from uc.templates import MACHINING


class TestTemplateMatch(unittest.TestCase):
    def test_matches_machining_and_maps_etapa(self):
        codes = {cv.parse_wbs(n) for (w, n, *_ ) in [(i[0], f"{i[0]}  {i[1]}") for i in MACHINING]}
        codes = {w for (w, _n, _e, _d, _p, _m) in MACHINING if not w.startswith("M")}
        name, mp = cv.match_template(codes)
        self.assertEqual(name, "[PLANTILLA] Proyecto de Maquinado")
        self.assertEqual(mp["5.5"], "Maquinado")

    def test_no_match_returns_none(self):
        name, mp = cv.match_template({"99", "98", "97"})
        self.assertIsNone(name)
        self.assertEqual(mp, {})

    def test_partial_below_threshold_is_none(self):
        # only 1 of 4 codes is a real machining WBS → 0.25 < 0.6
        name, _ = cv.match_template({"1.1", "80", "81", "82"})
        self.assertIsNone(name)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_customer_view.TestTemplateMatch -v`
Expected: FAIL (`no attribute 'match_template'`).

- [ ] **Step 3: Implement `match_template`**

```python
# add to uc/core/customer_view.py
from uc.templates import TEMPLATES

_MATCH_THRESHOLD = 0.6


def _template_wbs_etapa(items) -> dict[str, str]:
    return {w: etapa for (w, _n, etapa, _d, _p, _m) in items if not w.startswith("M")}


def match_template(wbs_codes: set[str]) -> tuple[str | None, dict[str, str]]:
    live = {w for w in wbs_codes if w and not w.startswith("M")}
    if not live:
        return None, {}
    best_name, best_cov, best_map = None, 0.0, {}
    for tname, items in TEMPLATES.items():
        tmap = _template_wbs_etapa(items)
        cov = len(live & set(tmap)) / len(live)
        if cov > best_cov:
            best_name, best_cov, best_map = tname, cov, tmap
    if best_cov >= _MATCH_THRESHOLD:
        return best_name, best_map
    return None, {}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.test_customer_view.TestTemplateMatch -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add uc/core/customer_view.py tests/test_customer_view.py
git commit -m "feat: match live project to a template for rich phase names"
```

---

### Task 5: Build the CustomerPlan (phases, milestones, progress, as_of)

Assemble the full plan: group work tasks into phases (rich or generic), roll up progress (duration-weighted), position nothing yet (dates only), and mark milestones reached/upcoming.

**Files:**
- Modify: `uc/core/customer_view.py`
- Test: `tests/test_customer_view.py` (add classes)

**Interfaces:**
- Produces:
  - `@dataclass PhaseBar`: `name: str`, `color: str`, `start: date`, `end: date`, `progress: float`, `done: bool`
  - `@dataclass MilestoneMark`: `name: str`, `day: date`, `reached: bool`
  - `@dataclass CustomerPlan`: `project_name: str`, `phases: list[PhaseBar]`, `milestones: list[MilestoneMark]`, `date_min: date`, `date_max: date`, `as_of: date`, `overall_progress: float`, `matched_template: str | None`
  - `weighted_progress(tasks: list[Task]) -> float`
  - `build(tasks: list[Task], project_name: str, as_of: date | None = None) -> CustomerPlan`
  - `build` drops phases whose tasks have no dates; if NO phase and NO milestone has a date, returns a `CustomerPlan` with empty `phases`/`milestones` (caller reports "needs planned dates").

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_customer_view.py

def _mk(id, name, s=None, e=None, done=False, progress=0.0, actual_end=None):
    return Task(id=id, name=name,
                planned_start=date.fromisoformat(s) if s else None,
                planned_end=date.fromisoformat(e) if e else None,
                done=done, progress=progress,
                actual_end=date.fromisoformat(actual_end) if actual_end else None)


class TestWeightedProgress(unittest.TestCase):
    def test_all_done_is_100(self):
        ts = [_mk(1, "1.1 a", "2026-07-13", "2026-07-15", done=True),
              _mk(2, "1.2 b", "2026-07-15", "2026-07-20", done=True)]
        self.assertEqual(cv.weighted_progress(ts), 100.0)

    def test_duration_weighted(self):
        # a: 2 days @ 0% ; b: 8 days @ 100%  -> (0*2 + 100*8)/10 = 80.0
        ts = [_mk(1, "1.1 a", "2026-07-13", "2026-07-15", progress=0),
              _mk(2, "1.2 b", "2026-07-15", "2026-07-27", progress=100)]
        self.assertEqual(cv.weighted_progress(ts), 80.0)


class TestBuildRich(unittest.TestCase):
    def _machining_tasks(self):
        # a handful of real machining WBS across two etapas + one milestone
        return [
            _mk(1, "2.1  Modelar/adaptar piezas en Fusion", "2026-07-13", "2026-07-20", done=True),
            _mk(2, "2.3  BOM: material, herramienta", "2026-07-20", "2026-07-24", done=True),
            _mk(3, "5.5  Corrida de producción", "2026-08-10", "2026-08-18", progress=50),
            _mk(4, "★ M5  Piezas entregadas", e="2026-09-18"),
        ]

    def test_phases_named_from_template(self):
        plan = cv.build(self._machining_tasks(), "Trabajo Cliente X",
                        as_of=date(2026, 8, 1))
        names = {p.name for p in plan.phases}
        self.assertIn("Diseño", names)      # 2.x → Diseño
        self.assertIn("Maquinado", names)   # 5.x → Maquinado
        self.assertEqual(plan.matched_template, "[PLANTILLA] Proyecto de Maquinado")

    def test_phase_color_from_palette(self):
        plan = cv.build(self._machining_tasks(), "X", as_of=date(2026, 8, 1))
        diseno = next(p for p in plan.phases if p.name == "Diseño")
        self.assertEqual(diseno.color, cv.ETAPA_COLOR["Diseño"])
        self.assertTrue(diseno.done)  # both 2.x tasks done

    def test_milestone_reached_vs_upcoming(self):
        plan = cv.build(self._machining_tasks(), "X", as_of=date(2026, 8, 1))
        m = next(x for x in plan.milestones if x.name == "Piezas entregadas")
        self.assertFalse(m.reached)  # 2026-09-18 > as_of


class TestBuildGeneric(unittest.TestCase):
    def test_generic_fase_grouping_when_no_match(self):
        ts = [_mk(1, "80.1  Cosa interna", "2026-07-13", "2026-07-15"),
              _mk(2, "81.1  Otra cosa", "2026-07-15", "2026-07-20")]
        plan = cv.build(ts, "Proyecto raro", as_of=date(2026, 7, 14))
        self.assertIsNone(plan.matched_template)
        self.assertEqual({p.name for p in plan.phases}, {"Fase 80", "Fase 81"})
        self.assertTrue(all(p.color == cv.ACCENT for p in plan.phases))

    def test_task_without_dates_dropped_from_phase(self):
        ts = [_mk(1, "80.1  sin fechas")]  # no dates
        plan = cv.build(ts, "X", as_of=date(2026, 7, 14))
        self.assertEqual(plan.phases, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_customer_view -v`
Expected: FAIL (missing `weighted_progress`, `build`, dataclasses).

- [ ] **Step 3: Implement the dataclasses + build**

```python
# add to uc/core/customer_view.py

@dataclass
class PhaseBar:
    name: str
    color: str
    start: date
    end: date
    progress: float
    done: bool


@dataclass
class MilestoneMark:
    name: str
    day: date
    reached: bool


@dataclass
class CustomerPlan:
    project_name: str
    phases: list[PhaseBar] = field(default_factory=list)
    milestones: list[MilestoneMark] = field(default_factory=list)
    date_min: date | None = None
    date_max: date | None = None
    as_of: date | None = None
    overall_progress: float = 0.0
    matched_template: str | None = None


def weighted_progress(tasks: list[Task]) -> float:
    total = sum(max(t.duration_days, 1) for t in tasks)
    if not total:
        return 0.0
    acc = sum((100.0 if t.done else float(t.progress)) * max(t.duration_days, 1) for t in tasks)
    return round(acc / total, 1)


def build(tasks: list[Task], project_name: str, as_of: date | None = None) -> CustomerPlan:
    as_of = as_of or date.today()
    work = [t for t in tasks if not is_milestone(t)]
    miles = [t for t in tasks if is_milestone(t)]

    wbs_of = {t.id: parse_wbs(t.name) for t in tasks}
    tname, tmap = match_template({wbs_of[t.id] for t in work if wbs_of[t.id]})

    groups: dict[str, list[Task]] = {}
    for t in work:
        w = wbs_of[t.id]
        if tname and w in tmap:
            key = tmap[w]
        elif w:
            key = f"Fase {wbs_root(w)}"
        else:
            key = "Proyecto"
        groups.setdefault(key, []).append(t)

    phases: list[PhaseBar] = []
    for key, ts in groups.items():
        dated = [t for t in ts if t.planned_start and t.planned_end]
        if not dated:
            continue
        color = ETAPA_COLOR.get(key, ACCENT)
        phases.append(PhaseBar(
            name=key, color=color,
            start=min(t.planned_start for t in dated),
            end=max(t.planned_end for t in dated),
            progress=weighted_progress(ts),
            done=all(t.done for t in ts),
        ))
    phases.sort(key=lambda p: p.start)

    milestones: list[MilestoneMark] = []
    for t in miles:
        day = t.planned_end or t.planned_start
        if not day:
            continue
        reached = t.done or (t.actual_end is not None and t.actual_end <= as_of)
        milestones.append(MilestoneMark(clean_name(t.name), day, reached))
    milestones.sort(key=lambda m: m.day)

    days = ([p.start for p in phases] + [p.end for p in phases]
            + [m.day for m in milestones])
    date_min = min(days) if days else None
    date_max = max(days) if days else None
    overall = weighted_progress(work) if work else 0.0
    return CustomerPlan(project_name, phases, milestones, date_min, date_max,
                        as_of, overall, tname)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m unittest tests.test_customer_view -v`
Expected: PASS (all customer_view tests).

- [ ] **Step 5: Commit**

```bash
git add uc/core/customer_view.py tests/test_customer_view.py
git commit -m "feat: build CustomerPlan (phases, milestones, weighted progress)"
```

---

### Task 6: Position the plan onto a date axis → Chart

Presentation mapping: turn a `CustomerPlan` into a `Chart` of positioned `Row`s, plus the full customer page HTML. Lives in the render layer (depends on core, not vice-versa).

**Files:**
- Modify: `uc/render/gantt_html.py`
- Test: `tests/test_gantt_html.py` (add a class)

**Interfaces:**
- Consumes: `uc.core.customer_view.CustomerPlan`, `PhaseBar`, `MilestoneMark`; `Row`, `Chart`, `render_chart`, `render_page`, `EXTRA_CSS_CUSTOMER`, `fmt_date`, `esc`, `ACCENT`.
- Produces:
  - `plan_to_chart(plan: CustomerPlan) -> Chart`
  - `render_customer_page(plan: CustomerPlan) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_gantt_html.py
from datetime import date

from uc.core.customer_view import CustomerPlan, PhaseBar, MilestoneMark
from uc.render.gantt_html import plan_to_chart, render_customer_page


def _plan():
    return CustomerPlan(
        project_name="Trabajo Cliente X",
        phases=[
            PhaseBar("Diseño", "#3f7cac", date(2026, 7, 13), date(2026, 7, 24), 100.0, True),
            PhaseBar("Maquinado", "#7a6cae", date(2026, 8, 10), date(2026, 8, 18), 50.0, False),
        ],
        milestones=[MilestoneMark("Piezas entregadas", date(2026, 9, 18), False)],
        date_min=date(2026, 7, 13), date_max=date(2026, 9, 18),
        as_of=date(2026, 8, 1), overall_progress=62.0,
        matched_template="[PLANTILLA] Proyecto de Maquinado",
    )


class TestPlanToChart(unittest.TestCase):
    def test_first_phase_starts_at_zero(self):
        chart = plan_to_chart(_plan())
        first = chart.rows[0]
        self.assertEqual(first.kind, "phase")
        self.assertAlmostEqual(first.left, 0.0, places=3)

    def test_milestone_row_present_and_positioned(self):
        chart = plan_to_chart(_plan())
        ms = [r for r in chart.rows if r.kind == "milestone"]
        self.assertEqual(len(ms), 1)
        self.assertAlmostEqual(ms[0].left, 100.0, places=3)  # date_max

    def test_today_line_within_range(self):
        chart = plan_to_chart(_plan())
        self.assertIsNotNone(chart.today_left)
        self.assertTrue(0 < chart.today_left < 100)


class TestRenderCustomerPage(unittest.TestCase):
    def test_page_is_self_contained_and_leak_safe(self):
        html = render_customer_page(_plan())
        self.assertIn("<style>", html)
        self.assertIn("Trabajo Cliente X", html)
        self.assertIn("62", html)                 # overall progress in header
        self.assertNotIn("ruta crítica", html)    # no internal jargon
        self.assertNotIn("días hábiles", html)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m unittest tests.test_gantt_html -v`
Expected: FAIL (`cannot import name 'plan_to_chart'`).

- [ ] **Step 3: Implement `plan_to_chart` + `render_customer_page`**

```python
# add to uc/render/gantt_html.py
from uc.core.customer_view import CustomerPlan
from uc.core.palette import ACCENT


def _pct(day, dmin, span_days: int) -> float:
    return (day - dmin).days / span_days * 100


def plan_to_chart(plan: CustomerPlan) -> Chart:
    span = max((plan.date_max - plan.date_min).days, 1)
    rows: list[Row] = []
    for ph in plan.phases:
        left = _pct(ph.start, plan.date_min, span)
        width = max(_pct(ph.end, plan.date_min, span) - left, 0.9)
        rows.append(Row(label=ph.name, kind="phase", left=left, width=width,
                        color=ph.color, progress=ph.progress, reached=ph.done))
    for m in plan.milestones:
        rows.append(Row(label=f"{m.name}  ({fmt_date(m.day)})", kind="milestone",
                        left=_pct(m.day, plan.date_min, span), color=ACCENT,
                        reached=m.reached))
    today_left = (_pct(plan.as_of, plan.date_min, span)
                  if plan.date_min <= plan.as_of <= plan.date_max else None)
    step = 7 / span * 100
    meta = (f"Avance <b>{plan.overall_progress:.0f}%</b> · "
            f"{len(plan.phases)} fases · {len(plan.milestones)} hitos · "
            f"al {fmt_date(plan.as_of)} {plan.as_of.year}")
    subtitle = "Cronograma del proyecto — fases y fechas clave."
    return Chart(title=plan.project_name, subtitle=subtitle, meta=meta,
                 rows=rows, step=step, today_left=today_left)


def render_customer_page(plan: CustomerPlan) -> str:
    chart = plan_to_chart(plan)
    header = (
        '  <p class="eyebrow">Unicontrol · Avance de proyecto</p>\n'
        f'  <h1>{esc(plan.project_name)}</h1>\n'
        f'  <p class="lede">Fases principales y fechas clave del proyecto. '
        f'Avance general <b>{plan.overall_progress:.0f}%</b> al {fmt_date(plan.as_of)} '
        f'{plan.as_of.year}.</p>\n'
        '  <div class="legend"><div class="grp">'
        '<span class="lg"><span class="swatch-bar"></span>Fase</span>'
        '<span class="lg"><span class="swatch-ms"></span>Hito pendiente</span>'
        '<span class="lg"><span class="swatch-ms" style="background:var(--accent)"></span>'
        'Hito cumplido</span>'
        '</div></div>'
    )
    body = render_chart(chart)
    return render_page(header, body, extra_css=EXTRA_CSS_CUSTOMER)
```

- [ ] **Step 4: Run to verify pass (and the whole suite)**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: all PASS, golden included.

- [ ] **Step 5: Commit**

```bash
git add uc/render/gantt_html.py tests/test_gantt_html.py
git commit -m "feat: position CustomerPlan on a date axis + customer page renderer"
```

---

### Task 7: Odoo read helper — fetch one project by id

**Files:**
- Modify: `uc/connectors/odoo_project.py`

**Interfaces:**
- Produces: `ProjectOdooClient.project_by_id(self, project_id: int) -> dict | None` → `{"id", "name"}` or `None`.

- [ ] **Step 1: Add the method (read-only)**

Insert after `active_projects` in `uc/connectors/odoo_project.py`:

```python
    def project_by_id(self, project_id: int) -> dict | None:
        rows = self.search_read(
            "project.project", [["id", "=", project_id]], ["id", "name"], limit=1
        )
        return rows[0] if rows else None
```

- [ ] **Step 2: Sanity-check import (no Odoo call)**

Run: `python -c "import ast,sys; ast.parse(open('uc/connectors/odoo_project.py',encoding='utf-8').read()); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add uc/connectors/odoo_project.py
git commit -m "feat: ProjectOdooClient.project_by_id (read-only)"
```

---

### Task 8: CLI entrypoint `gen_customer_gantt.py` + live verification

Thin wrapper: read one live project (read-only), build the plan, render, print HTML. Then verify end-to-end against a real Odoo project and publish the artifact.

**Files:**
- Create: `scripts/gen_customer_gantt.py`

**Interfaces:**
- Consumes: `load_config`, `add_hermes_to_path` (`uc.core.config`); `ProjectOdooClient`; `build` (`uc.core.customer_view`); `render_customer_page` (`uc.render.gantt_html`).

- [ ] **Step 1: Write the CLI**

```python
# scripts/gen_customer_gantt.py
"""Generate a customer-facing HTML Gantt for ONE live Odoo project (READ-ONLY).

    python scripts/gen_customer_gantt.py --project-id 5 [--as-of YYYY-MM-DD] > customer.html

Shows only milestones + synthesized phase bars with gentle progress — never individual
internal tasks. Publish the resulting HTML as a shareable artifact.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uc.core.config import add_hermes_to_path, load_config  # noqa: E402
from uc.core.customer_view import build  # noqa: E402
from uc.render.gantt_html import render_customer_page  # noqa: E402

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
        print(f"ERROR: project [{args.project_id}] {proj['name']} has no tasks",
              file=sys.stderr)
        return 2

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    plan = build(tasks, project_name=proj["name"], as_of=as_of)
    if not plan.phases and not plan.milestones:
        print(f"ERROR: project [{args.project_id}] {proj['name']} has no planned dates — "
              "add planned_date_begin / date_deadline before sharing.", file=sys.stderr)
        return 3

    print(render_customer_page(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify it imports and shows help (no Odoo call)**

Run: `./.venv/Scripts/python.exe scripts/gen_customer_gantt.py --help`
Expected: usage text listing `--project-id` and `--as-of`, exit 0.

- [ ] **Step 3: Live end-to-end (read-only) against a real project**

The templates live at ids `[5]` and `[6]`. Run:
```bash
./.venv/Scripts/python.exe scripts/gen_customer_gantt.py --project-id 5 --as-of 2026-08-01 > "$TMP/customer_5.html"
```
Expected: exit 0; the HTML contains the project name, phase names (Diseño/Compras/Maquinado/…), a few `◆`-style milestones, and NONE of the internal task names like "Estrategia de maquinado". Confirms template-match + leak-safety on real data. (Reads only — writes nothing to Odoo.)

- [ ] **Step 4: Full test suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: all PASS (golden + palette + customer_view + gantt_html).

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_customer_gantt.py
git commit -m "feat: gen_customer_gantt CLI — customer-facing live Gantt (read-only)"
```

- [ ] **Step 6: Publish the artifact (agent action, after user review of the HTML)**

Publish `$TMP/customer_5.html` as a shareable Artifact and give the user the URL. Keep the same file path on later re-publishes to preserve the URL.

---

## Self-Review

**Spec coverage:**
- Milestones + synthesized phase bars → Tasks 3, 5. ✅
- Mix phase-grouping (template rich / generic fallback) → Tasks 4, 5. ✅
- Plan + gentle progress (today line, % per phase, reached/upcoming) → Tasks 5, 6; renderer additive features Task 2. ✅
- Shared renderer refactor, template output identical → Tasks 1, 2 (golden test). ✅
- `--project-id` CLI, read-only Odoo → Tasks 7, 8. ✅
- Error handling (not found / no tasks / no dates) → Task 8 return codes; missing-date phase drop → Task 5. ✅
- No jargon / Spanish / no alarm colors → Task 6 (`render_customer_page`, meta), asserted in tests. ✅
- Testing pure logic via `unittest` → Tasks 3–6. ✅

**Placeholder scan:** The only intentional "paste verbatim" is `BASE_CSS` in Task 2, Step 3 — this is a mechanical move of the existing `<style>` body, guarded by the Task 1 golden test which fails loudly if a byte differs. All other steps contain complete code.

**Type consistency:** `Row`/`Chart` fields (`left`, `width`, `progress`, `reached`, `crit`, `lead`, `dur_label`, `wbs`) defined in Task 2 and consumed in Task 6. `PhaseBar`/`MilestoneMark`/`CustomerPlan` fields defined in Task 5 and consumed in Task 6. `build(tasks, project_name, as_of)` signature consistent between Tasks 5 and 8. `match_template(set) -> (name, map)` consistent Tasks 4→5. `project_by_id` consistent Tasks 7→8.

**Note for the implementer (Task 2):** the biggest risk is reproducing the template markup byte-for-byte. Treat `tests.test_template_golden` as the oracle: extract, run it, and adjust `render_chart`/`Row` (notably the `wbs` span, the `--total` variable, and the exact whitespace/newlines between `<div class="gantt">` and the first row) until it is green. Only then move on.
