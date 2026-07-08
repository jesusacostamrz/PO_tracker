# tests/test_template_golden.py
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "gantt_template_golden.html"


class TestTemplateArtifactGolden(unittest.TestCase):
    def test_output_matches_golden(self):
        out = subprocess.run(
            [sys.executable, "scripts/gen_gantt_artifact.py"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(out.returncode, 0, msg=out.stderr)
        produced = out.stdout.replace("\r\n", "\n")
        golden = GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertEqual(produced, golden)


if __name__ == "__main__":
    unittest.main()
