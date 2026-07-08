import tempfile
import unittest
from datetime import date
from pathlib import Path

from uc.core.baseline import Baseline, load, save, snapshot
from uc.core.models import Task


def _task(tid, s, e):
    return Task(id=tid, name=f"T{tid}", planned_start=s, planned_end=e)


class TestBaseline(unittest.TestCase):
    def test_snapshot_freezes_current_dates(self):
        tasks = [_task(1, date(2026, 7, 1), date(2026, 7, 10)),
                 _task(2, date(2026, 7, 11), date(2026, 7, 20))]
        b = snapshot(9, "Proj", tasks, approved_on=date(2026, 7, 8))
        self.assertEqual(b.end_of(1), date(2026, 7, 10))
        self.assertEqual(b.approved_on, date(2026, 7, 8))
        self.assertTrue(b.has(2))
        self.assertFalse(b.has(99))

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            b = snapshot(9, "Prój ñ", [_task(1, date(2026, 7, 1), date(2026, 7, 10))],
                         approved_on=date(2026, 7, 8))
            path = save(b, base_dir=base)
            self.assertTrue(path.exists())
            got = load(9, base_dir=base)
            self.assertEqual(got.project_name, "Prój ñ")
            self.assertEqual(got.approved_on, date(2026, 7, 8))
            self.assertEqual(got.tasks[1], (date(2026, 7, 1), date(2026, 7, 10)))

    def test_load_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(load(123, base_dir=Path(d)))

    def test_none_dates_survive_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            b = snapshot(9, "P", [_task(1, None, None)], approved_on=date(2026, 7, 8))
            save(b, base_dir=base)
            got = load(9, base_dir=base)
            self.assertEqual(got.tasks[1], (None, None))


if __name__ == "__main__":
    unittest.main()
