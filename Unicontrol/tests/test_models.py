import unittest
from datetime import date

from uc.core.models import Task, parse_date


class TestParseDate(unittest.TestCase):
    def test_parses_iso_date(self):
        self.assertEqual(parse_date("2026-01-15"), date(2026, 1, 15))

    def test_parses_odoo_datetime(self):
        self.assertEqual(parse_date("2026-01-15 13:45:00"), date(2026, 1, 15))

    def test_false_is_none(self):
        self.assertIsNone(parse_date(False))


class TestDuration(unittest.TestCase):
    def test_duration_from_planned_span(self):
        t = Task(id=1, name="x", planned_start=date(2026, 1, 1), planned_end=date(2026, 1, 6))
        self.assertEqual(t.duration_days, 5)

    def test_duration_fallback_when_missing(self):
        self.assertEqual(Task(id=1, name="x").duration_days, 1)


class TestFromOdoo(unittest.TestCase):
    # Field map mirrors the confirmed Odoo 17.0+e schema (state is the done signal).
    FMAP = {
        "planned_start": "planned_date_begin", "planned_end": "date_deadline",
        "deadline": "date_deadline", "depends_on": "depend_on_ids",
        "stage": "stage_id", "assignees": "user_ids", "progress": "progress",
        "state": "state", "actual_end": "date_end",
    }
    DONE = ["1_done", "1_canceled"]

    def test_maps_fields_and_dates(self):
        row = {
            "id": 7, "name": "Maquinado", "planned_date_begin": "2026-01-01 08:00:00",
            "date_deadline": "2026-01-10 17:00:00", "depend_on_ids": [3, 4],
            "stage_id": [44, "Fabricación"], "state": "01_in_progress", "date_end": False,
            "user_ids": [5, 6], "project_id": [4, "piloto"],
        }
        t = Task.from_odoo(row, self.FMAP, self.DONE)
        self.assertEqual(t.id, 7)
        self.assertEqual(t.planned_start, date(2026, 1, 1))
        self.assertEqual(t.planned_end, date(2026, 1, 10))
        self.assertEqual(t.depends_on, [3, 4])
        self.assertEqual(t.stage, "Fabricación")
        self.assertEqual(t.assignee_ids, [5, 6])
        self.assertEqual(t.project_name, "piloto")
        self.assertFalse(t.done)

    def test_done_when_state_done(self):
        row = {"id": 8, "name": "x", "state": "1_done", "depend_on_ids": []}
        self.assertTrue(Task.from_odoo(row, self.FMAP, self.DONE).done)

    def test_canceled_counts_as_closed(self):
        row = {"id": 9, "name": "x", "state": "1_canceled", "depend_on_ids": []}
        self.assertTrue(Task.from_odoo(row, self.FMAP, self.DONE).done)

    def test_done_when_has_actual_end(self):
        row = {"id": 10, "name": "x", "date_end": "2026-01-05", "state": "01_in_progress",
               "depend_on_ids": []}
        self.assertTrue(Task.from_odoo(row, self.FMAP, self.DONE).done)

    def test_in_progress_is_not_done(self):
        row = {"id": 11, "name": "x", "state": "03_approved", "depend_on_ids": []}
        self.assertFalse(Task.from_odoo(row, self.FMAP, self.DONE).done)


if __name__ == "__main__":
    unittest.main()
