"""
G1：按序执行多个向导图节点（供 `POST graph/run-chain/` 与 E2E）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models import EnglishLearningProfile
from .node_executors import NodeRunResult, apply_node_run_to_profile, run_wizard_node
from .nodes import WIZARD_GRAPH_NODE_NAMES

# 演示 / 冒烟：跳过需用户 Markdown 的 HITL，定稿用草案占位
DEFAULT_SMOKE_CHAIN: Tuple[str, ...] = (
    "intake_tags",
    "placement_or_confirm",
    "assessment_run",
    "assessment_score",
    "gap_feedback",
    "roadmap_draft_skill",
    "roadmap_finalize_skill",
)


@dataclass
class NodeChainResult:
    ok: bool = True
    error: str = ""
    http_status_hint: int = 400
    failed_node: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)


def run_wizard_node_chain(
    profile: EnglishLearningProfile,
    user,
    node_names: List[str],
    base_payload: Optional[dict] = None,
) -> NodeChainResult:
    """顺序执行节点；任一步失败则停止。payload 在步骤间累积 `data` 字段。"""
    payload = dict(base_payload or {})
    steps: List[Dict[str, Any]] = []
    for node_name in node_names:
        if node_name not in WIZARD_GRAPH_NODE_NAMES:
            return NodeChainResult(
                ok=False,
                error="unknown_node",
                http_status_hint=400,
                failed_node=node_name,
                steps=steps,
            )
        result: NodeRunResult = run_wizard_node(profile, user, node_name, payload)
        if not result.ok:
            return NodeChainResult(
                ok=False,
                error=result.error,
                http_status_hint=result.http_status_hint,
                failed_node=node_name,
                steps=steps,
            )
        apply_node_run_to_profile(profile, result)
        profile.refresh_from_db()
        step_rec = {"node": node_name, "data": dict(result.data or {})}
        steps.append(step_rec)
        if result.data.get("assessment_id"):
            payload["assessment_id"] = result.data["assessment_id"]
    return NodeChainResult(ok=True, steps=steps)
