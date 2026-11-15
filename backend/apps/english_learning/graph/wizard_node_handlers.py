"""
G1：向导图节点与 `session_state.phase` 对齐的业务副作用（不直接调 Skill，Skill 仍由 REST 触发）。

LangGraph 节点执行时更新 `phase` / `poc_trace`，与 `phase_cursor._PHASE_TO_CURSOR` 一致，
便于 POC 链观测与 Django checkpoint 游标协同。
"""

from __future__ import annotations

from typing import Any, Dict

from .nodes import WIZARD_GRAPH_NODE_NAMES

# 节点执行后写入的 phase（末节点 `tutor_runtime` 固定为 tutor）
_NODE_PHASE: Dict[str, str] = {
    "intake_tags": "intake",
    "placement_or_confirm": "intake",
    "assessment_run": "assessment",
    "assessment_score": "assessment",
    "gap_feedback": "roadmap",
    "roadmap_draft_skill": "roadmap",
    "roadmap_hitl": "roadmap_editing",
    "roadmap_finalize_skill": "tutor",
    "tutor_runtime": "tutor",
}


def apply_wizard_node(
    logical_name: str,
    state: Dict[str, Any],
    *,
    is_last: bool = False,
) -> Dict[str, Any]:
    """单步节点：追加 `poc_trace` 并按节点名更新 `phase`。"""
    if logical_name not in WIZARD_GRAPH_NODE_NAMES:
        raise ValueError(f"unknown wizard node: {logical_name}")
    tr = list(state.get("poc_trace") or [])
    tr.append(logical_name)
    out: Dict[str, Any] = {"poc_trace": tr}
    ph = _NODE_PHASE.get(logical_name)
    if ph:
        out["phase"] = ph
    elif is_last:
        out["phase"] = "tutor"
    return out
