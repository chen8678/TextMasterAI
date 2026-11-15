"""F4 补全：Celery 定时钩子（可选 beat），便于后续接推送 / 站内信。"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from celery import shared_task
except ImportError:

    def shared_task(*args, **kwargs):
        def decorator(f):
            return f

        return decorator(args[0]) if args and callable(args[0]) else decorator


logger = logging.getLogger(__name__)


@shared_task(name="apps.english_learning.tasks.english_reminder_tick")
def english_reminder_tick() -> Dict[str, Any]:
    """
    每日占位任务：统计处于 tutor 阶段的档案数并打日志。
    部署 Celery worker + beat 且设置 ENGLISH_REMINDER_BEAT=true 后才会入队（见 settings）。
    """
    from apps.english_learning.models import EnglishLearningProfile

    try:
        n = EnglishLearningProfile.objects.filter(
            session_state__contains={"phase": "tutor"}
        ).count()
    except Exception as exc:
        logger.warning("english_reminder_tick count failed: %s", exc)
        return {"ok": False, "error": str(exc)[:200]}
    logger.info("english_reminder_tick tutor_phase_profiles=%s", n)
    return {"ok": True, "tutor_phase_profiles": n}


@shared_task(name="apps.english_learning.tasks.english_graph_run_node")
def english_graph_run_node_task(
    profile_id: str,
    user_id: int,
    node_name: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """G1：异步执行单个向导图节点（需 Celery worker）。"""
    from django.contrib.auth import get_user_model

    from apps.english_learning.graph.node_executors import (
        apply_node_run_to_profile,
        run_wizard_node,
    )
    from apps.english_learning.models import EnglishLearningProfile

    User = get_user_model()
    try:
        profile = EnglishLearningProfile.objects.get(pk=profile_id)
        user = User.objects.get(pk=user_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "node": node_name}

    result = run_wizard_node(profile, user, node_name, payload or {})
    if not result.ok:
        return {
            "ok": False,
            "error": result.error,
            "node": node_name,
            "http_status_hint": result.http_status_hint,
        }
    try:
        apply_node_run_to_profile(profile, result)
    except Exception as exc:
        logger.exception("english_graph_run_node_task persist failed profile=%s node=%s", profile_id, node_name)
        return {"ok": False, "error": str(exc)[:200], "node": node_name}
    profile.refresh_from_db()
    return {
        "ok": True,
        "node": node_name,
        "phase": (profile.session_state or {}).get("phase"),
        "data": result.data,
    }


@shared_task(name="apps.english_learning.tasks.english_graph_wizard_resume")
def english_graph_wizard_resume_task(
    profile_id: str,
    user_id: int,
    resume_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """G1：异步恢复生产向导 LangGraph。"""
    from django.contrib.auth import get_user_model

    from apps.english_learning.graph.checkpoint_store import default_thread_id
    from apps.english_learning.graph.langgraph_wizard import (
        persist_wizard_graph_to_django,
        run_wizard_graph_until_pause,
    )
    from apps.english_learning.models import EnglishLearningProfile

    User = get_user_model()
    try:
        profile = EnglishLearningProfile.objects.get(pk=profile_id)
        user = User.objects.get(pk=user_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}

    tid = default_thread_id(profile.pk)
    try:
        run_result = run_wizard_graph_until_pause(
            thread_id=tid,
            profile_id=profile.pk,
            user_id=user.pk,
            resume_payload=resume_payload or {},
        )
    except Exception as exc:
        logger.exception("english_graph_wizard_resume_task failed profile=%s", profile_id)
        return {"ok": False, "error": str(exc)[:200]}

    persist_wizard_graph_to_django(
        profile, thread_id=tid, values=run_result.get("values") or {}, tip=run_result.get("tip")
    )
    vals = run_result.get("values") or {}
    return {
        "ok": not run_result.get("failed"),
        "completed": run_result.get("completed"),
        "interrupted": run_result.get("interrupted"),
        "phase": vals.get("phase"),
        "next_nodes": run_result.get("next_nodes"),
        "last_error": vals.get("last_error"),
    }
