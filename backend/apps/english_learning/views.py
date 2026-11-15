from typing import Any, Dict, Optional

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .graph.checkpoint_store import (
    default_thread_id,
    get_or_create_default_checkpoint,
    reconcile_checkpoint_node_cursor,
    sync_graph_projection_into_profile_session,
)
from .graph.nodes import WIZARD_GRAPH_NODE_NAMES
from .graph.runner import status_payload as graph_status_payload
from .models import AssessmentSession, EnglishLearningGraphCheckpoint, RoadmapRevision
from .serializers import AssessmentSessionSerializer, EnglishLearningProfileSerializer, RoadmapRevisionSerializer
from .services import get_or_create_profile, merge_session_state, SessionStateVersionConflict
from apps.skills.registry import SkillRegistry

from .blackboard import (
    build_today_tasks,
    is_proactive_reminder_suppressed,
    normalize_weak_dimensions,
    now_iso,
    reminder_prefs_from_state,
)
from .wizard_flow import (
    WizardFlowResult,
    bootstrap_from_tags,
    draft_roadmap,
    finalize_roadmap,
    save_roadmap_hitl,
    score_assessment,
    start_assessment,
)


def _profile_for(request):
    return get_or_create_profile(request.user)


def _recommended_curriculum_kb_id(profile):
    try:
        from .curriculum.services import get_recommended_curriculum_kb

        kb = get_recommended_curriculum_kb(profile.user, level_tags=profile.level_tags)
        return str(kb.id) if kb else None
    except Exception:
        return None


def _flow_error_response(flow: WizardFlowResult):
    return Response({"error": flow.error}, status=flow.http_status_hint)


def _guard_input(request, text: str, channel: str):
    from apps.system.content_safety.guards import require_safe_user_text

    return require_safe_user_text(request, text, channel=channel)


def _guard_wizard_payload(request, payload: dict):
    from apps.system.content_safety.guards import require_safe_user_text, require_safe_user_texts

    if not isinstance(payload, dict):
        return None
    exam = payload.get("exam_goal")
    if exam and str(exam).strip():
        blocked = require_safe_user_text(request, str(exam), channel="english_wizard")
        if blocked is not None:
            return blocked
    rm = payload.get("roadmap_markdown")
    if rm and str(rm).strip():
        blocked = require_safe_user_text(request, str(rm), channel="english_roadmap")
        if blocked is not None:
            return blocked
    responses = payload.get("responses")
    if isinstance(responses, list):
        texts = []
        for item in responses:
            if isinstance(item, dict):
                for key in ("answer", "response", "text", "value"):
                    if item.get(key):
                        texts.append(str(item[key]))
            elif item is not None:
                texts.append(str(item))
        if texts:
            blocked = require_safe_user_texts(request, texts, channel="english_assessment")
            if blocked is not None:
                return blocked
    return None


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    profile = _profile_for(request)
    if request.method == "PATCH":
        level_tags = request.data.get("level_tags")
        if level_tags is not None:
            profile.level_tags = level_tags
            profile.save(update_fields=["level_tags", "updated_at"])
        patch_state = request.data.get("session_state")
        if isinstance(patch_state, dict):
            patch_state = {k: v for k, v in patch_state.items() if k != "_merge_version"}
            draft_md = patch_state.get("roadmap_draft_markdown")
            if draft_md is not None and str(draft_md).strip():
                blocked = _guard_input(request, str(draft_md), "english_roadmap")
                if blocked is not None:
                    return blocked
            raw_ver = request.data.get("session_state_version")
            expect_ver = None
            if raw_ver is not None:
                try:
                    expect_ver = int(raw_ver)
                except (TypeError, ValueError):
                    expect_ver = None
            try:
                merge_session_state(profile, patch_state, expect_version=expect_ver)
            except SessionStateVersionConflict as ex:
                return Response(
                    {
                        "error": "session_state_version_conflict",
                        "session_state_version": ex.current_version,
                        "detail": "session_state 已被他处更新，请刷新后重试。",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        profile.refresh_from_db()
    return Response(EnglishLearningProfileSerializer(profile).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_bootstrap(request):
    """创建档案与默认知识库，并可附带标签跑 english_profile_from_tags。

    **Dev fallback**：生产向导主路径为 ``POST graph/wizard/start``；本接口供 ``?dev=1`` 经典 REST 模式。
    """
    profile = _profile_for(request)
    exam_goal = str(request.data.get("exam_goal") or "")
    blocked = _guard_input(request, exam_goal, "english_bootstrap")
    if blocked is not None:
        return blocked
    flow = bootstrap_from_tags(
        profile,
        request.user,
        level_tags=request.data.get("level_tags") or profile.level_tags,
        exam_goal=exam_goal,
        weekly_minutes=int(request.data.get("weekly_minutes") or 120),
    )
    if not flow.ok:
        return _flow_error_response(flow)
    merge_session_state(profile, flow.session_patch)
    profile.refresh_from_db()
    return Response(
        {
            "profile": EnglishLearningProfileSerializer(profile).data,
            "skill": flow.data.get("skill"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assessment_start(request):
    """开始测评组卷（经典 REST）。生产主路径：``POST graph/wizard/resume`` 或 ``resume/stream``。"""
    profile = _profile_for(request)
    kind_raw = request.data.get("kind")
    kind = kind_raw if kind_raw in dict(AssessmentSession.Kind.choices) else AssessmentSession.Kind.LEVEL_TEST
    flow = start_assessment(
        profile,
        request.user,
        kind=kind,
        question_count=int(request.data.get("question_count") or 5),
        level_target=(request.data.get("level_target") or "").strip(),
        dimensions=request.data.get("dimensions"),
    )
    if not flow.ok:
        return _flow_error_response(flow)
    merge_session_state(profile, flow.session_patch)
    return Response(flow.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def assessment_submit(request, assessment_id):
    profile = _profile_for(request)
    get_object_or_404(AssessmentSession, id=assessment_id, profile=profile)
    responses = request.data.get("responses")
    if not isinstance(responses, list):
        return Response({"error": "responses 须为非空数组"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.system.content_safety.guards import require_safe_user_texts

    answer_texts = []
    for item in responses:
        if isinstance(item, dict):
            for key in ("answer", "response", "text", "value"):
                if item.get(key):
                    answer_texts.append(str(item[key]))
        elif item is not None:
            answer_texts.append(str(item))
    blocked = require_safe_user_texts(request, answer_texts, channel="english_assessment")
    if blocked is not None:
        return blocked

    flow = score_assessment(
        profile,
        request.user,
        assessment_id=str(assessment_id),
        responses=responses,
        model=str(request.data.get("model") or "deepseek-chat"),
    )
    if not flow.ok:
        return _flow_error_response(flow)
    merge_session_state(profile, flow.session_patch)
    session = AssessmentSession.objects.get(id=assessment_id, profile=profile)
    return Response(
        {
            "assessment": AssessmentSessionSerializer(session).data,
            "gap_summary": flow.data.get("gap_summary"),
            "weak_dimensions": flow.data.get("weak_dimensions"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def roadmap_draft(request):
    profile = _profile_for(request)
    flow = draft_roadmap(
        profile,
        request.user,
        focus_dimensions=request.data.get("focus_dimensions") or [],
        assessment_id=request.data.get("assessment_id"),
        learner_note=str(request.data.get("learner_note") or ""),
        model=str(request.data.get("model") or "deepseek-chat"),
    )
    if not flow.ok:
        return _flow_error_response(flow)
    merge_session_state(profile, flow.session_patch)
    md = flow.data.get("roadmap_markdown") or ""
    from apps.system.content_safety.guards import apply_markdown_output_safety

    safe_md, _ = apply_markdown_output_safety(
        str(md),
        channel="english_roadmap_draft",
        user=request.user,
        request=request,
    )
    return Response(
        {
            "roadmap_markdown": safe_md,
            "outline_json": flow.data.get("outline_json"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def roadmap_save_draft(request):
    """路线 HITL：将用户编辑的 Markdown/大纲写回 session_state（不调用 LLM），可多次保存。"""
    profile = _profile_for(request)
    roadmap_md = str(request.data.get("roadmap_markdown") or "")
    blocked = _guard_input(request, roadmap_md, "english_roadmap")
    if blocked is not None:
        return blocked
    flow = save_roadmap_hitl(
        profile,
        roadmap_markdown=roadmap_md,
        outline_json=request.data.get("outline_json"),
    )
    if not flow.ok:
        return _flow_error_response(flow)

    raw_ver = request.data.get("session_state_version")
    expect_ver = None
    if raw_ver is not None:
        try:
            expect_ver = int(raw_ver)
        except (TypeError, ValueError):
            expect_ver = None
    try:
        merge_session_state(profile, flow.session_patch, expect_version=expect_ver)
    except SessionStateVersionConflict as ex:
        return Response(
            {
                "error": "session_state_version_conflict",
                "session_state_version": ex.current_version,
                "detail": "session_state 已被他处更新，请刷新后重试。",
            },
            status=status.HTTP_409_CONFLICT,
        )

    profile.refresh_from_db()
    ver = int((profile.session_state or {}).get("_merge_version") or 0)
    return Response(
        {
            "ok": True,
            "roadmap_hitl_rounds": flow.data.get("roadmap_hitl_rounds"),
            "session_state_version": ver,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def roadmap_revisions_list(request):
    """当前用户 Profile 下的路线修订历史（审计）；默认最多 50 条，可用 `?limit=` 指定 1–100。"""
    profile = _profile_for(request)
    raw_limit = request.query_params.get("limit")
    try:
        n = min(max(int(raw_limit), 1), 100) if raw_limit is not None else 50
    except (TypeError, ValueError):
        n = 50
    qs = (
        RoadmapRevision.objects.filter(profile=profile)
        .select_related("document")
        .order_by("-version", "-created_at")[:n]
    )
    return Response(RoadmapRevisionSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def roadmap_finalize(request):
    profile = _profile_for(request)
    raw_ver = request.data.get("session_state_version")
    expect_ver = None
    if raw_ver is not None:
        try:
            expect_ver = int(raw_ver)
        except (TypeError, ValueError):
            expect_ver = None

    md = request.data.get("roadmap_markdown")
    if not md or not str(md).strip():
        state = profile.session_state or {}
        md = state.get("roadmap_draft_markdown")
    if not md or not str(md).strip():
        return Response({"error": "缺少 roadmap_markdown"}, status=status.HTTP_400_BAD_REQUEST)

    blocked = _guard_input(request, str(md), "english_roadmap")
    if blocked is not None:
        return blocked

    if expect_ver is not None:
        cur = int((profile.session_state or {}).get("_merge_version") or 0)
        if expect_ver != cur:
            return Response(
                {
                    "error": "session_state_version_conflict",
                    "session_state_version": cur,
                    "detail": "session_state 已被他处更新，请刷新后再定稿。",
                },
                status=status.HTTP_409_CONFLICT,
            )

    flow = finalize_roadmap(
        profile,
        request.user,
        roadmap_markdown=str(md),
        knowledge_base_id=request.data.get("knowledge_base_id"),
        title=str(request.data.get("title") or "我的英语学习路线"),
        revision_note=str(request.data.get("revision_note") or ""),
    )
    if not flow.ok:
        body = {"error": flow.error}
        if flow.data.get("document_id"):
            body["document_id"] = flow.data["document_id"]
        if "finalize_persist_failed" in flow.error:
            body["error"] = "finalize_persist_failed"
            body["detail"] = flow.error.split(": ", 1)[-1]
        return Response(body, status=flow.http_status_hint)

    profile.refresh_from_db()
    return Response(flow.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def curriculum_libraries(request):
    """系统预置英语词库列表 + 按 level_tags 推荐 KB（用户无需上传教材）。"""
    profile = _profile_for(request)
    from .curriculum.services import curriculum_payload_for_user

    payload = curriculum_payload_for_user(profile.user, level_tags=profile.level_tags)
    payload["personal_kb_id"] = str(profile.default_kb_id) if profile.default_kb_id else None
    payload["note"] = "personal_kb 仅用于个人学习路线定稿；教材内容请使用 libraries 中的系统预置库"
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def today_suggestions(request):
    """MVP-B：规则型「今日任务」建议（读 session_state / 黑板）；打开页时刷新 last_wizard_open_at。"""
    profile = _profile_for(request)
    merge_session_state(profile, {"last_wizard_open_at": now_iso()})
    profile.refresh_from_db()
    st = profile.session_state or {}
    blackboard = {
        "active_unit_id": st.get("active_unit_id") or "",
        "last_drill_at": st.get("last_drill_at") or "",
        "weak_dimensions": normalize_weak_dimensions(st.get("weak_dimensions")),
        "last_wizard_open_at": st.get("last_wizard_open_at") or "",
    }
    tasks = build_today_tasks(st)
    reminder_prefs = reminder_prefs_from_state(st)

    recall_pack = None
    pack_q = (request.query_params.get("pack") or "1").strip().lower()
    recall_ok = (
        pack_q not in ("0", "false", "no")
        and str(st.get("phase") or "").lower() == "tutor"
        and not is_proactive_reminder_suppressed(st)
        and reminder_prefs.get("intensity") != "low"
    )
    if recall_ok:
        weak = normalize_weak_dimensions(st.get("weak_dimensions"))
        gap = st.get("gap_summary") or ""
        if weak or (isinstance(gap, str) and gap.strip()):
            res, err = SkillRegistry.execute_safe(
                "english_active_recall_pack",
                session_id=None,
                user=request.user,
                weak_dimensions=weak,
                learner_constraints=st.get("learner_constraints") or {},
                active_unit_id=st.get("active_unit_id") or "",
                gap_summary=str(gap)[:2000],
                _log_retrieval_refs={
                    "domain": "english_learning",
                    "profile_id": str(profile.pk),
                    "phase": str(st.get("phase") or ""),
                },
                _log_trigger_source="english_learning:today_recall",
            )
            if not err and res:
                recall_pack = res

    return Response(
        {
            "phase": st.get("phase") or "intake",
            "blackboard": blackboard,
            "tasks": tasks,
            "recall_pack": recall_pack,
            "reminder_prefs": reminder_prefs,
            "profile_id": str(profile.pk),
            "default_kb_id": str(profile.default_kb_id) if profile.default_kb_id else None,
            "recommended_curriculum_kb_id": _recommended_curriculum_kb_id(profile),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def graph_status(request):
    """Phase-C：返回默认 `thread_id` 下图 checkpoint 与占位节点游标（G1/G2）。"""
    profile = _profile_for(request)
    return Response(graph_status_payload(profile))


def _langgraph_not_installed_response():
    return Response(
        {
            "error": "langgraph_not_installed",
            "detail": "请在后端环境安装: pip install 'langgraph>=0.2,<0.3'",
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_langgraph_sync(request):
    """G1：按当前 `session_state.phase` 推进 LangGraph POC 直至与占位游标对齐（不修改 phase）。"""
    from .graph import langgraph_poc
    from .graph.langgraph_sync import sync_langgraph_poc_to_session_phase

    if not langgraph_poc.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    try:
        summary = sync_langgraph_poc_to_session_phase(profile)
    except Exception as ex:
        return Response(
            {"error": "langgraph_sync_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    payload["langgraph_sync"] = summary
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_langgraph_poc_step(request):
    """G1：跑完整 LangGraph POC 链，并写入 checkpoint `graph_state.langgraph_poc_*`（需安装 langgraph）。"""
    from .graph import langgraph_poc

    if not langgraph_poc.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    tid = default_thread_id(profile.pk)
    st = profile.session_state or {}
    initial = {"phase": str(st.get("phase") or "intake"), "poc_trace": []}
    try:
        out, tip = langgraph_poc.invoke_english_graph_poc(thread_id=tid, initial=initial)
    except Exception as ex:
        return Response(
            {"error": "langgraph_invoke_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    from .graph.langgraph_sync import persist_langgraph_poc_observability

    persist_langgraph_poc_observability(
        profile, thread_id=tid, out=out, tip=tip, create_checkpoint=True
    )
    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    payload["langgraph_poc"] = out
    payload["langgraph_poc_completed"] = True
    if tip is not None:
        payload["langgraph_checkpoint_tip"] = tip
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_langgraph_advance_step(request):
    """G1：单步推进 LangGraph POC（每节点 interrupt 一次），并同步 Django `node_cursor`。"""
    from .graph import langgraph_poc

    if not langgraph_poc.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    tid = default_thread_id(profile.pk)
    st = profile.session_state or {}
    initial = {"phase": str(st.get("phase") or "intake"), "poc_trace": []}
    try:
        out, tip, completed, next_nodes = langgraph_poc.advance_english_graph_poc_step(
            thread_id=tid,
            initial=initial,
        )
    except Exception as ex:
        return Response(
            {"error": "langgraph_advance_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    from .graph.langgraph_sync import persist_langgraph_poc_observability

    persist_langgraph_poc_observability(
        profile, thread_id=tid, out=out, tip=tip, create_checkpoint=True
    )

    node_run_payload = None
    run_skill = request.data.get("run_skill") in (True, "true", "1", 1)
    if run_skill:
        tr = list(out.get("poc_trace") or [])
        if tr:
            from .graph.node_executors import apply_node_run_to_profile, run_wizard_node

            nr = run_wizard_node(profile, request.user, tr[-1], request.data)
            if nr.ok:
                apply_node_run_to_profile(profile, nr)
                node_run_payload = {"node": nr.node, "data": nr.data}
            else:
                node_run_payload = {"node": nr.node, "error": nr.error}

    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    payload["langgraph_poc"] = out
    payload["langgraph_poc_completed"] = completed
    payload["langgraph_poc_next"] = next_nodes
    if node_run_payload is not None:
        payload["node_run"] = node_run_payload
    if tip is not None:
        payload["langgraph_checkpoint_tip"] = tip
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_run_node(request):
    """
    G1：按节点名执行 Skill / 会话副作用，并更新 checkpoint 游标。
    可选 `async=true` 入队 Celery（`english_graph_run_node`）。
    """
    profile = _profile_for(request)
    body = request.data if isinstance(request.data, dict) else {}
    node_name = (body.get("node") or "").strip()
    if not node_name:
        return Response({"error": "node_required"}, status=status.HTTP_400_BAD_REQUEST)

    run_skill = body.get("run_skill", True)
    if isinstance(run_skill, str):
        run_skill = run_skill.strip().lower() not in ("0", "false", "no", "off")

    use_async = body.get("async") in (True, "true", "1", 1)
    if use_async:
        from .tasks import english_graph_run_node_task

        async_result = english_graph_run_node_task.delay(
            str(profile.pk),
            request.user.pk,
            node_name,
            {k: v for k, v in body.items() if k not in ("async", "node")},
        )
        return Response(
            {
                "queued": True,
                "task_id": str(async_result.id),
                "node": node_name,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    from .graph.node_executors import apply_node_run_to_profile, run_wizard_node

    result = run_wizard_node(
        profile,
        request.user,
        node_name,
        body,
        run_skill=bool(run_skill),
    )
    if not result.ok:
        return Response(
            {"error": result.error, "node": node_name},
            status=result.http_status_hint,
        )
    apply_node_run_to_profile(profile, result)
    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    payload["node_run"] = {"node": result.node, "data": result.data}
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_run_chain(request):
    """
    G1：按序执行多个向导节点。body.nodes 缺省时使用 smoke 预设链。
    常用参数：level_tags、question_count、auto_responses、focus_dimensions。
    """
    from .graph.node_chain import DEFAULT_SMOKE_CHAIN, run_wizard_node_chain

    profile = _profile_for(request)
    body = request.data if isinstance(request.data, dict) else {}
    nodes = body.get("nodes")
    if nodes is None:
        node_names = list(DEFAULT_SMOKE_CHAIN)
    elif isinstance(nodes, list) and nodes:
        node_names = [str(n).strip() for n in nodes]
    else:
        return Response({"error": "nodes_must_be_non_empty_list"}, status=status.HTTP_400_BAD_REQUEST)

    payload = {k: v for k, v in body.items() if k != "nodes"}
    payload.setdefault("auto_responses", True)
    payload.setdefault("placement_choice", "full_test")

    chain = run_wizard_node_chain(profile, request.user, node_names, payload)
    if not chain.ok:
        return Response(
            {
                "error": chain.error,
                "failed_node": chain.failed_node,
                "steps": chain.steps,
            },
            status=chain.http_status_hint,
        )
    profile.refresh_from_db()
    out = dict(graph_status_payload(profile))
    out["chain"] = {"steps": chain.steps, "phase": (profile.session_state or {}).get("phase")}
    return Response(out)


def _wizard_graph_response(profile, run_result: dict) -> dict:
    from .graph.wizard_sse import build_wizard_graph_payload

    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    vals = run_result.get("values") or {}
    payload["wizard_graph"] = build_wizard_graph_payload(
        vals,
        completed=bool(run_result.get("completed")),
        interrupted=bool(run_result.get("interrupted")),
        next_nodes=run_result.get("next_nodes") or [],
        failed=bool(run_result.get("failed")),
    )
    if run_result.get("tip") is not None:
        payload["langgraph_checkpoint_tip"] = run_result["tip"]
    return payload


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_wizard_start(request):
    """
    G1：启动生产向导 LangGraph（Skill 节点 + interrupt），从 intake 跑到首个人机暂停或结束。
    body 作为首段 `node_payload`（如 level_tags、exam_goal）。
    """
    from .graph import langgraph_wizard

    if not langgraph_wizard.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    tid = default_thread_id(profile.pk)
    body = request.data if isinstance(request.data, dict) else {}
    payload = {k: v for k, v in body.items() if k not in ("async",)}
    blocked = _guard_wizard_payload(request, payload)
    if blocked is not None:
        return blocked

    try:
        run_result = langgraph_wizard.run_wizard_graph_until_pause(
            thread_id=tid,
            profile_id=profile.pk,
            user_id=request.user.pk,
            initial_payload=payload,
        )
    except Exception as ex:
        return Response(
            {"error": "wizard_graph_start_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    langgraph_wizard.persist_wizard_graph_to_django(
        profile, thread_id=tid, values=run_result.get("values") or {}, tip=run_result.get("tip")
    )
    return Response(_wizard_graph_response(profile, run_result))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_wizard_resume(request):
    """
    G1：恢复向导图。body 合并进 `node_payload` 后继续执行至下一 interrupt 或结束。
    测评暂停后传 `responses` 或 `auto_responses`；路线暂停后可传 `roadmap_markdown`。

    **异步（D1）**：body 传 ``async=true`` 时入队 Celery ``english_graph_wizard_resume_task``，
    返回 202 + ``task_id``（需 ``CELERY_TASK_ALWAYS_EAGER=false`` 与 Redis broker，见 ``docker-compose.celery.yml``）。
    前端主路径推荐 **SSE** ``graph/wizard/resume/stream/``（同步 HTTP，边执行边推送进度）。
    """
    from .graph import langgraph_wizard

    if not langgraph_wizard.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    tid = default_thread_id(profile.pk)
    body = request.data if isinstance(request.data, dict) else {}

    use_async = body.get("async") in (True, "true", "1", 1)
    resume_payload = {k: v for k, v in body.items() if k not in ("async",)}
    blocked = _guard_wizard_payload(request, resume_payload)
    if blocked is not None:
        return blocked

    if use_async:
        from .tasks import english_graph_wizard_resume_task

        async_result = english_graph_wizard_resume_task.delay(
            str(profile.pk),
            request.user.pk,
            resume_payload,
        )
        return Response(
            {"queued": True, "task_id": str(async_result.id)},
            status=status.HTTP_202_ACCEPTED,
        )

    try:
        run_result = langgraph_wizard.run_wizard_graph_until_pause(
            thread_id=tid,
            profile_id=profile.pk,
            user_id=request.user.pk,
            resume_payload=resume_payload,
        )
    except Exception as ex:
        return Response(
            {"error": "wizard_graph_resume_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    langgraph_wizard.persist_wizard_graph_to_django(
        profile, thread_id=tid, values=run_result.get("values") or {}, tip=run_result.get("tip")
    )
    return Response(_wizard_graph_response(profile, run_result))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_wizard_resume_stream(request):
    """
    G3：SSE 流式 resume（**生产主路径**）。推送 `node_done` / `token` / `interrupt` / `end`；
    路线生成等长耗时步骤可展示进度。body 同 `graph/wizard/resume/`（**不支持** `async=true`，异步请用 sync resume + Celery）。
    """
    import json

    from django.http import StreamingHttpResponse

    from .graph import langgraph_wizard
    from .graph.wizard_sse import format_sse_events, iter_wizard_resume_events

    if not langgraph_wizard.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    profile.refresh_from_db()
    tid = default_thread_id(profile.pk)
    body = request.data if isinstance(request.data, dict) else {}
    resume_payload = {k: v for k, v in body.items() if k not in ("async", "stream")}
    blocked = _guard_wizard_payload(request, resume_payload)
    if blocked is not None:
        return blocked

    def event_stream():
        try:
            gen = iter_wizard_resume_events(
                profile,
                request.user,
                thread_id=tid,
                resume_payload=resume_payload,
            )
            yield from format_sse_events(gen)
        except Exception as ex:
            err = {"type": "error", "error": str(ex)[:500]}
            yield f"event: error\ndata: {json.dumps(err, ensure_ascii=False)}\n\n"

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def graph_langgraph_history(request):
    """G1：只读列出当前用户默认 thread 在 LangGraph checkpointer（SQLite 或内存）中的最近 checkpoint 摘要。"""
    from .graph import langgraph_poc

    if not langgraph_poc.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    tid = default_thread_id(profile.pk)
    raw = (request.query_params.get("limit") or "20").strip()
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = 20
    limit = min(max(limit, 1), 50)

    summaries = langgraph_poc.list_langgraph_checkpoint_summaries(thread_id=tid, limit=limit)
    tip = langgraph_poc.read_langgraph_checkpoint_tip(thread_id=tid)
    return Response(
        {
            "thread_id": tid,
            "limit": limit,
            "summaries": summaries,
            "tip": tip,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_langgraph_reset(request):
    """G1：清空当前用户默认 thread 在 LangGraph checkpointer 中的记录，并移除 Django checkpoint 内 POC 观测字段。"""
    from .graph import langgraph_poc

    if not langgraph_poc.LANGGRAPH_AVAILABLE:
        return _langgraph_not_installed_response()

    profile = _profile_for(request)
    tid = default_thread_id(profile.pk)
    try:
        langgraph_poc.delete_langgraph_poc_thread(thread_id=tid)
    except Exception as ex:
        return Response(
            {"error": "langgraph_reset_failed", "detail": str(ex)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    get_or_create_default_checkpoint(profile)
    with transaction.atomic():
        cp = EnglishLearningGraphCheckpoint.objects.select_for_update().get(
            profile_id=profile.pk,
            thread_id=tid,
        )
        gs = dict(cp.graph_state or {})
        for k in ("langgraph_poc_phase", "langgraph_poc_trace", "langgraph_checkpoint_tip"):
            gs.pop(k, None)
        cp.graph_state = gs
        cp.save(update_fields=["graph_state", "updated_at"])

    sync_graph_projection_into_profile_session(profile)
    profile.refresh_from_db()
    payload = dict(graph_status_payload(profile))
    payload["langgraph_reset"] = True
    return Response(payload)


def _truthy_merge_flag(raw) -> bool:
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("0", "false", "no", "off"):
            return False
        if s in ("1", "true", "yes", "on"):
            return True
        return True
    return True


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def graph_save_checkpoint(request):
    """合并或替换 `graph_state`；可选更新 `node_cursor`（默认线程）。供 Worker / 调试。"""
    profile = _profile_for(request)
    profile.refresh_from_db()
    body = request.data if isinstance(request.data, dict) else {}
    patch = body.get("graph_state")
    if not isinstance(patch, dict):
        return Response({"error": "graph_state_object_required"}, status=status.HTTP_400_BAD_REQUEST)
    merge = _truthy_merge_flag(body.get("merge"))

    node_cursor = None
    if "node_cursor" in body and body["node_cursor"] is not None:
        try:
            node_cursor = int(body["node_cursor"])
        except (TypeError, ValueError):
            return Response({"error": "node_cursor_invalid"}, status=status.HTTP_400_BAD_REQUEST)
        n = len(WIZARD_GRAPH_NODE_NAMES)
        if node_cursor < 0 or node_cursor >= n:
            return Response({"error": "node_cursor_out_of_range"}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        get_or_create_default_checkpoint(profile)
        tid = default_thread_id(profile.pk)
        cp = EnglishLearningGraphCheckpoint.objects.select_for_update().get(
            profile_id=profile.pk,
            thread_id=tid,
        )
        if merge:
            new_gs = {**(cp.graph_state or {}), **patch}
        else:
            new_gs = dict(patch)
        cp.graph_state = new_gs
        fields = ["graph_state", "updated_at"]
        if node_cursor is not None:
            cp.node_cursor = node_cursor
            fields = ["graph_state", "node_cursor", "updated_at"]
        cp.save(update_fields=fields)
        if node_cursor is None:
            profile.refresh_from_db()
            reconcile_checkpoint_node_cursor(profile, cp)

        sync_graph_projection_into_profile_session(profile)

    profile.refresh_from_db()
    return Response(graph_status_payload(profile))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def drill_touch(request):
    """用户标记「今日巩固」完成，刷新 last_drill_at（免打扰等可后续扩展）。"""
    profile = _profile_for(request)
    merge_session_state(profile, {"last_drill_at": now_iso()})
    profile.refresh_from_db()
    return Response({"ok": True, "last_drill_at": (profile.session_state or {}).get("last_drill_at")})
