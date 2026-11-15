"""G1：LangGraph 与 session phase 自动同步。"""
import unittest

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.graph.langgraph_poc import LANGGRAPH_AVAILABLE, reset_langgraph_poc_runtime_for_tests
from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES
from apps.english_learning.models import EnglishLearningGraphCheckpoint
from apps.english_learning.services import get_or_create_profile, merge_session_state
from apps.english_learning.graph.checkpoint_store import default_thread_id

User = get_user_model()


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要 langgraph")
class LangGraphSyncOnMergeTests(APITestCase):
    def setUp(self):
        reset_langgraph_poc_runtime_for_tests()
        self.user = User.objects.create_user(
            username="el_sync_u", email="el_sync_u@t.local", password="pw-sync"
        )
        self.profile = get_or_create_profile(self.user)

    @override_settings(ENGLISH_LEARNING_LANGGRAPH_AUTO_SYNC=True)
    def test_merge_phase_change_writes_langgraph_trace(self):
        merge_session_state(self.profile, {"phase": "intake", "bootstrap_completed": True})
        merge_session_state(self.profile, {"phase": "assessment"})
        tid = default_thread_id(self.profile.pk)
        cp = EnglishLearningGraphCheckpoint.objects.filter(
            profile=self.profile, thread_id=tid
        ).first()
        self.assertIsNotNone(cp)
        gs = cp.graph_state or {}
        tr = gs.get("langgraph_poc_trace") or []
        self.assertGreaterEqual(len(tr), 3)
        self.assertEqual(tr[2], WIZARD_GRAPH_NODE_NAMES[2])

    def test_graph_langgraph_sync_endpoint(self):
        self.client.force_authenticate(user=self.user)
        merge_session_state(self.profile, {"phase": "roadmap"})
        r = self.client.post(reverse("english-graph-langgraph-sync"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        sync = r.data.get("langgraph_sync") or {}
        self.assertFalse(sync.get("skipped"))
        self.assertGreaterEqual(sync.get("target_cursor", 0), 4)
