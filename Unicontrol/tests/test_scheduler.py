import unittest
from datetime import date

from uc.core.scheduler import add_working_days, forward_schedule


class TestWorkingDays(unittest.TestCase):
    def test_zero_on_weekday_is_same_day(self):
        # 2026-07-13 is a Monday
        self.assertEqual(add_working_days(date(2026, 7, 13), 0), date(2026, 7, 13))

    def test_one_working_day_from_friday_is_monday(self):
        # 2026-07-10 is a Friday -> +1 working day -> Mon 2026-07-13
        self.assertEqual(add_working_days(date(2026, 7, 10), 1), date(2026, 7, 13))

    def test_zero_on_weekend_rolls_to_monday(self):
        # 2026-07-11 is a Saturday
        self.assertEqual(add_working_days(date(2026, 7, 11), 0), date(2026, 7, 13))

    def test_five_working_days_skips_weekend(self):
        # Mon + 5 working days -> next Mon
        self.assertEqual(add_working_days(date(2026, 7, 13), 5), date(2026, 7, 20))


class TestForwardSchedule(unittest.TestCase):
    def test_linear_chain(self):
        items = [("a", 2, []), ("b", 3, ["a"]), ("c", 1, ["b"])]
        sched = forward_schedule(items)
        self.assertEqual(sched["a"], (0, 2))
        self.assertEqual(sched["b"], (2, 5))
        self.assertEqual(sched["c"], (5, 6))

    def test_parallel_takes_max_predecessor(self):
        # d depends on both b(2..5) and a short branch e(0..1); starts at max EF = 5
        items = [("a", 2, []), ("b", 3, ["a"]), ("e", 1, ["a"]), ("d", 2, ["b", "e"])]
        sched = forward_schedule(items)
        self.assertEqual(sched["d"], (5, 7))

    def test_milestone_zero_duration(self):
        items = [("a", 2, []), ("m", 0, ["a"])]
        self.assertEqual(forward_schedule(items)["m"], (2, 2))

    def test_cycle_raises(self):
        with self.assertRaises(ValueError):
            forward_schedule([("a", 1, ["b"]), ("b", 1, ["a"])])


if __name__ == "__main__":
    unittest.main()
