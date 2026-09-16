"""Normalize the human-owned "Human Pendiente" (owner) column on the Orders tab
and attach a dropdown so the names stay consistent.

Dry-run by default (prints the cells it would change). --live writes.

Run:  python scripts/fix_owner_names.py [--live]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.sheets_client import SheetsClient  # noqa: E402

OWNERS = ["Antonio Acosta", "Miguel Bustamante", "Jesus Acosta", "Alejandro Dominguez",
          "Karina Lugo", "Roberto Jimenez", "Cuentas por Cobrar"]
COLUMN = "Human Pendiente"


def canon(raw: str) -> str:
    key = " ".join(raw.split()).lower()
    if not key:
        return ""
    toks = key.split()
    # ponytail: first name wins, then last name (two Acostas); extend OWNERS for new people
    for pos in (0, -1):
        for name in OWNERS:
            if toks[pos] == name.lower().split()[pos]:
                return name
    if key.startswith("cuen"):
        return "Cuentas por Cobrar"
    return raw  # unknown: leave untouched, reported below


def col_letter(i: int) -> str:
    return chr(ord("A") + i)


def main() -> int:
    live = "--live" in sys.argv
    cfg = load_config()
    sh = SheetsClient.from_config(cfg)
    tab = cfg["sheets"]["tabs"]["orders"] if "tabs" in cfg["sheets"] else "Orders"
    rows = sh.read(f"{tab}!A1:Z")
    headers = rows[0]
    if COLUMN not in headers:
        print(f"Column {COLUMN!r} not found in {headers}")
        return 1
    ci = headers.index(COLUMN)
    changes, unknown = [], []
    for r, row in enumerate(rows[1:], start=2):
        raw = row[ci] if ci < len(row) else ""
        new = canon(raw)
        if new != raw:
            if new not in OWNERS:
                unknown.append((r, raw))
            changes.append((r, raw, new))
    for r, raw, new in changes:
        print(f"row {r}: {raw!r} -> {new!r}")
    for r, raw in unknown:
        print(f"row {r}: unknown owner {raw!r} (left as is)")
    print(f"{len(changes)} cells to change; dropdown on column {col_letter(ci)} = {OWNERS}")
    if not live:
        print("dry-run: nothing written (add --live)")
        return 0
    for r, _raw, new in changes:
        sh.update_range(f"{tab}!{col_letter(ci)}{r}", [[new]])
    sh.add_dropdown(sh.sheet_ids()[tab], ci, OWNERS)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _selfcheck() -> None:
    assert canon("AntoniO aCOSTA") == "Antonio Acosta"
    assert canon("Alejandrio  Dominguez") == "Alejandro Dominguez"
    assert canon("Karina") == "Karina Lugo"
    assert canon("Someone Else") == "Someone Else"
    assert canon("Cuenats por Cobrar") == "Cuentas por Cobrar"
    assert canon("jesus acosta") == "Jesus Acosta"
    assert canon("") == ""
