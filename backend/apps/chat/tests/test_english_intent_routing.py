"""M1：english_orchestrator 自动 intent 路由（keyword + 可选 LLM）。"""
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import Agent
from apps.chat.english_intent_routing import (
    classify_english_delegate_by_keywords,
    resolve_english_delegate_auto,
)
from apps.knowledge.models import KnowledgeBase

User = get_user_model()


class EnglishIntentRoutingUnitTests(APITestCase):
    def test_keyword_grammar(self):
        self.assertEqual(classify_english_delegate_by_keywords("请讲解一下语法和时态"), "grammar")

    def test_keyword_vocab(self):
        self.assertEqual(classify_english_delegate_by_keywords("帮我背这几个单词"), "vocab")

    def test_keyword_listen(self):
        self.assertEqual(classify_english_delegate_by_keywords("这段听力怎么练"), "listen")

    def test_no_match_returns_none_source(self):
        r = resolve_english_delegate_auto("你好", use_llm=False)
        self.assertIsNone(r["slot"])
        self.assertEqual(r["source"], "none")

    @patch("apps.chat.english_intent_routing.classify_english_delegate_by_llm")
    def test_llm_fallback_when_no_keyword(self, mock_llm):
        mock_llm.return_value = "vocab"
        r = resolve_english_delegate_auto("I want to improve my word power", use_llm=True)
        self.assertEqual(r["slot"], "vocab")
        self.assertEqual(r["source"], "llm")
        self.assertEqual(r["agent_id"], "english_vocab")


class EnglishIntentAskSmokeTests(APITestCase):
    def setUp(self):
        u = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f"intent_{u}", email=f"intent_{u}@t.local", password="pw-intent"
        )
        self.kb = KnowledgeBase.objects.create(
            title="kb",
            owner=self.user,
            category="education",
            description="",
        )
        for aid, skills in [
            ("english_orchestrator", ["rag_answer", "cite_snippets"]),
            ("english_vocab", ["rag_answer"]),
            ("english_grammar", ["rag_answer"]),
            ("english_listen", ["rag_answer"]),
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

    @patch("apps.chat.views.get_orchestrator_by_tier")
    def test_auto_routes_grammar_via_keyword(self, mock_get):
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "grammar ok",
            "sources": [],
            "skills_used": ["rag_answer"],
            "agent_name": "english_grammar",
            "agent_id": "english_grammar",
        }
        mock_orch.agent.default_model = "deepseek-chat"
        mock_get.return_value = mock_orch

        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse("ask-question"),
            {
                "question": "请讲解一下语法和时态",
                "knowledge_base_id": str(self.kb.id),
                "agent_id": "english_orchestrator",
                "use_agent": True,
                "model": "deepseek",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0][1], "english_grammar")
        self.assertEqual(r.data.get("english_delegate"), "grammar")
        self.assertEqual(r.data.get("english_intent_source"), "keyword")

    @patch("apps.chat.views.get_orchestrator_by_tier")
    def test_explicit_delegate_overrides_auto(self, mock_get):
        mock_orch = MagicMock()
        mock_orch.process.return_value = {
            "answer": "vocab ok",
            "sources": [],
            "skills_used": ["rag_answer"],
            "agent_name": "english_vocab",
            "agent_id": "english_vocab",
        }
        mock_orch.agent.default_model = "deepseek-chat"
        mock_get.return_value = mock_orch

        self.client.force_authenticate(user=self.user)
        r = self.client.post(
            reverse("ask-question"),
            {
                "question": "请讲解一下语法和时态",
                "knowledge_base_id": str(self.kb.id),
                "agent_id": "english_orchestrator",
                "english_delegate": "vocab",
                "use_agent": True,
                "model": "deepseek",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_get.call_args[0][1], "english_vocab")
        self.assertEqual(r.data.get("english_intent_source"), "explicit")
