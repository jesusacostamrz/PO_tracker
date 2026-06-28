# Hermes Agent — Complete Build Task List

Owner legend:
- 👤 **You** — needs a login, payment, admin console, OAuth consent, or a secret. I can't do it for you, but I'll give you exact step-by-step instructions.
- 🤖 **Me** — I do it fully (code, config, docs, scaffolding).
- 🤝 **Shared** — I build it; you provide a credential / authorize / run it on your machine / approve a write.

Source plan: `C:\Users\jesus\.claude\plans\i-want-to-create-soft-duckling.md`

---

## ✅ Confirmed
**Odoo Online already exists** with your real quotes/invoices — only the Hermes **bot user** is new.
Matching works from day one (no quote-history bootstrap needed) and there is no Odoo instance to provision.

> **Odoo Online note:** no git staging branches (that's Odoo.sh only). We test the write path against a
> **duplicate "test" database** created from the Odoo database manager. The connector still uses the same
> XML-RPC External API + API key. Verify External API access is enabled on your plan (Standard/Custom paid
> plans have it; the "one-app-free" tier does not).

---

## Phase 0A — Foundational accounts

- [x] ✅ **Hermes mailbox** — `pounicontrol@gmail.com` (plain Gmail) already created. No Workspace/domain/MX needed.
- [ ] 👤 **LLM API** — get an **API key** (NOT a chat subscription): either **OpenAI API** (platform.openai.com, pay-per-token) or **GLM/Zhipu** (their Coding Plan *does* include API access). Must be **vision-capable** (some POs are scanned images). Build is provider-agnostic via the OpenAI-compatible interface.
- [ ] 👤 **Hostinger VPS** — buy a **KVM VPS** (NOT shared "Web Hosting"), OS **Ubuntu 24.04 LTS**. This is where Hermes runs 24/7.
- [x] ✅ **Odoo** — already exists (Custom plan = External API available); bot user `Unicontrolbot` on db `unicontrol` created.

## Phase 0B — Provision inside those accounts (YOU; I give exact steps)

- [ ] 👤 **Google Cloud project** — create a project (free) at console.cloud.google.com (sign in as `pounicontrol@gmail.com`).
- [ ] 👤 **Enable APIs** — Gmail API + Google Sheets API + Drive API in that project.
- [ ] 👤 **Google credentials** — (a) an **OAuth client (Desktop app)** for Gmail read/send — add `pounicontrol@gmail.com` as a test user, then **publish to Production** so the login doesn't expire every 7 days; (b) a **service account** for Sheets. Download both JSON files. *(Service accounts can't read consumer Gmail, so Gmail must use OAuth — that's why there are two.)*
- [ ] 👤 **Blank PO Tracker sheet** — create a new Google Sheet, then **share it (Editor)** with the service-account email. *(I scaffold the tabs/columns later.)*
- [ ] 👤 **LLM API key** — generate it in OpenAI or GLM console; confirm the model id you'll use.
- [x] ✅ **Odoo URL + database name** — `https://unicontrol.odoo.com` / db `unicontrol`.
- [x] ✅ **Odoo "Hermes" user + API key** — `Unicontrolbot` created; API key generated (held as a secret). *(Verify it has Sales → "User: All Documents".)*
- [ ] 👤 **Odoo test database** — when we're ready to test writes, duplicate your DB to a **test copy** from the database manager (expires ~15 days; renewable).
- [ ] 👤 **Salespeople map** — give me each salesperson's Gmail + their manager.

> Hand me each JSON/key by dropping it in `hermes/.secrets/` (never committed) or pasting the values.

---

## Phase 1 — Local scaffolding (ME — needs nothing from you, can start now)

- [ ] 🤖 `hermes/` project skeleton (folders + module files per plan).
- [ ] 🤖 `requirements.txt` (`google-api-python-client`, `google-auth(-oauthlib)`, `openai` (works for OpenAI **and** GLM via base_url), `pyyaml`, `pdfplumber`; Odoo via stdlib `xmlrpc.client`).
- [ ] 🤖 `hermes.config.yaml` ("Configuration C") with placeholders.
- [ ] 🤖 `.env.example`, `.gitignore`, `.secrets/` layout.
- [ ] 🤖 Connectors: `gmail_client.py`, `odoo_client.py`, `sheets_client.py`, `po_parser.py`.
- [ ] 🤖 Core: `matcher.py`, `tracker.py`, `digest.py`.
- [ ] 🤖 Skills: `process-po-inbox/`, `daily-order-digest/`.
- [ ] 🤖 Entrypoints: `run_intake.py`, `run_digest.py`.

---

## Phase 2 — Wire up & prove auth (SHARED — after Phase 0)

- [ ] 🤝 First-run OAuth: I run the read-only tests; **you click "Allow"** in the browser consent (one time).
- [ ] 🤝 Read-only smoke tests: Gmail list, Sheets read, Odoo read quotes — prove all three connect.
- [ ] 🤖 **Scaffold the PO Tracker tabs/columns** (Orders / Dashboard / Salespeople / Audit; Hermes-owned vs human-owned columns; dropdowns).
- [ ] 👤 **Auto-forward filters** — per-salesperson Gmail filter so customer POs forward to the Hermes mailbox automatically.

---

## Phase 3 — Build features (ME builds; YOU verify/approve)

- [ ] 🤖 **PO parser** — email + PDF → structured fields; inline vs attached PDFs; scanned/image fallback via vision.
- [ ] 🤖 **Matcher** — partner resolve (exact + fuzzy + alias map) + line/total scoring within tolerance → confidence + audit trail.
- [ ] 🤖 **Tracker upsert** — Received/Matched rows (Hermes-owned cols only); idempotency on Gmail msg ID + PO#.
- [ ] 🤝 **Odoo write path** — `client_order_ref`, attach PDF, chatter note (no auto-confirm). **You approve the first writes on the test database.**
- [ ] 🤖 **Needs-review + notifications** — Gmail label, email owning salesperson w/ ranked candidates, Needs-review row.
- [ ] 🤖 **Invoice sync (hybrid close)** — poll `invoice_status`; set `Invoiced_Suggested`, notify; human confirms in the Sheet.
- [ ] 🤖 **Digest + dashboard** — daily per-salesperson + manager rollup; weekly Dashboard pivots/charts.

---

## Phase 4 — Deploy to the Hostinger VPS (SHARED)

- [ ] 👤 Provision the **KVM VPS** (Ubuntu 24.04 LTS); create an SSH key.
- [ ] 🤝 Harden: non-root sudo user, SSH-key-only login, UFW firewall, auto-updates. (I give exact commands; you run them — or grant SSH and I run them.)
- [ ] 🤝 Deploy: clone/copy the `hermes/` code, create a Python venv, install `requirements.txt`, place secrets in `.secrets/.env` (chmod 600).
- [ ] 🤝 **Gmail OAuth bootstrap**: do the one-time browser consent on your laptop → copy the resulting token file to the VPS (headless servers have no browser).
- [ ] 🤝 Schedule with **systemd timers** (intake ~15 min; digest daily; dashboard weekly).

## Phase 5 — Harden & verify (SHARED)

- [ ] 🤖 Dry-run mode, logging, retries, failure alerts (email on crash).
- [ ] 🤝 **End-to-end verification**: sample PO dry-run → test-DB write → Sheet round-trip → Needs-review → invoice/close → digest. You confirm each.
- [ ] 👤 Point the manager rollup at yourself first, review, then switch to real managers.

---

## Summary — every task that is YOURS

**Accounts/keys to get:** LLM API key (OpenAI **or** GLM) · Hostinger **KVM VPS** (Ubuntu 24.04) · Google Cloud project + APIs + 2 credential files.
**Provisioning:** blank PO Tracker sheet (shared to service acct) · salespeople/Gmail/manager list · per-person auto-forward filters · SSH key for the VPS.
**Already done:** ✅ Hermes Gmail · ✅ Odoo bot user + API key + url/db.
**Approvals:** Gmail OAuth consent · first Odoo test-DB writes · enabling the systemd timers.

Everything else (all the code) is mine and can start immediately.
