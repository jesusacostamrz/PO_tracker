"""Read-only Google Sheets connectivity check.

Authenticates with the service account, opens the PO Tracker by ID, and prints
the spreadsheet title and its tab names. Writes nothing.

Run:  python scripts/test_sheets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402


def main() -> int:
    cfg = load_config()
    try:
        sh = SheetsClient.from_config(cfg)
        meta = sh.meta()
        title = meta.get("properties", {}).get("title", "?")
        tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
        print(f"Connected to spreadsheet: {title!r}")
        print(f"Spreadsheet ID: {sh.spreadsheet_id}")
        print(f"Tabs ({len(tabs)}): {', '.join(tabs)}")
        print("\nOK — Sheets read path works.")
        return 0
    except SheetsError as exc:
        print(f"FAILED: {exc}")
        return 1
    except Exception as exc:  # surface API/permission errors readably
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print("(If this is a 403, share the Sheet with the service-account email as Editor.)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
