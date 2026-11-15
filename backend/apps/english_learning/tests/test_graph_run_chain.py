"""G1：POST graph/run-chain/ 冒烟链。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import AssessmentSession, RoadmapRevision
from apps.english_learning.services import get_or_create_profile

User = get_user_model()

SMOKE_MD = "# Study Plan\n\n## Week 1\n- vocab\n"


class GraphRunChainApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_chain_u", email="el_chain_u@t.local", password="pw-chain"
        )
        self.profile = get_or_create_profile(self.user)
        self.client.force_authenticate(user=self.user)

    def _mock_skill(self, skill_id, *args, **kwargs):
        if skill_id == "english_profile_from_tags":
            return (
                {"learner_constraints": {"level_tags": ["CEFR:B1"], "weekly_minutes": 120}},
                None,
            )
        if skill_id == "english_assessment_build":
            items = [
                {
                    "id": "q1",
                    "type": "single_choice",
                    "dimension": "grammar",
                    "answer_key": "a",
                }
            ]
            return (
                {
                    "items": items,
                    "items_scoring": items,
                    "level_used": "B1",
                    "count": 1,
                },
                None,
            )
        if skill_id == "english_assessment_score":
            return (
                {
                    "scores": {"overall_pct": 100},
                    "gap_summary": "很好",
                    "weak_dimensions": [],
                },
                None,
            )
        if skill_id == "english_roadmap_draft":
            return (
                {
                    "roadmap_markdown": SMOKE_MD,
                    "outline_json": {"units": [{"id": "u1", "title": "Week 1"}]},
                },
                None,
            )
        if skill_id == "english_roadmap_finalize":
            doc_id = getattr(self, "_finalize_doc_id", None)
            return (
                {
                    "document_id": doc_id,
                    "knowledge_base_id": str(self.profile.default_kb_id),
                },
                None,
            )
        return ({}, None)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_run_chain_smoke_reaches_tutor(self, mock_exec):
        from apps.knowledge.models import Document

        doc = Document.objects.create(
            knowledge_base=self.profile.default_kb,
            title="chain doc",
            content=SMOKE_MD,
            content_type="markdown",
        )
        self._finalize_doc_id = str(doc.id)
        mock_exec.side_effect = self._mock_skill

        r = self.client.post(
            reverse("english-graph-run-chain"),
            {
                "level_tags": ["CEFR:B1"],
                "question_count": 1,
                "focus_dimensions": ["grammar"],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["chain"]["phase"], "tutor")
        self.assertGreaterEqual(len(r.data["chain"]["steps"]), 5)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.session_state or {}).get("phase"), "tutor")
        self.assertTrue(AssessmentSession.objects.filter(profile=self.profile, status="scored").exists())
        self.assertTrue(RoadmapRevision.objects.filter(profile=self.profile).exists())

    def test_run_chain_custom_nodes_empty_fails(self):
        r = self.client.post(
            reverse("english-graph-run-chain"),
            {"nodes": []},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
