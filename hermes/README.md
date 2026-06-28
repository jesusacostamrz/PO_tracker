# Hermes Agent

Centralizes customer purchase orders (POs) that currently scatter across salespeople's
inboxes. Hermes ingests forwarded PO emails, matches each one to its Odoo quotation,
writes the customer PO# back to the Sales Order, and maintains a Google Sheet "PO Tracker"
as the system of record — then emails daily digests.

Runs as an unattended **Python service on a VPS**, scheduled by systemd timers.
LLM steps (PO parsing, fuzzy matching, drafting) use a **provider-agnostic** OpenAI-compatible
API (OpenAI **or** GLM/Zhipu).

See the full design in `../PO tracker/hermes-task-list.md` and the source plan in
`~/.claude/plans/i-want-to-create-soft-duckling.md`.

## Layout

```
hermes/
  config/hermes.config.yaml   # all settings ("Configuration C")
  connectors/                 # deterministic API I/O
    odoo_client.py            # Odoo XML-RPC (quotes, write client_order_ref, attach, chatter, invoice_status)
    gmail_client.py           # (todo) Gmail API
    sheets_client.py          # (todo) Google Sheets API
    llm_client.py             # (todo) OpenAI-compatible LLM (OpenAI/GLM)
    po_parser.py              # (todo) PDF/email -> structured PO
  core/
    config.py                 # yaml + .env loader with ${VAR} substitution
    matcher.py                # (todo) partner/quote scoring
    tracker.py                # (todo) Sheet upsert + lifecycle
    digest.py                 # (todo) digests + dashboard
  scripts/
    test_odoo.py              # read-only Odoo connection test
    run_intake.py             # (todo) intake entrypoint (cron)
    run_digest.py             # (todo) digest entrypoint (cron)
  .secrets/.env               # secrets — NEVER commit (create from .env.example)
  requirements.txt
```

## Setup

1. Create and fill secrets:
   ```
   mkdir .secrets
   copy .env.example .secrets\.env      # Windows
   # then edit .secrets\.env with real values
   ```
2. Install deps (use a virtualenv):
   ```
   python -m venv .venv
   .venv\Scripts\activate                # Windows
   pip install -r requirements.txt
   ```
3. Prove Odoo works (read-only):
   ```
   python scripts\test_odoo.py
   ```

## Security
- All secrets live in `.secrets/.env` (gitignored, `chmod 600` on the VPS). Nothing is committed.
- Odoo: Hermes annotates only — it never confirms a Sales Order.
- The Sheet has Hermes-owned vs human-owned columns; Hermes never overwrites human columns.
