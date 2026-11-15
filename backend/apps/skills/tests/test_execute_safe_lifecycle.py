"""A0：execute_safe 生命周期 / 权限门禁自动化测试。"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.skills.models import Skill, SkillEvolutionStaging, SkillExecutionLog
from apps.skills.registry import SkillRegistry
from apps.skills.tasks import apply_staging_to_skill


User = get_user_model()


def _noop_execute(**kwargs):
    return {"ok": True, "echo": kwargs.get("question") or "ok"}


class ExecuteSafeLifecycleGateTests(TestCase):
    def setUp(self):
        SkillRegistry.register("gate_probe", _noop_execute, {"name": "Gate Probe"})
        self.normal = User.objects.create_user(
            username="gate_user", email="gate_user@example.com", password="x"
        )
        self.staff = User.objects.create_user(
            username="gate_staff", email="gate_staff@example.com", password="x", is_staff=True
        )
        self.superu = User.objects.create_superuser(
            username="gate_super", email="gate_super@example.com", password="x"
        )

    def _mk(self, sid, *, life="active", active=True, perm="rag"):
        SkillRegistry.register(sid, _noop_execute, {"name": sid})
        return Skill.objects.create(
            id=sid,
            name=sid,
            permission_level=perm,
            lifecycle_status=life,
            is_active=active,
        )

    def test_draft_denied_for_normal_user(self):
        self._mk("g_draft", life="draft", active=False)
        result, err = SkillRegistry.execute_safe("g_draft", user=self.normal, question="hi")
        self.assertIsNone(result)
        self.assertIn("未对普通用户开放", err or "")
        log = SkillExecutionLog.objects.filter(skill_id="g_draft").latest("created_at")
        self.assertEqual(log.status, "denied")

    def test_draft_allowed_for_staff_trial(self):
        self._mk("g_draft_staff", life="draft", active=False)
        result, err = SkillRegistry.execute_safe("g_draft_staff", user=self.staff, question="hi")
        self.assertIsNone(err)
        self.assertTrue(result and result.get("ok"))

    def test_disabled_denied_for_normal_and_staff(self):
        self._mk("g_disabled", life="disabled", active=False)
        r1, e1 = SkillRegistry.execute_safe("g_disabled", user=self.normal, question="hi")
        r2, e2 = SkillRegistry.execute_safe("g_disabled", user=self.staff, question="hi")
        self.assertIsNone(r1)
        self.assertIsNone(r2)
        self.assertIn("disabled", (e1 or "") + (e2 or ""))

    def test_rolled_back_denied_for_normal(self):
        self._mk("g_rb", life="rolled_back", active=True)
        result, err = SkillRegistry.execute_safe("g_rb", user=self.normal, question="hi")
        self.assertIsNone(result)
        self.assertIn("rolled_back", err or "")

    def test_active_ok_for_normal(self):
        self._mk("g_ok", life="active", active=True)
        result, err = SkillRegistry.execute_safe("g_ok", user=self.normal, question="hi")
        self.assertIsNone(err)
        self.assertTrue(result and result.get("ok"))

    def test_system_perm_denied_for_normal(self):
        self._mk("g_sys", life="active", active=True, perm="system")
        result, err = SkillRegistry.execute_safe("g_sys", user=self.normal, question="hi")
        self.assertIsNone(result)
        self.assertIn("权限不足", err or "")
        log = SkillExecutionLog.objects.filter(skill_id="g_sys").latest("created_at")
        self.assertEqual(log.status, "denied")

    def test_apply_staging_does_not_activate(self):
        skill = self._mk("g_apply", life="draft", active=False)
        st = SkillEvolutionStaging.objects.create(
            skill=skill,
            status=SkillEvolutionStaging.Status.PENDING,
            draft_markdown="## Troubleshooting\n- note",
            provenance="unit_test",
        )
        ok = apply_staging_to_skill(st.id, reviewer=self.staff)
        self.assertTrue(ok)
        skill.refresh_from_db()
        st.refresh_from_db()
        self.assertEqual(st.status, SkillEvolutionStaging.Status.APPLIED)
        self.assertFalse(skill.is_active)
        self.assertEqual(skill.lifecycle_status, "draft")
        self.assertIn("Troubleshooting", skill.metadata.get("evolution_merged_markdown", ""))

    def test_inactive_active_status_denied_for_normal(self):
        """lifecycle=active 但 is_active=false → 普通用户仍 denied。"""
        self._mk("g_inactive", life="active", active=False)
        result, err = SkillRegistry.execute_safe("g_inactive", user=self.normal, question="hi")
        self.assertIsNone(result)
        self.assertTrue(err)
