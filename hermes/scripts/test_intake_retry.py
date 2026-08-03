"""Offline check: transient errors retry without labeling; cap -> NeedsReview; others label at once."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.intake as intake  # noqa: E402

CFG = {"gmail": {"poll_query": "q", "labels": {"needs_review": "Hermes/NeedsReview"}}}


class FakeGmail:
    def __init__(self):
        self.labeled = []

    def search(self, query, max_results=25):
        return [{"id": "m1"}]

    def apply_label(self, msg_id, label, mark_read=False):
        self.labeled.append((msg_id, label))


def run(gm):
    with patch.object(intake, "candidate_quotes", lambda odoo, cfg: []):
        return intake.run_once(gm, None, None, CFG, None, dry=False, max_msgs=25, mark_read=False)


def main():
    # 1) transient error: no label, marked for retry
    intake._transient_fails.clear()
    gm = FakeGmail()
    with patch.object(intake, "_process_message", side_effect=TimeoutError("read timed out")):
        st = run(gm)
    assert st.errored == 1 and gm.labeled == [], (st, gm.labeled)
    assert "RETRY 1/3" in st.labeled[0]

    # 2) third consecutive transient failure -> NeedsReview label
    with patch.object(intake, "_process_message", side_effect=TimeoutError("read timed out")):
        run(gm)
        st = run(gm)
    assert gm.labeled == [("m1", "Hermes/NeedsReview")], gm.labeled
    assert "[ERROR]" in st.labeled[0]

    # 3) success clears the counter
    intake._transient_fails["m1"] = 2
    gm = FakeGmail()
    with patch.object(intake, "_process_message", lambda *a, **k: None):
        run(gm)
    assert "m1" not in intake._transient_fails

    # 4) non-transient error labels immediately
    intake._transient_fails.clear()
    gm = FakeGmail()
    with patch.object(intake, "_process_message", side_effect=ValueError("bad pdf")):
        st = run(gm)
    assert gm.labeled == [("m1", "Hermes/NeedsReview")] and "[ERROR]" in st.labeled[0]

    print("OK: transient retry x2, cap->NeedsReview, counter reset, non-transient labels at once")


if __name__ == "__main__":
    main()
