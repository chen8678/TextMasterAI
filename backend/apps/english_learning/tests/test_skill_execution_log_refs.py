"""G4：英语学习 API 触发的 Skill 日志写入 retrieval_refs / trigger_source。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import AssessmentSession
from apps.english_learning.services import get_or_create_profile
from apps.skills.models import SkillExecutionLog

User = get_user_model()


class EnglishSkillExecutionLogRefsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="el_log_u", email="el_log_u@t.local", password="pw-log"
        )
        self.profile = get_or_create_profile(self.user)

    def test_assessment_submit_log_has_assessment_trigger_and_refs(self):
        session = AssessmentSession.objects.create(
            profile=self.profile,
            kind=AssessmentSession.Kind.LEVEL_TEST,
            level_target="B1",
            items_json=[
                {"id": "a", "type": "single_choice", "dimension": "grammar", "answer_key": "were"},
            ],
            responses_json=[],
            status=AssessmentSession.Status.DRAFT,
        )
        self.client.force_authenticate(user=self.user)
        url = reverse("english-assessment-submit", kwargs={"assessment_id": session.id})
        r = self.client.post(
            url,
            {"responses": [{"item_id": "a", "answer": "were"}]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

        log = (
            SkillExecutionLog.objects.filter(skill_id="english_assessment_score", user=self.user)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.trigger_source, "english_learning:assessment_submit")
        self.assertIsInstance(log.retrieval_refs, dict)
        self.assertEqual(log.retrieval_refs.get("assessment_id"), str(session.id))
        self.assertEqual(log.retrieval_refs.get("profile_id"), str(self.profile.pk))
        self.assertEqual(log.retrieval_refs.get("domain"), "english_learning")
