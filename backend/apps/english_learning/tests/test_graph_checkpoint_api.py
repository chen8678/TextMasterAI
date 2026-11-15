"""Phase-C G2：图 checkpoint 与 GET graph/status API。"""
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.graph.checkpoint_store import (
    default_thread_id,
    get_or_create_default_checkpoint,
)
from apps.english_learning.graph.langgraph_poc import LANGGRAPH_AVAILABLE
from apps.english_learning.graph.runner import advance_cursor
from apps.english_learning.models import EnglishLearningGraphCheckpoint
from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


class GraphStatusApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_graph_u", email="el_graph_u@t.local", password="pw-graph"
        )
        self.profile = get_or_create_profile(self.user)

    def test_get_graph_status_creates_checkpoint_and_thread_id(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-graph-status"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["thread_id"], default_thread_id(self.profile.pk))
        self.assertEqual(r.data["node_cursor"], 0)
        self.assertEqual(r.data["current_node"], "intake_tags")
        self.assertIn("wizard_nodes", r.data)
        self.assertEqual(
            EnglishLearningGraphCheckpoint.objects.filter(profile=self.profile).count(),
            1,
        )

    def test_graph_status_requires_authentication(self):
        r = self.client.get(reverse("english-graph-status"))
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_session_phase_synced_into_graph_state(self):
        merge_session_state(self.profile, {"phase": "assessment", "placement_choice": "full_test"})
        self.profile.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-graph-status"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        gs = r.data.get("graph_state") or {}
        self.assertEqual(gs.get("phase"), "assessment")
        self.assertEqual(gs.get("placement_choice"), "full_test")
        self.assertEqual(r.data.get("session_phase"), "assessment")
        self.assertEqual(r.data.get("node_cursor"), 2)
        self.assertEqual(r.data.get("current_node"), "assessment_run")


class GraphRunnerTests(APITestCase):
    def test_advance_cursor_moves_current_node(self):
        u = User.objects.create_user(username="el_graph_adv", email="el_graph_adv@t.local", password="pw")
        p = get_or_create_profile(u)
        advance_cursor(p, delta=2)
        p.refresh_from_db()
        cp = EnglishLearningGraphCheckpoint.objects.get(
            profile=p, thread_id=default_thread_id(p.pk)
        )
        self.assertEqual(cp.node_cursor, 2)


class MergeSessionStateGraphSyncTests(APITestCase):
    def test_merge_updates_existing_checkpoint_overlay(self):
        u = User.objects.create_user(username="el_sync_u", email="el_sync_u@t.local", password="pw")
        p = get_or_create_profile(u)
        get_or_create_default_checkpoint(p)
        merge_session_state(p, {"phase": "roadmap_editing", "assessment_id": "abc"})
        cp = EnglishLearningGraphCheckpoint.objects.get(profile=p, thread_id=default_thread_id(p.pk))
        self.assertEqual(cp.graph_state.get("phase"), "roadmap_editing")
        self.assertEqual(cp.graph_state.get("assessment_id"), "abc")
        self.assertEqual(cp.node_cursor, 6)

    def test_merge_maps_active_assessment_id_to_graph_assessment_id(self):
        u = User.objects.create_user(username="el_sync_aid", email="el_sync_aid@t.local", password="pw")
        p = get_or_create_profile(u)
        get_or_create_default_checkpoint(p)
        merge_session_state(p, {"phase": "assessment", "active_assessment_id": "sess-uuid-1"})
        cp = EnglishLearningGraphCheckpoint.objects.get(profile=p, thread_id=default_thread_id(p.pk))
        self.assertEqual(cp.graph_state.get("assessment_id"), "sess-uuid-1")

    def test_merge_writes_graph_projection_into_session_state(self):
        u = User.objects.create_user(username="el_gp_w", email="el_gp_w@t.local", password="pw")
        p = get_or_create_profile(u)
        get_or_create_default_checkpoint(p)
        merge_session_state(p, {"phase": "tutor"})
        p.refresh_from_db()
        st = p.session_state or {}
        self.assertEqual(st.get("graph_thread_id"), default_thread_id(p.pk))
        self.assertEqual(st.get("graph_node_cursor"), 8)
        self.assertEqual(st.get("graph_current_node"), "tutor_runtime")

    def test_merge_graph_projection_does_not_extra_bump_merge_version(self):
        u = User.objects.create_user(username="el_gp_v", email="el_gp_v@t.local", password="pw")
        p = get_or_create_profile(u)
        get_or_create_default_checkpoint(p)
        merge_session_state(p, {"marker": 1})
        p.refresh_from_db()
        self.assertEqual((p.session_state or {}).get("_merge_version"), 1)
        self.assertIn("graph_thread_id", p.session_state or {})

    def test_merge_does_not_create_checkpoint_row(self):
        u = User.objects.create_user(username="el_sync_n", email="el_sync_n@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(p, {"phase": "intake"})
        self.assertEqual(EnglishLearningGraphCheckpoint.objects.filter(profile=p).count(), 0)


class GraphCheckpointPostApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_gcp_u", email="el_gcp_u@t.local", password="pw-gcp"
        )
        self.profile = get_or_create_profile(self.user)

    def test_post_merge_graph_state(self):
        self.client.force_authenticate(user=self.user)
        self.client.get(reverse("english-graph-status"))
        r = self.client.post(
            reverse("english-graph-checkpoint"),
            {"graph_state": {"worker_note": "ok"}, "merge": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["graph_state"].get("worker_note"), "ok")

    def test_post_replace_graph_state(self):
        self.client.force_authenticate(user=self.user)
        self.client.get(reverse("english-graph-status"))
        merge_session_state(self.profile, {"phase": "tutor"})
        self.profile.refresh_from_db()
        r = self.client.post(
            reverse("english-graph-checkpoint"),
            {"graph_state": {"only": "x"}, "merge": False},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        gs = r.data.get("graph_state") or {}
        self.assertEqual(gs.get("only"), "x")
        # 响应前会再次从 session_state 覆盖约定键，故 phase 仍存在
        self.assertEqual(gs.get("phase"), "tutor")

    def test_post_invalid_graph_state(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-checkpoint"), {"graph_state": []}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_node_cursor_out_of_range(self):
        self.client.force_authenticate(user=self.user)
        self.client.get(reverse("english-graph-status"))
        r = self.client.post(
            reverse("english-graph-checkpoint"),
            {"graph_state": {}, "node_cursor": 99},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class GraphLangGraphPocApiTests(APITestCase):
    def setUp(self):
        from apps.english_learning.graph.langgraph_poc import reset_langgraph_poc_runtime_for_tests

        reset_langgraph_poc_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_lgp_u", email="el_lgp_u@t.local", password="pw-lgp"
        )
        self.profile = get_or_create_profile(self.user)

    @patch("apps.english_learning.graph.langgraph_poc.LANGGRAPH_AVAILABLE", False)
    def test_langgraph_poc_returns_503_when_not_installed(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-langgraph-poc"))
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(r.data.get("error"), "langgraph_not_installed")

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
    def test_langgraph_poc_writes_checkpoint_and_response(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-langgraph-poc"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("langgraph_poc", r.data)
        from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES

        self.assertEqual(r.data["langgraph_poc"].get("phase"), "tutor")
        gs = r.data.get("graph_state") or {}
        self.assertEqual(gs.get("langgraph_poc_phase"), "tutor")
        self.assertEqual(gs.get("langgraph_poc_trace"), list(WIZARD_GRAPH_NODE_NAMES))
        tip = gs.get("langgraph_checkpoint_tip")
        self.assertIsInstance(tip, dict)
        self.assertIn("checkpoint_id", tip)
        self.assertIn("values", tip)
        self.assertEqual(r.data.get("langgraph_checkpoint_tip"), tip)


class GraphLangGraphHistoryApiTests(APITestCase):
    def setUp(self):
        from apps.english_learning.graph.langgraph_poc import reset_langgraph_poc_runtime_for_tests

        reset_langgraph_poc_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_lgh_u", email="el_lgh_u@t.local", password="pw-lgh"
        )
        self.profile = get_or_create_profile(self.user)

    @patch("apps.english_learning.graph.langgraph_poc.LANGGRAPH_AVAILABLE", False)
    def test_langgraph_history_503_when_not_installed(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-graph-langgraph-history"))
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
    def test_langgraph_history_after_poc(self):
        self.client.force_authenticate(user=self.user)
        p = self.client.post(reverse("english-graph-langgraph-poc"))
        self.assertEqual(p.status_code, status.HTTP_200_OK)
        r = self.client.get(reverse("english-graph-langgraph-history"), {"limit": "10"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data.get("thread_id"), default_thread_id(self.profile.pk))
        self.assertGreaterEqual(len(r.data.get("summaries") or []), 1)
        self.assertIsNotNone(r.data.get("tip"))


class GraphLangGraphAdvanceApiTests(APITestCase):
    def setUp(self):
        from apps.english_learning.graph.langgraph_poc import reset_langgraph_poc_runtime_for_tests

        reset_langgraph_poc_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_lga_u", email="el_lga_u@t.local", password="pw-lga"
        )
        self.profile = get_or_create_profile(self.user)

    @patch("apps.english_learning.graph.langgraph_poc.LANGGRAPH_AVAILABLE", False)
    def test_langgraph_advance_503_when_not_installed(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-langgraph-advance"))
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
    def test_langgraph_advance_one_step_updates_cursor(self):
        from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES

        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-langgraph-advance"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data.get("langgraph_poc_completed"))
        tr = (r.data.get("langgraph_poc") or {}).get("poc_trace") or []
        self.assertEqual(len(tr), 1)
        self.assertEqual(tr[0], WIZARD_GRAPH_NODE_NAMES[0])
        self.assertEqual(r.data.get("node_cursor"), 0)
        self.assertIn("langgraph_checkpointer", r.data)


class GraphLangGraphResetApiTests(APITestCase):
    def setUp(self):
        from apps.english_learning.graph.langgraph_poc import reset_langgraph_poc_runtime_for_tests

        reset_langgraph_poc_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_lgr_u", email="el_lgr_u@t.local", password="pw-lgr"
        )
        self.profile = get_or_create_profile(self.user)

    @patch("apps.english_learning.graph.langgraph_poc.LANGGRAPH_AVAILABLE", False)
    def test_langgraph_reset_503_when_not_installed(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-graph-langgraph-reset"))
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(r.data.get("error"), "langgraph_not_installed")

    @unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
    def test_langgraph_reset_clears_history_and_graph_state_keys(self):
        self.client.force_authenticate(user=self.user)
        p = self.client.post(reverse("english-graph-langgraph-poc"))
        self.assertEqual(p.status_code, status.HTTP_200_OK)
        gs_before = (p.data.get("graph_state") or {})
        self.assertIn("langgraph_poc_phase", gs_before)

        rst = self.client.post(reverse("english-graph-langgraph-reset"))
        self.assertEqual(rst.status_code, status.HTTP_200_OK)
        self.assertTrue(rst.data.get("langgraph_reset"))
        gs_after = rst.data.get("graph_state") or {}
        self.assertNotIn("langgraph_poc_phase", gs_after)
        self.assertNotIn("langgraph_poc_trace", gs_after)
        self.assertNotIn("langgraph_checkpoint_tip", gs_after)

        hist = self.client.get(reverse("english-graph-langgraph-history"), {"limit": "10"})
        self.assertEqual(hist.status_code, status.HTTP_200_OK)
        self.assertEqual(hist.data.get("summaries") or [], [])
        self.assertIsNone(hist.data.get("tip"))
