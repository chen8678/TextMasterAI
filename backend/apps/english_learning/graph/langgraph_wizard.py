"""
Phase-C G1：生产向导 LangGraph——节点内调用 `run_wizard_node`（Skill + Django 持久化），
在需用户输入的步骤后 **interrupt**（定级确认 / 测评作答 / 路线 HITL 前草案）。

与 `langgraph_poc` 共用 checkpointer 连接；编译图为独立单例 `get_compiled_wizard_app()`。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict

from django.contrib.auth import get_user_model

from ..models import EnglishLearningProfile
from .langgraph_poc import (
    LANGGRAPH_AVAILABLE,
    _compile_lock,
    _make_saver_and_conn,
    _snapshot_to_dict,
    poc_trace_to_node_cursor,
    reset_langgraph_poc_runtime_for_tests,
)
from .node_executors import apply_node_run_to_profile, run_wizard_node
from .nodes import WIZARD_GRAPH_NODE_NAMES

# 节点执行后暂停，等待 `resume` 携带 `node_payload`
WIZARD_HUMAN_INTERRUPT_AFTER: Tuple[str, ...] = (
    "placement_or_confirm",
    "assessment_run",
    "roadmap_draft_skill",
)

_wizard_compiled_app: Any = None


class EnglishWizardGraphState(TypedDict, total=False):
    profile_id: str
    user_id: str
    phase: str
    poc_trace: List[str]
    node_payload: Dict[str, Any]
    last_error: str
    pending_human_node: str
    node_data: Dict[str, Any]


def reset_langgraph_wizard_runtime_for_tests(**kwargs) -> None:
    """与 POC 测试隔离一并重置 wizard 图单例。"""
    global _wizard_compiled_app
    reset_langgraph_poc_runtime_for_tests(**kwargs)
    with _compile_lock:
        _wizard_compiled_app = None


def _build_wizard_graph(saver: Any) -> Any:
    from langgraph.graph import END, START, StateGraph

    names = tuple(WIZARD_GRAPH_NODE_NAMES)
    if not names:
        raise RuntimeError("WIZARD_GRAPH_NODE_NAMES 为空")

    def make_step(logical_name: str, *, is_last: bool):
        def step(state: EnglishWizardGraphState) -> Dict[str, Any]:
            pid = state.get("profile_id")
            uid = state.get("user_id")
            if pid in (None, "") or uid in (None, ""):
                return {
                    "last_error": "missing profile_id or user_id",
                    "pending_human_node": logical_name,
                }
            User = get_user_model()
            profile = EnglishLearningProfile.objects.get(pk=pid)
            user = User.objects.get(pk=uid)
            payload = dict(state.get("node_payload") or {})
            result = run_wizard_node(profile, user, logical_name, payload, run_skill=True)
            if not result.ok:
                return {
                    "last_error": result.error,
                    "phase": (profile.session_state or {}).get("phase") or "intake",
                    "pending_human_node": logical_name,
                }
            apply_node_run_to_profile(profile, result)
            profile.refresh_from_db()
            st = profile.session_state or {}
            pending = logical_name if logical_name in WIZARD_HUMAN_INTERRUPT_AFTER else ""
            return {
                "phase": str(st.get("phase") or "intake"),
                "poc_trace": list(result.graph_patch.get("poc_trace") or []),
                "node_payload": {},
                "last_error": "",
                "pending_human_node": pending,
                "node_data": dict(result.data or {}),
            }

        return step

    g = StateGraph(EnglishWizardGraphState)
    last = len(names) - 1
    for i, nm in enumerate(names):
        g.add_node(nm, make_step(nm, is_last=(i == last)))
    g.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        g.add_edge(a, b)
    g.add_edge(names[-1], END)
    return g.compile(checkpointer=saver, interrupt_after=list(WIZARD_HUMAN_INTERRUPT_AFTER))


def get_compiled_wizard_app() -> Any:
    global _wizard_compiled_app
    from . import langgraph_poc as poc

    if _wizard_compiled_app is not None:
        return _wizard_compiled_app
    with _compile_lock:
        if _wizard_compiled_app is not None:
            return _wizard_compiled_app
        if poc._saver is None:
            poc._saver, poc._sqlite_conn, poc._active_backend = _make_saver_and_conn()
        _wizard_compiled_app = _build_wizard_graph(poc._saver)
        return _wizard_compiled_app


def read_wizard_checkpoint_tip(*, thread_id: str) -> Optional[Dict[str, Any]]:
    if not LANGGRAPH_AVAILABLE:
        return None
    try:
        app = get_compiled_wizard_app()
        st = app.get_state({"configurable": {"thread_id": thread_id}})
    except Exception:
        return None
    if st is None or getattr(st, "values", None) is None:
        return None
    tip = _snapshot_to_dict(st)
    vals = tip.get("values") or {}
    if not tip.get("checkpoint_id") and not vals:
        return None
    return tip


def _merge_resume_payload(config: dict, payload: Dict[str, Any]) -> None:
    app = get_compiled_wizard_app()
    st = app.get_state(config)
    if st is None:
        return
    vals = dict(getattr(st, "values", {}) or {})
    merged = dict(vals.get("node_payload") or {})
    merged.update(payload or {})
    vals["node_payload"] = merged
    app.update_state(config, vals)


def _wizard_completed(values: Dict[str, Any], *, next_nodes: List[str]) -> bool:
    tr = list(values.get("poc_trace") or [])
    if tr and tr[-1] == WIZARD_GRAPH_NODE_NAMES[-1] and not next_nodes:
        return True
    return str(values.get("phase") or "").lower() == "tutor" and not next_nodes


def run_wizard_graph_until_pause(
    *,
    thread_id: str,
    profile_id: Any,
    user_id: int,
    initial_payload: Optional[Dict[str, Any]] = None,
    resume_payload: Optional[Dict[str, Any]] = None,
    max_steps: int = 20,
) -> Dict[str, Any]:
    """
    启动或恢复向导图，直到下一处 interrupt、跑完全链或出错。
    `resume_payload` 非空时合并进 state 后 `invoke(None)`。
    """
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("未安装 langgraph")

    app = get_compiled_wizard_app()
    config = {"configurable": {"thread_id": thread_id}}
    tip_before = read_wizard_checkpoint_tip(thread_id=thread_id)

    if tip_before is None:
        init: Dict[str, Any] = {
            "profile_id": str(profile_id),
            "user_id": str(user_id),
            "phase": "intake",
            "poc_trace": [],
            "node_payload": dict(initial_payload or {}),
            "last_error": "",
            "pending_human_node": "",
            "node_data": {},
        }
        out = app.invoke(init, config=config)
    else:
        if resume_payload:
            _merge_resume_payload(config, resume_payload)
        out = app.invoke(None, config=config)

    steps = 0
    while steps < max_steps:
        st = app.get_state(config)
        if st is None:
            break
        tip = _snapshot_to_dict(st)
        next_nodes = list(tip.get("next") or [])
        vals = dict(tip.get("values") or out or {})
        if _wizard_completed(vals, next_nodes=next_nodes):
            return {
                "values": vals,
                "tip": tip,
                "completed": True,
                "interrupted": False,
                "next_nodes": [],
            }
        if next_nodes:
            return {
                "values": vals,
                "tip": tip,
                "completed": False,
                "interrupted": True,
                "next_nodes": next_nodes,
            }
        if vals.get("last_error"):
            return {
                "values": vals,
                "tip": tip,
                "completed": False,
                "interrupted": False,
                "next_nodes": [],
                "failed": True,
            }
        out = app.invoke(None, config=config)
        steps += 1

    st = app.get_state(config)
    tip = _snapshot_to_dict(st) if st else None
    vals = dict((tip or {}).get("values") or out or {})
    next_nodes = list((tip or {}).get("next") or [])
    return {
        "values": vals,
        "tip": tip,
        "completed": _wizard_completed(vals, next_nodes=next_nodes),
        "interrupted": bool(next_nodes),
        "next_nodes": next_nodes,
    }


def persist_wizard_graph_to_django(
    profile: EnglishLearningProfile,
    *,
    thread_id: str,
    values: Dict[str, Any],
    tip: Optional[Dict[str, Any]],
) -> None:
    from .langgraph_sync import persist_langgraph_poc_observability

    out = {
        "phase": values.get("phase"),
        "poc_trace": values.get("poc_trace"),
        "langgraph_wizard": True,
        "pending_human_node": values.get("pending_human_node"),
        "node_data": values.get("node_data"),
        "last_error": values.get("last_error"),
    }
    persist_langgraph_poc_observability(
        profile,
        thread_id=thread_id,
        out=out,
        tip=tip,
        create_checkpoint=True,
    )
    gs_patch = {
        "langgraph_wizard": True,
        "langgraph_wizard_phase": values.get("phase"),
        "langgraph_wizard_trace": values.get("poc_trace"),
        "langgraph_pending_human": values.get("pending_human_node"),
        "langgraph_node_data": values.get("node_data"),
    }
    if values.get("last_error"):
        gs_patch["langgraph_last_error"] = values.get("last_error")
    from .checkpoint_store import default_thread_id, get_or_create_default_checkpoint

    cp = get_or_create_default_checkpoint(profile)
    if cp.thread_id == default_thread_id(profile.pk):
        merged = dict(cp.graph_state or {})
        merged.update({k: v for k, v in gs_patch.items() if v is not None})
        cp.graph_state = merged
        cp.node_cursor = poc_trace_to_node_cursor(values.get("poc_trace"))
        cp.save(update_fields=["graph_state", "node_cursor", "updated_at"])
