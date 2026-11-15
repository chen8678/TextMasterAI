from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.english_learning.skill_handlers.roadmap_draft import execute as draft_execute
from apps.english_learning.skill_handlers.roadmap_finalize import execute as finalize_execute
from apps.knowledge.models import Document, KnowledgeBase

User = get_user_model()


class RoadmapDraftSkillTests(SimpleTestCase):
    @patch(
        "apps.english_learning.skill_handlers.roadmap_draft.stream_chat_completion",
        return_value="",
    )
    def test_output_has_markdown_and_outline(self, _mock_llm):
        r = draft_execute(
            scores={"overall_percent": 72.0},
            gap_summary="Grammar weak.",
            focus_dimensions=["grammar"],
            learner_constraints={"level_tags": ["B1"]},
            model="deepseek-chat",
        )
        self.assertIn("roadmap_markdown", r)
        self.assertTrue(str(r["roadmap_markdown"]).strip())
        self.assertIsInstance(r.get("outline_json"), dict)
        self.assertTrue(r["outline_json"])
        # 离线 fallback 应为中文四级报告/路线
        md = str(r["roadmap_markdown"])
        self.assertTrue("四级" in md or "学习报告" in md or "个性化" in md)

    @patch(
        "apps.english_learning.skill_handlers.roadmap_draft.stream_chat_completion",
        return_value="",
    )
    def test_learner_note_appears_in_fallback(self, _mock_llm):
        r = draft_execute(
            scores={"overall_percent": 60.0},
            gap_summary="词汇偏弱",
            focus_dimensions=["vocabulary"],
            learner_constraints={
                "level_tags": ["stage:cet4"],
                "exam_goal": "大学英语四级",
                "learner_note": "想加强听力长对话",
            },
            model="deepseek-chat",
        )
        md = str(r["roadmap_markdown"])
        self.assertIn("想加强听力长对话", md)


class RoadmapFinalizeSkillTests(TestCase):
    def test_creates_document_in_kb(self):
        user = User.objects.create_user(
            username="el_rf_1", email="el_rf_1@t.local", password="pw-test-el-rf"
        )
        kb = KnowledgeBase.objects.create(
            title="EL test kb",
            owner=user,
            category="education",
            description="",
        )
        r = finalize_execute(
            roadmap_markdown="# My Roadmap\n\n- item",
            kb_id=str(kb.id),
            title="T",
            user_id=user.id,
        )
        self.assertIn("document_id", r)
        doc = Document.objects.get(id=r["document_id"])
        self.assertEqual(doc.knowledge_base_id, kb.id)
        self.assertIn("My Roadmap", doc.content)

    def test_wrong_owner_raises(self):
        owner = User.objects.create_user(
            username="el_rf_o", email="el_rf_o@t.local", password="pw-test-el-rf"
        )
        other = User.objects.create_user(
            username="el_rf_x", email="el_rf_x@t.local", password="pw-test-el-rf"
        )
        kb = KnowledgeBase.objects.create(
            title="EL kb other",
            owner=owner,
            category="education",
            description="",
        )
        with self.assertRaises(PermissionError):
            finalize_execute(
                roadmap_markdown="# x",
                kb_id=str(kb.id),
                title="T",
                user_id=other.id,
            )
