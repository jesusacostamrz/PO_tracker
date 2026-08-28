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


class TestBaselineVersioning(unittest.TestCase):
    def test_resave_archives_and_bumps_version(self):
        import tempfile
        from pathlib import Path
        from uc.core import baseline as bl
        from uc.core.models import Task
        from datetime import date
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            t = [Task(id=1, name="a", planned_start=date(2026, 7, 1), planned_end=date(2026, 7, 5))]
            b1 = bl.snapshot(9, "P", t, approved_on=date(2026, 7, 1))
            bl.save(b1, base)
            t[0].planned_end = date(2026, 7, 9)
            b2 = bl.snapshot(9, "P", t, approved_on=date(2026, 8, 1))
            b2.reason = "cliente pidió más piezas"
            bl.save(b2, base)
            cur = bl.load(9, base)
            self.assertEqual(cur.version, 2)
            self.assertEqual(cur.reason, "cliente pidió más piezas")
            self.assertEqual(cur.previous_approved_on, date(2026, 7, 1))
            self.assertEqual(cur.end_of(1), date(2026, 7, 9))
            arch = base / "history" / "project-9-v1.json"
            self.assertTrue(arch.exists())
            self.assertIn('"2026-07-05"', arch.read_text(encoding="utf-8"))
