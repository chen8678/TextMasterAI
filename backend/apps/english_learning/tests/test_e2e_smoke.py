"""
E1：端到端冒烟 — 建档 → 测评 → 路线草案 → 定稿入库 → 主编排问答能带上路线摘录。

真实 LLM 用 stub 替代，仅断言编排链路与 `additional_context_text` 注入是否贯通。
"""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.chat.services import QAService
from apps.english_learning.models import AssessmentSession, RoadmapRevision
from apps.skills.models import SkillExecutionLog

User = get_user_model()

MARKER = "EL_E2E_ROUTE_VERIFY_TOKEN"


def _stub_generate_answer(
    self,
    question,
    context_docs,
    use_general_knowledge=False,
    agent=None,
    additional_context_text="",
):
    blob = (additional_context_text or "") + "".join(
        (getattr(d, "content", "") or "") for d in (context_docs or [])
    )
    if MARKER in blob:
        return f"OK:{MARKER}"
    return "STUB_NO_MARKER"


class EnglishLearningE2ESmokeTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        Agent.objects.update_or_create(
            id="english_orchestrator",
            defaults={
                "name": "英语学习主编排",
                "description": "e2e",
                "skills": ["rag_answer", "cite_snippets"],
                "default_model": "deepseek-chat",
                "is_active": True,
            },
        )

    def test_bootstrap_through_finalize_sets_active_roadmap_document(self):
        user = User.objects.create_user(
            username=f"e2e_{uuid.uuid4().hex[:8]}",
            email=f"e2e_{uuid.uuid4().hex[:8]}@t.local",
            password="pw-e2e-test",
        )
        self.client.force_authenticate(user=user)

        boot = self.client.post(
            reverse("english-profile-bootstrap"),
            {"level_tags": ["CEFR:B1"], "exam_goal": "", "weekly_minutes": 120},
            format="json",
        )
        self.assertEqual(boot.status_code, status.HTTP_200_OK)
        profile_data = boot.data["profile"]
        kb_id = profile_data["default_kb_id"]
        profile_id = profile_data["id"]

        start = self.client.post(
            reverse("english-assessment-start"),
            {"question_count": 2, "level_target": "B1"},
            format="json",
        )
        self.assertEqual(start.status_code, status.HTTP_201_CREATED, start.data)
        aid = start.data["assessment_id"]
        session = AssessmentSession.objects.get(id=aid)
        responses = [{"item_id": it["id"], "answer": it["answer_key"]} for it in session.items_json]

        sub = self.client.post(
            reverse("english-assessment-submit", kwargs={"assessment_id": aid}),
            {"responses": responses},
            format="json",
        )
        self.assertEqual(sub.status_code, status.HTTP_200_OK)

        draft = self.client.post(
            reverse("english-roadmap-draft"),
            {"focus_dimensions": ["grammar"], "assessment_id": aid},
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_200_OK)

        md = (
            f"# E2E Roadmap Title\n\n## Week 1\nSecret verification token: {MARKER}\n\n"
            + str(draft.data.get("roadmap_markdown") or "")[:200]
        )
        fin = self.client.post(
            reverse("english-roadmap-finalize"),
            {
                "roadmap_markdown": md,
                "knowledge_base_id": str(kb_id),
                "title": "E2E Roadmap",
            },
            format="json",
        )
        self.assertEqual(fin.status_code, status.HTTP_200_OK, fin.data)

        user.refresh_from_db()
        profile = user.english_learning_profile
        self.assertIsNotNone(profile.active_roadmap_document_id)

        rev = RoadmapRevision.objects.filter(profile=profile).order_by("-version").first()
        self.assertIsNotNone(rev)
        self.assertTrue(rev.source_skill_run_id)
        log = SkillExecutionLog.objects.filter(id=rev.source_skill_run_id).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.skill_id, "english_roadmap_finalize")

        payload = {
            "question": "路线里的验证码是什么？",
            "knowledge_base_id": str(kb_id),
            "agent_id": "english_orchestrator",
            "use_agent": True,
            "english_phase": "tutor",
            "english_profile_id": str(profile_id),
            "model": "deepseek",
        }
        with patch.object(QAService, "generate_answer", _stub_generate_answer):
            ans = self.client.post(reverse("ask-question"), payload, format="json")
        self.assertEqual(ans.status_code, status.HTTP_200_OK, ans.data)
        self.assertIn(MARKER, ans.data.get("answer", ""))
