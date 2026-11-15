"""G4：execute_safe / execute_skill 从 kwargs 剥离审计元数据。"""
from django.test import SimpleTestCase

from apps.skills.registry import pop_skill_log_metadata


class PopSkillLogMetadataTests(SimpleTestCase):
    def test_pops_keys_and_truncates_trigger(self):
        kw = {
            "a": 1,
            "_log_retrieval_refs": {"domain": "english_learning", "profile_id": "x"},
            "_log_trigger_source": "english_learning:" + "x" * 80,
        }
        refs, trigger = pop_skill_log_metadata(kw)
        self.assertEqual(kw, {"a": 1})
        self.assertEqual(refs["profile_id"], "x")
        self.assertEqual(len(trigger), 64)

    def test_empty_when_absent(self):
        kw = {"items": []}
        refs, trigger = pop_skill_log_metadata(kw)
        self.assertIsNone(refs)
        self.assertEqual(trigger, "")
