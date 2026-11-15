"""
G1：向导图节点 → Skill / 会话副作用（供 `POST graph/run-node/` 与可选 Celery worker）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ..models import EnglishLearningProfile
from ..wizard_flow import (
    WizardFlowResult,
    bootstrap_from_tags,
    draft_roadmap,
    finalize_roadmap,
    save_roadmap_hitl,
    score_assessment,
    start_assessment,
)
from .nodes import WIZARD_GRAPH_NODE_NAMES
from .wizard_node_handlers import apply_wizard_node

# 节点是否调用 Skill / 写库（其余节点仅更新 phase 投影）
SKILL_CAPABLE_NODES = frozenset(
    {
        "intake_tags",
        "assessment_run",
        "assessment_score",
        "roadmap_draft_skill",
        "roadmap_hitl",
        "roadmap_finalize_skill",
    }
)


@dataclass
class NodeRunResult:
    ok: bool = True
    error: str = ""
    http_status_hint: int = 400
    node: str = ""
    session_patch: Dict[str, Any] = field(default_factory=dict)
    graph_patch: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


def _noop_flow(_profile, _user, _payload) -> WizardFlowResult:
    return WizardFlowResult(ok=True, session_patch={})


def _run_placement(_profile, _user, payload: dict) -> WizardFlowResult:
    patch: Dict[str, Any] = {"phase": "intake"}
    pc = payload.get("placement_choice")
    if pc in ("quick", "full_test"):
        patch["placement_choice"] = pc
    return WizardFlowResult(ok=True, session_patch=patch)


def _run_gap_feedback(profile, _user, _payload) -> WizardFlowResult:
    st = profile.session_state or {}
    patch: Dict[str, Any] = {"phase": "roadmap"}
    if st.get("gap_summary"):
        patch["gap_summary"] = st.get("gap_summary")
    return WizardFlowResult(ok=True, session_patch=patch)


def _run_intake(profile, user, payload: dict) -> WizardFlowResult:
    if payload.get("skip_skill"):
        st = profile.session_state or {}
        if st.get("bootstrap_completed"):
            return WizardFlowResult(ok=True, session_patch={"phase": "intake"})
        return WizardFlowResult(ok=False, error="请先 bootstrap 或传 level_tags", http_status_hint=400)
    return bootstrap_from_tags(
        profile,
        user,
        level_tags=payload.get("level_tags"),
        exam_goal=payload.get("exam_goal", ""),
        weekly_minutes=int(payload.get("weekly_minutes") or 120),
    )


def _run_assessment_build(profile, user, payload: dict) -> WizardFlowResult:
    return start_assessment(
        profile,
        user,
        kind=payload.get("kind"),
        question_count=int(payload.get("question_count") or 5),
        level_target=(payload.get("level_target") or "").strip(),
        dimensions=payload.get("dimensions"),
    )


def _run_assessment_score(profile, user, payload: dict) -> WizardFlowResult:
    auto = payload.get("auto_responses") in (True, "true", "1", 1)
    return score_assessment(
        profile,
        user,
        assessment_id=payload.get("assessment_id"),
        responses=payload.get("responses"),
        auto_responses=auto,
        model=str(payload.get("model") or "deepseek-chat"),
    )


def _run_roadmap_draft(profile, user, payload: dict) -> WizardFlowResult:
    return draft_roadmap(
        profile,
        user,
        focus_dimensions=payload.get("focus_dimensions"),
        assessment_id=payload.get("assessment_id"),
        learner_note=str(payload.get("learner_note") or ""),
        model=str(payload.get("model") or "deepseek-chat"),
    )


def _run_roadmap_hitl(profile, _user, payload: dict) -> WizardFlowResult:
    return save_roadmap_hitl(
        profile,
        roadmap_markdown=str(payload.get("roadmap_markdown") or ""),
        outline_json=payload.get("outline_json"),
    )


def _run_finalize(profile, user, payload: dict) -> WizardFlowResult:
    return finalize_roadmap(
        profile,
        user,
        roadmap_markdown=payload.get("roadmap_markdown"),
        knowledge_base_id=payload.get("knowledge_base_id"),
        title=str(payload.get("title") or "我的英语学习路线"),
        revision_note=str(payload.get("revision_note") or ""),
    )


_NODE_FLOW: Dict[str, Callable[..., WizardFlowResult]] = {
    "intake_tags": _run_intake,
    "placement_or_confirm": _run_placement,
    "assessment_run": _run_assessment_build,
    "assessment_score": _run_assessment_score,
    "gap_feedback": _run_gap_feedback,
    "roadmap_draft_skill": _run_roadmap_draft,
    "roadmap_hitl": _run_roadmap_hitl,
    "roadmap_finalize_skill": _run_finalize,
    "tutor_runtime": _noop_flow,
}


def node_index(node_name: str) -> int:
    return WIZARD_GRAPH_NODE_NAMES.index(node_name)


def run_wizard_node(
    profile: EnglishLearningProfile,
    user,
    node_name: str,
    payload: Optional[dict] = None,
    *,
    run_skill: bool = True,
    sync_phase_handler: bool = True,
) -> NodeRunResult:
    """
    执行单个向导节点：
    - `run_skill=True` 时调用对应 Skill / 写库（Skill 节点）
    - `sync_phase_handler=True` 时用 `wizard_node_handlers` 对齐 phase（与 LangGraph POC 一致）
    """
    payload = dict(payload or {})
    if node_name not in WIZARD_GRAPH_NODE_NAMES:
        return NodeRunResult(
            ok=False,
            error="unknown_node",
            http_status_hint=400,
            node=node_name,
        )

    flow_fn = _NODE_FLOW.get(node_name, _noop_flow)
    session_patch: Dict[str, Any] = {}
    data: Dict[str, Any] = {}

    if run_skill:
        flow_res = flow_fn(profile, user, payload)
        if not flow_res.ok:
            return NodeRunResult(
                ok=False,
                error=flow_res.error,
                http_status_hint=flow_res.http_status_hint,
                node=node_name,
            )
        session_patch.update(flow_res.session_patch)
        data.update(flow_res.data)

    if sync_phase_handler:
        st = dict(profile.session_state or {})
        st.update(session_patch)
        wiz = apply_wizard_node(
            node_name,
            {"phase": str(st.get("phase") or "intake"), "poc_trace": list(st.get("poc_trace") or [])},
            is_last=(node_name == WIZARD_GRAPH_NODE_NAMES[-1]),
        )
        if wiz.get("phase") and (
            node_name not in SKILL_CAPABLE_NODES or "phase" not in session_patch
        ):
            session_patch["phase"] = wiz["phase"]
        graph_patch = {
            "last_executed_node": node_name,
            "poc_trace": wiz.get("poc_trace"),
        }
    else:
        graph_patch = {"last_executed_node": node_name}

    return NodeRunResult(
        ok=True,
        node=node_name,
        session_patch=session_patch,
        graph_patch=graph_patch,
        data=data,
    )


def apply_node_run_to_profile(profile: EnglishLearningProfile, result: NodeRunResult) -> None:
    """将节点执行结果写入 `session_state` 与默认 checkpoint（调用方需已认证且 profile 属当前用户）。"""
    from django.db import transaction

    from ..services import merge_session_state
    from .checkpoint_store import (
        get_or_create_default_checkpoint,
        reconcile_checkpoint_node_cursor,
        default_thread_id,
    )
    from ..models import EnglishLearningGraphCheckpoint

    if result.session_patch:
        merge_session_state(profile, result.session_patch)
    profile.refresh_from_db()

    get_or_create_default_checkpoint(profile)
    tid = default_thread_id(profile.pk)
    with transaction.atomic():
        cp = EnglishLearningGraphCheckpoint.objects.select_for_update().get(
            profile_id=profile.pk, thread_id=tid
        )
        gs = dict(cp.graph_state or {})
        gs.update(result.graph_patch or {})
        cp.graph_state = gs
        cp.node_cursor = node_index(result.node)
        cp.save(update_fields=["graph_state", "node_cursor", "updated_at"])
    reconcile_checkpoint_node_cursor(profile, cp)
