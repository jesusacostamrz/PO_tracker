# Session Handoff — Hermes purchase-order agent: plan approved, PDF + skill installed

## Where it started
User wants a "Hermes" agent to centralize customer purchase orders that currently scatter across multiple salespeople's inboxes (orders getting lost, no backlog visibility). This session was planning only: clarify requirements, design the workflow, recommend a better approach, produce a plan PDF for tomorrow, and properly install a `session-handoff` skill. Implementation has NOT started — it begins 2026-06-27.

## Decisions locked + what shipped
- Approved architecture for Hermes PO-intake/order-tracking agent — plan at `C:\Users\jesus\.claude\plans\i-want-to-create-soft-duckling.md`.
- Intake = salespeople forward PO emails to one dedicated **Gmail** (Google Workspace) mailbox; cron poll ~15 min.
- **Odoo.sh**, used narrowly (quotes to match against + invoices). On a confident match Hermes writes the customer PO# into the SO `client_order_ref`, attaches the PO PDF, posts a chatter note — **never auto-confirms the SO**.
- **Source of truth for order status = a Google Sheet "PO Tracker"** that Hermes builds/maintains, bidirectionally linked to Odoo. Sheet split into **Hermes-owned columns** vs **human-owned columns** so the agent never clobbers manual edits.
- Lifecycle (granular): Needs-review → Received → Matched → In production → Shipped → Invoiced → Closed. In-production/Shipped are human-set in the Sheet; **Invoiced is hybrid** (Hermes suggests from the Odoo invoice, a human confirms).
- Matching signals: customer identity + customer PO# + line items + total (no quote number from us is reliably on the PO).
- Reminders: daily per-salesperson email digest + manager rollup; weekly Sheet dashboard for review.
- Runtime: Claude **skills** + **scheduled cron routines**, with thin Python connectors for Gmail / Odoo (xmlrpc) / Sheets I/O.
- Shipped: plan PDF at `C:\Users\jesus\Documents\Claude Code\Hermes-Agent-Plan.pdf` (186 KB, rendered via Chrome headless).
- Shipped: installed `session-handoff` skill at `C:\Users\jesus\Documents\Claude Code\.claude\skills\session-handoff\SKILL.md` (fixed nateh→jesus paths; deleted the old flat `skills\session-handoff-SKILL.md` and its empty folder).
- Shipped: project memory written.

## Key files for next session
- Plan file (read first): `C:\Users\jesus\.claude\plans\i-want-to-create-soft-duckling.md`
- Plan PDF (same content): `C:\Users\jesus\Documents\Claude Code\Hermes-Agent-Plan.pdf`
- Memory: `C:\Users\jesus\.claude\projects\c--Users-jesus-Documents-Claude-Code\memory\hermes-agent-project.md` and `...\memory\MEMORY.md`
- Installed skill: `C:\Users\jesus\Documents\Claude Code\.claude\skills\session-handoff\SKILL.md`
- This handoff: `C:\Users\jesus\Documents\Claude Code\PO tracker\session-handoff-2026-06-26.md`

## Running state
- Background processes: none
- Dev servers / ports: none
- Open worktrees / branches: none (working dir is not a git repo)

## Verification — how to confirm things still work
- Open `C:\Users\jesus\Documents\Claude Code\Hermes-Agent-Plan.pdf` — full plan renders (~186 KB).
- `/clear` or start a new session, then check `/session-handoff` is an available command — confirms the skill installed correctly.
- No code exists yet, so nothing to build/test; implementation starts 2026-06-27.

## Deferred + open questions
- Deferred: all implementation (Python connectors, the two skills `process-po-inbox` + `daily-order-digest`, cron routines, scaffolding the PO Tracker sheet) — starts 2026-06-27.
- Open: Odoo URL + database name (needed for the Odoo connector).
- Open: list of salespeople with their Gmail addresses, for the Gmail ↔ Odoo user ↔ manager mapping.
- Open: which setup track to start first (Google / Odoo / runtime).
- Note: "PO Tracker" is currently a planned Google Sheet that does not exist yet; the local `PO tracker\` folder holds this handoff.

## Pick up here
Start Track 1 (Google): create the Hermes mailbox + a Cloud project with Gmail API and Sheets API enabled and credentials, then scaffold the PO Tracker sheet — and collect the Odoo URL/db and salesperson Gmail list along the way.
