"""Reactive 自进化调度（E2E #7 / schedule_evolution_after_user_turn）。"""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.skills.evolution import schedule_evolution_after_user_turn
from apps.skills.models import Skill, SkillEvolutionStaging, SkillExecutionLog

User = get_user_model()


class ReactiveEvolutionManagerTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.user = User.objects.create_user(
            username=f"reactive_ev_{uid}",
            email=f"reactive_ev_{uid}@t.local",
            password="pw-reactive",
        )
        self.session_id = uuid.uuid4()

    def _failed_log(self, skill_id: str) -> SkillExecutionLog:
        return SkillExecutionLog.objects.create(
            skill_id=skill_id,
            session_id=self.session_id,
            user=self.user,
            status="failed",
            input_summary="用户问合同条款",
            output_summary="检索失败",
        )

    @override_settings(
        EVOLUTION_ENFORCE_DOMAIN_GUARD=True,
        EVOLUTION_ALLOWED_DOMAINS=frozenset({"law"}),
    )
    def test_guard_blocks_with_evolution_guard_log(self):
        skill = Skill.objects.create(
            id=f"reactive_guard_{uuid.uuid4().hex[:6]}",
            name="Guard Block",
            evolution_enabled=True,
            metadata={"evolution_domain": "qa_enhancement"},
        )
        self._failed_log(skill.id)
        with self.assertLogs("apps.skills.evolution.guard", level="WARNING") as cm:
            result = schedule_evolution_after_user_turn(
                user=self.user,
                session_id=self.session_id,
                user_message="不对，你应该重新检索相关条款",
            )
        self.assertFalse(result.scheduled)
        self.assertIn("domain_not_allowed", result.reason)
        self.assertTrue(any("[evolution_guard]" in line for line in cm.output))
        self.assertEqual(SkillEvolutionStaging.objects.filter(skill=skill).count(), 0)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_reactive_creates_staging(self):
        skill = Skill.objects.create(
            id=f"reactive_ok_{uuid.uuid4().hex[:6]}",
            name="Reactive OK",
            evolution_enabled=True,
            metadata={"evolution_domain": "qa_enhancement"},
        )
        log = self._failed_log(skill.id)
        result = schedule_evolution_after_user_turn(
            user=self.user,
            session_id=self.session_id,
            user_message="错了，请纠正上面的回答",
        )
        self.assertTrue(result.scheduled, result.reason)
        staging = SkillEvolutionStaging.objects.filter(skill=skill).first()
        self.assertIsNotNone(staging)
        self.assertEqual(staging.source_log_id, log.id)
        self.assertEqual(staging.status, SkillEvolutionStaging.Status.PENDING)
        self.assertIn("Troubleshooting", staging.draft_markdown)
