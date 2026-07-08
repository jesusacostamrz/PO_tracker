# Unicontrol PM Tools — Complete Build Plan (all phases)

> Executable spec for every phase of [`ROADMAP.md`](ROADMAP.md). Owner legend: 👤 **You (Jesús)**
> · 🤖 **Me (Claude)** · 🤝 **Shared** (I build; you run/authorize). Source plan:
> `~/.claude/plans/now-draft-a-very-lively-pebble.md`.

## Decisions locked
- Code lives in a **standalone `Unicontrol/` package** that **imports Hermes connectors** from the
  sibling `hermes/` package (both on the same VPS) and subclasses `OdooClient` to add project
  methods. One source of truth for connectors; business logic is Unicontrol-owned.
- **Alerts** go out by adding the **`gmail.send`** scope to the existing bot
  (`pounicontrol@gmail.com`) + a new send method. *(Today's Gmail connector is `gmail.modify` =
  read/label only — it cannot send. This is a real Phase-1 task, not free.)*
- Odoo is **Custom plan** → Project + Gantt + dependencies + Planning available.

## Load-bearing unknown → resolve first
Exact `project.task` field names for planned start/end and dependencies are Odoo-version-specific
and can't be checked without hitting your Odoo. **Step 0 is a read-only schema probe** before any
logic is built on assumed names. All Odoo field names live in `config/unicontrol.config.yaml`
(`odoo_project.fields`), never hardcoded.

## Guiding invariants (carried from Hermes — do not violate)
- **`runtime.dry_run: true` is the default.** Agents log intended actions; only `--live` writes.
- **Never message the customer automatically.** The agent drafts a client heads-up and routes it
  to a human for approval — the mirror of Hermes's "annotate, never confirm the SO."
- **Odoo writes stay narrow + reversible:** internal chatter notes on tasks and (Phase 1b) draft
  tasks in a "Por revisar" stage. Never touch customer-facing SO fields.
- **Idempotent alerts:** never re-send the same alert for the same task the same day.

---

## Architecture & reuse
Own package name `uc` avoids a `connectors/` name-clash with Hermes.
```
Unicontrol/
  config/unicontrol.config.yaml     # field mappings, thresholds, channels, schedule, dry_run
  requirements.txt
  .secrets/.env                     # own copies of ODOO/LLM keys; new send-scoped gmail token
  uc/
    core/config.py                  # load_config/secret (Hermes pattern) + hermes-path bootstrap
    core/models.py                  # Project/Task dataclasses normalized from Odoo rows
    core/critical_path.py           # DAG longest-path + slack (deterministic, stdlib-only)
    core/risk.py                    # at-risk rules -> RiskItem list (deterministic, stdlib-only)
    core/baseline.py                # snapshot planned dates at approval (stored in Sheet)
    core/digest.py                  # weekly per-project summary (LLM draft + table)
    core/plan_builder.py            # Phase 1b: client Gantt -> internal backward plan
    core/actions.py                 # dry_run + audit-to-Sheet + idempotency (Hermes actions pattern)
    connectors/odoo_project.py      # ProjectOdooClient(OdooClient) — adds project.* methods
    connectors/notifier.py          # Gmail SEND wrapper (new gmail.send scope)
  scripts/test_project.py           # STEP 0 probe (read-only)
  scripts/test_logic.py             # runnable unit check of critical_path + risk (no Odoo needed)
  scripts/delay_watch.py            # Phase 1 entrypoint (mirrors hermes/scripts/intake.py)
  scripts/plan_build.py             # Phase 1b entrypoint
```
- **Reuse mechanism:** `uc/core/config.py` puts the sibling `hermes/` root on `sys.path`; code does
  `from connectors.odoo_client import OdooClient` / `from connectors.llm_client import LLMClient` /
  `from core.po_parser import extract_text, render_pages_as_data_urls`; Unicontrol's own code lives
  under `uc.*`. Reused as-is: `LLMClient`, `SheetsClient`, `po_parser` render path, config loader pattern.
- **State store:** a Google Sheet "Unicontrol PM" (reuse `SheetsClient` + the `setup_sheet.py`
  pattern) with tabs: `Baselines`, `AtRisk`, `Alerts` (idempotency log), `Approvals`, `Audit`.

---

## Step 0 — Probe Odoo schema (read-only, do FIRST) · 🤝
`scripts/test_project.py`: authenticate as `Unicontrolbot`, call `project.task` `fields_get`, read the
pilot's tasks. Confirm real names for: planned start/end (`planned_date_begin`/`planned_date_end` vs
`date_deadline`), dependencies (`depend_on_ids`), `stage_id`, `user_ids`, `milestone_id`,
`kanban_state`, progress. Lock them into `odoo_project.fields`. **Verify:** script prints the fields;
nothing built on guessed names. *(Requires 👤 the bot to have Project rights — see Phase 0.)*

## Phase 0 — Odoo substrate (configure, NO code) · ~1 wk
- 👤 Grant `Unicontrolbot` **Project** access; enable the Project app.
- 👤 Build a reusable **Project Template** with the 6 etapas (Diseño → Revisión de Diseño → Compras →
  Maquinado → Ensamble → Entrega), each a task with owner + planned dates + dependency.
- 👤 Instantiate **one pilot project** from the template, linked to its Sales Order.
- **Verify:** pilot shows the 6 etapas with dates + dependency arrows in Odoo Gantt.

## Phase 1 — "Delay Watch" agent · ~1–2 wk
- 🤖 `connectors/odoo_project.py` — `ProjectOdooClient(OdooClient)`: `active_projects()`,
  `project_tasks(ids)` (bulk, config field-map), `post_task_note()`, `set_task_dates()`.
- 🤖 `connectors/notifier.py` — `send_email(to, subject, body)` via Gmail `messages().send`.
  🤝 requires re-consent with `gmail.send` added.
- 🤖 `core/critical_path.py` + `core/risk.py` — DAG longest-path + slack; at-risk rules
  (**overdue**, **near-deadline no progress**, **predecessor slipped onto critical path**).
  Deterministic, stdlib-only → unit-tested via `scripts/test_logic.py`.
- 🤖 `core/baseline.py` — snapshot planned dates to the `Baselines` tab on approval.
- 🤖 `core/actions.py` + `core/digest.py` — mirror `hermes/core/actions.py`: dry_run branch, audit to
  Sheet, idempotent alert log. Internal alert = Odoo task note + `send_email`. Critical-path slip =
  **LLM-drafted client heads-up to `Approvals` (+ emailed to approver) — never sent to the client.**
- 🤖 `scripts/delay_watch.py` — entrypoint mirroring `intake.py` (argparse `--live`, dry_run default,
  `--watch`, stats). Nightly via systemd timer.
- **👤 you:** pick approver; dept→email list; re-consent gmail.send; hand me the pilot.
- **Verify:** `delay_watch.py --dry` on the pilot with a seeded overdue task — read console + `AtRisk`
  tab + drafted message; hand-check the critical path (tails: first task, delivery task, slipped one).

## Phase 1b — "Plan Builder" agent · ~1–2 wk
- 🤖 `core/plan_builder.py` — reuse `po_parser` render path + `LLMClient` vision/JSON with a new prompt
  to extract phases/dates from a **client Gantt**; then a deterministic **backward scheduler**
  (delivery − durations − supplier lead-times, respecting dependencies) → **draft tasks** in a
  "Por revisar" stage for human review.
- Surfaces critical-path (longest-lead) components → "define these now" list (attacks bottleneck #2).
- 🤖 `scripts/plan_build.py` — `plan_build.py <gantt.pdf> --project <id> [--live]`.
- **👤 you:** 2–3 past client Gantts (PDF) + real phase durations; a starter supplier lead-time list.
- **Verify:** feed a past Gantt; diff generated plan vs. actual; check tails (longest-lead comp, slipped etapa).

## Phase 2 — Backlog (after 0/1/1b) · lower resolution, honest uncertainty
- **Components / lead-times (2nd priority) 🤖🤝:** `scripts/dwg_bom.py` + `core/dwg_reader.py`.
  ⚠️ **Spike first:** raw **DWG is not vision-friendly** — read a **DXF (`ezdxf`)** or **PDF/PNG export
  from Fusion**. Output = dimension/BOM list joined to lead-times → feeds Phase 1b. 👤 sample export.
- **Design-review assist (optional, low confidence) 🤖:** vision check of a Fusion export vs a rework
  checklist (costillas/alojamientos/cables). The *gate* is already a Phase-0 task, not code.
- **Sales / CRM 🤖🤝:** Odoo CRM + AI visit-note capture (voice→CRM) + a "vendido vs comprado" report.
  Relationship issues are human, not AI.
- **Machine utilization 🤝👤:** **no data today.** Capture runtime via Odoo **MRP** work centers first
  (non-AI) **before** any analytics. Separate track.

---

## Sequencing
**Step 0 probe → Phase 0 (Odoo config) → Phase 1 (Delay Watch) → Phase 1b (Plan Builder) → Phase 2.**
Step 0 + Phase 0 + Phase 1 is the shippable-before-next-review target and reuses Hermes.

## Verification (end-to-end, per phase)
- **Step 0:** field names printed and locked in config.
- **P0:** pilot Gantt renders 6 etapas + dependencies in Odoo.
- **P1:** `delay_watch.py --dry` flags a seeded overdue task, computes the correct critical path, and
  drafts a sensible client message to `Approvals` — read the actual output.
- **P1b:** generated backward plan diffed against a real past job; tails checked.
- **P2:** DWG spike proves a readable export path before building the BOM reader.
