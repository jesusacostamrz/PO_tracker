import unittest

from uc.render.gantt_html import Chart, Row, esc, fmt_date, render_chart


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


if __name__ == "__main__":
    unittest.main()
