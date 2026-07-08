import unittest
from datetime import date, timedelta

from uc.core.models import Task
from uc.core.critical_path import compute_cpm

_A = date(2026, 1, 1)


def _t(i, deps, off, dur):
    return Task(
        id=i, name=f"T{i}", depends_on=deps,
        planned_start=_A + timedelta(days=off),
        planned_end=_A + timedelta(days=off + dur),
    )


def _network():
    # Diamond: 1->2->3->5->6 is the long (critical) chain; 4 is a short parallel branch.
    # durations: 1=5, 2=15, 3=10, 4=2, 5=5, 6=1
    return [
        _t(1, [], 0, 5),
        _t(2, [1], 5, 15),
        _t(3, [2], 20, 10),
        _t(4, [1], 5, 2),
        _t(5, [3, 4], 30, 5),
        _t(6, [5], 35, 1),
    ]


class TestCPM(unittest.TestCase):
    def test_identifies_critical_path(self):
        self.assertEqual(compute_cpm(_network()).critical, {1, 2, 3, 5, 6})

    def test_offpath_task_has_slack(self):
        self.assertEqual(compute_cpm(_network()).slack[4], 23)

    def test_critical_tasks_have_zero_slack(self):
        r = compute_cpm(_network())
        self.assertTrue(all(r.slack[i] == 0 for i in {1, 2, 3, 5, 6}))

    def test_project_length(self):
        self.assertEqual(compute_cpm(_network()).project_length, 36)

    def test_cycle_raises(self):
        a = Task(id=1, name="a", depends_on=[2])
        b = Task(id=2, name="b", depends_on=[1])
        with self.assertRaises(ValueError):
            compute_cpm([a, b])

    def test_empty_is_safe(self):
        self.assertEqual(compute_cpm([]).critical, set())


if __name__ == "__main__":
    unittest.main()
