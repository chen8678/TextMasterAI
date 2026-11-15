"""
向导各步骤可复用业务逻辑（REST 视图与图节点 `run-node` 共用）。

**路径说明（G1 收敛）**：
- **生产主路径**：``POST graph/wizard/start|resume|resume/stream``（LangGraph + interrupt）。
- **本模块**：供经典 REST（``?dev=1``）与 ``graph/run-node`` 单步调试；勿在此平行实现第三套编排。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.skills.registry import SkillRegistry

from .blackboard import active_unit_id_from_outline, normalize_weak_dimensions, now_iso
from .models import AssessmentSession, EnglishLearningProfile, RoadmapRevision
from .services import merge_session_state


@dataclass
class WizardFlowResult:
    ok: bool = True
    error: str = ""
    http_status_hint: int = 400
    session_patch: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)


def bootstrap_from_tags(
    profile: EnglishLearningProfile,
    user,
    *,
    level_tags=None,
    exam_goal: str = "",
    weekly_minutes: int = 120,
) -> WizardFlowResult:
    result, err = SkillRegistry.execute_safe(
        "english_profile_from_tags",
        session_id=None,
        user=user,
        level_tags=level_tags or profile.level_tags,
        exam_goal=exam_goal,
        weekly_minutes=weekly_minutes,
        _log_retrieval_refs={"domain": "english_learning", "profile_id": str(profile.pk)},
        _log_trigger_source="english_learning:bootstrap",
    )
    if err:
        return WizardFlowResult(ok=False, error=err, http_status_hint=500)
    lc = (result or {}).get("learner_constraints") or {}
    profile.level_tags = lc.get("level_tags") or profile.level_tags
    profile.save(update_fields=["level_tags", "updated_at"])
    return WizardFlowResult(
        ok=True,
        session_patch={
            "phase": "intake",
            "learner_constraints": lc,
            "bootstrap_completed": True,
        },
        data={"skill": result},
    )


def start_assessment(
    profile: EnglishLearningProfile,
    user,
    *,
    kind: Optional[str] = None,
    question_count: int = 5,
    level_target: str = "",
    dimensions=None,
) -> WizardFlowResult:
    if kind in dict(AssessmentSession.Kind.choices):
        session_kind = kind
    else:
        session_kind = AssessmentSession.Kind.LEVEL_TEST

    if session_kind == AssessmentSession.Kind.PLACEMENT:
        question_count = min(max(1, int(question_count or 3)), 3)
    else:
        question_count = max(1, min(int(question_count or 5), 20))

    lc = (profile.session_state or {}).get("learner_constraints") or {}
    build_res, err = SkillRegistry.execute_safe(
        "english_assessment_build",
        user=user,
        learner_constraints=lc,
        question_count=question_count,
        dimensions=dimensions,
        level_target=level_target,
        _log_retrieval_refs={"domain": "english_learning", "profile_id": str(profile.pk)},
        _log_trigger_source="english_learning:assessment_build",
    )
    if err:
        return WizardFlowResult(ok=False, error=err, http_status_hint=500)

    items_scoring = build_res.get("items_scoring") or []
    session = AssessmentSession.objects.create(
        profile=profile,
        kind=session_kind,
        level_target=level_target or str(build_res.get("level_used") or ""),
        items_json=items_scoring,
        responses_json=[],
        status=AssessmentSession.Status.DRAFT,
    )
    return WizardFlowResult(
        ok=True,
        session_patch={
            "phase": "assessment",
            "active_assessment_id": str(session.id),
            "placement_choice": "quick" if session_kind == AssessmentSession.Kind.PLACEMENT else "full_test",
        },
        data={
            "assessment_id": str(session.id),
            "kind": session.kind,
            "items": build_res.get("items") or [],
            "level_used": build_res.get("level_used"),
            "count": build_res.get("count"),
        },
    )


def auto_responses_for_items(items: List[dict]) -> List[dict]:
    """测试 / 图节点演示：用题库 answer_key 自动填答。"""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        iid = it.get("id")
        if not iid:
            continue
        out.append({"item_id": str(iid), "answer": it.get("answer_key")})
    return out


def score_assessment(
    profile: EnglishLearningProfile,
    user,
    *,
    assessment_id: Optional[str] = None,
    responses: Optional[List[dict]] = None,
    auto_responses: bool = False,
    model: str = "deepseek-chat",
) -> WizardFlowResult:
    state = profile.session_state or {}
    aid = assessment_id or state.get("active_assessment_id") or state.get("last_assessment_id")
    if not aid:
        return WizardFlowResult(ok=False, error="缺少 assessment_id", http_status_hint=400)
    session = AssessmentSession.objects.filter(id=aid, profile=profile).first()
    if session is None:
        return WizardFlowResult(ok=False, error="测评会话不存在", http_status_hint=404)

    resp = list(responses or [])
    if not resp and auto_responses:
        resp = auto_responses_for_items(session.items_json or [])
    if not resp:
        return WizardFlowResult(ok=False, error="responses 须为非空数组", http_status_hint=400)

    score_res, err = SkillRegistry.execute_safe(
        "english_assessment_score",
        user=user,
        items=session.items_json,
        responses=resp,
        model=model,
        _log_retrieval_refs={
            "domain": "english_learning",
            "profile_id": str(profile.pk),
            "assessment_id": str(session.id),
        },
        _log_trigger_source="english_learning:assessment_submit",
    )
    if err:
        return WizardFlowResult(ok=False, error=err, http_status_hint=500)

    session.responses_json = resp
    session.scores_json = score_res.get("scores") or {}
    session.status = AssessmentSession.Status.SCORED
    session.save(update_fields=["responses_json", "scores_json", "status", "updated_at"])

    return WizardFlowResult(
        ok=True,
        session_patch={
            "phase": "roadmap",
            "last_scores": score_res.get("scores"),
            "gap_summary": score_res.get("gap_summary"),
            "weak_dimensions": normalize_weak_dimensions(score_res.get("weak_dimensions")),
            "last_assessment_id": str(session.id),
            "last_drill_at": now_iso(),
        },
        data={
            "assessment_id": str(session.id),
            "gap_summary": score_res.get("gap_summary"),
            "weak_dimensions": score_res.get("weak_dimensions"),
        },
    )


def draft_roadmap(
    profile: EnglishLearningProfile,
    user,
    *,
    focus_dimensions=None,
    assessment_id: Optional[str] = None,
    learner_note: str = "",
    model: str = "deepseek-chat",
) -> WizardFlowResult:
    focus_dimensions = list(focus_dimensions or [])
    state = profile.session_state or {}
    session = None
    if assessment_id:
        session = AssessmentSession.objects.filter(id=assessment_id, profile=profile).first()
    elif state.get("last_assessment_id"):
        session = AssessmentSession.objects.filter(
            id=state["last_assessment_id"], profile=profile
        ).first()

    scores = (session.scores_json if session else None) or state.get("last_scores") or {}
    gap_summary = state.get("gap_summary") or ""
    lc = dict(state.get("learner_constraints") or {})
    note = (learner_note or state.get("learner_note") or "").strip()
    if note:
        lc["learner_note"] = note

    log_refs = {"domain": "english_learning", "profile_id": str(profile.pk)}
    if session:
        log_refs["assessment_id"] = str(session.id)
    rv = state.get("roadmap_version")
    if rv is not None:
        log_refs["roadmap_version"] = rv

    draft_res, err = SkillRegistry.execute_safe(
        "english_roadmap_draft",
        user=user,
        scores=scores,
        gap_summary=gap_summary,
        focus_dimensions=focus_dimensions,
        learner_constraints=lc,
        model=model,
        _log_retrieval_refs=log_refs,
        _log_trigger_source="english_learning:roadmap_draft",
    )
    if err:
        return WizardFlowResult(ok=False, error=err, http_status_hint=500)

    md = draft_res.get("roadmap_markdown") or ""
    outline = draft_res.get("outline_json") or {}
    unit_id = active_unit_id_from_outline(outline)
    patch = {
        "phase": "roadmap_review",
        "roadmap_draft_markdown": md,
        "roadmap_outline_json": outline,
        "focus_dimensions": focus_dimensions,
        "learner_constraints": lc,
    }
    if note:
        patch["learner_note"] = note
    if unit_id:
        patch["active_unit_id"] = unit_id
    return WizardFlowResult(
        ok=True,
        session_patch=patch,
        data={"roadmap_markdown": md, "outline_json": outline},
    )


def save_roadmap_hitl(
    profile: EnglishLearningProfile,
    *,
    roadmap_markdown: str,
    outline_json: Optional[dict] = None,
) -> WizardFlowResult:
    if not isinstance(roadmap_markdown, str) or not roadmap_markdown.strip():
        return WizardFlowResult(ok=False, error="roadmap_markdown 须为非空字符串", http_status_hint=400)
    state = profile.session_state or {}
    patch: Dict[str, Any] = {
        "phase": "roadmap_review",
        "roadmap_draft_markdown": roadmap_markdown.strip(),
    }
    if isinstance(outline_json, dict) and outline_json:
        patch["roadmap_outline_json"] = outline_json
        unit_id = active_unit_id_from_outline(outline_json)
    else:
        unit_id = active_unit_id_from_outline(state.get("roadmap_outline_json"))
    if unit_id:
        patch["active_unit_id"] = unit_id
    patch["roadmap_hitl_rounds"] = int(state.get("roadmap_hitl_rounds") or 0) + 1
    return WizardFlowResult(
        ok=True,
        session_patch=patch,
        data={"roadmap_hitl_rounds": patch["roadmap_hitl_rounds"]},
    )


def finalize_roadmap(
    profile: EnglishLearningProfile,
    user,
    *,
    roadmap_markdown: Optional[str] = None,
    knowledge_base_id: Optional[str] = None,
    title: str = "我的英语学习路线",
    revision_note: str = "",
) -> WizardFlowResult:
    state = profile.session_state or {}
    md = roadmap_markdown or state.get("roadmap_draft_markdown")
    if not md or not str(md).strip():
        return WizardFlowResult(ok=False, error="缺少 roadmap_markdown", http_status_hint=400)

    kb_id = knowledge_base_id or str(profile.default_kb_id)
    last_v = (
        RoadmapRevision.objects.filter(profile=profile).order_by("-version").values_list("version", flat=True).first()
        or 0
    )
    next_version = last_v + 1

    fin_res, err = SkillRegistry.execute_safe(
        "english_roadmap_finalize",
        user=user,
        roadmap_markdown=str(md),
        kb_id=kb_id,
        title=title,
        revision_note=revision_note,
        user_id=user.id,
        _log_retrieval_refs={
            "domain": "english_learning",
            "profile_id": str(profile.pk),
            "knowledge_base_id": str(kb_id),
            "roadmap_version": next_version,
        },
        _log_trigger_source="english_learning:roadmap_finalize",
    )
    if err:
        hint = 403 if "无权写入" in err else 500
        return WizardFlowResult(ok=False, error=err, http_status_hint=hint)

    doc_id = fin_res.get("document_id")
    from apps.knowledge.models import Document
    from apps.skills.models import SkillExecutionLog

    run_log = (
        SkillExecutionLog.objects.filter(
            skill_id="english_roadmap_finalize",
            user=user,
            trigger_source="english_learning:roadmap_finalize",
            status="success",
            retrieval_refs__contains={"profile_id": str(profile.pk)},
        )
        .order_by("-created_at")
        .first()
    )
    source_run_id = (str(run_log.id)[:128]) if run_log else ""

    try:
        with transaction.atomic():
            rev = RoadmapRevision.objects.create(
                profile=profile,
                version=next_version,
                markdown=str(md),
                document_id=doc_id if doc_id else None,
                source_skill_run_id=source_run_id,
            )
            if doc_id:
                profile.active_roadmap_document = get_object_or_404(Document, id=doc_id)
                profile.save(update_fields=["active_roadmap_document", "updated_at"])
            merge_session_state(
                profile,
                {
                    "phase": "tutor",
                    "roadmap_document_id": doc_id,
                    "roadmap_version": rev.version,
                    "last_drill_at": now_iso(),
                },
            )
    except Exception as ex:
        if doc_id:
            Document.objects.filter(pk=doc_id, knowledge_base__owner=user).delete()
        return WizardFlowResult(
            ok=False,
            error=f"finalize_persist_failed: {ex}",
            http_status_hint=500,
            data={"document_id": doc_id},
        )

    profile.refresh_from_db()
    return WizardFlowResult(
        ok=True,
        session_patch={},
        data={
            "document_id": doc_id,
            "knowledge_base_id": fin_res.get("knowledge_base_id"),
            "revision_version": next_version,
            "session_state_version": int((profile.session_state or {}).get("_merge_version") or 0),
        },
    )
