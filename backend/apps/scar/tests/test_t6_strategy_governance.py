"""T6 单测：策略补丁校验、Staging 门禁、execute_safe active。"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.skills.models import Skill, SkillExecutionLog, SkillEvolutionStaging
from apps.skills.registry import SkillRegistry
from apps.scar.services.strategy_evolution import (
    apply_scar_strategy_with_heldout_gate,
    ensure_scar_retrieve_skill,
    propose_scar_strategy_patch,
)
from apps.scar.services.strategy_patch import validate_strategy_patch

User = get_user_model()


class StrategyPatchSchemaTests(TestCase):
    def test_rejects_engineering_values(self):
        ok, reason = validate_strategy_patch(
            {
                "patch_type": "recall_strategy",
                "window_width_mm": 1500,
            }
        )
        self.assertFalse(ok)
        self.assertTrue("forbidden" in reason or "unknown_keys" in reason)

    def test_accepts_alias_and_disambiguation(self):
        ok, reason = validate_strategy_patch(
            {
                "patch_type": "recall_strategy",
                "alias_overrides": {"窗口宽度": "window_width_mm"},
                "disambiguation_priority": [
                    {"when_field": "window_width_mm", "prefer_over": "window_height_mm"}
                ],
                "retry_rules": [
                    {"on_coverage": "conflict", "action": "expand_top_k", "expand_top_k": 16}
                ],
            }
        )
        self.assertTrue(ok, reason)


class ScarStrategyStagingTests(TestCase):
    def test_pending_does_not_mutate_active_patch(self):
        skill = ensure_scar_retrieve_skill()
        before = dict((skill.metadata or {}).get("scar_strategy_patch") or {})
        staging = propose_scar_strategy_patch(
            {
                "patch_type": "recall_strategy",
                "alias_overrides": {"窗宽别名测试": "window_width_mm"},
            }
        )
        skill.refresh_from_db()
        after = (skill.metadata or {}).get("scar_strategy_patch") or {}
        self.assertEqual(staging.status, SkillEvolutionStaging.Status.PENDING)
        self.assertEqual(before, after)

    def test_apply_skip_gate_bumps_version(self):
        skill = ensure_scar_retrieve_skill()
        v0 = skill.version
        staging = propose_scar_strategy_patch(
            {
                "patch_type": "recall_strategy",
                "alias_overrides": {"开口宽度": "window_width_mm"},
            }
        )
        result = apply_scar_strategy_with_heldout_gate(
            str(staging.id),
            skip_gate=True,
        )
        self.assertTrue(result["ok"], result)
        skill.refresh_from_db()
        self.assertEqual(skill.version, v0 + 1)
        self.assertEqual(
            (skill.metadata or {}).get("scar_strategy_patch", {}).get("alias_overrides", {}).get("开口宽度"),
            "window_width_mm",
        )


class ScarExecuteSafeLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="scar_gate_user", email="scar_gate@example.com", password="x"
        )
        # builtin 已注册 scar_retrieve；此处确保 DB 行存在
        self.skill = ensure_scar_retrieve_skill()

    def test_draft_scar_retrieve_denied_for_normal(self):
        self.skill.lifecycle_status = "draft"
        self.skill.is_active = False
        self.skill.save(update_fields=["lifecycle_status", "is_active"])
        result, err = SkillRegistry.execute_safe(
            "scar_retrieve",
            user=self.user,
            query="2号楼3层窗宽",
            knowledge_base_id="00000000-0000-0000-0000-000000000000",
        )
        self.assertIsNone(result)
        self.assertTrue(err)
        log = SkillExecutionLog.objects.filter(skill_id="scar_retrieve").latest("created_at")
        self.assertEqual(log.status, "denied")

    def test_active_scar_retrieve_allowed_for_normal(self):
        self.skill.lifecycle_status = "active"
        self.skill.is_active = True
        self.skill.save(update_fields=["lifecycle_status", "is_active"])
        result, err = SkillRegistry.execute_safe(
            "scar_retrieve",
            user=self.user,
            query="2号楼3层窗宽",
            knowledge_base_id="00000000-0000-0000-0000-000000000000",
        )
        # KB 空时仍应执行成功（返回 evidence_pack / 空结果）
        self.assertIsNone(err)
        self.assertIsNotNone(result)
