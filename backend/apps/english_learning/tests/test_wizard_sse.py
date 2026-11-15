"""G3：向导图 resume SSE。"""
import json
import unittest
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.english_learning.graph.human_hints import human_action_hint
from apps.english_learning.graph.langgraph_poc import LANGGRAPH_AVAILABLE
from apps.english_learning.graph.langgraph_wizard import reset_langgraph_wizard_runtime_for_tests
from apps.english_learning.services import get_or_create_profile

User = get_user_model()


class HumanHintsTests(unittest.TestCase):
    def test_pending_assessment_run(self):
        h = human_action_hint(pending_human_node="assessment_run", next_nodes=["assessment_score"])
        self.assertEqual(h["kind"], "wait_input")
        self.assertEqual(h["suggested_step"], 1)


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
class WizardResumeStreamApiTests(TransactionTestCase):
    """SSE 在后台线程 invoke，须 TransactionTestCase 以便子线程可见 Profile。"""

    def setUp(self):
        reset_langgraph_wizard_runtime_for_tests()
        uid = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f"el_sse_{uid}", email=f"el_sse_{uid}@t.local", password="pw-sse"
        )
        self.profile = get_or_create_profile(self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _mock_skill(self, skill_id, *args, **kwargs):
        if skill_id == "english_profile_from_tags":
            return ({"learner_constraints": {"level_tags": ["B1"]}}, None)
        if skill_id == "english_assessment_build":
            items = [{"id": "q1", "type": "single_choice", "dimension": "g", "answer_key": "a"}]
            return ({"items": items, "items_scoring": items, "level_used": "B1", "count": 1}, None)
        return ({}, None)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_resume_stream_content_type(self, mock_exec):
        mock_exec.side_effect = self._mock_skill
        self.client.post(
            reverse("english-graph-wizard-start"),
            {"level_tags": ["CEFR:B1"]},
            format="json",
        )
        resp = self.client.post(
            reverse("english-graph-wizard-resume-stream"),
            {"placement_choice": "full_test", "kind": "level_test", "question_count": 2},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/event-stream", resp.get("Content-Type", ""))
        body = b"".join(resp.streaming_content).decode("utf-8", errors="replace")
        self.assertIn("event:", body)
        self.assertTrue("node_done" in body or "interrupt" in body or "end" in body)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_resume_stream_score_payload(self, mock_exec):
        def _score(skill_id, *args, **kwargs):
            if skill_id == "english_assessment_score":
                return (
                    {
                        "gap_summary": "ok",
                        "weak_dimensions": ["grammar"],
                        "scores_json": {"grammar": 0.5},
                    },
                    None,
                )
            return self._mock_skill(skill_id, *args, **kwargs)

        mock_exec.side_effect = _score
        self.client.post(
            reverse("english-graph-wizard-start"),
            {"level_tags": ["CEFR:B1"]},
            format="json",
        )
        self.client.post(
            reverse("english-graph-wizard-resume"),
            {"placement_choice": "full_test", "kind": "level_test", "question_count": 1},
            format="json",
        )
        resp = self.client.post(
            reverse("english-graph-wizard-resume-stream"),
            {
                "responses": [{"item_id": "q1", "answer": "a"}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = b"".join(resp.streaming_content).decode("utf-8", errors="replace")
        self.assertIn("event:", body)
        self.assertTrue("interrupt" in body or "end" in body)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_resume_stream_roadmap_token_events(self, mock_exec):
        from apps.english_learning.skill_handlers.stream_context import emit_wizard_token

        def _skill(skill_id, *args, **kwargs):
            if skill_id == "english_roadmap_draft":
                emit_wizard_token('{"roadmap_markdown": "# ', "roadmap_draft_skill")
                emit_wizard_token('Stream Title"}', "roadmap_draft_skill")
                return (
                    {
                        "roadmap_markdown": "# Stream Title",
                        "outline_json": {"weeks": [{"week": "1", "theme": "t", "tasks": []}]},
                    },
                    None,
                )
            if skill_id == "english_assessment_score":
                return (
                    {
                        "gap_summary": "ok",
                        "weak_dimensions": ["grammar"],
                        "scores_json": {"grammar": 0.5},
                    },
                    None,
                )
            return self._mock_skill(skill_id, *args, **kwargs)

        mock_exec.side_effect = _skill
        self.client.post(
            reverse("english-graph-wizard-start"),
            {"level_tags": ["CEFR:B1"]},
            format="json",
        )
        self.client.post(
            reverse("english-graph-wizard-resume"),
            {"placement_choice": "full_test", "kind": "level_test", "question_count": 1},
            format="json",
        )
        # 评分 + 路线草案在同一次 stream 中执行，token 在 roadmap_draft_skill 期间推送
        resp = self.client.post(
            reverse("english-graph-wizard-resume-stream"),
            {"responses": [{"item_id": "q1", "answer": "a"}]},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = b"".join(resp.streaming_content).decode("utf-8", errors="replace")
        self.assertIn("event: token", body)
        self.assertIn("Stream Title", body)
        self.assertTrue("interrupt" in body or "end" in body)
