# Unicontrol

Internal AI tooling for **Unicontrol y Gabinetes del Pacífico** — beyond the Hermes PO
tracker (`../hermes/`). Home for the operations initiative that came out of the company
review meeting: give every custom-automation project an **internal plan** and catch **delays
before the client does**.

The recurring problem: projects ship late because there's no internal build plan and slippage
is caught too late to warn the customer. The fix is a shared task store in **Odoo** plus
**edge agents** (built in the Hermes style) that add the intelligence Odoo lacks — critical
path, schedule variance, and proactive delay alerts.

## Docs
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — **start here.** Phased build plan (Odoo substrate →
  Delay Watch agent → Plan Builder agent → backlog), the AI agent per phase, and owner-tagged
  tasks (👤 you / 🤖 me / 🤝 shared).

## Status
📌 **Planning.** Roadmap approved; no code yet. Next action is Phase 0 (configure Odoo Project)
— see the owner-tagged checklist in the roadmap.

## Layout
```
Unicontrol/
  README.md            # this file — overview + doc index
  docs/
    ROADMAP.md         # phased build roadmap (first doc)
  # agent code (Delay Watch, Plan Builder, …) added in later approved steps
```

## Related
- `../hermes/` — the PO-intake service whose connectors (`odoo_client`, `llm_client`,
  `po_parser`) and scheduler this initiative reuses.
- `../PO tracker/` — Hermes design docs (doc-structure convention followed here).
