import tempfile
import unittest
from datetime import date
from pathlib import Path

from uc.core.alerts import (
    AlertLog, alert_key, load_alert_log, resolve_recipient_user_ids, save_alert_log,
)


class TestRecipients(unittest.TestCase):
    def test_medium_is_assignees_plus_manager(self):
        r = resolve_recipient_user_ids([5, 6], 2, [99], severity="medium")
        self.assertEqual(r, [2, 5, 6])  # sorted, no escalation on medium

    def test_high_adds_escalation(self):
        r = resolve_recipient_user_ids([5], 2, [99], severity="high")
        self.assertEqual(r, [2, 5, 99])

    def test_dedup_when_manager_is_assignee(self):
        r = resolve_recipient_user_ids([2], 2, [], severity="medium")
        self.assertEqual(r, [2])

    def test_no_assignees_falls_back_to_manager(self):
        r = resolve_recipient_user_ids([], 2, [99], severity="high")
        self.assertEqual(r, [2, 99])

    def test_no_manager_ok(self):
        r = resolve_recipient_user_ids([5], None, [], severity="medium")
        self.assertEqual(r, [5])


class TestAlertLog(unittest.TestCase):
    DAY = date(2026, 7, 7)

    def test_not_sent_initially(self):
        log = AlertLog()
        self.assertFalse(log.already_sent(60, "overdue", self.DAY))

    def test_marked_then_sent(self):
        log = AlertLog()
        log.mark(60, "overdue", self.DAY)
        self.assertTrue(log.already_sent(60, "overdue", self.DAY))

    def test_different_day_not_sent(self):
        log = AlertLog()
        log.mark(60, "overdue", self.DAY)
        self.assertFalse(log.already_sent(60, "overdue", date(2026, 7, 8)))

    def test_different_kind_not_sent(self):
        log = AlertLog()
        log.mark(60, "overdue", self.DAY)
        self.assertFalse(log.already_sent(60, "predecessor_slipped", self.DAY))

    def test_key_is_stable_and_distinct(self):
        self.assertEqual(alert_key(60, "overdue", self.DAY), alert_key(60, "overdue", self.DAY))
        self.assertNotEqual(alert_key(60, "overdue", self.DAY), alert_key(61, "overdue", self.DAY))


class TestPersistence(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alerts.json"
            log = AlertLog()
            log.mark(60, "overdue", date(2026, 7, 7))
            save_alert_log(p, log)
            reloaded = load_alert_log(p)
            self.assertTrue(reloaded.already_sent(60, "overdue", date(2026, 7, 7)))

    def test_load_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            log = load_alert_log(Path(d) / "does_not_exist.json")
            self.assertFalse(log.already_sent(1, "overdue", date(2026, 7, 7)))


if __name__ == "__main__":
    unittest.main()
