"""G1：POST graph/run-node/ 与节点 Skill 执行。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import AssessmentSession, EnglishLearningGraphCheckpoint
from apps.english_learning.services import get_or_create_profile, merge_session_state
from apps.english_learning.graph.checkpoint_store import default_thread_id
from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES

User = get_user_model()


class GraphRunNodeApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_run_node_u", email="el_run_node_u@t.local", password="pw-run"
        )
        self.profile = get_or_create_profile(self.user)
        self.client.force_authenticate(user=self.user)

    def test_run_node_requires_node_name(self):
        r = self.client.post(reverse("english-graph-run-node"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_run_unknown_node(self):
        r = self.client.post(
            reverse("english-graph-run-node"),
            {"node": "not_a_real_node"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_assessment_run_creates_session(self, mock_exec):
        mock_exec.return_value = (
            {
                "items": [{"id": "q1", "stem": "x"}],
                "items_scoring": [{"id": "q1", "answer_key": "a"}],
                "level_used": "B1",
                "count": 1,
            },
            None,
        )
        merge_session_state(
            self.profile,
            {"phase": "intake", "bootstrap_completed": True, "learner_constraints": {}},
        )
        r = self.client.post(
            reverse("english-graph-run-node"),
            {"node": "assessment_run", "question_count": 2},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["node_run"]["node"], "assessment_run")
        self.assertTrue(
            AssessmentSession.objects.filter(profile=self.profile).exists()
        )
        cp = EnglishLearningGraphCheckpoint.objects.get(
            profile=self.profile, thread_id=default_thread_id(self.profile.pk)
        )
        self.assertEqual(cp.node_cursor, WIZARD_GRAPH_NODE_NAMES.index("assessment_run"))

    @patch("apps.skills.registry.SkillRegistry.execute_safe")
    def test_assessment_score_auto_responses(self, mock_exec):
        mock_exec.return_value = (
            {
                "scores": {"overall_pct": 80},
                "gap_summary": "不错",
                "weak_dimensions": ["grammar"],
            },
            None,
        )
        session = AssessmentSession.objects.create(
            profile=self.profile,
            kind="level_test",
            level_target="B1",
            items_json=[{"id": "q1", "type": "single_choice", "dimension": "grammar", "answer_key": "a"}],
            responses_json=[],
            status=AssessmentSession.Status.DRAFT,
        )
        merge_session_state(
            self.profile,
            {"phase": "assessment", "active_assessment_id": str(session.id)},
        )
        r = self.client.post(
            reverse("english-graph-run-node"),
            {"node": "assessment_score", "auto_responses": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.status, AssessmentSession.Status.SCORED)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.session_state or {}).get("phase"), "roadmap")

    def test_placement_node_without_skill(self):
        r = self.client.post(
            reverse("english-graph-run-node"),
            {"node": "placement_or_confirm", "placement_choice": "quick", "run_skill": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.session_state or {}).get("placement_choice"), "quick")
