# Hermes — Purchasing workflow (shortage → draft RFQs in Odoo)

Status 2026-09-16: committed (deb0bb8). Offline tests pass. NOT yet run against Odoo 19 (the instance upgraded from 17 in Sept 2026): run the dry-run on the VPS first, then --live on one real SO.

## Flow

1. `python scripts/order_shortage.py S03107` — READ-ONLY report.
   Reads the Sales Order lines from Odoo, reads on-hand stock from the inventory
   workbook (`SHEETS_INVENTORY_SPREADSHEET_ID`, tab `Actualizacion`), auto-detects
   the part/qty columns (override with `--part-col`/`--qty-col`), and prints
   Ordered / On hand / BUY per line. Part matching is accent-, case- and
   whitespace-insensitive (`32 09 53 6` == `3209536`); the MODELO column is indexed too.
2. `python scripts/order_purchasing.py S03107` — DRY-RUN by default.
   Takes the BUY lines, resolves each product's vendor via `product.supplierinfo`
   (same records `import_pricelist.py` maintains), clusters by vendor, and prints
   one block per vendor with last-known cost and vendor min-qty warnings.
   Lines with no vendor on file are listed for a human to assign.
3. `python scripts/order_purchasing.py S03107 --live` — creates ONE DRAFT
   `purchase.order` per vendor with `origin = <SO name>` and posts a chatter note
   on the SO listing the RFQs. Never confirms, never sends. Idempotent per
   (SO, vendor): any existing PO citing that SO for that vendor is skipped.

## Files

- `hermes/scripts/order_shortage.py`, `hermes/scripts/test_shortage.py`
- `hermes/scripts/order_purchasing.py`, `hermes/scripts/test_purchasing.py`
- Odoo helpers already committed in `hermes/connectors/odoo_client.py`:
  `product_tmpl_map`, `supplierinfo_by_tmpl`, `purchase_orders_by_origin`, `create_draft_rfq`.

## Guardrails

- Stock workbook is read-only for Hermes (Viewer share is enough).
- Only draft RFQs are ever written; humans review and send from Odoo Compras.
- Check: `python scripts/test_shortage.py && python scripts/test_purchasing.py`.
