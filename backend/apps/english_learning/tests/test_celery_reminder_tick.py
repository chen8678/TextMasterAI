"""F4：english_reminder_tick 可同步调用（Celery eager 或直连）。"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.english_learning.services import get_or_create_profile, merge_session_state
from apps.english_learning.tasks import english_reminder_tick

User = get_user_model()


class EnglishReminderTickTaskTests(TestCase):
    def test_tick_returns_count(self):
        u = User.objects.create_user(username="el_tick", email="el_tick@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(p, {"phase": "tutor"})
        r = english_reminder_tick()
        self.assertTrue(r.get("ok"))
        self.assertGreaterEqual(int(r.get("tutor_phase_profiles") or 0), 1)
