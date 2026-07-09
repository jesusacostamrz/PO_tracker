import unittest
from pathlib import Path

# Import the pure helpers from the launcher without triggering Odoo connection.
import importlib.util

_SPEC = importlib.util.spec_from_file_location(
    "gantt_launcher",
    Path(__file__).resolve().parents[1] / "scripts" / "gantt.py",
)


class TestLauncherHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.util.module_from_spec(_SPEC)
        _SPEC.loader.exec_module(cls.mod)

    def test_norm_view_accepts_aliases(self):
        for tok in ("c", "C", "customer", "cliente", " Cliente "):
            self.assertEqual(self.mod.norm_view(tok), "customer")
        for tok in ("i", "internal", "interno", "INTERNO"):
            self.assertEqual(self.mod.norm_view(tok), "internal")

    def test_norm_view_rejects_garbage(self):
        self.assertIsNone(self.mod.norm_view("x"))
        self.assertIsNone(self.mod.norm_view(""))
        self.assertIsNone(self.mod.norm_view(None))

    def test_out_path_naming(self):
        p = self.mod.out_path("internal", 8)
        self.assertEqual(p.name, "internal_8.html")
        self.assertEqual(p.parent.name, "out")


if __name__ == "__main__":
    unittest.main()
