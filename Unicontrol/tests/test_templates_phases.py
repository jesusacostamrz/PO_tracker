import unittest

from uc.templates import INTEGRATION, MACHINING, PHASE_NAMES, TEMPLATES, phase_groups


class TestPhaseNames(unittest.TestCase):
    def test_every_template_has_names_for_all_majors(self):
        for tname, items in TEMPLATES.items():
            majors = {w.split(".")[0] for (w, *_r) in items if not _r[-1]}  # non-milestone
            self.assertTrue(majors)
            self.assertLessEqual(majors, set(PHASE_NAMES[tname]),
                                 msg=f"{tname} missing phase name(s)")


class TestPhaseGroups(unittest.TestCase):
    def test_groups_are_ordered_and_named(self):
        groups = phase_groups(MACHINING, PHASE_NAMES["[PLANTILLA] Proyecto de Maquinado"])
        majors = [g["major"] for g in groups]
        self.assertEqual(majors, ["1", "2", "3", "4", "5", "6", "7"])
        g2 = next(g for g in groups if g["major"] == "2")
        self.assertEqual(g2["name"], "2. Diseño")
        self.assertIn("2.1", g2["leaves"])

    def test_milestones_excluded_from_groups(self):
        groups = phase_groups(MACHINING, PHASE_NAMES["[PLANTILLA] Proyecto de Maquinado"])
        all_leaves = [w for g in groups for w in g["leaves"]]
        self.assertNotIn("M1", all_leaves)
        self.assertFalse(any(w.startswith("M") for w in all_leaves))

    def test_dominant_etapa_reported(self):
        groups = phase_groups(INTEGRATION, PHASE_NAMES["[PLANTILLA] Integración de Sistemas"])
        g2 = next(g for g in groups if g["major"] == "2")
        self.assertEqual(g2["etapa"], "Diseño")  # 2.x are all Diseño


if __name__ == "__main__":
    unittest.main()
