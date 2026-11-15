"""roadmap/save-draft：HITL 多轮保存 session_state，不调 Skill。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


class RoadmapSaveDraftApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_sd_u", email="el_sd_u@t.local", password="pw-sd"
        )
        self.profile = get_or_create_profile(self.user)
        merge_session_state(
            self.profile,
            {
                "phase": "roadmap_review",
                "roadmap_draft_markdown": "# v0",
                "roadmap_outline_json": {"weeks": [{"week": "1", "theme": "t"}]},
            },
        )
        self.client.force_authenticate(user=self.user)

    def test_save_draft_updates_markdown_and_rounds(self):
        r = self.client.post(
            reverse("english-roadmap-save-draft"),
            {"roadmap_markdown": "# v1\n\nmore"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertTrue(r.data.get("ok"))
        self.assertEqual(r.data.get("roadmap_hitl_rounds"), 1)
        self.assertGreaterEqual(int(r.data.get("session_state_version") or 0), 1)
        self.profile.refresh_from_db()
        st = self.profile.session_state or {}
        self.assertIn("# v1", st.get("roadmap_draft_markdown") or "")
        self.assertEqual(st.get("roadmap_hitl_rounds"), 1)

    def test_save_draft_rejects_empty_markdown(self):
        r = self.client.post(
            reverse("english-roadmap-save-draft"),
            {"roadmap_markdown": "  "},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_save_draft_version_conflict(self):
        self.profile.refresh_from_db()
        v0 = int((self.profile.session_state or {}).get("_merge_version") or 0)
        r1 = self.client.post(
            reverse("english-roadmap-save-draft"),
            {"roadmap_markdown": "# a", "session_state_version": v0},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK, r1.data)
        self.profile.refresh_from_db()
        v1 = int((self.profile.session_state or {}).get("_merge_version") or 0)
        r2 = self.client.post(
            reverse("english-roadmap-save-draft"),
            {"roadmap_markdown": "# b", "session_state_version": v0},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r2.data.get("session_state_version"), v1)
