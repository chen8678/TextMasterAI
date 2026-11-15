"""G1：生产向导 LangGraph（interrupt + Skill 节点）。"""
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.graph.langgraph_poc import LANGGRAPH_AVAILABLE
from apps.english_learning.graph.langgraph_wizard import (
    WIZARD_HUMAN_INTERRUPT_AFTER,
    reset_langgraph_wizard_runtime_for_tests,
)
from apps.english_learning.services import get_or_create_profile

User = get_user_model()


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
class LangGraphWizardApiTests(APITestCase):
    def setUp(self):
        reset_langgraph_wizard_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_wiz_u", email="el_wiz_u@t.local", password="pw-wiz"
        )
        self.profile = get_or_create_profile(self.user)
        self.client.force_authenticate(user=self.user)

    def _mock_skill(self, skill_id, *args, **kwargs):
        if skill_id == "english_profile_from_tags":
            return ({"learner_constraints": {"level_tags": ["CEFR:B1"]}}, None)
        if skill_id == "english_assessment_build":
            items = [{"id": "q1", "type": "single_choice", "dimension": "grammar", "answer_key": "a"}]
            return ({"items": items, "items_scoring": items, "level_used": "B1", "count": 1}, None)
        if skill_id == "english_assessment_score":
            return (
                {"scores": {"overall_pct": 100}, "gap_summary": "ok", "weak_dimensions": []},
                None,
            )
        if skill_id == "english_roadmap_draft":
            return (
                {
                    "roadmap_markdown": "# Plan\n",
                    "outline_json": {"units": [{"id": "u1", "title": "W1"}]},
                },
                None,
            )
        if skill_id == "english_roadmap_finalize":
            return (
                {"document_id": getattr(self, "_doc_id", None), "knowledge_base_id": str(self.profile.default_kb_id)},
                None,
            )
        return ({}, None)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_wizard_start_interrupts_after_assessment_run(self, mock_exec):
        mock_exec.side_effect = self._mock_skill
        r = self.client.post(
            reverse("english-graph-wizard-start"),
            {"level_tags": ["CEFR:B1"], "placement_choice": "full_test"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        wg = r.data.get("wizard_graph") or {}
        self.assertTrue(wg.get("interrupted"), wg)
        next_nodes = wg.get("next_nodes") or []
        self.assertTrue(
            "assessment_run" in next_nodes or "assessment_score" in next_nodes,
            next_nodes,
        )
        self.assertIn(
            wg.get("pending_human_node"),
            ("placement_or_confirm", "assessment_run"),
        )
        self.assertIn("assessment_run", WIZARD_HUMAN_INTERRUPT_AFTER)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_wizard_resume_with_auto_responses_can_progress(self, mock_exec):
        from apps.knowledge.models import Document

        doc = Document.objects.create(
            knowledge_base=self.profile.default_kb,
            title="wiz doc",
            content="# Plan\n",
            content_type="markdown",
        )
        self._doc_id = str(doc.id)
        mock_exec.side_effect = self._mock_skill

        self.client.post(
            reverse("english-graph-wizard-start"),
            {"level_tags": ["CEFR:B1"]},
            format="json",
        )
        r2 = self.client.post(
            reverse("english-graph-wizard-resume"),
            {
                "auto_responses": True,
                "focus_dimensions": ["grammar"],
                "placement_choice": "full_test",
            },
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK, r2.data)
        wg = r2.data.get("wizard_graph") or {}
        self.assertIn("phase", wg)
        self.assertTrue(wg.get("interrupted") or wg.get("completed"))
