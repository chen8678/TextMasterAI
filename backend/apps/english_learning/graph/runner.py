"""G1 占位：在引入 LangGraph 前，用 `node_cursor` 指向 `WIZARD_GRAPH_NODE_NAMES` 的逻辑位。"""

from __future__ import annotations

from typing import Any, Dict

from django.db import transaction

from ..models import EnglishLearningGraphCheckpoint, EnglishLearningProfile
from .nodes import WIZARD_GRAPH_NODE_NAMES, wizard_node_name_at
from .checkpoint_store import (
    default_thread_id,
    get_or_create_default_checkpoint,
    sync_graph_projection_into_profile_session,
)


def current_node_name(checkpoint: EnglishLearningGraphCheckpoint) -> str | None:
    return wizard_node_name_at(int(checkpoint.node_cursor or 0))


def _wizard_graph_snapshot(profile: EnglishLearningProfile, graph_state: dict) -> Dict[str, Any] | None:
    """从 checkpoint `graph_state` 还原 `wizard_graph` 摘要（供 GET status / 前端恢复）。"""
    if not graph_state.get("langgraph_wizard") and not graph_state.get("langgraph_wizard_trace"):
        return None
    from .wizard_sse import build_wizard_graph_payload

    phase = graph_state.get("langgraph_wizard_phase") or (profile.session_state or {}).get("phase")
    pending = graph_state.get("langgraph_pending_human") or ""
    return build_wizard_graph_payload(
        {
            "phase": phase,
            "poc_trace": graph_state.get("langgraph_wizard_trace") or graph_state.get("langgraph_poc_trace"),
            "pending_human_node": pending,
            "node_data": graph_state.get("langgraph_node_data") or {},
            "last_error": graph_state.get("langgraph_last_error") or "",
        },
        completed=str(phase or "").lower() == "tutor",
        interrupted=bool(pending),
        next_nodes=[],
    )


def status_payload(profile: EnglishLearningProfile) -> Dict[str, Any]:
    cp = get_or_create_default_checkpoint(profile)
    profile.refresh_from_db()
    from .langgraph_poc import LANGGRAPH_AVAILABLE, get_checkpointer_backend

    gs = dict(cp.graph_state or {})
    out: Dict[str, Any] = {
        "thread_id": cp.thread_id,
        "node_cursor": cp.node_cursor,
        "current_node": current_node_name(cp),
        "wizard_nodes": list(WIZARD_GRAPH_NODE_NAMES),
        "graph_state": gs,
        "session_phase": (profile.session_state or {}).get("phase"),
        "langgraph_available": LANGGRAPH_AVAILABLE,
        "langgraph_checkpointer": get_checkpointer_backend(),
    }
    wg = _wizard_graph_snapshot(profile, gs)
    if wg is not None:
        out["wizard_graph"] = wg
    return out


def advance_cursor(
    profile: EnglishLearningProfile,
    *,
    delta: int = 1,
) -> EnglishLearningGraphCheckpoint:
    """测试或后台任务用：沿占位节点表前进（不替代 LangGraph 路由）。"""
    with transaction.atomic():
        get_or_create_default_checkpoint(profile)
        tid = default_thread_id(profile.pk)
        cp = EnglishLearningGraphCheckpoint.objects.select_for_update().get(
            profile_id=profile.pk,
            thread_id=tid,
        )
        n = len(WIZARD_GRAPH_NODE_NAMES)
        new_i = min(max(0, int(cp.node_cursor or 0) + int(delta)), max(0, n - 1))
        if new_i != cp.node_cursor:
            cp.node_cursor = new_i
            cp.save(update_fields=["node_cursor", "updated_at"])
    sync_graph_projection_into_profile_session(profile)
    return EnglishLearningGraphCheckpoint.objects.get(profile_id=profile.pk, thread_id=tid)
