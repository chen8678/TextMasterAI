"""MVP-B：english_delegate 仅可与 english_orchestrator 同用。"""
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.knowledge.models import KnowledgeBase

User = get_user_model()


class EnglishDelegateAskTests(APITestCase):
    def setUp(self):
        u = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f"del_{u}", email=f"del_{u}@t.local", password="pw-del-test"
        )
        self.kb = KnowledgeBase.objects.create(
            title="kb",
            owner=self.user,
            category="education",
            description="",
        )
        for aid, skills in [
            ("qa", ["rag_answer"]),
            ("english_orchestrator", ["rag_answer", "cite_snippets"]),
            ("english_vocab", ["rag_answer"]),
        ]:
            Agent.objects.update_or_create(
                id=aid,
                defaults={
                    "name": aid,
                    "skills": skills,
                    "is_active": True,
                    "default_model": "deepseek-chat",
                    "description": "",
                },
            )

    def test_delegate_with_non_orchestrator_returns_400(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse("ask-question"),
            {
                "question": "test",
                "knowledge_base_id": str(self.kb.id),
                "agent_id": "qa",
                "english_delegate": "vocab",
                "use_agent": True,
                "model": "deepseek",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("english_delegate", str(r.data))

    def test_invalid_delegate_returns_400(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse("ask-question"),
            {
                "question": "test",
                "knowledge_base_id": str(self.kb.id),
                "agent_id": "english_orchestrator",
                "english_delegate": "not_a_slot",
                "use_agent": True,
                "model": "deepseek",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
