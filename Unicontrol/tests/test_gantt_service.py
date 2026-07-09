import importlib.util
import unittest
from pathlib import Path

from uc.service.gantt_service import RenderError, norm_view


class TestService(unittest.TestCase):
    def test_norm_view_aliases(self):
        self.assertEqual(norm_view("cliente"), "customer")
        self.assertEqual(norm_view("I"), "internal")
        self.assertIsNone(norm_view("nope"))

    def test_render_error_carries_code(self):
        e = RenderError("boom", code=6)
        self.assertEqual(e.code, 6)
        self.assertEqual(e.message, "boom")
        self.assertIn("boom", str(e))


_WEB = importlib.util.spec_from_file_location(
    "gantt_web", Path(__file__).resolve().parents[1] / "scripts" / "gantt_web.py")


class TestWebPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.web = importlib.util.module_from_spec(_WEB)
        _WEB.loader.exec_module(cls.web)

    def test_index_lists_projects_and_form(self):
        html = self.web.render_index([{"id": 7, "name": "Maquinado"},
                                      {"id": 8, "name": "Integración"}])
        self.assertIn('value="7"', html)
        self.assertIn("Maquinado", html)
        self.assertIn('action="/render"', html)
        self.assertIn('value="customer"', html)
        self.assertIn('value="internal"', html)
        self.assertIn("USO INTERNO", html)

    def test_error_page_includes_extra(self):
        html = self.web.error_page("no baseline", '<a class="btn">Guardar</a>')
        self.assertIn("no baseline", html)
        self.assertIn("Guardar", html)


if __name__ == "__main__":
    unittest.main()
