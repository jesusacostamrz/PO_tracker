# Hermes

Unattended Python service (runs on a VPS via systemd timers) that centralizes customer
purchase orders. Flow: **forwarded PO email → parse PDF → match to an Odoo quotation →
narrowly annotate the Odoo Sales Order → upsert a Google Sheet "PO Tracker" → daily
digest.** LLM steps are provider-agnostic (OpenAI SDK + `base_url`, works with OpenAI
**or** GLM/Zhipu).

## Commands (run from `hermes/`)

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows; VPS uses .venv/bin/activate
pip install -r requirements.txt

# Connectivity smoke tests — all READ-ONLY, write nothing:
python scripts/test_odoo.py        # Odoo auth + can read quotations
python scripts/test_gmail.py       # Gmail auth + poll query
python scripts/test_sheets.py      # Sheets service-account read
python scripts/test_llm.py         # one tiny chat call (few tokens)
python scripts/test_parse.py <po.pdf>   # PDF -> extracted JSON
python scripts/test_match.py <po.pdf>   # parse + match, no writes

python scripts/gmail_auth.py       # one-time OAuth consent (loopback port 8765; SSH-tunnel on VPS)
python scripts/setup_sheet.py      # build/repair the Tracker tabs (idempotent, additive; never deletes rows)

# End-to-end. DEFAULTS TO DRY-RUN (config runtime.dry_run: true). --live actually writes.
python scripts/process_po.py <po.pdf> [--live] [--odoo-db NAME] [--gmail-msg-id ID]
python scripts/intake.py [--live] [--odoo-db NAME] [--max N] [--watch SECONDS] [--mark-read]
python scripts/apply_manual.py [--live] [--odoo-db NAME]   # apply Odoo writes for rows a human resolved via Manual SO # (col K);
                                                           # typing NEW/NUEVA there instead creates a DRAFT quote from the PO itself
                                                           # (lines at the PO's own prices; unmatched products auto-created) and
                                                           # completes the same workflow on it -> "Matched (new quote)"

# Quotes pipeline (RFQ -> draft Odoo quotation). Same dry-run defaults.
python scripts/process_rfq.py <file.xlsx|.csv|.png|.jpg|.txt|.pdf> [--live]   # local test bench
python scripts/intake_rfq.py [--live] [--max N] [--watch SECONDS]        # Gmail batch (subject contains "RFQ")
python scripts/apply_quotes.py [--live]              # apply human pricing from the Pricing Queue tab
python scripts/import_pricelist.py --brand <key> <lista.xlsx> [--live]   # distributor price list -> Odoo catalog
# offline self-checks (no network): test_rfq_gmail, test_rfq_parse, test_product_match,
#   test_pricelist, test_web_pricing, test_pricebook
```

There is no test framework, linter, or build step — `scripts/test_*.py` are hand-run
diagnostics, not a pytest suite. Every script prepends the repo root to `sys.path`, so
run them from inside `hermes/` as `python scripts/<name>.py`.

## Architecture

Three layers, deliberately separated:

- `connectors/` — **deterministic API I/O only.** One class per external system
  (`OdooClient` via stdlib `xmlrpc.client`, `GmailClient`, `SheetsClient`, `LLMClient`).
  Each has a `from_config(cfg)` classmethod. No business logic lives here.
- `core/` — the decision logic.
  - `config.py` — loads `config/hermes.config.yaml` and substitutes `${VAR}` from
    `.secrets/.env`. Use `load_config()` and `secret(name)`; never read env directly.
  - `po_parser.py` — PDF → structured PO JSON. Text PDFs go through `pdfplumber`;
    scanned/image PDFs are rendered with `pypdfium2` and sent to the vision model. Key
    subtlety: **the PO is issued by our customer**, so on the document *we* are the
    "Proveedor/Supplier" — the parser is told who we are (`company:` block) to extract
    the *other* party as the customer.
  - `matcher.py` — scores a PO against quotes. Signal strength, strongest first:
    (1) PO cites our quote number → near-certain; (2) line **unit-price** overlap
    (quantity-independent — customers reorder different quantities); (3) untaxed-total
    agreement is corroboration only. Customer name must fuzzy-match (`rapidfuzz`).
    Ambiguity (top two scores within a margin) or no identifying signal → `needs_review`.
  - `pipeline.py` — shared parse→match orchestration used by BOTH entrypoints, so they
    can't drift. Fetches the candidate-quote pool ONCE per batch and reuses it; per-PO it
    mutates each quote's `_lines` in place (candidates get real lines, others `[]`).
  - `actions.py` — turns a `(PO, MatchResult)` into Odoo writes + Tracker rows.
  - `rfq_parser.py` / `product_matcher.py` / `quote_actions.py` — the quotes pipeline:
    RFQ (xlsx/csv/image/email body) → line items → Odoo product matches (exact
    `default_code` or product name, then fuzzy; ambiguity or no sale price → Pricing
    Queue) → draft quotation + Quotes/Pricing Queue tabs. **Catalog convention: the
    part number IS the product name** (no `default_code` — Odoo would display
    "[code] name" and mix the quote's Product/Description columns); descriptions go
    to `description_sale`. `import_pricelist.py` upserts distributor Excel lists into
    the catalog (dedup on part# in name or internal reference; cost →
    `product.supplierinfo`; sale price = cost × brand markup from `pricebook:` config).
  - `pricebook.py` — LOCAL distributor pricebooks (`pricebook.files:` config, e.g. the
    72k-row Phoenix Contact list): big xlsx lists consulted at match time instead of
    being imported into Odoo. A queued RFQ line that hits one (by item number OR type
    designation, both indexed) is priced at the LIST price — no extra margin unless the
    email instructs one; an email-granted discount multiplies (10% → ×0.9), capped by
    `max_discount_pct` (15) — above the cap the draft is created at LIST and flagged
    for approval (chatter + audit), never auto-granted. USD lists quoting into MXN use
    the official Odoo rate + `mxn_fx_surcharge` (0.5). Products auto-create on demand
    (name = the CLEANED type designation — list spacing normalized; item# in the sale
    description) at **list_price 0 on purpose**: a 0-price product requeues on the next
    RFQ and reprices from the current list, never a stale Odoo price. An existing
    catalog product under either identifier is reused, never duplicated; a typo'd item#
    is rescued by the type inside the description (joined-token windows, longest wins).
    Product images come ONLY from the brand's `image_site` when configured (blank beats
    wrong). The xlsx is cached as JSON next to it (mtime+column-mapping keyed);
    `pricebooks/` is gitignored (private pricing data).
- `scripts/` — thin CLI entrypoints (`process_po.py` single PDF, `intake.py` Gmail batch).

## Invariants — do not violate

- **Hermes annotates, never confirms.** On a confident match it only sets
  `client_order_ref`, appends `PO Cliente: <#>` to the quote's terms, attaches the PDF,
  and posts a chatter note. `auto_confirm_so` is `false` and must stay that way — never
  confirm a Sales Order.
- **`runtime.dry_run: true` is the safe default.** In dry-run nothing is written to Odoo
  and no Gmail label is applied; the intended actions are logged to the Sheet's Audit tab
  and Orders cells read `Dry-run`. Only `--live` performs real writes.
- **Human-owned Sheet columns are never overwritten.** The Orders tab splits Hermes-owned
  columns from human-owned ones (Manual SO #, Human Verified, Invoiced (Confirmed), Human
  Notes). On an upsert, `actions.py` writes only its own column ranges and preserves the
  human cells. The Orders column order in `actions.py` MUST stay in lockstep with
  `ORDERS_HEADERS` in `scripts/setup_sheet.py`.
- **Idempotency** is keyed on PO# / Gmail message id inside `apply_match`: a live Tracker
  row blocks reprocessing; a prior dry-run row is upserted (overwritten) by a later live
  run. Re-polling never double-writes.
- Only a **confident (`matched`)** result populates Quote/SO #, Odoo SO ID, and
  Salesperson. A `needs_review` best-guess must leave those blank.
- **Quotes pipeline:** Hermes creates DRAFT quotations only — never sends one to a
  customer. Quotes, Pricing Queue, and the pipeline's Audit tab live in a SEPARATE
  workbook (`sheets.quotes_spreadsheet_id` / `SHEETS_QUOTES_SPREADSHEET_ID`), not in
  the PO Tracker. Quotes-tab reprocessing is blocked only by a row with an Odoo Quote ID
  (dry-run and Needs-Review rows are upserted). Pricing Queue rows are written on live
  runs only. The Quotes Status column (E) is SHARED: Hermes writes the pipeline states
  and a human flips the same cell to Sent/Cancelled (quotes go out by email/WhatsApp
  beyond Hermes's reach); Hermes never downgrades a Sent/Cancelled status. Human-owned
  cells are Quotes col K (Human Notes) and Pricing Queue cols M:P. Column
  constants in `core/quote_actions.py` and `scripts/apply_quotes.py` MUST stay in
  lockstep with `QUOTES_HEADERS`/`PQ_HEADERS` in `scripts/setup_sheet.py`. Products ARE
  now auto-created on live RFQ intake for any queued line with no suggested match (price
  0, recorded in the Pricing Queue; product image attached best-effort) so EVERY RFQ
  line lands on the draft quotation immediately — auto-matched lines priced from the
  pricelist, lines with an extracted supplier cost (supplier-quote mode) at
  cost × fx ÷ (1 − margin) — margin is on the SELLING price, so 40% on cost
  1000 quotes 1666.67 — remaining queued lines at price 0. Web-researched price suggestions (Pricing Queue
  cols Q-S: Web Price, Web Currency, Web Source) are advisory only — a human always
  confirms Sale Price before it reaches the quote — with ONE exception: when the email
  body EXPLICITLY orders pricing from a named website (parsed to `price_source_site`),
  a validated offer from THAT site only becomes the line's cost and is quoted at
  cost × fx ÷ (1 − margin); off-site offers are demoted to reference links and
  unpriceable lines still queue. Drafts are still never confirmed/sent.

## Secrets & config

- All secrets live in `hermes/.secrets/.env` (gitignored; `chmod 600` on the VPS),
  referenced from the YAML as `${VAR}`. Create it from `.env.example`. Google OAuth/token
  and service-account JSON also live under `.secrets/`. Nothing here is ever committed.
  Web price research + product image lookups prefer Google via serper.dev when
  `SERPER_API_KEY` is set (better exact-SKU retrieval + direct Google Images);
  otherwise they ride the existing OpenAI key (Responses API `web_search` tool),
  on iff the LLM key is set and `base_url` is OpenAI.
- `config/hermes.config.yaml` holds all non-secret settings (company identity, matching
  thresholds, write toggles, digest schedule). Tune behavior here, not in code.
