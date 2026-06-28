"""Read-only Odoo connectivity check.

Proves: authentication works, External API is enabled, and the bot user can READ
quotations (needs Sales -> "User: All Documents"). Writes nothing.

Run:  python scripts/test_odoo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.odoo_client import OdooClient, OdooError  # noqa: E402


def main() -> int:
    cfg = load_config()
    try:
        client = OdooClient.from_config(cfg)
        ver = client.version().get("server_version", "?")
        print(f"Connected to {cfg['odoo']['url']}  (Odoo {ver})")
        print(f"Authenticated as uid={client.uid}  (user: {cfg['odoo']['username']})")

        quotes = client.candidate_quotes(
            states=tuple(cfg["matching"]["candidate_states"]),
            lookback_days=cfg["matching"]["lookback_days"],
            limit=5,
        )
        print(f"\nRead {len(quotes)} recent quotation(s) (draft/sent):")
        for q in quotes:
            partner = q["partner_id"][1] if q.get("partner_id") else "?"
            cur = q["currency_id"][1] if q.get("currency_id") else ""
            print(f"  {q['name']:<16} {partner:<32} total={q['amount_total']} {cur}  [{q['state']}]")

        if not quotes:
            print("  (none found — check the bot user has Sales 'User: All Documents', "
                  "or widen lookback_days)")
        print("\nOK — Odoo read path works.")
        return 0
    except OdooError as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
