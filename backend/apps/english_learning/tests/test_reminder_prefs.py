"""F5：免打扰、安静时段、提醒强度（黑板规则 + session_state 合并）。"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.english_learning.blackboard import (
    build_today_tasks,
    is_proactive_reminder_suppressed,
    normalize_quiet_hours_dict,
    quiet_hours_active_now,
    reminder_prefs_from_state,
)
from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


@override_settings(TIME_ZONE="UTC", USE_TZ=True)
class QuietHoursLogicTests(SimpleTestCase):
    def test_overnight_window_inside(self):
        cfg = {"enabled": True, "start": "22:00", "end": "07:00"}
        t23 = timezone.make_aware(datetime(2026, 5, 6, 23, 0))
        self.assertTrue(quiet_hours_active_now(cfg, now=t23))
        t05 = timezone.make_aware(datetime(2026, 5, 7, 5, 30))
        self.assertTrue(quiet_hours_active_now(cfg, now=t05))

    def test_overnight_window_outside(self):
        cfg = {"enabled": True, "start": "22:00", "end": "07:00"}
        t12 = timezone.make_aware(datetime(2026, 5, 6, 12, 0))
        self.assertFalse(quiet_hours_active_now(cfg, now=t12))

    def test_same_day_window(self):
        cfg = {"enabled": True, "start": "09:00", "end": "17:00"}
        t12 = timezone.make_aware(datetime(2026, 5, 6, 12, 0))
        self.assertTrue(quiet_hours_active_now(cfg, now=t12))
        t20 = timezone.make_aware(datetime(2026, 5, 6, 20, 0))
        self.assertFalse(quiet_hours_active_now(cfg, now=t20))


class TutorReminderTasksTests(SimpleTestCase):
    def test_dnd_replaces_proactive_tutor_tasks(self):
        st = {
            "phase": "tutor",
            "weak_dimensions": ["grammar"],
            "last_drill_at": "1999-01-01T00:00:00+00:00",
            "gap_summary": "g",
            "reminder_prefs": {"do_not_disturb": True},
        }
        tasks = build_today_tasks(st)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["id"], "reminder_suppressed")

    def test_low_intensity_caps_proactive_before_daily_chat(self):
        st = {
            "phase": "tutor",
            "weak_dimensions": ["grammar", "vocabulary"],
            "last_drill_at": "1999-01-01T00:00:00+00:00",
            "gap_summary": "g",
            "reminder_prefs": {"intensity": "low"},
        }
        tasks = build_today_tasks(st)
        ids = [t["id"] for t in tasks]
        self.assertIn("daily_chat", ids)
        proactive = [i for i in ids if i in ("yesterday_miss", "weak_review")]
        self.assertLessEqual(len(proactive), 1)


class ReminderPrefsMergeTests(TestCase):
    def test_merge_normalizes_quiet_hours_times(self):
        u = User.objects.create_user(username="rp_norm", email="rp_norm@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(
            p,
            {"reminder_prefs": {"quiet_hours": {"enabled": True, "start": "x", "end": "99:99"}}},
        )
        p.refresh_from_db()
        qh = ((p.session_state or {}).get("reminder_prefs") or {}).get("quiet_hours") or {}
        self.assertEqual(qh.get("start"), "22:00")
        self.assertEqual(qh.get("end"), "07:00")

    def test_merge_session_state_nested_reminder_prefs(self):
        u = User.objects.create_user(username="rp_m", email="rp_m@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(p, {"reminder_prefs": {"do_not_disturb": True, "intensity": "high"}})
        p.refresh_from_db()
        merge_session_state(p, {"reminder_prefs": {"intensity": "low"}})
        p.refresh_from_db()
        rp = (p.session_state or {}).get("reminder_prefs") or {}
        self.assertTrue(rp.get("do_not_disturb"))
        self.assertEqual(rp.get("intensity"), "low")

    def test_merge_quiet_hours_subdict(self):
        u = User.objects.create_user(username="rp_q", email="rp_q@t.local", password="pw")
        p = get_or_create_profile(u)
        merge_session_state(
            p,
            {"reminder_prefs": {"quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00"}}},
        )
        p.refresh_from_db()
        merge_session_state(p, {"reminder_prefs": {"quiet_hours": {"enabled": False}}})
        p.refresh_from_db()
        qh = ((p.session_state or {}).get("reminder_prefs") or {}).get("quiet_hours") or {}
        self.assertFalse(qh.get("enabled"))
        self.assertEqual(qh.get("start"), "22:00")


class ReminderPrefsApiShapeTests(SimpleTestCase):
    def test_reminder_prefs_from_state_defaults(self):
        p = reminder_prefs_from_state({})
        self.assertFalse(p["do_not_disturb"])
        self.assertEqual(p["intensity"], "normal")
        self.assertFalse(p["quiet_hours_active"])
        self.assertEqual(p["quiet_hours"].get("start"), "22:00")
        self.assertEqual(p["quiet_hours"].get("end"), "07:00")

    def test_normalize_quiet_hours_invalid_strings(self):
        n = normalize_quiet_hours_dict({"enabled": True, "start": "nope", "end": "25:99"})
        self.assertEqual(n["start"], "22:00")
        self.assertEqual(n["end"], "07:00")
        self.assertTrue(n["enabled"])

    def test_is_suppressed_when_quiet_active(self):
        st = {
            "reminder_prefs": {
                "do_not_disturb": False,
                "quiet_hours": {"enabled": True, "start": "00:00", "end": "23:59"},
            }
        }
        self.assertTrue(is_proactive_reminder_suppressed(st))
