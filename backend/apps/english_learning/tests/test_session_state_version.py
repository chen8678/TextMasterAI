"""A9：session_state 乐观锁（_merge_version / session_state_version）。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


class SessionStateVersionApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_ver_u", email="el_ver_u@t.local", password="pw-ver"
        )
        get_or_create_profile(self.user)

    def test_get_profile_exposes_session_state_version(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-profile"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("session_state_version", r.data)
        self.assertEqual(r.data["session_state_version"], 0)
        st = r.data.get("session_state") or {}
        self.assertNotIn("_merge_version", st)

    def test_patch_with_stale_version_returns_409(self):
        self.client.force_authenticate(user=self.user)
        r1 = self.client.patch(
            reverse("english-profile"),
            {"session_state": {"a": 1}, "session_state_version": 0},
            format="json",
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data.get("session_state_version"), 1)
        r2 = self.client.patch(
            reverse("english-profile"),
            {"session_state": {"b": 2}, "session_state_version": 0},
            format="json",
        )
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r2.data.get("session_state_version"), 1)

    def test_patch_with_current_version_succeeds(self):
        self.client.force_authenticate(user=self.user)
        self.client.patch(
            reverse("english-profile"),
            {"session_state": {"a": 1}, "session_state_version": 0},
            format="json",
        )
        r = self.client.patch(
            reverse("english-profile"),
            {"session_state": {"b": 2}, "session_state_version": 1},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data.get("session_state_version"), 2)


class MergeSessionStateVersionTests(APITestCase):
    def test_merge_increments_version(self):
        u = User.objects.create_user(username="el_ver_m", email="el_ver_m@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(p, {"x": 1})
        p.refresh_from_db()
        self.assertEqual((p.session_state or {}).get("_merge_version"), 1)
        merge_session_state(p, {"y": 2})
        p.refresh_from_db()
        self.assertEqual((p.session_state or {}).get("_merge_version"), 2)
