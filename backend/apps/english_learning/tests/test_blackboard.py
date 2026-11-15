from unittest import mock
from datetime import date

from django.test import SimpleTestCase

from apps.english_learning.blackboard import (
    active_unit_id_from_outline,
    build_today_tasks,
    missed_yesterday_drill,
    normalize_weak_dimensions,
)


class BlackboardHelpersTests(SimpleTestCase):
    def test_normalize_weak_dimensions(self):
        self.assertEqual(normalize_weak_dimensions(None), [])
        self.assertEqual(normalize_weak_dimensions(["grammar", ""]), ["grammar"])
        self.assertEqual(normalize_weak_dimensions("x"), ["x"])

    def test_active_unit_id_from_outline(self):
        self.assertEqual(active_unit_id_from_outline({}), "week_1")
        self.assertEqual(
            active_unit_id_from_outline({"weeks": [{"week": "1-2", "theme": "foundation"}]}),
            "1-2:foundation",
        )

    def test_today_intake_bootstrap_done(self):
        tasks = build_today_tasks({"phase": "intake", "bootstrap_completed": True})
        self.assertTrue(any(t["id"] == "post_bootstrap" for t in tasks))

    def test_today_tutor_weak_task(self):
        tasks = build_today_tasks(
            {
                "phase": "tutor",
                "weak_dimensions": ["grammar"],
                "active_unit_id": "1-2:foundation",
                "last_drill_at": "2000-01-01T00:00:00+00:00",
            }
        )
        self.assertTrue(any(t["id"] == "weak_review" for t in tasks))

    @mock.patch("apps.english_learning.blackboard.timezone.localdate")
    def test_missed_yesterday_drill_calendar(self, m_ld):
        m_ld.return_value = date(2026, 5, 8)
        self.assertTrue(missed_yesterday_drill("2026-05-06T12:00:00+08:00"))
        self.assertFalse(missed_yesterday_drill("2026-05-07T12:00:00+08:00"))
