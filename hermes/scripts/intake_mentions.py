"""Odoo mention intake: poll chatter mentions of Unicontrolbot on Sales Orders,
build a purchase requisition from the SO's quantities + attached supplier quote.

Command in a chatter note on a sale.order, addressed to the bot:
    @Unicontrolbot req [--shortage] [vendor name]
    Unicontrolbot: requisicion SKS

Long-running poller like intake_req.py. Reads mail.message ids newer than a
persisted watermark so history is never replayed; state lives in a small JSON
file (``req.mentions_state`` in config).

Usage: python scripts/intake_mentions.py [--live] [--odoo-db NAME] [--watch SECONDS]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config                    # noqa: E402
from core.requisition import from_sales_order           # noqa: E402
from connectors.llm_client import LLMClient            # noqa: E402
from connectors.odoo_client import OdooClient, OdooError         # noqa: E402

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# anywhere in the note: "@antonio.acosta @Unicontrolbot req sks" is a command too, and so is
# "@Unicontrolbot @antonio.acosta req SKS" (other @mentions may sit between bot and verb)
_CMD_RE = re.compile(
    r"@?unicontrolbot[,:]?\s*(?:@[\w.\-]+[,:]?\s*)*(req|requisici[oó]n)\b\s*(?:--shortage\s*)?(.*)$", re.I)


def _plain(body_html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", unescape(str(body_html or "")))).strip()


def parse_command(body_html: str) -> tuple[str | None, bool] | None:
    """(vendor_hint or None, shortage) if the message is a req command, else None."""
    text = _plain(body_html)
    m = _CMD_RE.search(text)
    if not m:
        return None
    shortage = bool(re.search(r"--shortage\b", text, re.I))
    # vendor = words up to the next @mention / sentence break ("req SKS @Antonio favor de..."
    # -> "SKS"); the rest of the note is for humans
    rest = re.split(r"[@,.;:\n]", m.group(2), maxsplit=1)[0]
    vendor_hint = re.sub(r"--shortage\b", "", rest, flags=re.I).strip() or None
    return vendor_hint, shortage


def _load_state(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def run_once(odoo, cfg, llm, dry, state_path: Path) -> list[str]:
    lines_out: list[str] = []
    state = _load_state(state_path)
    bot_partner_id = odoo.read_field("res.users", odoo.uid, "partner_id")
    if isinstance(bot_partner_id, (list, tuple)):
        bot_partner_id = bot_partner_id[0]

    if "last_id" not in state:
        # first run: initialize watermark to current max id, process nothing
        # so pre-existing history is never replayed.
        latest = odoo.search_read(
            "mail.message",
            [["partner_ids", "in", [bot_partner_id]], ["model", "=", "sale.order"]],
            ["id"], limit=1, order="id desc")
        state["last_id"] = latest[0]["id"] if latest else 0
        _save_state(state_path, state)
        lines_out.append(f"  [init] watermark set to message id {state['last_id']}")
        return lines_out

    msgs = odoo.search_read(
        "mail.message",
        [["partner_ids", "in", [bot_partner_id]], ["model", "=", "sale.order"],
         ["id", ">", state["last_id"]]],
        ["id", "res_id", "body", "author_id", "date"], order="id asc")
    if not msgs:
        return lines_out

    last_id = state["last_id"]
    for msg in msgs:
        last_id = msg["id"]
        cmd = parse_command(msg.get("body"))
        if not cmd:  # mentioned without a command — say so, so a typo is visible in the log
            lines_out.append(f"  [skip] msg {msg['id']} on sale.order {msg['res_id']} — no req command: "
                             f"{_plain(msg.get('body'))[:80]!r}")
            continue
        vendor_hint, shortage = cmd
        so_name = None
        try:
            so_name = odoo.read_field("sale.order", msg["res_id"], "name")
            if not so_name:
                lines_out.append(f"  [ERROR] msg {msg['id']} — res_id {msg['res_id']} is not a sale.order")
                continue
            created = from_sales_order(odoo, llm, cfg, so_name, vendor_hint=vendor_hint,
                                       shortage=shortage, live=not dry, out=lines_out.append)
            lines_out.append(f"  [{'SIM' if dry else 'Processed'}] {so_name} — "
                             f"{len(created)} draft RFQ(s) created"
                             + (" (shortage)" if shortage else ""))
        except RuntimeError as exc:
            lines_out.append(f"  [ERROR] {so_name or msg['res_id']} — {exc}")
            if not dry:
                try:
                    odoo.post_chatter(msg["res_id"], f"<p>Hermes: {exc}</p>", model="sale.order")
                except Exception:
                    pass
        except Exception as exc:  # one bad message must not kill the batch or block the watermark
            lines_out.append(f"  [ERROR] msg {msg['id']} — {type(exc).__name__}: {exc}")

    state["last_id"] = last_id
    _save_state(state_path, state)
    return lines_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--odoo-db", default=None)
    ap.add_argument("--watch", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config()
    if args.odoo_db:
        cfg["odoo"]["db"] = args.odoo_db
    dry = cfg.get("runtime", {}).get("dry_run", True) and not args.live
    state_path = Path(cfg["req"].get("mentions_state", ".state/mentions.json"))
    if not state_path.is_absolute():
        state_path = Path(__file__).resolve().parents[1] / state_path

    try:
        odoo = OdooClient.from_config(cfg)
    except OdooError as exc:
        print(f"FAILED (connect): {exc}")
        return 1
    llm = LLMClient.from_config(cfg)
    print(f"Mentions intake  Odoo db: {cfg['odoo']['db']}  mode: {'DRY-RUN' if dry else 'LIVE'}")

    while True:
        try:
            for line in run_once(odoo, cfg, llm, dry, state_path) or ["  (no mentions)"]:
                print(line)
        except Exception as exc:
            print(f"[poll] failed: {type(exc).__name__}: {exc}")
        if args.watch <= 0:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
