"""E2：他人 Profile / Assessment / 私库定稿不可访问。"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import AssessmentSession
from apps.english_learning.services import get_or_create_profile, merge_session_state
from apps.knowledge.models import Document

User = get_user_model()


class EnglishLearningIsolationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="el_iso_a", email="el_iso_a@t.local", password="pw-el-iso"
        )
        self.user_b = User.objects.create_user(
            username="el_iso_b", email="el_iso_b@t.local", password="pw-el-iso"
        )
        self.profile_a = get_or_create_profile(self.user_a)

    def test_cannot_submit_others_assessment(self):
        session = AssessmentSession.objects.create(
            profile=self.profile_a,
            kind=AssessmentSession.Kind.LEVEL_TEST,
            level_target="B1",
            items_json=[
                {"id": "a", "type": "single_choice", "dimension": "grammar", "answer_key": "were"},
            ],
            responses_json=[],
            status=AssessmentSession.Status.DRAFT,
        )
        url = reverse("english-assessment-submit", kwargs={"assessment_id": session.id})
        self.client.force_authenticate(user=self.user_b)
        r = self.client.post(
            url,
            {"responses": [{"item_id": "a", "answer": "were"}]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_finalize_into_others_kb(self):
        url = reverse("english-roadmap-finalize")
        self.client.force_authenticate(user=self.user_b)
        kb_id = str(self.profile_a.default_kb_id)
        r = self.client.post(
            url,
            {
                "roadmap_markdown": "# Hijack",
                "knowledge_base_id": kb_id,
                "title": "Bad",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_get_each_user_own_kb(self):
        profile_b = get_or_create_profile(self.user_b)
        self.assertNotEqual(str(self.profile_a.default_kb_id), str(profile_b.default_kb_id))
        self.client.force_authenticate(user=self.user_a)
        ra = self.client.get(reverse("english-profile"))
        self.assertEqual(ra.status_code, status.HTTP_200_OK)
        self.assertEqual(str(ra.data.get("default_kb_id")), str(self.profile_a.default_kb_id))
        self.client.force_authenticate(user=self.user_b)
        rb = self.client.get(reverse("english-profile"))
        self.assertEqual(rb.status_code, status.HTTP_200_OK)
        self.assertEqual(str(rb.data.get("default_kb_id")), str(profile_b.default_kb_id))

    def test_today_never_leaks_other_user_blackboard(self):
        merge_session_state(
            self.profile_a,
            {
                "phase": "tutor",
                "weak_dimensions": ["grammar"],
                "secret_marker": "USER_A_ONLY",
            },
        )
        self.client.force_authenticate(user=self.user_b)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn("USER_A_ONLY", str(r.data))

    def test_patch_profile_only_updates_authenticated_user(self):
        merge_session_state(self.profile_a, {"marker_only_a": True})
        profile_b = get_or_create_profile(self.user_b)
        merge_session_state(profile_b, {"marker_only_b": True})
        self.client.force_authenticate(user=self.user_a)
        r = self.client.patch(
            reverse("english-profile"),
            {"session_state": {"patched_by": "user_a"}},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.profile_a.refresh_from_db()
        profile_b.refresh_from_db()
        st_a = self.profile_a.session_state or {}
        st_b = profile_b.session_state or {}
        self.assertEqual(st_a.get("patched_by"), "user_a")
        self.assertTrue(st_a.get("marker_only_a"))
        self.assertEqual(st_b.get("patched_by"), None)
        self.assertTrue(st_b.get("marker_only_b"))

    def test_roadmap_draft_foreign_assessment_returns_200_without_binding(self):
        session = AssessmentSession.objects.create(
            profile=self.profile_a,
            kind=AssessmentSession.Kind.LEVEL_TEST,
            level_target="B1",
            items_json=[{"id": "x", "type": "single_choice", "dimension": "grammar", "answer_key": "a"}],
            responses_json=[],
            status=AssessmentSession.Status.DRAFT,
        )
        get_or_create_profile(self.user_b)
        self.client.force_authenticate(user=self.user_b)
        r = self.client.post(
            reverse("english-roadmap-draft"),
            {"assessment_id": str(session.id), "focus_dimensions": ["vocabulary"]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("roadmap_markdown", r.data)

    def test_save_draft_only_updates_authenticated_user_profile(self):
        merge_session_state(
            self.profile_a,
            {
                "phase": "roadmap_review",
                "roadmap_draft_markdown": "# ONLY_USER_A",
            },
        )
        profile_b = get_or_create_profile(self.user_b)
        self.client.force_authenticate(user=self.user_b)
        r = self.client.post(
            reverse("english-roadmap-save-draft"),
            {"roadmap_markdown": "# USER_B_DRAFT"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.profile_a.refresh_from_db()
        profile_b.refresh_from_db()
        st_a = self.profile_a.session_state or {}
        st_b = profile_b.session_state or {}
        self.assertIn("ONLY_USER_A", st_a.get("roadmap_draft_markdown", ""))
        self.assertIn("USER_B_DRAFT", st_b.get("roadmap_draft_markdown", ""))

    def test_finalize_returns_409_when_session_state_version_stale(self):
        merge_session_state(
            self.profile_a,
            {"phase": "roadmap_review", "roadmap_draft_markdown": "# Ready"},
        )
        self.profile_a.refresh_from_db()
        ver = int((self.profile_a.session_state or {}).get("_merge_version") or 0)
        self.assertGreaterEqual(ver, 1)
        self.client.force_authenticate(user=self.user_a)
        with patch("apps.english_learning.views.SkillRegistry.execute_safe") as ex:
            ex.return_value = ({}, None)
            r = self.client.post(
                reverse("english-roadmap-finalize"),
                {
                    "roadmap_markdown": "# Ready",
                    "session_state_version": ver - 1,
                },
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r.data.get("error"), "session_state_version_conflict")
        ex.assert_not_called()

    def test_peer_cannot_list_or_fetch_documents_in_others_default_kb(self):
        """他人 default_kb 内文档：无成员关系时列表与详情均为 404（防枚举）。"""
        doc = Document.objects.create(
            knowledge_base=self.profile_a.default_kb,
            title="User A roadmap",
            content="# Secret content",
            content_type="markdown",
            file_path="",
            content_hash="a" * 64,
        )
        get_or_create_profile(self.user_b)
        self.client.force_authenticate(user=self.user_b)
        kb_a = str(self.profile_a.default_kb_id)
        list_url = reverse("document-list", kwargs={"knowledge_base_id": kb_a})
        r_list = self.client.get(list_url)
        self.assertEqual(r_list.status_code, status.HTTP_404_NOT_FOUND)
        detail_url = reverse(
            "document-detail",
            kwargs={"knowledge_base_id": kb_a, "pk": str(doc.pk)},
        )
        r_detail = self.client.get(detail_url)
        self.assertEqual(r_detail.status_code, status.HTTP_404_NOT_FOUND)
