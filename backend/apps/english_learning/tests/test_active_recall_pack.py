from django.test import SimpleTestCase

from apps.english_learning.skill_handlers.active_recall_pack import execute as recall_execute


class ActiveRecallPackSkillTests(SimpleTestCase):
    def test_pack_items_for_weak_dimensions(self):
        r = recall_execute(
            weak_dimensions=["vocabulary", "grammar"],
            learner_constraints={"level_tags": ["B1"]},
            active_unit_id="1-2:x",
            gap_summary="gap text",
        )
        self.assertIn("pack_items", r)
        self.assertGreaterEqual(len(r["pack_items"]), 2)
        self.assertEqual(r["schema_version"], 1)

    def test_default_pack_when_no_weak(self):
        r = recall_execute(weak_dimensions=[], gap_summary="only gap")
        self.assertTrue(r["pack_items"])
