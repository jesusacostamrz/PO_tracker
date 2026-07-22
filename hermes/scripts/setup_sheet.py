"""Build the PO Tracker spreadsheet structure (idempotent, additive — never deletes).

Creates/updates four tabs and applies headers, header formatting, frozen header row,
status-based row tints on Orders, and dropdowns on the status columns. Re-running is
safe: it rewrites row-1 headers, re-applies formatting, and (if the live column order
differs) remaps existing Orders rows to the current layout in place; it never appends
or removes data rows.

Usage:  python scripts/setup_sheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import load_config  # noqa: E402
from connectors.sheets_client import SheetsClient, SheetsError  # noqa: E402

HERMES_BLUE = (0.20, 0.33, 0.51)   # header band (single navy header, no owner bands)

# Status row tints — exceptions pop, matched stays calm-green.
TINT_MATCHED = (0.85, 0.94, 0.83)   # light green: Matched / Matched (manual)
TINT_REVIEW = (1.00, 0.93, 0.74)    # amber: Needs Review
TINT_NOMATCH = (1.00, 0.80, 0.80)   # red: No Match

# Orders columns, in order (idx in comments). "Manual SO #" sits right after Match
# Notes so a human fixing a Needs-Review row types it next to the status — not at the
# far right. Audit/plumbing columns are hidden (see ORDERS_HIDDEN_COLS) but kept here
# for the data model. Human-owned cells: Manual SO # (K) and Human Verified /
# Invoiced (Confirmed) / Human Notes (T:V) — the writer never clobbers these.
ORDERS_HEADERS = [
    "Received At", "PO #", "Customer", "Salesperson", "Quote/SO #",   # 0-4  A-E
    "PO Amount (untaxed)", "Currency", "Match Status", "Confidence",  # 5-8  F-I
    "Match Notes", "Manual SO #",                                     # 9-10 J-K
    "Odoo SO ID", "Ref Written", "PDF Attached", "Chatter Posted",    # 11-14 L-O
    "Terms Updated", "Invoice Status", "Invoiced (Suggested)",        # 15-17 P-R
    "Gmail Msg ID", "Human Verified", "Invoiced (Confirmed)",         # 18-20 S-U
    "Human Notes",                                                    # 21    V
]

# Columns salespeople don't need day-to-day -> hidden (still there for audit / un-hide).
# Confidence, Odoo SO ID, Ref/PDF/Chatter/Terms Written, raw Invoice Status, Gmail Msg ID.
ORDERS_HIDDEN_COLS = [8, 11, 12, 13, 14, 15, 16, 18]

YN = ["Yes", "No"]
YND = ["Yes", "No", "Dry-run"]
ORDERS_DROPDOWNS = {
    7: ["Matched", "Needs Review", "No Match", "Matched (manual)"],  # Match Status
    12: YND,                                       # Ref Written
    13: YND,                                       # PDF Attached
    14: YND,                                       # Chatter Posted
    15: YND,                                       # Terms Updated
    17: YN,                                        # Invoiced (Suggested)
    19: YN,                                        # Human Verified
    20: YN,                                        # Invoiced (Confirmed)
}

PEOPLE_HEADERS = ["Name", "Gmail", "Manager Name", "Manager Gmail", "Active"]
PEOPLE_DROPDOWNS = {4: YN}

AUDIT_HEADERS = ["Timestamp", "PO #", "Action", "Detail", "Result", "Run Mode"]
AUDIT_DROPDOWNS = {
    2: ["parse", "match", "odoo_write_ref", "odoo_attach_pdf", "odoo_chatter",
        "sheet_upsert", "needs_review", "error"],
    4: ["ok", "dry-run", "error", "skipped"],
    5: ["live", "dry-run"],
}

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

# Dashboard: (label, formula-or-blank). Orders col letters: H=Match Status,
# M=Ref Written, N=PDF Attached, P=Terms, R=Invoiced(Suggested),
# T=Human Verified, U=Invoiced(Confirmed), B=PO #. "Matched*" counts both
# auto "Matched" and resolver-set "Matched (manual)".
DASHBOARD_ROWS = [
    ["Hermes — PO Tracker Dashboard", ""],
    ["", ""],
    ["Total POs received", "=COUNTA(Orders!B2:B)"],
    ["Matched", '=COUNTIF(Orders!H2:H,"Matched*")'],
    ["Needs Review", '=COUNTIF(Orders!H2:H,"Needs Review")'],
    ["No Match", '=COUNTIF(Orders!H2:H,"No Match")'],
    ["", ""],
    ["Refs written to Odoo", '=COUNTIF(Orders!M2:M,"Yes")'],
    ["PDFs attached to Odoo", '=COUNTIF(Orders!N2:N,"Yes")'],
    ["Terms updated in Odoo", '=COUNTIF(Orders!P2:P,"Yes")'],
    ["Awaiting human verify", '=COUNTIF(Orders!H2:H,"Matched*")-COUNTIF(Orders!T2:T,"Yes")'],
    ["", ""],
    ["Invoiced (suggested)", '=COUNTIF(Orders!R2:R,"Yes")'],
    ["Invoiced (confirmed)", '=COUNTIF(Orders!U2:U,"Yes")'],
    ["", ""],
    ["Last setup run", "=TEXT(NOW(),\"yyyy-mm-dd hh:mm\")"],
]


def _apply(sc: SheetsClient, tab: str, headers: list[str], dropdowns: dict) -> None:
    sid = sc.ensure_tab(tab)
    end_col = chr(ord("A") + len(headers) - 1)
    sc.update_range(f"{tab}!A1:{end_col}1", [headers])
    sc.format_header(sid, len(headers), rgb=HERMES_BLUE)
    for col, values in dropdowns.items():
        sc.add_dropdown(sid, col, values)
    sc.auto_resize(sid, len(headers))
    print(f"  [{tab}] {len(headers)} cols, {len(dropdowns)} dropdown(s)")


def _reorder_orders_data(sc: SheetsClient, tab: str, new_headers: list[str]) -> bool:
    """Remap existing Orders rows to ``new_headers`` order (name-based; idempotent).

    Reads the CURRENT header row to learn the live column order, then rewrites every
    data row so each value lands under the same-named column in the new layout. Does
    nothing if the live header already matches or the tab has no data. MUST run before
    the new header is written (it relies on the live header still describing the data).
    """
    existing = sc.read(f"{tab}!1:1")
    old_header = existing[0] if existing else []
    if not old_header or old_header == new_headers:
        return False
    end_col = chr(ord("A") + len(new_headers) - 1)
    data = sc.read(f"{tab}!A2:{end_col}")
    if not data:
        return False
    pos = {name: i for i, name in enumerate(old_header)}
    new_data = [
        [row[pos[name]] if (name in pos and pos[name] < len(row)) else "" for name in new_headers]
        for row in data
    ]
    sc.update_range(f"{tab}!A2:{end_col}{1 + len(new_data)}", new_data)
    print(f"  [{tab}] reordered {len(new_data)} existing data row(s) to the new layout")
    return True


def _style_orders(sc: SheetsClient, sid: int, n_cols: int) -> None:
    """Make Orders read like a task list: banding, status-colored rows, clean columns, filter."""
    sc.clear_visual_rules(sid)                 # idempotent: drop prior rules before re-adding
    sc.add_banding(sid, n_cols)
    # Rows tinted purely by Match Status. Exceptions pop (amber/red); matched is calm green.
    # '^Matched' catches both "Matched" and the resolver's "Matched (manual)".
    sc.add_conditional_rule(sid, n_cols, '=REGEXMATCH($H2,"^Matched")', TINT_MATCHED)  # green
    sc.add_conditional_rule(sid, n_cols, '=$H2="No Match"', TINT_NOMATCH)              # red
    sc.add_conditional_rule(sid, n_cols, '=$H2="Needs Review"', TINT_REVIEW)           # amber
    sc.set_number_format(sid, 5, "#,##0.00")   # PO Amount (untaxed)
    sc.hide_columns(sid, list(range(n_cols)), hidden=False)  # reset so a moved col un-hides
    sc.hide_columns(sid, ORDERS_HIDDEN_COLS)
    sc.set_basic_filter(sid, n_cols)
    print(f"  [Orders] visuals: banding, status row-colors, amount format, "
          f"{len(ORDERS_HIDDEN_COLS)} cols hidden, header filter on")


def main() -> int:
    cfg = load_config()
    try:
        sc = SheetsClient.from_config(cfg)
    except SheetsError as exc:
        print(f"FAILED: {exc}")
        return 1

    tabs = cfg["sheets"]["tabs"]  # configured display names
    print(f"Spreadsheet {sc.spreadsheet_id}")
    print("Existing tabs:", ", ".join(sc.tab_names()) or "(none)")

    orders_tab = tabs["orders"]
    sc.ensure_tab(orders_tab)
    _reorder_orders_data(sc, orders_tab, ORDERS_HEADERS)  # migrate live rows BEFORE new header
    _apply(sc, orders_tab, ORDERS_HEADERS, ORDERS_DROPDOWNS)
    _style_orders(sc, sc.sheet_ids()[orders_tab], len(ORDERS_HEADERS))
    _apply(sc, tabs["people"], PEOPLE_HEADERS, PEOPLE_DROPDOWNS)
    _apply(sc, tabs["audit"], AUDIT_HEADERS, AUDIT_DROPDOWNS)

    # Dashboard: KPI list (label col A, value col B); header band on row 1.
    dash = tabs["dashboard"]
    sid = sc.ensure_tab(dash)
    sc.update_range(f"{dash}!A1:B{len(DASHBOARD_ROWS)}", DASHBOARD_ROWS)
    sc.format_header(sid, 2, rgb=HERMES_BLUE)
    sc.auto_resize(sid, 2)
    print(f"  [{dash}] {len(DASHBOARD_ROWS)} KPI rows")

    print("\nDone. PO Tracker tabs:", ", ".join(sc.tab_names()))
    print("Orders rows tint by Match Status: green=matched · amber=needs review · red=no match.")

    # --- Quotes workbook (separate spreadsheet; skipped if its id isn't configured) ---
    try:
        qc = SheetsClient.from_config(cfg, key="quotes_spreadsheet_id")
    except SheetsError as exc:
        print(f"\nQuotes workbook SKIPPED: {exc}")
        return 0
    print(f"\nQuotes spreadsheet {qc.spreadsheet_id}")
    print("Existing tabs:", ", ".join(qc.tab_names()) or "(none)")
    _apply(qc, tabs["quotes"], QUOTES_HEADERS, QUOTES_DROPDOWNS)
    _apply(qc, tabs["pricing_queue"], PQ_HEADERS, PQ_DROPDOWNS)
    _apply(qc, tabs["audit"], AUDIT_HEADERS, AUDIT_DROPDOWNS)  # quotes pipeline audits here
    print("Done. Quotes workbook tabs:", ", ".join(qc.tab_names()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
