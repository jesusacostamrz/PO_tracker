# Hermes Quotes — Automated Quotation Workflow (Design)

Date: 2026-07-20
Status: Approved (brainstorm 2026-07-20)

## Problem

Customers send RFQs — lists of 20–30 components — in mixed formats (Excel, images,
email tables). Some components don't exist as Odoo products; most prices are unknown
at intake. Quotes are typed into Odoo by hand today. We are official distributors for
3–6 brands and receive their price lists as periodic Excel/CSV files. Volume: 5–20
RFQs/week. A future e-commerce site will sell from the same catalog.

## Decisions made

- **Inventory control is a separate, later project** on the same Odoo foundation.
- **Pricing = mix**: default markup rules per brand compute a proposed sale price;
  the salesperson always reviews/overrides on the draft quote before sending.
- **Everything lands in the Odoo product catalog** (products, costs via
  `product.supplierinfo`, sale prices) so Odoo eCommerce later is configuration,
  not a rebuild. No pricing data lives only in Sheets.
- **Hermes drafts, never sends.** Same invariant family as the PO side: dry-run
  default, idempotency on Gmail message id, human-owned Sheet columns preserved.

## Phase 1 — RFQ pipeline (workflow skeleton)

New flow alongside the PO pipeline, reusing all four connectors (Gmail, Odoo,
Sheets, LLM):

1. **Intake.** RFQ emails forwarded to the same mailbox, distinct Gmail label/query.
   New `core/rfq_parser.py` normalizes any input — Excel/CSV via `openpyxl`, images
   via the existing vision path, email-body tables via the LLM — into
   `[{part_number, description, qty}]`.
2. **Product match per line** against Odoo: exact match on internal reference /
   part number → fuzzy match on name+description (`rapidfuzz`) → unmatched.
   Ambiguity (two close fuzzy scores) → queue, never guess.
3. **Draft quotation in Odoo** created immediately with all matched-and-priced
   lines. Dry-run default; `--live` writes.
4. **Pricing Queue** — new Tracker Sheet tab, one row per unresolved line:
   Hermes' best-guess match + human-owned columns (Price, Create Product? Y/N,
   Notes). `scripts/apply_quotes.py` (sibling of `apply_manual.py`) creates
   approved products and completes the draft quote.
5. **Quotes tab** in the Tracker: one row per RFQ — customer, # lines,
   # auto-priced, # pending, Odoo quote #, status.

Hermes never creates a product without either a price-list entry (Phase 2) or
explicit human approval in the Pricing Queue.

## Phase 2 — Price book (one brand at a time)

- `scripts/import_pricelist.py --brand <name> <file.xlsx>` — per-brand column
  mapping (part #, description, cost columns) in `hermes.config.yaml`. Run when a
  distributor sends a new list.
- Upserts Odoo products keyed on **manufacturer part number stored as the
  product's internal reference** (the dedup rule). Cost → `product.supplierinfo`;
  sale price computed from a **default markup per brand** in config.
- Effect: each imported brand converts its lines from Pricing Queue to
  auto-priced, and builds the e-commerce catalog as a side effect.

## Phase 3 (optional) — quote-history pricing

For unpriced items, look up the last price we quoted for that product in Odoo
quote history and propose it in the Pricing Queue as "last quoted @ date".
No web research or agents until proven necessary.

## Out of scope

Inventory control, e-commerce site build, agentic/web price research, sending
quotes to customers, confirming sales orders.
