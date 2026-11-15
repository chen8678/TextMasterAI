"""
Phase-C G1：LangGraph POC 与 Django `session_state.phase` / checkpoint 的同步。

`merge_session_state` 在 **phase 变更** 时可自动调用 `maybe_sync_langgraph_on_phase_change`（可配置关闭）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction

from ..models import EnglishLearningGraphCheckpoint, EnglishLearningProfile
from .checkpoint_store import (
    default_thread_id,
    get_or_create_default_checkpoint,
    reconcile_checkpoint_node_cursor,
    sync_graph_projection_into_profile_session,
)
from .langgraph_poc import (
    LANGGRAPH_AVAILABLE,
    advance_english_graph_poc_step,
    poc_trace_to_node_cursor,
    read_langgraph_checkpoint_tip,
)
from .nodes import WIZARD_GRAPH_NODE_NAMES
from .phase_cursor import node_cursor_for_session_phase

logger = logging.getLogger(__name__)


def langgraph_auto_sync_enabled() -> bool:
    raw = getattr(settings, "ENGLISH_LEARNING_LANGGRAPH_AUTO_SYNC", True)
    if isinstance(raw, str):
        return raw.lower() in ("1", "true", "yes", "on")
    return bool(raw)


def persist_langgraph_poc_observability(
    profile: EnglishLearningProfile,
    *,
    thread_id: str,
    out: Dict[str, Any],
    tip: Optional[Dict[str, Any]],
    create_checkpoint: bool = False,
) -> None:
    """把 LangGraph POC 输出写入 Django checkpoint，并按 `poc_trace` 同步 `node_cursor`。"""
    if create_checkpoint:
        get_or_create_default_checkpoint(profile)
    cp_exists = EnglishLearningGraphCheckpoint.objects.filter(
        profile_id=profile.pk, thread_id=thread_id
    ).exists()
    if not cp_exists:
        return
    with transaction.atomic():
        cp = EnglishLearningGraphCheckpoint.objects.select_for_update().get(
            profile_id=profile.pk,
            thread_id=thread_id,
        )
        gs = dict(cp.graph_state or {})
        gs["langgraph_poc_phase"] = out.get("phase")
        gs["langgraph_poc_trace"] = out.get("poc_trace")
        if tip is not None:
            gs["langgraph_checkpoint_tip"] = tip
        cp.graph_state = gs
        update_fields = ["graph_state", "updated_at"]
        new_cur = poc_trace_to_node_cursor(out.get("poc_trace"))
        if int(cp.node_cursor or 0) != new_cur:
            cp.node_cursor = new_cur
            update_fields.append("node_cursor")
        cp.save(update_fields=update_fields)
    sync_graph_projection_into_profile_session(profile)


def _current_poc_trace(thread_id: str) -> list[str]:
    tip = read_langgraph_checkpoint_tip(thread_id=thread_id)
    if not tip:
        return []
    vals = tip.get("values") or {}
    tr = vals.get("poc_trace")
    return list(tr) if isinstance(tr, list) else []


def sync_langgraph_poc_to_session_phase(profile: EnglishLearningProfile) -> Dict[str, Any]:
    """
    按 `session_state.phase` 推断的目标 `node_cursor`，单步推进 LangGraph POC 直至对齐（只进不退）。
    返回摘要 dict（含 `advanced_steps`、`target_cursor`、`current_cursor` 等）。
    """
    if not LANGGRAPH_AVAILABLE:
        return {"skipped": True, "reason": "langgraph_not_installed"}

    target = node_cursor_for_session_phase(profile.session_state)
    if target is None:
        return {"skipped": True, "reason": "unknown_phase"}

    tid = default_thread_id(profile.pk)
    st = profile.session_state or {}
    initial = {"phase": str(st.get("phase") or "intake"), "poc_trace": []}

    trace = _current_poc_trace(tid)
    current_cur = poc_trace_to_node_cursor(trace)
    advanced = 0
    out: Dict[str, Any] = {"phase": st.get("phase"), "poc_trace": trace}
    tip: Optional[Dict[str, Any]] = read_langgraph_checkpoint_tip(thread_id=tid)
    completed = False

    max_steps = len(WIZARD_GRAPH_NODE_NAMES) + 2
    while current_cur < target and advanced < max_steps:
        out, tip, completed, _ = advance_english_graph_poc_step(thread_id=tid, initial=initial)
        trace = list(out.get("poc_trace") or [])
        current_cur = poc_trace_to_node_cursor(trace)
        advanced += 1
        if completed:
            break

    if advanced > 0:
        get_or_create_default_checkpoint(profile)
        persist_langgraph_poc_observability(profile, thread_id=tid, out=out, tip=tip)
    elif EnglishLearningGraphCheckpoint.objects.filter(profile_id=profile.pk, thread_id=tid).exists():
        persist_langgraph_poc_observability(profile, thread_id=tid, out=out, tip=tip)

    cp = EnglishLearningGraphCheckpoint.objects.filter(profile_id=profile.pk, thread_id=tid).first()
    if cp is not None:
        reconcile_checkpoint_node_cursor(profile, cp)

    return {
        "skipped": False,
        "advanced_steps": advanced,
        "target_cursor": target,
        "current_cursor": current_cur,
        "poc_trace": trace,
        "langgraph_poc_completed": completed,
        "thread_id": tid,
    }


def maybe_sync_langgraph_on_phase_change(profile: EnglishLearningProfile) -> Optional[Dict[str, Any]]:
    """phase 变更后 best-effort 同步；失败只记日志，不抛出。"""
    if not langgraph_auto_sync_enabled():
        return None
    try:
        return sync_langgraph_poc_to_session_phase(profile)
    except Exception:
        logger.exception("LangGraph auto-sync failed for profile_id=%s", profile.pk)
        return None
