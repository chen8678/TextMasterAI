"""normalize_suggested_skill_ids：注册表 ∩ DB 启用。"""
from django.test import TestCase

from apps.skills.evolution.validation import normalize_suggested_skill_ids
from apps.skills.models import Skill


class NormalizeSuggestedSkillIdsTests(TestCase):
    def setUp(self):
        Skill.objects.update_or_create(
            id="rag_answer",
            defaults={"name": "知识库", "is_active": True},
        )
        Skill.objects.update_or_create(
            id="cite_snippets",
            defaults={"name": "引用", "is_active": False},
        )

    def test_filters_unknown_and_inactive(self):
        out = normalize_suggested_skill_ids(
            ["rag_answer", "not_in_registry", "cite_snippets", "rag_answer"]
        )
        self.assertEqual(out, ["rag_answer"])

    def test_empty_input(self):
        self.assertEqual(normalize_suggested_skill_ids([]), [])
        self.assertEqual(normalize_suggested_skill_ids(None), [])
