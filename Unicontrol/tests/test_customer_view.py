# tests/test_customer_view.py
import unittest
from datetime import date

from uc.core.models import Task
from uc.core import customer_view as cv


def _mk(id, name, s=None, e=None, done=False, progress=0.0, actual_end=None, parent=None):
    return Task(id=id, name=name,
                planned_start=date.fromisoformat(s) if s else None,
                planned_end=date.fromisoformat(e) if e else None,
                done=done, progress=progress,
                actual_end=date.fromisoformat(actual_end) if actual_end else None,
                parent_id=parent)


class TestHelpers(unittest.TestCase):
    def test_is_milestone_by_star(self):
        self.assertTrue(cv.is_milestone(_mk(1, "★ M2  Concepto aprobado")))
        self.assertFalse(cv.is_milestone(_mk(2, "2. Diseño")))

    def test_clean_name_strips_star_and_wbs(self):
        self.assertEqual(cv.clean_name("★ M5  Piezas entregadas"), "Piezas entregadas")

    def test_clean_phase_name_strips_number(self):
        self.assertEqual(cv.clean_phase_name("2. Diseño"), "Diseño")

    def test_weighted_progress_duration_weighted(self):
        # a: 2 calendar days @ 0%, b: 12 calendar days @ 100% -> (0*2 + 100*12)/14 = 85.7
        ts = [_mk(1, "a", "2026-07-13", "2026-07-15", progress=0),
              _mk(2, "b", "2026-07-15", "2026-07-27", progress=100)]
        self.assertEqual(cv.weighted_progress(ts), 85.7)

    def test_is_hierarchical_true_when_a_task_has_parent(self):
        ts = [_mk(1, "2. Diseño"), _mk(2, "2.1  Layout", parent=1)]
        self.assertTrue(cv.is_hierarchical(ts))

    def test_is_hierarchical_false_for_flat_project(self):
        ts = [_mk(1, "1.1  x"), _mk(2, "1.2  y"), _mk(3, "★ M1  z")]
        self.assertFalse(cv.is_hierarchical(ts))


class TestBuild(unittest.TestCase):
    def _tasks(self):
        return [
            _mk(10, "2. Diseño", "2026-07-13", "2026-07-24"),                       # phase parent
            _mk(11, "2.1  Layout", "2026-07-13", "2026-07-18", done=True, parent=10),
            _mk(12, "2.2  Concepto", "2026-07-18", "2026-07-24", progress=50, parent=10),
            _mk(20, "5. Maquinado", "2026-08-10", "2026-08-18"),                    # phase parent
            _mk(21, "5.1  CAM", "2026-08-10", "2026-08-18", progress=0, parent=20),
            _mk(30, "★ M5  Piezas entregadas", e="2026-09-18"),                     # milestone
        ]

    def test_phases_are_top_level_nonmilestone(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        self.assertEqual([p.name for p in plan.phases], ["Diseño", "Maquinado"])

    def test_children_never_become_rows(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        names = [p.name for p in plan.phases] + [m.name for m in plan.milestones]
        self.assertNotIn("Layout", " ".join(names))
        self.assertNotIn("CAM", " ".join(names))

    def test_phase_progress_from_children(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        diseno = next(p for p in plan.phases if p.name == "Diseño")
        # child 11 done(100, 5d) + child 12 (50, 6d) → (100*5 + 50*6)/11 = 72.7
        self.assertAlmostEqual(diseno.progress, 72.7, places=1)

    def test_colors_follow_timeline_order(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        self.assertEqual(plan.phases[0].color, cv.PHASE_PALETTE[0])
        self.assertEqual(plan.phases[1].color, cv.PHASE_PALETTE[1])

    def test_milestone_reached_vs_upcoming(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        m = plan.milestones[0]
        self.assertEqual(m.name, "Piezas entregadas")
        self.assertFalse(m.reached)  # 2026-09-18 > as_of

    def test_overall_progress_and_range(self):
        plan = cv.build(self._tasks(), "Trabajo X", as_of=date(2026, 8, 1))
        self.assertEqual(plan.date_min, date(2026, 7, 13))
        self.assertEqual(plan.date_max, date(2026, 9, 18))
        self.assertTrue(0 < plan.overall_progress < 100)


if __name__ == "__main__":
    unittest.main()
