"""快速定级 placement：组卷题量与 session_state.placement_choice。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import AssessmentSession
from apps.english_learning.services import get_or_create_profile, merge_session_state

User = get_user_model()


class AssessmentPlacementApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_pl_u", email="el_pl_u@t.local", password="pw-pl"
        )
        self.profile = get_or_create_profile(self.user)
        merge_session_state(
            self.profile,
            {"learner_constraints": {"level_tags": ["CEFR:B1"]}, "bootstrap_completed": True},
        )
        self.client.force_authenticate(user=self.user)

    def test_placement_defaults_three_items(self):
        r = self.client.post(
            reverse("english-assessment-start"),
            {"kind": "placement", "level_target": "B1"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data.get("kind"), AssessmentSession.Kind.PLACEMENT)
        self.assertEqual(len(r.data.get("items") or []), 3)
        self.assertEqual(r.data.get("count"), 3)
        aid = r.data["assessment_id"]
        session = AssessmentSession.objects.get(id=aid)
        self.assertEqual(session.kind, AssessmentSession.Kind.PLACEMENT)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.session_state or {}).get("placement_choice"), "quick")

    def test_level_test_default_five_items(self):
        r = self.client.post(
            reverse("english-assessment-start"),
            {"kind": "level_test", "level_target": "B1"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data.get("kind"), AssessmentSession.Kind.LEVEL_TEST)
        self.assertEqual(len(r.data.get("items") or []), 5)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.session_state or {}).get("placement_choice"), "full_test")
