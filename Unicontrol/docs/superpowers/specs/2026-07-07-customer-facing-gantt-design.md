# Customer-Facing Live Gantt — Design

**Date:** 2026-07-07
**Status:** Approved (design), pending implementation
**Owner:** Jesús

## Problem

We can already generate a beautiful, self-contained HTML Gantt for the two PMI
schedule *templates* (`scripts/gen_gantt_artifact.py`). We want to point the same
capability at a **live Odoo project** and produce a page that is safe and useful to
**share with a customer**.

A customer view must be a deliberate *subset* of the internal plan: it must never leak
internal task detail by accident. The internal projects are flat (no parent/child
nesting) — the WBS lives as a text prefix in each task name (`"1.1  ..."`,
`"★ M1  ..."`), and every real task is at WBS depth 2, so a naïve "indentation level"
filter would hide nothing. Instead we show **milestones + one synthesized phase bar per
phase**, so individual internal task names never reach the customer.

## Decisions (locked)

1. **Customer rows = milestones + synthesized phase bars.** No individual internal task
   rows are ever rendered. Leak-safe by construction.
2. **Phase grouping = mix path.** Match the live project's tasks back to
   `MACHINING`/`INTEGRATION` by WBS coverage; on a confident match recover the real
   `etapa` (phase **name + color**). Otherwise fall back to generic "Fase N" grouping by
   WBS-major integer (single accent color); with no WBS at all, a single "Proyecto" bar.
3. **Plan + gentle progress.** Show a `today` line, a `% complete` per phase, and each
   milestone as ✓ reached / upcoming. Neutral styling for behind-schedule — no alarm
   colors (that is internal Delay Watch's job, not the customer's).
4. **Shared renderer refactor is in scope.** Extract the existing renderer into a shared
   module used by BOTH the template artifact and the customer Gantt (no drift). The
   template artifact's output stays byte-for-byte identical.
5. **Primary handle = `--project-id`.** Matches how projects are already referenced.
6. **Read-only on Odoo.** The tool only reads tasks; it writes nothing.

## Architecture

One shared presentation engine, two data sources that each pre-position their rows.

```
uc/render/gantt_html.py       NEW. Pure presentation. Input: Chart{title, subtitle, meta,
                              rows[]} where each Row is ALREADY positioned
                              (left%, width%, color, kind, progress, reached, label).
                              Output: a self-contained HTML page (theme-aware CSS moved
                              here from gen_gantt_artifact.py). Knows nothing about Odoo,
                              scheduler, CPM, or templates.

uc/core/customer_view.py      NEW. Pure logic (no Odoo, no HTML). list[Task] -> CustomerPlan
                              { phases[], milestones[], date_min, date_max, as_of }.
                              Fully unit-testable.

scripts/gen_customer_gantt.py NEW. Thin CLI. Reads ONE live Odoo project (read-only),
                              runs customer_view, positions rows by real dates on the
                              project's date axis, calls the renderer, prints HTML to stdout.

scripts/gen_gantt_artifact.py REFACTORED. Builds Rows via scheduler/CPM and calls the
                              shared renderer. Output must stay byte-for-byte identical.

uc/connectors/odoo_project.py Small helper: fetch one project (by id, optional name lookup),
                              reusing existing load_tasks(). No new write paths.
```

**Key simplification:** live Odoo tasks already carry real `planned_start`/`planned_end`
(or `deadline`). So the customer path needs **no scheduler and no CPM** — it positions
bars directly on a `date_min -> date_max` axis. The renderer only ever draws
pre-positioned rows; each caller computes positions in its own way (template path via
working-day scheduler + CPM; customer path via real dates).

## Data flow (customer path)

```
project_id
  -> ProjectOdooClient.load_tasks([id])          # real dates, progress, done, name w/ WBS
  -> customer_view.build(tasks, as_of)           # detect phases + milestones, roll up
       - optional match against MACHINING/INTEGRATION for etapa name+color
  -> CustomerPlan{ phases[], milestones[], date_min, date_max, as_of }
  -> position rows on date axis (left%, width% per phase/milestone)
  -> gantt_html.render(chart)                     # self-contained HTML
  -> stdout -> publish as Artifact
```

## customer_view logic (the heart)

- **Milestone detection:** task name starts with `★` OR its parsed WBS matches `M\d+`.
- **WBS parse:** regex `^★?\s*(M?\d+)(?:\.\d+)*` against the task name; the captured
  leading token is the WBS root. Milestones use the `M\d+` form.
- **Phase detection:**
  1. **Rich path** — match the project's set of parsed WBS codes against each template's
     WBS set; if coverage of a template is high enough (threshold, e.g. ≥ 0.6 of live
     non-milestone tasks map to a template WBS), adopt that template: each task's WBS →
     its `etapa` (phase name) and the phase's color comes from `ETAPA_COLOR`.
  2. **Fallback** — no confident match → group non-milestone tasks by WBS-major integer,
     labeled "Fase 1/2/3…", single accent color. No WBS at all → one "Proyecto" bar
     spanning all dated tasks.
- **Phase bar:** span = `min(planned_start) -> max(planned_end)` over that phase's
  non-milestone tasks that have dates; **% complete** = duration-weighted mean of task
  `progress` (a `done` task counts as 100); phase shows ✓ when all its tasks are done.
- **Milestone row:** date = `planned_end`/`deadline`; **reached** when `done` OR
  `actual_end <= as_of`.
- **as_of** defaults to today; overridable via `--as-of` for reproducible output/tests.

## Renderer additions (vs. current template renderer)

- A **progress fill** inside a phase bar (two-layer bar: track + filled portion).
- A **today vertical line** positioned on the same axis.
- Milestone diamonds styled **reached vs upcoming**.
- Customer variant **omits** internal jargon (no "ruta crítica", no "días hábiles");
  meta line reads as customer status (e.g. "En progreso · X% completado · al <fecha>").
- Shared CSS keeps the existing theme-aware light/dark behavior and horizontal-scroll
  containment.

## Invocation & delivery

```bash
python scripts/gen_customer_gantt.py --project-id 5 [--as-of YYYY-MM-DD] > customer.html
```

Then publish `customer.html` as a shareable Artifact. Read-only on Odoo; safe to run
against live projects at any time.

## Error handling

- Project id not found / project has no tasks → clear message, non-zero exit.
- Tasks missing dates → excluded from their phase's span but still counted toward
  progress; a phase with **no** dated tasks is dropped with a warning.
- No dates anywhere in the project → the tool reports that the project needs planned
  dates rather than emitting an empty chart.
- Ambiguous / weak template match → silently use the generic fallback (never guess a
  wrong phase name).

## Testing (TDD)

`customer_view` and the positioning math are pure → unit tests with fixture `Task` lists:

- Rich path: WBS present, matches a template → correct phase names, colors, spans.
- Generic fallback: no WBS / no match → "Fase N" grouping.
- Milestone reached vs upcoming across a chosen `as_of`.
- Progress rollup: all-done phase = 100 / ✓; partial = weighted value.
- Missing-date handling: task without dates excluded from span; phase with no dated
  tasks dropped.
- Positioning math: given a `date_min/date_max` axis, rows get correct `left%`/`width%`.

Renderer is verified by asserting row positions and structural HTML, not pixels. Existing
template-artifact output is protected by a byte-identical check (or visual re-publish).

## Out of scope (YAGNI)

- Reading arbitrary non-template projects with rich phase names (fallback is enough).
- Writing anything back to Odoo.
- Multi-project / portfolio pages (one project per page).
- Localization beyond the existing Spanish output.
