"""Offline self-check for actions._find_existing dedupe logic (no network).

Regression: a 2nd PDF in the same email must NOT be skipped just because the
1st PDF's Tracker row carries the same Gmail msg id.

  python scripts/test_dedupe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.actions import _find_existing, _other_po_on_quote  # noqa: E402


class FakeSheets:
    def __init__(self, rows):
        self.rows = rows

    def read(self, _rng):
        return self.rows


def _row(po, msg_id, ref="Yes"):
    r = [""] * 18
    r[0], r[11], r[17] = po, ref, msg_id
    return r


def main() -> int:
    sheets = FakeSheets([_row("PO-111", "msg-A")])

    # same PO# -> dup (regardless of msg id)
    assert _find_existing(sheets, "Orders", "PO-111", "msg-Z") == (2, False)
    # DIFFERENT PO#, same email -> NOT a dup (the multi-PDF bug)
    assert _find_existing(sheets, "Orders", "PO-222", "msg-A") is None
    # no PO number parsed -> msg id is the only key -> dup
    assert _find_existing(sheets, "Orders", "", "msg-A") == (2, False)
    # nothing in common -> no dup
    assert _find_existing(sheets, "Orders", "PO-222", "msg-Z") is None
    # dry-run row is reported as such (upsertable)
    dry = FakeSheets([_row("PO-333", "msg-B", ref="Dry-run")])
    assert _find_existing(dry, "Orders", "PO-333", "") == (2, True)

    # 2nd PO on a quote already linked to another live PO -> flagged
    q = _row("PO-1", "m1"); q[3] = "S03354"
    assert _other_po_on_quote(FakeSheets([q]), "Orders", "S03354", "PO-2") == "PO-1"
    assert _other_po_on_quote(FakeSheets([q]), "Orders", "S03354", "PO-1") == ""   # own row
    assert _other_po_on_quote(FakeSheets([q]), "Orders", "S09999", "PO-2") == ""   # other quote
    qd = _row("PO-1", "m1", ref="Dry-run"); qd[3] = "S03354"
    assert _other_po_on_quote(FakeSheets([qd]), "Orders", "S03354", "PO-2") == ""  # dry-run ignored

    print("test_dedupe: OK (9 cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
