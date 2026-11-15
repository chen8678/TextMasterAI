from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


class TodaySuggestionsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_today_u", email="el_today_u@t.local", password="pw-today"
        )

    def test_get_today_requires_auth(self):
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_today_tutor_returns_tasks(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(
            profile,
            {
                "phase": "tutor",
                "weak_dimensions": ["vocabulary"],
                "active_unit_id": "w1",
                "last_drill_at": "1999-01-01T00:00:00+00:00",
            },
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["phase"], "tutor")
        self.assertIn("tasks", r.data)
        self.assertTrue(len(r.data["tasks"]) >= 1)
        self.assertIn("blackboard", r.data)
        self.assertIn("last_wizard_open_at", r.data["blackboard"])
        self.assertIn("recall_pack", r.data)
        self.assertIsNotNone(r.data["recall_pack"])
        self.assertTrue(len(r.data["recall_pack"].get("pack_items") or []) >= 1)

    def test_today_pack_disabled(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(
            profile,
            {
                "phase": "tutor",
                "weak_dimensions": ["grammar"],
                "gap_summary": "x",
            },
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"), {"pack": "0"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data.get("recall_pack"))

    def test_today_includes_reminder_prefs(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(profile, {"phase": "tutor", "reminder_prefs": {"intensity": "high"}})
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("reminder_prefs", r.data)
        self.assertEqual(r.data["reminder_prefs"].get("intensity"), "high")

    def test_today_dnd_suppresses_recall_and_proactive_tasks(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(
            profile,
            {
                "phase": "tutor",
                "weak_dimensions": ["grammar"],
                "gap_summary": "gap text",
                "reminder_prefs": {"do_not_disturb": True},
            },
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data.get("recall_pack"))
        ids = [t.get("id") for t in (r.data.get("tasks") or [])]
        self.assertIn("reminder_suppressed", ids)
        self.assertTrue(r.data["reminder_prefs"].get("do_not_disturb"))

    def test_today_low_intensity_no_recall_pack(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(
            profile,
            {
                "phase": "tutor",
                "weak_dimensions": ["grammar"],
                "gap_summary": "x",
                "reminder_prefs": {"intensity": "low"},
            },
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIsNone(r.data.get("recall_pack"))
        self.assertEqual(r.data["reminder_prefs"].get("intensity"), "low")

    def test_today_echoes_custom_quiet_hours(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(
            profile,
            {
                "phase": "intake",
                "reminder_prefs": {"quiet_hours": {"enabled": False, "start": "21:30", "end": "06:00"}},
            },
        )
        self.client.force_authenticate(user=self.user)
        r = self.client.get(reverse("english-today"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        qh = r.data["reminder_prefs"]["quiet_hours"]
        self.assertEqual(qh.get("start"), "21:30")
        self.assertEqual(qh.get("end"), "06:00")

    def test_drill_touch_updates_timestamp(self):
        profile = get_or_create_profile(self.user)
        merge_session_state(profile, {"phase": "tutor"})
        self.client.force_authenticate(user=self.user)
        r = self.client.post(reverse("english-drill-touch"), {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data.get("ok"))
        profile.refresh_from_db()
        self.assertTrue((profile.session_state or {}).get("last_drill_at"))
