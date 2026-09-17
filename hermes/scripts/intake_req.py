"""Gmail requisitions: parse body/attachments -> products -> vendor draft purchase RFQs.

Reuses RFQ extraction; unknown products auto-create at sale price zero in live mode.
Draft purchases are grouped by vendor, with a placeholder for unknown vendors.
Existing purchases with the same subject origin and vendor are skipped.
Never confirms or sends; dry-run creates nothing and applies no Gmail labels.

Usage: python scripts/intake_req.py [--live] [--odoo-db NAME] [--max N] [--watch SECONDS] [--mark-read]
"""
from __future__ import annotations

import argparse
import sys
import time
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.rfq_parser import parse_rfq                  # noqa: E402
from core.product_matcher import match_lines           # noqa: E402
from core.quote_actions import _trusted, _create_missing_products, set_unspsc  # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.gmail_client import GmailClient, GmailError      # noqa: E402
from connectors.odoo_client import OdooClient, OdooError         # noqa: E402
from scripts.intake_rfq import _sources_from_message   # noqa: E402
from scripts.order_purchasing import plan_rfqs          # noqa: E402


def _process_message(gm, odoo, cfg, llm, products, msg_id, dry, mark_read, lines_out):
    labels = cfg["req"]["labels"]
    full = gm.get_message(msg_id)
    subj_full = gm.headers(full).get("subject") or "(no subject)"
    subj = subj_full[:50]

    sources = _sources_from_message(gm, full)
    sources.insert(0, ("text", "email-subject", f"EMAIL SUBJECT: {subj_full}"))

    rfq = parse_rfq(sources, llm, cfg.get("company", {}))
    if not rfq["line_items"]:
        if not dry:
            gm.apply_label(msg_id, labels["needs_review"], mark_read=mark_read)
        lines_out.append(f"  [{'SIM' if dry else 'NeedsReview'}] {subj} — no line items extracted")
        return

    matches = match_lines(rfq["line_items"], products, cfg["rfq"]["match"])
    if dry:
        for m in matches:  # no catalog product: dry-run shows what live would create
            if not _trusted(m):
                name = m.line.get("part_number") or m.line.get("description") or "Unknown item"
                lines_out.append(f"  [SIM] would create product {name!r} (list_price=0)")
                m.product = {"id": 0, "name": name}
    else:
        # same path as the RFQ/PO flows: accounts from product_defaults, dedup by
        # part#, UNSPSC best-effort — products stay consistent whoever creates them
        audit = lambda *a: lines_out.append("  [audit] " + " ".join(str(x) for x in a))  # noqa: E731
        created_products, _ = _create_missing_products(odoo, cfg, matches, audit)
        pdef = cfg["rfq"].get("product_defaults") or {}
        if created_products and pdef.get("unspsc", True):
            try:
                set_unspsc(odoo, llm, created_products, audit,
                           fallback=str(pdef.get("unspsc_fallback") or ""))
            except Exception as exc:
                audit("unspsc", f"{type(exc).__name__}: {exc}", "error")
        products.extend({"id": pid, "name": name, "list_price": 0.0}
                        for pid, name, *_ in created_products)  # reusable within this batch
    to_buy = [{"product_id": m.product["id"], "part": m.product["name"], "buy": m.line["quantity"]}
              for m in matches]

    # ponytail: Gmail msg-id tail keeps the origin unique — the per-vendor SKIP in
    # plan_rfqs keys on origin, and requisition subjects repeat ("REQ semanal")
    origin = f"{subj_full.strip()[:48]} #{msg_id[-6:]}"
    created, _ = plan_rfqs(odoo, origin, to_buy, live=not dry, out=lines_out.append)
    if not dry:
        sender = gm.headers(full).get("from") or "(sin remitente)"
        for rfq_id, _, _ in created:
            odoo.post_chatter(rfq_id,
                              "<p>Hermes creó esta solicitud de presupuesto de compra "
                              f"en borrador desde el correo de {escape(sender)}. "
                              f"Asunto: {escape(subj_full)}.</p>", model="purchase.order")
        # Nonempty lines: each vendor was created or skipped because it already exists.
        gm.apply_label(msg_id, labels["processed"], mark_read=mark_read)
    tag = "SIM" if dry else "Processed"
    lines_out.append(f"  [{tag}] {subj} — {len(created)} draft RFQ(s) created"
                     + (" (skipped: already existing)" if not dry and not created else ""))


# Transient network failures are retried on later polls instead of being labeled
# NeedsReview (which would permanently exclude the message from the poll query).
# ponytail: in-memory counter — resets on restart, which just re-grants 3 tries.
_TRANSIENT = (TimeoutError, ConnectionError)
_RETRY_CAP = 3
_transient_fails: dict[str, int] = {}


def run_once(gm, odoo, cfg, llm, dry, max_msgs, mark_read) -> list[str]:
    lines_out: list[str] = []
    msgs = gm.search(cfg["req"]["poll_query"], max_results=max_msgs)
    if not msgs:
        return lines_out
    products = odoo.all_products()  # fetch the pool once per batch
    for m in msgs:
        try:
            _process_message(gm, odoo, cfg, llm, products, m["id"], dry, mark_read, lines_out)
            _transient_fails.pop(m["id"], None)
        except Exception as exc:  # one bad message must not kill the batch
            if isinstance(exc, _TRANSIENT):
                n = _transient_fails[m["id"]] = _transient_fails.get(m["id"], 0) + 1
                if n < _RETRY_CAP:
                    lines_out.append(f"  [RETRY {n}/{_RETRY_CAP}] msg {m['id']} — "
                                     f"{type(exc).__name__}: {exc} (will retry next poll)")
                    continue
            if not dry:
                try:
                    gm.apply_label(m["id"], cfg["req"]["labels"]["needs_review"], mark_read=mark_read)
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
    # Default ON — see intake.py: the unread-only poll query relies on it.
    ap.add_argument("--mark-read", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live

    try:
        gm = GmailClient.from_config(cfg)
        odoo = OdooClient.from_config(cfg)
    except (GmailError, OdooError) as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"REQ intake  Gmail: {gm.account}  Odoo db: {cfg['odoo']['db']}  "
          f"mode: {'DRY-RUN' if dry else 'LIVE'}")

    while True:
        try:
            for line in run_once(gm, odoo, cfg, llm, dry, args.max, args.mark_read) or ["  (no REQ messages)"]:
                print(line)
        except Exception as exc:
            print(f"[poll] failed: {type(exc).__name__}: {exc}")
        if args.watch <= 0:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
