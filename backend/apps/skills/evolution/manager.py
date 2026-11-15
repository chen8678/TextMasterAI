"""
调度入口：在用户发送一轮问题并得到回答之后，判断是否应排队进化任务。
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional
from uuid import UUID

from django.conf import settings

from .guard import skill_allowed_for_evolution
from .signal_detector import user_hints_correction
from .types import EvolutionEnqueueResult

logger = logging.getLogger(__name__)


def schedule_evolution_after_user_turn(
    *,
    user,
    session_id: Optional[UUID],
    user_message: str,
    skills_used: Optional[List[str]] = None,
) -> EvolutionEnqueueResult:
    """
    条件：本会话内存在最近的 failed 日志 + 当前用户消息含纠正类关键词 + 对应 Skill 开启 evolution_enabled。
    """
    if not session_id or not user_message:
        return EvolutionEnqueueResult(False, "no_session_or_message")
    if not user_hints_correction(user_message):
        return EvolutionEnqueueResult(False, "no_correction_signal")

    from apps.skills.models import Skill, SkillExecutionLog

    last_failed = (
        SkillExecutionLog.objects.filter(session_id=session_id, status="failed")
        .order_by("-created_at")
        .first()
    )
    if not last_failed:
        return EvolutionEnqueueResult(False, "no_failed_log_in_session")

    try:
        skill = Skill.objects.get(id=last_failed.skill_id)
    except Skill.DoesNotExist:
        return EvolutionEnqueueResult(False, "skill_missing")

    if not getattr(skill, "evolution_enabled", False):
        return EvolutionEnqueueResult(False, "evolution_disabled")

    ok_dom, dom_reason = skill_allowed_for_evolution(skill)
    if not ok_dom:
        return EvolutionEnqueueResult(False, dom_reason)

    if skill.permission_level == "system" and getattr(settings, "FORBID_SYSTEM_SKILL_EVOLUTION", True):
        return EvolutionEnqueueResult(False, "system_skill_blocked")

    try:
        from apps.skills.tasks import run_skill_evolution_task

        run_skill_evolution_task.delay(
            skill_id=skill.id,
            source_log_id=str(last_failed.id),
            user_id=getattr(user, "id", None),
            user_message=user_message[:2000],
        )
    except Exception as exc:
        logger.exception("enqueue skill evolution failed: %s", exc)
        return EvolutionEnqueueResult(False, f"enqueue_error:{exc}")

    return EvolutionEnqueueResult(True, "queued")
