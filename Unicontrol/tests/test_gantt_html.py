import unittest
from datetime import date

from uc.core.customer_view import CustomerPlan, MilestoneMark, PhaseBar
from uc.render.gantt_html import (
    Chart,
    Row,
    esc,
    fmt_date,
    plan_to_chart,
    render_chart,
    render_customer_page,
)


class TestRenderChart(unittest.TestCase):
    def test_phase_bar_has_position_and_fill(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="Diseño", kind="phase", left=10.0, width=25.0, color="#3f7cac", progress=60)
        ])
        html = render_chart(chart)
        self.assertIn("left:10.000%", html)
        self.assertIn("width:25.000%", html)
        self.assertIn('class="fill"', html)
        self.assertIn("60.0%", html)

    def test_zero_progress_emits_no_fill(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="x", kind="phase", left=0, width=5, color="#000", progress=0)])
        self.assertNotIn('class="fill"', render_chart(chart))

    def test_reached_milestone_gets_class(self):
        chart = Chart("P", "s", "m", rows=[
            Row(label="Entrega", kind="milestone", left=80, reached=True)])
        self.assertIn("reached", render_chart(chart))

    def test_today_line_only_when_set(self):
        self.assertNotIn("todayline", render_chart(Chart("P", "s", "m", rows=[])))
        self.assertIn("todayline", render_chart(Chart("P", "s", "m", rows=[], today_left=50.0)))

    def test_helpers(self):
        from datetime import date
        self.assertEqual(fmt_date(date(2026, 7, 24)), "24 jul")
        self.assertEqual(esc("<a>"), "&lt;a&gt;")


def _plan():
    return CustomerPlan(
        project_name="Trabajo Cliente X",
        phases=[
            PhaseBar("Diseño", "#3f7cac", date(2026, 7, 13), date(2026, 7, 24), 100.0, True),
            PhaseBar("Maquinado", "#7a6cae", date(2026, 8, 10), date(2026, 8, 18), 50.0, False),
        ],
        milestones=[MilestoneMark("Piezas entregadas", date(2026, 9, 18), False)],
        date_min=date(2026, 7, 13), date_max=date(2026, 9, 18),
        as_of=date(2026, 8, 1), overall_progress=62.0,
    )


class TestPlanToChart(unittest.TestCase):
    def test_first_phase_starts_at_zero(self):
        self.assertAlmostEqual(plan_to_chart(_plan()).rows[0].left, 0.0, places=3)

    def test_milestone_at_far_end(self):
        ms = [r for r in plan_to_chart(_plan()).rows if r.kind == "milestone"]
        self.assertEqual(len(ms), 1)
        self.assertAlmostEqual(ms[0].left, 100.0, places=3)

    def test_today_line_within_range(self):
        self.assertIsNotNone(plan_to_chart(_plan()).today_left)

    def test_rows_interleaved_in_date_order(self):
        # A milestone dated between the two phase starts must sit between them,
        # not be pushed below every phase.
        plan = CustomerPlan(
            project_name="X",
            phases=[
                PhaseBar("A", "#111", date(2026, 7, 1), date(2026, 7, 20), 0.0, False),
                PhaseBar("B", "#222", date(2026, 8, 1), date(2026, 8, 20), 0.0, False),
            ],
            milestones=[MilestoneMark("Gate", date(2026, 7, 25), False)],
            date_min=date(2026, 7, 1), date_max=date(2026, 8, 20),
            as_of=date(2026, 7, 1), overall_progress=0.0,
        )
        kinds = [(r.kind, r.label) for r in plan_to_chart(plan).rows]
        self.assertEqual([k for k, _ in kinds], ["phase", "milestone", "phase"])


class TestRenderCustomerPage(unittest.TestCase):
    def test_self_contained_and_leak_safe(self):
        html = render_customer_page(_plan())
        self.assertIn("<style>", html)
        self.assertIn("Trabajo Cliente X", html)
        self.assertIn("62", html)
        self.assertNotIn("ruta crítica", html)
        self.assertNotIn("días hábiles", html)

    def test_title_is_project_name(self):
        # the browser-tab title should be the project, not the template artifact's title
        html = render_customer_page(_plan())
        self.assertIn("<title>Trabajo Cliente X</title>", html)


class TestInternalRender(unittest.TestCase):
    def _iplan(self):
        from uc.core.internal_view import InternalPlan, InternalRow
        return InternalPlan(
            project_name="Proj",
            rows=[
                InternalRow("Diseño", "phase", 0, date(2026, 7, 1), date(2026, 7, 20),
                            40.0, "#3f7cac", False, variance_days=5,
                            baseline_end=date(2026, 7, 15)),
                InternalRow("Modelado", "step", 1, date(2026, 7, 1), date(2026, 7, 10),
                            100.0, "#3f7cac", True, variance_days=-2,
                            baseline_end=date(2026, 7, 12)),
                InternalRow("Nuevo", "step", 1, date(2026, 7, 3), date(2026, 7, 6),
                            0.0, "#3f7cac", False, variance_days=None),
                InternalRow("Aprobado", "milestone", 0, date(2026, 7, 25), date(2026, 7, 25),
                            0.0, "", False, reached=False, variance_days=0,
                            baseline_end=date(2026, 7, 25)),
            ],
            date_min=date(2026, 7, 1), date_max=date(2026, 7, 25),
            as_of=date(2026, 7, 15), overall_progress=40.0,
            overall_variance_days=5, approved_on=date(2026, 7, 8),
        )

    def test_variance_tags_and_indent(self):
        from uc.render.gantt_html import render_internal_page
        html = render_internal_page(self._iplan())
        self.assertIn('class="vtag late"', html)      # +5d phase
        self.assertIn("+5d", html)
        self.assertIn('class="vtag early"', html)      # -2d step
        self.assertIn('class="vtag new"', html)        # nuevo (no baseline)
        self.assertIn("nuevo", html)
        self.assertIn("padding-left:32px", html)       # indent=1 -> 12+20
        self.assertIn('class="row step"', html)
        self.assertIn('class="btick"', html)           # baseline tick
        self.assertIn("Uso interno", html)
        self.assertIn("Atraso de <b>5 d</b>", html)

    def test_internal_uses_full_detail(self):
        from uc.render.gantt_html import render_internal_page
        html = render_internal_page(self._iplan())
        self.assertIn("Modelado", html)  # child step IS shown (unlike customer view)


if __name__ == "__main__":
    unittest.main()
