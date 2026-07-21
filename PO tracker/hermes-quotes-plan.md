# Hermes Quotes Implementation Plan (Phase 1 + 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate RFQ → draft Odoo quotation: parse customer component lists (Excel/images/email tables), match lines to Odoo products, auto-price known items, queue unknown items for a human, and (Phase 2) import distributor Excel price lists into the Odoo catalog.

**Architecture:** A second pipeline beside the PO pipeline, reusing the four connectors (Gmail, Odoo, Sheets, LLM). New modules: `core/rfq_parser.py` (any input → line-item JSON), `core/product_matcher.py` (lines → Odoo products), `core/quote_actions.py` (create draft quote + Sheet rows). New scripts: `process_rfq.py`, `intake_rfq.py`, `apply_quotes.py`, `import_pricelist.py`. Two new Tracker tabs: **Quotes** and **Pricing Queue**.

**Tech Stack:** Python 3.11+, stdlib `xmlrpc.client` via existing `OdooClient`, `openpyxl` (NEW dependency — the only one), `rapidfuzz` (already installed), OpenAI-compatible LLM via existing `LLMClient`.

**Spec:** `PO tracker/hermes-quotes-design.md`

## Global Constraints

- Run everything from inside `hermes/` as `python scripts/<name>.py` (scripts prepend repo root to `sys.path`).
- No pytest/linter exists. Tests are hand-run `scripts/test_*.py` diagnostics; pure-logic ones must run OFFLINE (fake data, no network) and exit non-zero on assert failure.
- `runtime.dry_run: true` is the safe default; only `--live` writes to Odoo/Gmail/Sheet-status-cells. Mirror how `intake.py`/`apply_manual.py` compute `dry`.
- **Hermes drafts, never sends or confirms.** Draft `sale.order` only; never `action_confirm`, never email a customer.
- Human-owned Sheet columns are NEVER overwritten on upsert. Column index constants in code MUST stay in lockstep with the header lists in `scripts/setup_sheet.py` (existing convention).
- Pricing Queue rows are written on LIVE runs only; dry-runs log intent to the Audit tab instead (avoids multi-row upserts).
- All audit logging appends to the existing Audit tab with the existing 6-column row shape: `[timestamp, ref, action, detail, result, run_mode]`.
- Config in `config/hermes.config.yaml`; secrets only via `.secrets/.env` `${VAR}` substitution; use `core.config.load_config()`.
- Commit after every task; message prefix `feat(hermes):` / `test(hermes):`.

---

### Task 1: Config + new Tracker tabs (Quotes, Pricing Queue)

**Files:**
- Modify: `hermes/config/hermes.config.yaml`
- Modify: `hermes/scripts/setup_sheet.py`
- Modify: `hermes/requirements.txt` (add `openpyxl`)

**Interfaces:**
- Produces: `cfg["rfq"]` block, `cfg["sheets"]["tabs"]["quotes"]` = `"Quotes"`, `cfg["sheets"]["tabs"]["pricing_queue"]` = `"Pricing Queue"`; `QUOTES_HEADERS` / `PQ_HEADERS` layouts that Tasks 6, 9 index into.

- [ ] **Step 1: Add config blocks**

Append to `hermes/config/hermes.config.yaml` (and add the two tab names under the existing `sheets.tabs`):

```yaml
sheets:
  tabs:
    # ... existing four tabs stay ...
    quotes: Quotes
    pricing_queue: Pricing Queue

rfq:
  # Team convention: forward RFQ emails with "RFQ" in the subject.
  poll_query: 'is:unread subject:RFQ -label:Hermes/Processed -label:Hermes/NeedsReview'
  labels:
    processed: Hermes/Processed        # reuse existing labels
    needs_review: Hermes/NeedsReview
  match:
    fuzzy_threshold: 88       # >= this token_set_ratio -> candidate match
    ambiguity_margin: 3       # top-2 scores closer than this -> queue, never guess
    partner_threshold: 85     # customer-name fuzzy floor to pick the Odoo partner
```

- [ ] **Step 2: Add tab definitions to `setup_sheet.py`**

Insert after `AUDIT_DROPDOWNS`:

```python
# Quotes tab: one row per RFQ. Human-owned: Human Notes (K / idx 10).
QUOTES_HEADERS = [
    "Received At", "Customer", "RFQ Ref", "Lines",         # 0-3  A-D
    "Auto-priced", "Queued", "Quote #", "Odoo Quote ID",   # 4-7  E-H
    "Status", "Gmail Msg ID",                              # 8-9  I-J
    "Human Notes",                                         # 10   K (human-owned)
]
QUOTES_DROPDOWNS = {
    8: ["Draft Created", "Pending Pricing", "Complete", "Needs Review", "Dry-run"],
}

# Pricing Queue: one row per unresolved RFQ line. Human-owned cols M-P (idx 12-15).
PQ_HEADERS = [
    "Added At", "Customer", "RFQ Ref", "Quote #", "Odoo Quote ID",   # 0-4  A-E
    "Part #", "Description", "Qty",                                  # 5-7  F-H
    "Suggested Product", "Suggested Product ID", "Match Note",       # 8-10 I-K
    "Status",                                                        # 11   L
    "Sale Price", "Use Product ID", "Create Product?", "Human Notes",# 12-15 M-P (human-owned)
]
PQ_DROPDOWNS = {
    11: ["Pending", "Resolved", "Error"],   # Status (Hermes-owned)
    14: ["Yes", "No"],                      # Create Product?
}
```

In `main()`, after the Audit `_apply(...)` call, add:

```python
    _apply(sc, tabs["quotes"], QUOTES_HEADERS, QUOTES_DROPDOWNS)
    _apply(sc, tabs["pricing_queue"], PQ_HEADERS, PQ_DROPDOWNS)
```

Add `openpyxl` on its own line to `hermes/requirements.txt`, then `pip install openpyxl` in the venv.

- [ ] **Step 3: Run and verify**

Run: `python scripts/setup_sheet.py`
Expected: output lists `[Quotes] 11 cols, 1 dropdown(s)` and `[Pricing Queue] 16 cols, 2 dropdown(s)`; final "Tabs now:" includes both. Idempotent: run twice, no error.

- [ ] **Step 4: Commit**

```bash
git add config/hermes.config.yaml scripts/setup_sheet.py requirements.txt
git commit -m "feat(hermes): rfq config + Quotes / Pricing Queue tracker tabs"
```

---

### Task 2: Gmail connector — generic attachments + email body text

**Files:**
- Modify: `hermes/connectors/gmail_client.py`
- Create: `hermes/scripts/test_rfq_gmail.py` (OFFLINE — fake message dicts, no network)

**Interfaces:**
- Produces: `GmailClient.attachments_by_ext(msg, exts) -> list[tuple[str, bytes]]` and `GmailClient.body_text(msg) -> str`. Task 8 consumes both.
- Note: `body_text` is pure (no API call) — make it a `@staticmethod` so the offline test needs no service.

- [ ] **Step 1: Write the failing test**

`hermes/scripts/test_rfq_gmail.py`:

```python
"""Offline check of GmailClient.body_text (fake payloads, no network)."""
import base64, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectors.gmail_client import GmailClient

def b64(s): return base64.urlsafe_b64encode(s.encode()).decode()

plain = {"payload": {"mimeType": "text/plain", "body": {"data": b64("hola\n2x bearing 6204")}}}
nested_html = {"payload": {"mimeType": "multipart/alternative", "body": {}, "parts": [
    {"mimeType": "text/html", "body": {"data": b64("<table><tr><td>ABC-1</td><td>5</td></tr></table>")}},
]}}

assert "bearing 6204" in GmailClient.body_text(plain)
html_out = GmailClient.body_text(nested_html)
assert "ABC-1" in html_out and "<" not in html_out  # tags stripped
print("OK test_rfq_gmail")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python scripts/test_rfq_gmail.py`
Expected: `AttributeError: ... has no attribute 'body_text'`

- [ ] **Step 3: Implement**

Add to `GmailClient` (after `pdf_attachments`):

```python
    def attachments_by_ext(self, msg: dict, exts: tuple[str, ...]) -> list[tuple[str, bytes]]:
        """[(filename, bytes)] for attachments whose name ends with one of ``exts``."""
        out: list[tuple[str, bytes]] = []

        def walk(part: dict) -> None:
            filename = part.get("filename") or ""
            body = part.get("body", {})
            if filename.lower().endswith(exts) and body.get("attachmentId"):
                data = (
                    self.service.users().messages().attachments()
                    .get(userId="me", messageId=msg["id"], id=body["attachmentId"])
                    .execute()
                )
                out.append((filename, base64.urlsafe_b64decode(data["data"])))
            for sub in part.get("parts") or []:
                walk(sub)

        walk(msg.get("payload", {}))
        return out

    @staticmethod
    def body_text(msg: dict) -> str:
        """Best-effort message body as plain text: text/plain preferred, else de-tagged HTML."""
        import re
        texts: dict[str, list[str]] = {"text/plain": [], "text/html": []}

        def walk(part: dict) -> None:
            mime = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if mime in texts and data and not part.get("filename"):
                texts[mime].append(base64.urlsafe_b64decode(data).decode("utf-8", "replace"))
            for sub in part.get("parts") or []:
                walk(sub)

        walk(msg.get("payload", {}))
        if texts["text/plain"]:
            return "\n".join(texts["text/plain"]).strip()
        html = "\n".join(texts["text/html"])
        # ponytail: regex tag-strip is enough for RFQ tables; the LLM tolerates messy text
        html = re.sub(r"</(tr|p|div|table|br)>", "\n", html, flags=re.I)
        html = re.sub(r"</td>", "\t", html, flags=re.I)
        return re.sub(r"<[^>]+>", " ", html).strip()
```

- [ ] **Step 4: Run to verify it passes**

Run: `python scripts/test_rfq_gmail.py` → `OK test_rfq_gmail`

- [ ] **Step 5: Commit**

```bash
git add connectors/gmail_client.py scripts/test_rfq_gmail.py
git commit -m "feat(hermes): gmail attachments_by_ext + body_text for RFQ intake"
```

---

### Task 3: `core/rfq_parser.py` — any input → line-item JSON

**Files:**
- Create: `hermes/core/rfq_parser.py`
- Create: `hermes/scripts/test_rfq_parse.py` (offline xlsx_to_text check + optional live LLM smoke)

**Interfaces:**
- Consumes: `LLMClient.chat_json`, `LLMClient.vision_json` (existing).
- Produces (Tasks 7/8 consume):
  - `xlsx_to_text(data: bytes) -> str`
  - `parse_rfq(sources, llm, company) -> dict` where `sources` is `list[tuple[str, str, bytes | str]]` of `(kind, filename, payload)`, `kind in {"xlsx", "image", "text"}` (`"image"` payload = raw image bytes; `"text"` payload = str).
  - Return shape: `{"customer_name": str|None, "rfq_ref": str|None, "line_items": [{"part_number": str|None, "description": str, "quantity": number}]}` plus `"_source"`.

- [ ] **Step 1: Write the failing offline test**

`hermes/scripts/test_rfq_parse.py`:

```python
"""Offline: xlsx_to_text. Optional live: parse a real RFQ file if passed as argv[1]."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.rfq_parser import xlsx_to_text

from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(["Part Number", "Descripcion", "Cant"])
ws.append(["6204-2RS", "Rodamiento sellado", 12])
ws.append([None, "Cable 14 AWG rojo", 100])
buf = io.BytesIO(); wb.save(buf)

text = xlsx_to_text(buf.getvalue())
assert "6204-2RS" in text and "Cable 14 AWG rojo" in text and "12" in text
print("OK xlsx_to_text")

if len(sys.argv) > 1:  # live LLM smoke: python scripts/test_rfq_parse.py <rfq.xlsx|.png|.txt>
    from core.config import load_config
    from connectors.llm_client import LLMClient
    from core.rfq_parser import parse_rfq
    cfg = load_config(); llm = LLMClient.from_config(cfg)
    p = Path(sys.argv[1]); ext = p.suffix.lower()
    kind = "xlsx" if ext in (".xlsx", ".xlsm") else "image" if ext in (".png", ".jpg", ".jpeg") else "text"
    payload = p.read_bytes() if kind != "text" else p.read_text(encoding="utf-8", errors="replace")
    rfq = parse_rfq([(kind, p.name, payload)], llm, cfg.get("company", {}))
    print(f"customer={rfq.get('customer_name')}  ref={rfq.get('rfq_ref')}  lines={len(rfq['line_items'])}")
    for li in rfq["line_items"][:5]:
        print("  ", li)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python scripts/test_rfq_parse.py`
Expected: `ModuleNotFoundError: No module named 'core.rfq_parser'`

- [ ] **Step 3: Implement `core/rfq_parser.py`**

```python
"""Parse a customer RFQ (component list) into structured line items via the LLM.

Inputs arrive in mixed formats — Excel/CSV attachments, images/photos, or a table
pasted in the email body. Everything is normalized to text (or image data-URLs)
and pushed through ONE extraction prompt, so all formats yield the same JSON.
"""
from __future__ import annotations

import base64
import io

_MAX_TEXT_CHARS = 15000


def xlsx_to_text(data: bytes) -> str:
    """All sheets -> TSV-ish text. Header detection is the LLM's job, not ours."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        lines.append(f"=== SHEET {ws.title} ===")
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c) for c in row]
            if any(c.strip() for c in cells):
                lines.append("\t".join(cells))
    wb.close()
    return "\n".join(lines).strip()


def _system_prompt(company: dict) -> str:
    aka = ", ".join(company.get("aka", []) or [])
    who = f'Our company is the SUPPLIER named "{company.get("legal_name", "")}"'
    if aka:
        who += f" (aka {aka})"
    return f"""You extract a Request For Quotation (RFQ) — a list of components a customer wants priced.

{who}. The RFQ is sent BY a customer TO us; the customer is the requesting company, never our own.

Return ONLY a JSON object (null where absent):
{{
  "customer_name": string,   // the requesting company, if identifiable; else null
  "rfq_ref": string,         // the customer's RFQ/requisition number, if any; else null
  "line_items": [
    {{"part_number": string,  // manufacturer part number / catalog code; null if only a description
      "description": string,  // what the item is, as written
      "quantity": number}}    // requested quantity; default 1 if truly absent
  ]
}}

Rules:
- Extract EVERY requested item; never invent items; never drop rows.
- part_number is a catalog/manufacturer code (e.g. "6204-2RS", "1SVR405613R3100") — not a line number.
- Numbers: dot decimal, no thousands separators; quantity must be a number.
- Content may be Spanish/English or both. Ignore signatures, disclaimers, prices the customer typed.
- Output JSON only — no prose, no code fences."""


def _img_data_url(img_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    mime = "image/png" if ext == "png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(img_bytes).decode("ascii")


def parse_rfq(sources: list[tuple[str, str, bytes | str]], llm, company: dict) -> dict:
    """sources: [(kind, filename, payload)] with kind in {'xlsx','image','text'}.

    Text-ish sources are concatenated into one prompt; images go to the vision
    model. If both exist, text wins (cheaper, usually the authoritative list).
    """
    system = _system_prompt(company)
    texts: list[str] = []
    image_urls: list[str] = []
    for kind, filename, payload in sources:
        if kind == "xlsx":
            texts.append(f"--- ATTACHMENT {filename} ---\n{xlsx_to_text(payload)}")
        elif kind == "text":
            texts.append(f"--- EMAIL BODY ---\n{payload}")
        elif kind == "image":
            image_urls.append(_img_data_url(payload, filename))

    if texts:
        blob = "\n\n".join(texts)[:_MAX_TEXT_CHARS]
        result = llm.chat_json(system=system, user="RFQ content:\n\n" + blob, max_tokens=3000)
        result["_source"] = "text"
    elif image_urls:
        result = llm.vision_json(system=system, user_text="Extract the RFQ from the attached image(s).",
                                 image_data_urls=image_urls[:4], max_tokens=3000)
        result["_source"] = "vision"
    else:
        result = {"customer_name": None, "rfq_ref": None, "line_items": [], "_source": "empty"}

    result.setdefault("line_items", [])
    # normalize lines defensively — downstream indexes these keys
    for li in result["line_items"]:
        li["part_number"] = (li.get("part_number") or None)
        li["description"] = str(li.get("description") or "")
        try:
            li["quantity"] = float(li.get("quantity") or 1)
        except (TypeError, ValueError):
            li["quantity"] = 1.0
    return result
```

- [ ] **Step 4: Run offline test**

Run: `python scripts/test_rfq_parse.py` → `OK xlsx_to_text`
(Optionally, with a real RFQ file + LLM creds: `python scripts/test_rfq_parse.py path/to/rfq.xlsx` prints extracted lines.)

- [ ] **Step 5: Commit**

```bash
git add core/rfq_parser.py scripts/test_rfq_parse.py
git commit -m "feat(hermes): rfq parser — xlsx/image/email-body to line items"
```

---

### Task 4: `core/product_matcher.py` — lines → Odoo products (pure logic)

**Files:**
- Create: `hermes/core/product_matcher.py`
- Create: `hermes/scripts/test_product_match.py` (OFFLINE — fake product dicts)

**Interfaces:**
- Consumes: product dicts shaped `{"id": int, "default_code": str|False, "name": str, "list_price": float}` (Odoo `search_read` returns `False` for empty char fields — handle it).
- Produces (Task 6 consumes):

```python
@dataclass
class LineMatch:
    line: dict            # the rfq line item
    status: str           # "matched" | "queue"
    product: dict | None  # best product (also set on queue rows as the suggestion)
    score: float
    reason: str
```
  - `match_lines(lines, products, mcfg) -> list[LineMatch]` where `mcfg = cfg["rfq"]["match"]`.
  - `norm_code(s) -> str` (also used by Task 10's price-list dedup).

- [ ] **Step 1: Write the failing test**

`hermes/scripts/test_product_match.py`:

```python
"""Offline check of product matching rules (no network)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.product_matcher import match_lines, norm_code

MCFG = {"fuzzy_threshold": 88, "ambiguity_margin": 3}
PRODUCTS = [
    {"id": 1, "default_code": "6204-2RS", "name": "Rodamiento 6204 2RS sellado", "list_price": 45.0},
    {"id": 2, "default_code": "6205-2RS", "name": "Rodamiento 6205 2RS sellado", "list_price": 52.0},
    {"id": 3, "default_code": False, "name": "Cable THW 14 AWG rojo (m)", "list_price": 8.5},
    {"id": 4, "default_code": "REL-24V", "name": "Relevador 24VDC 2 polos", "list_price": 0.0},
]

assert norm_code(" 6204‑2rs ") == norm_code("6204-2RS")  # case/space/unicode-dash insensitive

def one(line):
    return match_lines([line], PRODUCTS, MCFG)[0]

# 1. exact code -> matched
m = one({"part_number": "6204-2rs", "description": "rodamiento", "quantity": 2})
assert m.status == "matched" and m.product["id"] == 1

# 2. matched product but price 0 -> queue (no price to quote)
m = one({"part_number": "REL-24V", "description": "relevador", "quantity": 1})
assert m.status == "queue" and m.product["id"] == 4 and "price" in m.reason.lower()

# 3. description-only fuzzy hit -> matched
m = one({"part_number": None, "description": "cable thw 14 awg rojo", "quantity": 100})
assert m.status == "matched" and m.product["id"] == 3

# 4. ambiguous (6204 vs 6205 close names, wrong/missing code) -> queue
m = one({"part_number": None, "description": "rodamiento 2RS sellado", "quantity": 1})
assert m.status == "queue"

# 5. nothing similar -> queue with no strong suggestion
m = one({"part_number": "ZZZ-999", "description": "valvula solenoide 3/4", "quantity": 1})
assert m.status == "queue"

print("OK test_product_match")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python scripts/test_product_match.py`
Expected: `ModuleNotFoundError: No module named 'core.product_matcher'`

- [ ] **Step 3: Implement `core/product_matcher.py`**

```python
"""Match RFQ line items to Odoo products. Pure logic — no I/O.

Signal order: exact (normalized) part-number == default_code beats everything;
then fuzzy description-vs-name. Ambiguity (top-2 too close) or a hit without a
sale price goes to the Pricing Queue — Hermes never guesses a product or quotes 0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

_CODE_JUNK = re.compile(r"[\s‐-―_./]+")  # spaces, unicode dashes, separators


def norm_code(s) -> str:
    if not s:
        return ""
    return _CODE_JUNK.sub("", str(s)).replace("-", "").upper()


@dataclass
class LineMatch:
    line: dict
    status: str            # "matched" | "queue"
    product: dict | None
    score: float
    reason: str


def _best_two(line: dict, products: list[dict]) -> list[tuple[float, dict]]:
    """Top-2 (score, product) by fuzzy similarity of code+description vs code+name."""
    want = f"{line.get('part_number') or ''} {line.get('description') or ''}".strip()
    scored = []
    for p in products:
        have = f"{p.get('default_code') or ''} {p.get('name') or ''}".strip()
        scored.append((fuzz.token_set_ratio(want.lower(), have.lower()), p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[:2]


def _decide(product: dict, score: float, how: str) -> "LineMatch | None":
    """Matched only if the product is actually quotable (has a sale price)."""
    if (product.get("list_price") or 0) > 0:
        return ("matched", product, score, how)
    return ("queue", product, score, f"{how}, but product has no sale price")


def match_lines(lines: list[dict], products: list[dict], mcfg: dict) -> list[LineMatch]:
    threshold = mcfg.get("fuzzy_threshold", 88)
    margin = mcfg.get("ambiguity_margin", 3)
    by_code = {norm_code(p.get("default_code")): p for p in products if p.get("default_code")}

    out: list[LineMatch] = []
    for line in lines:
        code = norm_code(line.get("part_number"))
        if code and code in by_code:
            status, prod, score, why = _decide(by_code[code], 100.0, "exact part-number match")
            out.append(LineMatch(line, status, prod, score, why))
            continue

        top2 = _best_two(line, products)
        if not top2 or top2[0][0] < threshold:
            best = top2[0][1] if top2 and top2[0][0] >= 60 else None
            score = top2[0][0] if top2 else 0.0
            out.append(LineMatch(line, "queue", best, score, "no product above match threshold"))
            continue
        if len(top2) == 2 and (top2[0][0] - top2[1][0]) < margin:
            out.append(LineMatch(line, "queue", top2[0][1], top2[0][0],
                                 f"ambiguous: two products within {margin} pts"))
            continue
        status, prod, score, why = _decide(top2[0][1], top2[0][0],
                                           f"fuzzy match {top2[0][0]:.0f}")
        out.append(LineMatch(line, status, prod, score, why))
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python scripts/test_product_match.py` → `OK test_product_match`
(If assertion 4 trips because token_set_ratio scores drift from these fakes, adjust the FAKE data, not the thresholds — thresholds are config.)

- [ ] **Step 5: Commit**

```bash
git add core/product_matcher.py scripts/test_product_match.py
git commit -m "feat(hermes): product matcher — rfq lines to odoo products"
```

---

### Task 5: OdooClient — product + quotation methods

**Files:**
- Modify: `hermes/connectors/odoo_client.py`
- Create: `hermes/scripts/test_rfq_odoo.py` (READ-ONLY live smoke)

**Interfaces:**
- Produces (Tasks 6, 9, 10 consume):
  - `all_products(self, limit=10000) -> list[dict]` — fields `["default_code", "name", "list_price"]` (+ `id` implicit), domain `[["sale_ok", "=", True]]`
  - `create_draft_quote(self, partner_id: int, lines: list[dict], client_ref: str = "") -> int` — `lines` items: `{"product_id": int, "product_uom_qty": float}` optionally + `"price_unit": float`
  - `add_quote_lines(self, order_id: int, lines: list[dict]) -> bool`
  - `create_product(self, name: str, default_code: str = "", list_price: float = 0.0) -> int`
  - `product_tmpl_id(self, product_id: int) -> int`
  - `ensure_vendor(self, name: str) -> int`
  - `upsert_supplierinfo(self, tmpl_id: int, partner_id: int, price: float) -> None`

- [ ] **Step 1: Implement** (append inside `OdooClient`, before the factory)

```python
    # ---- products & quotations (Hermes Quotes) ----
    def all_products(self, limit=10000) -> list[dict]:
        return self.search_read(
            "product.product", [["sale_ok", "=", True]],
            ["default_code", "name", "list_price"], limit=limit,
        )

    def create_draft_quote(self, partner_id: int, lines: list[dict], client_ref: str = "") -> int:
        """Create a DRAFT sale.order. Never confirms it. Omit price_unit in a line
        to let Odoo price it from the pricelist."""
        vals = {"partner_id": partner_id, "order_line": [(0, 0, l) for l in lines]}
        if client_ref:
            vals["client_order_ref"] = client_ref
        return self.execute("sale.order", "create", vals)

    def add_quote_lines(self, order_id: int, lines: list[dict]) -> bool:
        return self.execute("sale.order", "write", [order_id],
                            {"order_line": [(0, 0, l) for l in lines]})

    def create_product(self, name: str, default_code: str = "", list_price: float = 0.0) -> int:
        vals = {"name": name, "sale_ok": True, "list_price": list_price}
        if default_code:
            vals["default_code"] = default_code
        return self.execute("product.product", "create", vals)

    def product_tmpl_id(self, product_id: int) -> int:
        rec = self.execute("product.product", "read", [product_id], ["product_tmpl_id"])
        v = rec[0]["product_tmpl_id"]
        return v[0] if isinstance(v, (list, tuple)) else v

    def ensure_vendor(self, name: str) -> int:
        recs = self.search_read("res.partner", [["name", "=", name]], ["name"], limit=1)
        if recs:
            return recs[0]["id"]
        return self.execute("res.partner", "create", {"name": name, "is_company": True})

    def upsert_supplierinfo(self, tmpl_id: int, partner_id: int, price: float) -> None:
        dom = [["product_tmpl_id", "=", tmpl_id], ["partner_id", "=", partner_id]]
        recs = self.search_read("product.supplierinfo", dom, ["price"], limit=1)
        if recs:
            self.execute("product.supplierinfo", "write", [recs[0]["id"]], {"price": price})
        else:
            self.execute("product.supplierinfo", "create",
                         {"product_tmpl_id": tmpl_id, "partner_id": partner_id, "price": price})
```

- [ ] **Step 2: Write the read-only smoke test**

`hermes/scripts/test_rfq_odoo.py`:

```python
"""READ-ONLY smoke: product pool is reachable and shaped right. Writes nothing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import load_config
from connectors.odoo_client import OdooClient

cfg = load_config()
odoo = OdooClient.from_config(cfg)
prods = odoo.all_products(limit=5000)
print(f"OK — {len(prods)} sellable products")
with_code = sum(1 for p in prods if p.get("default_code"))
priced = sum(1 for p in prods if (p.get("list_price") or 0) > 0)
print(f"   with internal reference: {with_code}   with sale price > 0: {priced}")
for p in prods[:3]:
    print("  ", p)
```

- [ ] **Step 3: Run**

Run: `python scripts/test_rfq_odoo.py`
Expected: `OK — N sellable products` with plausible counts. (Also note the with-code/priced counts — they predict Phase-1 auto-match rates.)

- [ ] **Step 4: Commit**

```bash
git add connectors/odoo_client.py scripts/test_rfq_odoo.py
git commit -m "feat(hermes): odoo product + draft-quotation methods"
```

---

### Task 6: `core/quote_actions.py` — RFQ + matches → Odoo draft + Sheet rows

**Files:**
- Create: `hermes/core/quote_actions.py`

**Interfaces:**
- Consumes: `LineMatch` (Task 4), Odoo methods (Task 5), `SheetsClient.read/append_row/update_range`, tab names from Task 1. Reuses `_now()` from `core.actions`.
- Produces (Tasks 7/8 consume):

```python
@dataclass
class QuoteOutcome:
    dry_run: bool
    status: str          # Quotes-tab Status value
    order_id: int | None = None
    order_name: str = ""
    auto_priced: int = 0
    queued: int = 0
    skipped: bool = False
    notes: list[str] = field(default_factory=list)
```
  - `apply_rfq(odoo, sheets, cfg, rfq, matches, gmail_msg_id="", dry_run=None) -> QuoteOutcome`
  - Column-index constants `Q_GMAIL_MSG = 9`, `Q_STATUS = 8` (lockstep with `QUOTES_HEADERS`).

- [ ] **Step 1: Implement `core/quote_actions.py`**

```python
"""Action layer for RFQs: (rfq, line matches) -> Odoo draft quotation + Tracker rows.

Mirrors core/actions.py doctrine: honors runtime.dry_run; idempotency keyed on the
Gmail message id in the Quotes tab (a live row blocks, a dry-run row is upserted);
human-owned cells (Quotes col K) are never overwritten. Pricing Queue rows are only
written on LIVE runs — a dry-run logs intent to Audit instead. NEVER confirms or
sends anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from connectors.odoo_client import OdooClient
from connectors.sheets_client import SheetsClient
from core.actions import _now
from core.product_matcher import LineMatch

# Quotes tab column indices (0-based). Lockstep with QUOTES_HEADERS in setup_sheet.py.
Q_STATUS, Q_GMAIL_MSG = 8, 9


@dataclass
class QuoteOutcome:
    dry_run: bool
    status: str
    order_id: int | None = None
    order_name: str = ""
    auto_priced: int = 0
    queued: int = 0
    skipped: bool = False
    notes: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.notes.append(msg)


def _find_partner(odoo: OdooClient, name: str, threshold: int) -> dict | None:
    if not name:
        return None
    cands = odoo.find_partners(name, limit=10)
    best, best_score = None, 0
    for c in cands:
        s = max(fuzz.token_set_ratio(name.lower(), (c.get(k) or "").lower())
                for k in ("name", "display_name"))
        if s > best_score:
            best, best_score = c, s
    return best if best and best_score >= threshold else None


def _find_existing(sheets: SheetsClient, tab: str, msg_id: str):
    """(row_1based, is_dry) for a prior Quotes row with this Gmail msg id, else None."""
    if not msg_id:
        return None
    rows = sheets.read(f"{tab}!A2:K")
    for i, r in enumerate(rows):
        if len(r) > Q_GMAIL_MSG and r[Q_GMAIL_MSG] == msg_id:
            return (i + 2, (r[Q_STATUS] if len(r) > Q_STATUS else "") == "Dry-run")
    return None


def apply_rfq(odoo, sheets, cfg, rfq: dict, matches: list[LineMatch],
              gmail_msg_id: str = "", dry_run: bool | None = None) -> QuoteOutcome:
    dry = cfg.get("runtime", {}).get("dry_run", True) if dry_run is None else dry_run
    tabs = cfg["sheets"]["tabs"]
    quotes_tab, pq_tab, audit_tab = tabs["quotes"], tabs["pricing_queue"], tabs["audit"]
    run_mode = "dry-run" if dry else "live"
    rfq_ref = rfq.get("rfq_ref") or ""
    customer = rfq.get("customer_name") or ""
    audit: list[list] = []

    def _audit(action, detail, result):
        audit.append([_now(), rfq_ref or customer, action, detail, result, run_mode])

    def _flush(out):
        for a in audit:
            sheets.append_row(audit_tab, a)
        return out

    auto = [m for m in matches if m.status == "matched"]
    queue = [m for m in matches if m.status == "queue"]
    out = QuoteOutcome(dry_run=dry, status="Dry-run" if dry else "Draft Created",
                       auto_priced=len(auto), queued=len(queue))

    # --- idempotency ---
    existing = _find_existing(sheets, quotes_tab, gmail_msg_id)
    existing_row = None
    if existing:
        existing_row, was_dry = existing
        if not was_dry:
            out.skipped = True
            out.log("RFQ already tracked (live Quotes row) — skipped.")
            _audit("sheet_upsert", f"RFQ msg {gmail_msg_id} already tracked (row {existing_row})", "skipped")
            return _flush(out)

    # --- customer partner ---
    partner = _find_partner(odoo, customer, cfg["rfq"]["match"].get("partner_threshold", 85))
    if not partner:
        out.status = "Needs Review"
        out.log(f"Customer '{customer or '?'}' not found in Odoo — no draft created.")
        _audit("needs_review", f"no Odoo partner for '{customer}'", "ok")
    else:
        lines = [{"product_id": m.product["id"], "product_uom_qty": m.line["quantity"]}
                 for m in auto]  # no price_unit: Odoo prices from the pricelist
        if dry:
            _audit("odoo_create_quote",
                   f"would create draft quote for {partner['name']}: {len(lines)} auto line(s), "
                   f"{len(queue)} queued", "dry-run")
        else:
            out.order_id = odoo.create_draft_quote(partner["id"], lines, client_ref=rfq_ref)
            out.order_name = odoo.read_field("sale.order", out.order_id, "name") or ""
            out.status = "Pending Pricing" if queue else "Draft Created"
            _audit("odoo_create_quote",
                   f"created draft {out.order_name} for {partner['name']} "
                   f"({len(lines)} auto, {len(queue)} queued)", "ok")

    # --- Pricing Queue rows (LIVE only; dry-run just audits intent) ---
    if queue and not dry and partner:
        for m in queue:
            sheets.append_row(pq_tab, [
                _now(), customer, rfq_ref, out.order_name, out.order_id or "",
                m.line.get("part_number") or "", m.line.get("description") or "",
                m.line.get("quantity") or "",
                (m.product or {}).get("name") or "", (m.product or {}).get("id") or "",
                m.reason, "Pending", "", "", "", "",
            ])
        _audit("sheet_upsert", f"queued {len(queue)} line(s) in Pricing Queue", "ok")
    elif queue and dry:
        for m in queue[:5]:
            _audit("needs_pricing", f"would queue: {m.line.get('part_number') or m.line.get('description')}"
                                     f" — {m.reason}", "dry-run")
        if len(queue) > 5:
            _audit("needs_pricing", f"... and {len(queue) - 5} more line(s)", "dry-run")

    # --- Quotes row (lockstep with QUOTES_HEADERS) ---
    quotes_row = [
        _now(), customer, rfq_ref, len(matches),
        out.auto_priced, out.queued,
        out.order_name or ("Dry-run" if dry and partner else ""), out.order_id or "",
        out.status, gmail_msg_id,
        "",  # K Human Notes (human-owned)
    ]
    if existing_row:  # upsert prior dry-run row; preserve K
        sheets.update_range(f"{quotes_tab}!A{existing_row}:J{existing_row}", [quotes_row[0:10]])
        _audit("sheet_upsert", f"updated Quotes row {existing_row}", "ok")
    else:
        sheets.append_row(quotes_tab, quotes_row)
        _audit("sheet_upsert", "appended Quotes row", "ok")
    return _flush(out)
```

- [ ] **Step 2: Sanity-check imports**

Run: `python -c "import sys; sys.path.insert(0,'.'); from core.quote_actions import apply_rfq, QuoteOutcome; print('OK')"` (from `hermes/`)
Expected: `OK` (full behavior is exercised end-to-end in Task 7's dry-run).

- [ ] **Step 3: Commit**

```bash
git add core/quote_actions.py
git commit -m "feat(hermes): quote actions — rfq to draft quotation + tracker rows"
```

---

### Task 7: `scripts/process_rfq.py` — single local file (the test bench)

**Files:**
- Create: `hermes/scripts/process_rfq.py`

**Interfaces:**
- Consumes: `parse_rfq` (Task 3), `match_lines` + `fetch` via `odoo.all_products` (Tasks 4/5), `apply_rfq` (Task 6).

- [ ] **Step 1: Implement**

```python
"""Process one local RFQ file (xlsx/csv/png/jpg/txt) -> parse, match, act.

DEFAULTS TO DRY-RUN (runtime.dry_run). --live creates the draft quotation and
writes Tracker rows. No Gmail involved — this is the test bench; idempotency is
skipped (no Gmail msg id), so repeated --live runs create repeated drafts.

Usage:  python scripts/process_rfq.py <file> [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.rfq_parser import parse_rfq                  # noqa: E402
from core.product_matcher import match_lines           # noqa: E402
from core.quote_actions import apply_rfq               # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.odoo_client import OdooClient, OdooError    # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

KINDS = {".xlsx": "xlsx", ".xlsm": "xlsx", ".png": "image", ".jpg": "image",
         ".jpeg": "image", ".txt": "text", ".csv": "text"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    p = Path(args.file)
    kind = KINDS.get(p.suffix.lower())
    if not kind:
        print(f"Unsupported file type: {p.suffix}")
        return 1
    payload = p.read_text(encoding="utf-8", errors="replace") if kind == "text" else p.read_bytes()

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"RFQ {p.name}   Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")

    rfq = parse_rfq([(kind, p.name, payload)], llm, cfg.get("company", {}))
    print(f"  customer: {rfq.get('customer_name')}   ref: {rfq.get('rfq_ref')}   "
          f"lines: {len(rfq['line_items'])}   source: {rfq.get('_source')}")

    products = odoo.all_products()
    matches = match_lines(rfq["line_items"], products, cfg["rfq"]["match"])
    for m in matches:
        tag = "AUTO " if m.status == "matched" else "QUEUE"
        want = m.line.get("part_number") or m.line.get("description", "")[:40]
        got = (m.product or {}).get("name", "-")
        print(f"  [{tag}] {want!r:45} -> {got[:45]!r}  ({m.score:.0f}) {m.reason}")

    out = apply_rfq(odoo, sheets, cfg, rfq, matches, dry_run=dry)
    print(f"  -> status={out.status}  quote={out.order_name or '-'}  "
          f"auto={out.auto_priced}  queued={out.queued}")
    for n in out.notes:
        print("     ", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Acceptance check (dry-run, real services, writes only Quotes/Audit sim rows)**

Make a throwaway RFQ: a small `.xlsx` with 3–5 real-ish part numbers (at least one that exists in Odoo, one that doesn't) and a customer name matching a real Odoo partner in row 1 (e.g. "RFQ de <partner>: ...").

Run: `python scripts/process_rfq.py sample_rfq.xlsx`
Expected: parsed lines print; each line shows AUTO or QUEUE with a sensible suggestion; final line `status=Dry-run` (or `Needs Review` if the customer name doesn't resolve); a Quotes row with Status `Dry-run` appears in the Sheet; Audit shows `odoo_create_quote ... dry-run` and `needs_pricing` rows. Nothing appears in Odoo.

- [ ] **Step 3: Commit**

```bash
git add scripts/process_rfq.py
git commit -m "feat(hermes): process_rfq test-bench entrypoint"
```

---

### Task 8: `scripts/intake_rfq.py` — Gmail batch

**Files:**
- Create: `hermes/scripts/intake_rfq.py`

**Interfaces:**
- Consumes: `cfg["rfq"]["poll_query"]` / labels (Task 1), `GmailClient.attachments_by_ext` / `body_text` (Task 2), `parse_rfq`, `match_lines`, `apply_rfq`.

- [ ] **Step 1: Implement** (clone `intake.py`'s shape; one-shot, `--watch` optional)

```python
"""Gmail RFQ intake: poll RFQ emails -> parse -> match products -> draft quote -> label.

Mirrors scripts/intake.py. One-shot (timer-friendly); --watch N to keep polling.
Dry-run: nothing written to Odoo, no labels applied, Quotes row logged as Dry-run.
Live: draft quotation created, Pricing Queue populated, message labeled
Hermes/Processed (all lines auto-priced) or Hermes/NeedsReview (anything queued,
customer unknown, or error). Idempotency on Gmail msg id inside apply_rfq.

Usage:  python scripts/intake_rfq.py [--live] [--odoo-db NAME] [--max N] [--watch SECONDS] [--mark-read]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.rfq_parser import parse_rfq                  # noqa: E402
from core.product_matcher import match_lines           # noqa: E402
from core.quote_actions import apply_rfq               # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.gmail_client import GmailClient, GmailError      # noqa: E402
from connectors.odoo_client import OdooClient, OdooError         # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError   # noqa: E402

XLSX_EXTS = (".xlsx", ".xlsm")
IMG_EXTS = (".png", ".jpg", ".jpeg")


def _sources_from_message(gm: GmailClient, full: dict) -> list[tuple[str, str, bytes | str]]:
    """Collect RFQ content: spreadsheets first, then images, then the email body."""
    sources: list[tuple[str, str, bytes | str]] = []
    for fn, data in gm.attachments_by_ext(full, XLSX_EXTS):
        sources.append(("xlsx", fn, data))
    for fn, data in gm.attachments_by_ext(full, IMG_EXTS):
        sources.append(("image", fn, data))
    body = gm.body_text(full)
    if body and not any(k == "xlsx" for k, _, _ in sources):
        sources.append(("text", "email-body", body))
    return sources


def _process_message(gm, odoo, sheets, cfg, llm, products, msg_id, dry, mark_read, lines_out):
    labels = cfg["rfq"]["labels"]
    full = gm.get_message(msg_id)
    subj = (gm.headers(full).get("subject") or "(no subject)")[:50]

    sources = _sources_from_message(gm, full)
    if not sources:
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        lines_out.append(f"  [{'SIM' if dry else 'NeedsReview'}] {subj} — no usable content")
        return

    rfq = parse_rfq(sources, llm, cfg.get("company", {}))
    if not rfq["line_items"]:
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        lines_out.append(f"  [{'SIM' if dry else 'NeedsReview'}] {subj} — no line items extracted")
        return

    matches = match_lines(rfq["line_items"], products, cfg["rfq"]["match"])
    out = apply_rfq(odoo, sheets, cfg, rfq, matches, gmail_msg_id=msg_id, dry_run=dry)

    clean = out.queued == 0 and out.status in ("Draft Created", "Dry-run") and not out.skipped
    if not dry:
        gm.apply_label(msg_id, labels["processed"] if clean else labels["needs_review"],
                       mark_read=mark_read)
    tag = "SIM" if dry else ("Processed" if clean else "NeedsReview")
    lines_out.append(f"  [{tag}] {subj} — {out.status}: quote={out.order_name or '-'} "
                     f"auto={out.auto_priced} queued={out.queued}"
                     + (" (skipped: already tracked)" if out.skipped else ""))


def run_once(gm, odoo, sheets, cfg, llm, dry, max_msgs, mark_read) -> list[str]:
    lines_out: list[str] = []
    msgs = gm.search(cfg["rfq"]["poll_query"], max_results=max_msgs)
    if not msgs:
        return lines_out
    products = odoo.all_products()  # fetch the pool once per batch
    for m in msgs:
        try:
            _process_message(gm, odoo, sheets, cfg, llm, products, m["id"], dry, mark_read, lines_out)
        except Exception as exc:  # one bad message must not kill the batch
            if not dry:
                try:
                    gm.apply_label(m["id"], cfg["rfq"]["labels"]["needs_review"], mark_read=mark_read)
                except Exception:
                    pass
            lines_out.append(f"  [ERROR] msg {m['id']} — {type(exc).__name__}: {exc}")
    return lines_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--watch", type=int, default=0)
    ap.add_argument("--mark-read", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    try:
        gm = GmailClient.from_config(cfg)
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (GmailError, OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"RFQ intake  Gmail: {gm.account}  Odoo db: {cfg['odoo']['db']}  "
          f"mode: {'DRY-RUN' if dry else 'LIVE'}")

    while True:
        try:
            for line in run_once(gm, odoo, sheets, cfg, llm, dry, args.max, args.mark_read) or ["  (no RFQ messages)"]:
                print(line)
        except Exception as exc:
            print(f"[poll] failed: {type(exc).__name__}: {exc}")
        if args.watch <= 0:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Acceptance check**

Forward a real customer RFQ email (subject containing "RFQ") to the Hermes mailbox, leave it unread.
Run: `python scripts/intake_rfq.py`
Expected: `[SIM] <subject> — Dry-run: quote=- auto=N queued=M`; a Dry-run Quotes row appears; inbox untouched (still unread, no labels). Run twice: second run upserts the same row (no duplicate).

- [ ] **Step 3: Commit**

```bash
git add scripts/intake_rfq.py
git commit -m "feat(hermes): intake_rfq gmail batch entrypoint"
```

---

### Task 9: `scripts/apply_quotes.py` — resolve the Pricing Queue

**Files:**
- Create: `hermes/scripts/apply_quotes.py`

**Interfaces:**
- Consumes: PQ column layout (Task 1), Odoo methods (Task 5). Row is actionable when Status == `Pending` AND `Sale Price` filled AND (`Use Product ID` filled OR `Create Product?` == `Yes`).
- Produces: adds the line to the draft order, sets PQ Status = `Resolved`, refreshes the Quotes row's Queued count / Status.

- [ ] **Step 1: Implement**

```python
"""Pricing-queue resolver: apply human pricing decisions back to Odoo drafts.

For each Pricing Queue row a human resolved (Sale Price + either an existing
product id in "Use Product ID" or "Create Product? = Yes"):
  1. create the product if asked (name = Description, code = Part #, price = Sale Price)
  2. add the line to the RFQ's draft quotation (explicit price_unit = human's price)
  3. mark the row Resolved; refresh the Quotes row (Queued count, Status -> Complete at 0)

Idempotency: only rows with Status == "Pending" are touched; Resolved rows never re-apply.
Honors runtime.dry_run (simulate + audit only). NEVER confirms the order.

Usage:  python scripts/apply_quotes.py [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config          # noqa: E402
from core.actions import _now                # noqa: E402
from connectors.odoo_client import OdooClient, OdooError        # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

# Pricing Queue column indices (0-based). Lockstep with PQ_HEADERS in setup_sheet.py.
PQ_ORDER_NAME, PQ_ORDER_ID, PQ_PART, PQ_DESC, PQ_QTY = 3, 4, 5, 6, 7
PQ_SUGG_ID, PQ_STATUS, PQ_PRICE, PQ_USE_ID, PQ_CREATE = 9, 11, 12, 13, 14
# Quotes tab indices. Lockstep with QUOTES_HEADERS.
Q_QUEUED, Q_ORDER_ID, Q_STATUS = 5, 7, 8


def _cell(row, idx) -> str:
    return str(row[idx] if len(row) > idx else "").strip()


def _num(s: str) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("$", ""))
    except (TypeError, ValueError):
        return None


def _refresh_quotes_row(sheets, quotes_tab, pq_rows, order_id) -> None:
    pending = sum(1 for r in pq_rows
                  if _cell(r, PQ_ORDER_ID) == str(order_id) and _cell(r, PQ_STATUS) == "Pending")
    qrows = sheets.read(f"{quotes_tab}!A2:K")
    for i, r in enumerate(qrows):
        if _cell(r, Q_ORDER_ID) == str(order_id):
            status = "Complete" if pending == 0 else "Pending Pricing"
            sheets.update_range(f"{quotes_tab}!F{i + 2}", [[pending]])
            sheets.update_range(f"{quotes_tab}!I{i + 2}", [[status]])
            return


def run_once(odoo, sheets, cfg, dry) -> int:
    tabs = cfg["sheets"]["tabs"]
    pq_tab, quotes_tab, audit_tab = tabs["pricing_queue"], tabs["quotes"], tabs["audit"]
    run_mode = "dry-run" if dry else "live"
    rows = sheets.read(f"{pq_tab}!A2:P")

    applied, touched_orders = 0, set()
    for i, r in enumerate(rows):
        rownum = i + 2
        if _cell(r, PQ_STATUS) != "Pending":
            continue
        price = _num(_cell(r, PQ_PRICE))
        use_id = _cell(r, PQ_USE_ID)
        create = _cell(r, PQ_CREATE).lower() == "yes"
        if price is None or not (use_id or create):
            continue  # human hasn't finished this row

        order_id = _num(_cell(r, PQ_ORDER_ID))
        desc, part = _cell(r, PQ_DESC), _cell(r, PQ_PART)
        qty = _num(_cell(r, PQ_QTY)) or 1.0

        def _audit(action, detail, result):
            sheets.append_row(audit_tab, [_now(), part or desc[:30], action, detail, result, run_mode])

        if order_id is None:
            _audit("error", f"PQ row {rownum} has no Odoo Quote ID", "error")
            if not dry:
                sheets.update_range(f"{pq_tab}!L{rownum}", [["Error"]])
            continue

        if dry:
            what = f"create product '{desc[:40]}'" if create else f"use product {use_id}"
            print(f"  row {rownum}: [SIM] {what}, add to order {int(order_id)} @ {price} x {qty:g}")
            _audit("apply_quote_line", f"would {what} on order {int(order_id)} @ {price}", "dry-run")
            applied += 1
            continue

        try:
            if create:
                product_id = odoo.create_product(desc or part, default_code=part, list_price=price)
                _audit("odoo_create_product", f"created product {product_id} '{desc[:40]}'", "ok")
            else:
                product_id = int(float(use_id))
            odoo.add_quote_lines(int(order_id), [{
                "product_id": product_id, "product_uom_qty": qty, "price_unit": price,
            }])
            sheets.update_range(f"{pq_tab}!L{rownum}", [["Resolved"]])
            _audit("apply_quote_line", f"added product {product_id} to order {int(order_id)} @ {price}", "ok")
            touched_orders.add(int(order_id))
            applied += 1
            print(f"  row {rownum}: product {product_id} -> order {int(order_id)} @ {price} x {qty:g}")
        except Exception as exc:
            sheets.update_range(f"{pq_tab}!L{rownum}", [["Error"]])
            _audit("error", f"PQ row {rownum}: {type(exc).__name__}: {exc}", "error")
            print(f"  row {rownum}: ERROR {exc}")

    if not dry and touched_orders:
        fresh = sheets.read(f"{pq_tab}!A2:P")
        for oid in touched_orders:
            _refresh_quotes_row(sheets, quotes_tab, fresh, oid)
    return applied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1

    print(f"Quote resolver  Odoo db: {cfg['odoo']['db']}   mode: {'DRY-RUN' if dry else 'LIVE'}")
    n = run_once(odoo, sheets, cfg, dry)
    print(f"  -> {n} line(s) {'simulated' if dry else 'applied'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Acceptance check**

Hand-type one Pending row in Pricing Queue against a real draft order id in a test DB (or a live-run RFQ from Task 8 against `--odoo-db` test copy): fill Sale Price + `Create Product? = Yes`.
Run: `python scripts/apply_quotes.py` → prints `[SIM] create product ...`, row untouched.
Run: `python scripts/apply_quotes.py --live --odoo-db <testdb>` → product created, line added to the draft order in Odoo, PQ row `Resolved`, Quotes row Status flips to `Complete` when no Pending rows remain. Re-run: `0 line(s)` (idempotent).

- [ ] **Step 3: Commit**

```bash
git add scripts/apply_quotes.py
git commit -m "feat(hermes): apply_quotes pricing-queue resolver"
```

---

### Task 10 (Phase 2): `scripts/import_pricelist.py` — distributor Excel → Odoo catalog

**Files:**
- Modify: `hermes/config/hermes.config.yaml` (add `pricebook:` block)
- Create: `hermes/scripts/import_pricelist.py`
- Create: `hermes/scripts/test_pricelist.py` (OFFLINE — mapping + markup on a synthetic xlsx)

**Interfaces:**
- Consumes: `norm_code` (Task 4), `create_product` / `product_tmpl_id` / `ensure_vendor` / `upsert_supplierinfo` (Task 5).
- Produces: `read_pricelist(xlsx_bytes, brand_cfg) -> list[dict]` rows `{"part": str, "description": str, "cost": float, "sale_price": float}`.

- [ ] **Step 1: Add config** (one real brand once known; `acme` shows the shape)

```yaml
pricebook:
  default_markup_pct: 25
  brands:
    acme:                              # key used as --brand acme
      vendor_name: "ACME Distribution" # res.partner created/reused as the vendor
      markup_pct: 25                   # sale = cost * (1 + pct/100)
      header_row: 1                    # 1-based row holding the column headers
      columns:                         # header CELL TEXT (exact, case-insensitive)
        part: "Part Number"
        description: "Description"
        cost: "Net Price"
```

- [ ] **Step 2: Write the failing offline test**

`hermes/scripts/test_pricelist.py`:

```python
"""Offline: brand-mapped xlsx -> normalized rows with computed sale price."""
import io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openpyxl import Workbook
from scripts.import_pricelist import read_pricelist

wb = Workbook(); ws = wb.active
ws.append(["Part Number", "Description", "List", "Net Price"])
ws.append(["AB-100", "Contactor 3P 25A", 100.0, 60.0])
ws.append(["AB-200", "Contactor 3P 40A", 150.0, "  $95.50 "])
ws.append([None, "junk row", None, None])
buf = io.BytesIO(); wb.save(buf)

brand = {"vendor_name": "X", "markup_pct": 25, "header_row": 1,
         "columns": {"part": "Part Number", "description": "Description", "cost": "Net Price"}}
rows = read_pricelist(buf.getvalue(), brand)
assert len(rows) == 2
assert rows[0] == {"part": "AB-100", "description": "Contactor 3P 25A", "cost": 60.0, "sale_price": 75.0}
assert rows[1]["cost"] == 95.5 and rows[1]["sale_price"] == 119.38
print("OK test_pricelist")
```

- [ ] **Step 3: Run to verify it fails**

Run: `python scripts/test_pricelist.py`
Expected: `ImportError`/`ModuleNotFoundError` for `scripts.import_pricelist`.

- [ ] **Step 4: Implement `scripts/import_pricelist.py`**

```python
"""Import a distributor Excel/CSV price list into the Odoo catalog.

Per brand (configured under pricebook.brands): upsert products keyed on the
manufacturer part number stored as the product's INTERNAL REFERENCE
(default_code); cost -> product.supplierinfo under the brand's vendor partner;
sale price = cost * (1 + markup_pct/100) -> list_price.

DEFAULTS TO DRY-RUN: prints the would-be creates/updates, writes nothing.

Usage:  python scripts/import_pricelist.py --brand acme path/to/list.xlsx [--live] [--odoo-db NAME]
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config           # noqa: E402
from core.actions import _now                 # noqa: E402
from core.product_matcher import norm_code    # noqa: E402
from connectors.odoo_client import OdooClient, OdooError        # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def read_pricelist(xlsx_bytes: bytes, brand: dict) -> list[dict]:
    """Map the brand's columns; skip rows without part or cost; compute sale price."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    hdr_i = brand.get("header_row", 1) - 1
    header = [str(c or "").strip().lower() for c in rows[hdr_i]]
    want = {k: str(v).strip().lower() for k, v in brand["columns"].items()}
    idx = {}
    for key, label in want.items():
        if label not in header:
            raise SystemExit(f"Column '{brand['columns'][key]}' not found in header row {hdr_i + 1}: {header}")
        idx[key] = header.index(label)

    markup = 1 + (brand.get("markup_pct", 25) / 100.0)
    out = []
    for r in rows[hdr_i + 1:]:
        part = str(r[idx["part"]] or "").strip() if len(r) > idx["part"] else ""
        cost = _num(r[idx["cost"]]) if len(r) > idx["cost"] else None
        if not part or cost is None:
            continue
        desc = str(r[idx["description"]] or "").strip() if len(r) > idx["description"] else ""
        out.append({"part": part, "description": desc, "cost": cost,
                    "sale_price": round(cost * markup, 2)})
    return out


def upsert(odoo: OdooClient, sheets, audit_tab, vendor_id, rows, dry) -> tuple[int, int]:
    run_mode = "dry-run" if dry else "live"
    existing = odoo.search_read("product.product", [], ["default_code"], limit=100000)
    by_code = {norm_code(p.get("default_code")): p["id"] for p in existing if p.get("default_code")}

    created = updated = 0
    for row in rows:
        key = norm_code(row["part"])
        pid = by_code.get(key)
        action = "update" if pid else "create"
        if dry:
            print(f"  [SIM] {action}: {row['part']:<20} cost={row['cost']:<10} sale={row['sale_price']}")
        else:
            if pid is None:
                pid = odoo.create_product(row["description"] or row["part"],
                                          default_code=row["part"], list_price=row["sale_price"])
                created += 1
            else:
                odoo.execute("product.product", "write", [pid], {"list_price": row["sale_price"]})
                updated += 1
            odoo.upsert_supplierinfo(odoo.product_tmpl_id(pid), vendor_id, row["cost"])
    sheets.append_row(audit_tab, [_now(), "pricebook", "import_pricelist",
                                  f"{len(rows)} row(s): {created} created, {updated} updated",
                                  "dry-run" if dry else "ok", run_mode])
    return created, updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    brands = cfg.get("pricebook", {}).get("brands", {})
    if args.brand not in brands:
        print(f"Unknown brand '{args.brand}'. Configured: {', '.join(brands) or '(none)'}")
        return 1
    brand = brands[args.brand]
    rows = read_pricelist(Path(args.file).read_bytes(), brand)
    print(f"Price list '{args.brand}': {len(rows)} usable row(s)   "
          f"markup {brand.get('markup_pct', cfg['pricebook'].get('default_markup_pct', 25))}%   "
          f"mode: {'DRY-RUN' if dry else 'LIVE'}")

    try:
        odoo = OdooClient.from_config(cfg)
        sheets = SheetsClient.from_config(cfg)
    except (OdooError, SheetsError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1

    vendor_id = 0
    if not dry:
        vendor_id = odoo.ensure_vendor(brand["vendor_name"])
    created, updated = upsert(odoo, sheets, cfg["sheets"]["tabs"]["audit"], vendor_id, rows, dry)
    if not dry:
        print(f"  -> {created} created, {updated} updated (vendor '{brand['vendor_name']}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run offline test**

Run: `python scripts/test_pricelist.py` → `OK test_pricelist`

- [ ] **Step 6: Acceptance check (real file, dry-run)**

Configure the first real brand's `columns` mapping from its actual Excel, then:
Run: `python scripts/import_pricelist.py --brand <real> "path/to/lista.xlsx"`
Expected: `[SIM] create/update ...` line per product with sane costs and sale prices; row count matches the file. Then `--live --odoo-db <testdb>` on a test copy before ever touching production.

- [ ] **Step 7: Commit**

```bash
git add config/hermes.config.yaml scripts/import_pricelist.py scripts/test_pricelist.py
git commit -m "feat(hermes): import_pricelist — distributor excel to odoo catalog"
```

---

## Rollout (after all tasks)

1. All offline tests green: `test_rfq_gmail`, `test_rfq_parse`, `test_product_match`, `test_pricelist`.
2. Dry-run soak on the VPS: run `intake_rfq.py` (dry) against real forwarded RFQs for a few days; review Quotes/Audit rows.
3. Import the first brand's price list into a **test DB copy**, spot-check 10 products.
4. Flip to `--live` on RFQ intake; add a systemd timer next to the existing intake timer (same pattern, e.g. every 15 min) and one for `apply_quotes.py`.
5. Update `hermes/CLAUDE.md` commands/invariants with the new scripts and the two new tabs.
