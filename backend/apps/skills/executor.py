"""
Skill 安全执行引擎
- 权限校验（permission_level）
- 超时控制（可选）
- 执行日志
"""
import signal
from typing import Optional, Any, Callable
from django.conf import settings

from .registry import SkillRegistry, check_skill_permission, log_skill_execution, pop_skill_log_metadata


class SkillExecutionTimeout(Exception):
    """Skill 执行超时"""
    pass


def _run_with_timeout(execute_func: Callable, timeout_seconds: Optional[int], **kwargs) -> Any:
    """带超时的执行（仅 Unix 可用）"""
    if timeout_seconds is None or timeout_seconds <= 0:
        return execute_func(**kwargs)

    def _handler(signum, frame):
        raise SkillExecutionTimeout(f"执行超时（{timeout_seconds}s）")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_seconds)
    try:
        result = execute_func(**kwargs)
        return result
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def execute_skill(
    skill_id: str,
    user=None,
    session_id=None,
    timeout_seconds: Optional[int] = None,
    **kwargs
) -> tuple[Optional[dict], Optional[str]]:
    """
    安全执行 Skill：权限校验 + 可选超时 + 日志
    
    Args:
        skill_id: 技能 ID
        user: 当前用户（用于权限校验）
        session_id: 会话 ID（用于日志）
        timeout_seconds: 超时秒数，None 表示不限制
    
    Returns:
        (result, error) 与 SkillRegistry.execute_safe 一致
    """
    log_refs, log_trigger = pop_skill_log_metadata(kwargs)
    allowed, perm_err = check_skill_permission(skill_id, user)
    if not allowed:
        log_skill_execution(
            skill_id,
            "denied",
            str(kwargs)[:200] if kwargs else "",
            perm_err or "",
            session_id,
            user=user,
            retrieval_refs=log_refs,
            trigger_source=log_trigger,
        )
        return (None, perm_err)

    skill = SkillRegistry.get(skill_id)
    if not skill:
        return (None, f"未知 Skill: {skill_id}")

    input_summary = str(kwargs)[:200] if kwargs else ""
    timeout = timeout_seconds or getattr(settings, "SKILL_EXECUTION_TIMEOUT", 60)

    try:
        if hasattr(signal, "SIGALRM"):
            result = _run_with_timeout(skill["execute"], timeout, **kwargs)
        else:
            result = skill["execute"](**kwargs)
        output_summary = str(result)[:200] if result else ""
        log_skill_execution(
            skill_id,
            "success",
            input_summary,
            output_summary,
            session_id,
            user=user,
            retrieval_refs=log_refs,
            trigger_source=log_trigger,
        )
        return (result, None)
    except SkillExecutionTimeout as e:
        log_skill_execution(
            skill_id,
            "failed",
            input_summary,
            str(e)[:200],
            session_id,
            user=user,
            retrieval_refs=log_refs,
            trigger_source=log_trigger,
        )
        return (None, str(e))
    except Exception as e:
        err_msg = str(e)[:200]
        log_skill_execution(
            skill_id,
            "failed",
            input_summary,
            err_msg,
            session_id,
            user=user,
            retrieval_refs=log_refs,
            trigger_source=log_trigger,
        )
        return (None, str(e))
