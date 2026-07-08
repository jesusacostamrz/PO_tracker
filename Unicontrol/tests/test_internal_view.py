import unittest
from datetime import date

from uc.core.baseline import Baseline
from uc.core.internal_view import build, current_end
from uc.core.models import Task


def _fixture():
    phase = Task(id=10, name="Diseño detallado", parent_id=None,
                 planned_start=date(2026, 7, 1), planned_end=date(2026, 7, 22))
    c11 = Task(id=11, name="3.1  Modelado", parent_id=10,
               planned_start=date(2026, 7, 1), planned_end=date(2026, 7, 10),
               done=True, actual_end=date(2026, 7, 12))          # late +2
    c12 = Task(id=12, name="3.2  Planos", parent_id=10,
               planned_start=date(2026, 7, 11), planned_end=date(2026, 7, 22),
               progress=50.0)                                     # baseline end 7/20 -> +2
    c13 = Task(id=13, name="3.3  Nuevo", parent_id=10,
               planned_start=date(2026, 7, 5), planned_end=date(2026, 7, 8))  # no baseline
    ms = Task(id=20, name="★ M2  Diseño aprobado", parent_id=None,
              planned_end=date(2026, 7, 25))
    tasks = [phase, c11, c12, c13, ms]
    baseline = Baseline(9, "Proj", date(2026, 7, 8), {
        10: (date(2026, 7, 1), date(2026, 7, 20)),
        11: (date(2026, 7, 1), date(2026, 7, 10)),
        12: (date(2026, 7, 11), date(2026, 7, 20)),
        20: (None, date(2026, 7, 25)),
    })
    return tasks, baseline


class TestInternalView(unittest.TestCase):
    def test_current_end_uses_actual_for_done(self):
        t = Task(id=1, name="x", done=True, actual_end=date(2026, 7, 12),
                 planned_end=date(2026, 7, 10))
        self.assertEqual(current_end(t), date(2026, 7, 12))

    def test_current_end_uses_planned_when_open(self):
        t = Task(id=1, name="x", done=False, planned_end=date(2026, 7, 10))
        self.assertEqual(current_end(t), date(2026, 7, 10))

    def test_grouping_and_indent_order(self):
        tasks, baseline = _fixture()
        plan = build(tasks, "Proj", baseline, as_of=date(2026, 7, 15))
        seq = [(r.kind, r.indent, r.name) for r in plan.rows]
        self.assertEqual(seq, [
            ("phase", 0, "Diseño detallado"),
            ("step", 1, "Modelado"),
            ("step", 1, "Nuevo"),      # 7/5 sorts before 7/11
            ("step", 1, "Planos"),
            ("milestone", 0, "Diseño aprobado"),
        ])

    def test_variance_late_step(self):
        tasks, baseline = _fixture()
        plan = build(tasks, "Proj", baseline, as_of=date(2026, 7, 15))
        modelado = next(r for r in plan.rows if r.name == "Modelado")
        self.assertEqual(modelado.variance_days, 2)

    def test_no_baseline_entry_is_none(self):
        tasks, baseline = _fixture()
        plan = build(tasks, "Proj", baseline, as_of=date(2026, 7, 15))
        nuevo = next(r for r in plan.rows if r.name == "Nuevo")
        self.assertIsNone(nuevo.variance_days)

    def test_overall_variance(self):
        tasks, baseline = _fixture()
        plan = build(tasks, "Proj", baseline, as_of=date(2026, 7, 15))
        self.assertEqual(plan.overall_variance_days, 2)
        self.assertEqual(plan.approved_on, date(2026, 7, 8))

    def test_no_baseline_yields_none_variance(self):
        tasks, _ = _fixture()
        plan = build(tasks, "Proj", None, as_of=date(2026, 7, 15))
        self.assertIsNone(plan.overall_variance_days)
        self.assertTrue(all(r.variance_days is None for r in plan.rows))


if __name__ == "__main__":
    unittest.main()
