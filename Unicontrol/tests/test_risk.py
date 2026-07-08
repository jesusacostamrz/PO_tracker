import unittest
from datetime import date, timedelta

from uc.core.models import Task
from uc.core.risk import assess

_A = date(2026, 1, 1)
_TODAY = _A + timedelta(days=21)  # 2026-01-22


def _t(i, deps, off, dur, done=False, progress=0.0):
    return Task(
        id=i, name=f"T{i}", depends_on=deps,
        planned_start=_A + timedelta(days=off),
        planned_end=_A + timedelta(days=off + dur),
        done=done, progress=progress,
    )


def _network():
    # T2 is overdue (ends day 20 < today 21) and critical; T3 depends on the overdue T2.
    return [
        _t(1, [], 0, 5, done=True),
        _t(2, [1], 5, 15, done=False),
        _t(3, [2], 20, 10, done=False),
        _t(4, [1], 5, 2, done=True),
        _t(5, [3, 4], 30, 5),
        _t(6, [5], 35, 1),
    ]


class TestRisk(unittest.TestCase):
    def test_overdue_critical_task_flagged_high(self):
        _, risks = assess(_network(), today=_TODAY)
        items = {(r.task_id, r.kind): r for r in risks}
        self.assertIn((2, "overdue"), items)
        self.assertEqual(items[(2, "overdue")].severity, "high")
        self.assertTrue(items[(2, "overdue")].on_critical_path)

    def test_predecessor_slip_flagged(self):
        _, risks = assess(_network(), today=_TODAY)
        kinds = {(r.task_id, r.kind) for r in risks}
        self.assertIn((3, "predecessor_slipped"), kinds)

    def test_done_task_not_flagged(self):
        _, risks = assess(_network(), today=_TODAY)
        self.assertFalse(any(r.task_id == 1 for r in risks))

    def test_near_deadline_no_progress(self):
        tasks = [_t(10, [], 19, 2, done=False, progress=0.0)]  # ends today, 0% progress
        _, risks = assess(tasks, today=_TODAY, near_deadline_days=3, min_progress=10)
        kinds = {(r.task_id, r.kind) for r in risks}
        self.assertIn((10, "near_deadline_no_progress"), kinds)

    def test_far_off_task_not_flagged(self):
        tasks = [_t(11, [], 100, 5, done=False, progress=0.0)]  # ends far in the future
        _, risks = assess(tasks, today=_TODAY)
        self.assertEqual(risks, [])


if __name__ == "__main__":
    unittest.main()
