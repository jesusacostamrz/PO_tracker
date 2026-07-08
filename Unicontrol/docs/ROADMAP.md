# Unicontrol — Project Planning & Delay Early-Warning · Roadmap

> First doc of the Unicontrol initiative. Source plan:
> `~/.claude/plans/now-draft-a-very-lively-pebble.md`.

## Why this exists
Unicontrol delivers custom automation projects **late in nearly every recent case** — not
because of capacity, but because **no project has an internal plan** and delays are caught
**too late to warn the client**. This initiative gives every project an internal plan (derived
from the client's Gantt) and an agent that raises delays *before the client asks*.

**Stack:** Odoo **Custom plan** (Sales/CRM live today; Project + Gantt + all apps available) +
Fusion 360. **Approach:** buy/configure the standard parts, **build the edge agents** (like
Hermes). **First target:** project planning & delay early-warning.

**Guiding rule:** the task store lives in **Odoo**; the intelligence lives in the **agent**.
Odoo won't compute critical path or schedule variance — the agent will.

## Owner legend
- 👤 **You (Jesús)** — needs a login, credential, decision, or approval.
- 🤖 **Me (Claude)** — I build it fully (code, config, docs).
- 🤝 **Shared** — I build it; you provide a secret / authorize / approve a write.

## Reused Hermes assets (don't rebuild)
| Asset | Reuse for |
|---|---|
| `hermes/connectors/odoo_client.py` | Generic `execute`/`search_read` ORM — extend with `project.project` / `project.task` methods (same pattern as the `sale.order` helpers). Bot user + `ODOO_API_KEY` already exist. |
| `hermes/connectors/llm_client.py` | Provider-agnostic (OpenAI/GLM) drafting + vision. |
| `hermes/core/po_parser.py` | PDF-text + `pypdfium2` vision path — reuse to read client Gantts. |
| `hermes/config/hermes.config.yaml` (`reminders:`, `runtime.dry_run`) | Nightly scheduler + safe dry-run default for alerts. |

---

## Phase 0 — Substrate in Odoo (configure, **no AI**) · ~1 wk
The precondition: you can't alert on a delay if there's no plan to watch.
- Turn on **Odoo Project**; one project per job, linked to its Sales Order.
- Fixed etapa template for every project: **Diseño → Revisión de Diseño → Compras → Maquinado
  → Ensamble → Entrega**, each task with **owner, planned start/end, dependency** on the prior etapa.
- Bakes in two junta agreements for free: the **mandatory design-review gate** and a concrete
  thing to review in the **weekly juntas**.

**AI needed:** none.

- [ ] 👤 Confirm the 6 etapas + owners with the team.
- [ ] 👤 Enable the Project app in Odoo.
- [ ] 👤 Create **one pilot project** manually as the Phase 1 test bed.

## Phase 1 — "Delay Watch" agent (**the first build**) · ~1–2 wk
New Hermes-style `scripts/delay_watch.py` + `core/` logic. Computes the four things Odoo can't:
1. **Baseline** — snapshot planned dates on plan approval (Odoo overwrites, keeps none).
2. **Critical path** — the task chain that drives the delivery date.
3. **At-risk rules** — overdue, or near-deadline with no progress, or a predecessor that
   slipped onto the critical path.
4. **Alerts** — internal ping (owner + coordinator); when the critical path slips, an
   **LLM-drafted client heads-up for human approval before send**; weekly per-project digest.

**AI needed:** deterministic at-risk / critical-path logic in Python; **LLM only for the
natural-language messages + weekly digest.** Runs nightly via the reminders scheduler; starts
in `dry_run`.

- [ ] 🤝 Approve me extending `odoo_client` with `project.task` read/write.
- [ ] 👤 Pick alert channel: **email via existing Gmail (zero new cost)** or WhatsApp (Twilio/Meta creds).
- [ ] 👤 Decide **who approves** client messages before send.
- [ ] 🤝 Hand me the Phase 0 pilot project to test against.
- [ ] 🤖 Build + verify the agent in `dry_run`.

## Phase 1b — "Plan Builder" agent · ~1–2 wk
- LLM reads the **client Gantt (PDF/image)** + etapa template + past-project durations → drafts
  an internal **backward plan** (entrega − ensamble − maquinado − proveedor lead-time − diseño)
  → writes `project.task` rows into Odoo for human review.
- Side effect: forces **components + supplier lead-times to be defined at quote time** —
  directly attacks the #2 bottleneck.

**AI needed:** `llm_client` (text + vision) reusing `po_parser`'s render path; `odoo_client` write path.

- [ ] 👤 Give me **2–3 real past client Gantts (PDF)** + their actual phase durations.
- [ ] 👤 Provide a starter **supplier lead-time list**.
- [ ] 🤖 Build + verify against a past job (diff generated plan vs. what actually happened).

## Phase 2 — Backlog (after 0 / 1 / 1b) · sequenced by leverage
- **Components / lead-times (2nd priority):** finish the in-dev **DWG→BOM** tool (vision/LLM on
  the drawing) + supplier lead-time table → feeds Phase 1b. · 👤 sample DWG + lead-time data.
- **Design-review:** already mandatory via Phase 0. *Optional later:* vision check of a Fusion
  export vs a rework checklist (costillas / alojamientos / cables). Low confidence, nice-to-have.
- **Sales / CRM:** use Odoo CRM (owned) + AI visit-note capture (voice→CRM) + a "vendido vs
  comprado" report. *Relationship issues (Signify / Norma / ABC) are human, not AI.*
- **Machine utilization:** **no data exists today** (the <50% is a guess). Capture machine
  runtime first (Odoo **MRP** work centers, on the Custom plan) **before** any analytics.
  Separate track.

---

## Two honest risks (say these to the team)
- **Adoption:** alerts go blind if task status isn't updated. Keep updates minimal and wire the
  agent's weekly *at-risk* list into the 5–20 min juntas so the human loop closes.
- **Cold-start estimates:** the first plans will be wrong (no duration baseline). Capture
  actuals; the system becomes trustworthy after ~3–4 projects.

## Verification (per phase)
- **P0:** open Odoo — pilot project shows the 6 etapas with dates + dependencies in Gantt.
- **P1:** run `delay_watch.py` in `dry_run` on the pilot — confirm it flags a deliberately
  overdue task and drafts a sensible client message (read the actual output, don't assume).
- **P1b:** feed one real past Gantt — diff the agent's backward plan vs. what actually happened;
  check the tails (longest-lead component, the etapa that slipped).

## Sequence
**P0 → P1 → P1b → P2.** P0 + P1 alone move the needle on the #1 pain and reuse Hermes — the
shippable-before-next-review target.
