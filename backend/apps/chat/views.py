from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import QARecord, ChatSession, StudioDraft, StudioDraftRevision
from .services import QAService
from .agent_service import AgentOrchestrator, get_orchestrator_by_tier
from .ai_services import AIModel, AIServiceFactory
from .api_config_service import APIConfigService
from ai_qa_system.ai_config import AIConfig
from django.conf import settings
from .serializers import (
    QARecordSerializer,
    ChatSessionSerializer,
    ChatSessionListSerializer,
    StudioDraftSerializer,
    StudioDraftRevisionListSerializer,
    StudioDraftRevisionDetailSerializer,
)
from django.utils import timezone
from django.http import StreamingHttpResponse
from django.core.cache import cache
import json
from apps.agents.models import Agent
from apps.skills.evolution import schedule_evolution_after_user_turn
from apps.agents.evolution import schedule_agent_evolution_after_turn
from apps.auth.permissions import IsProUser
import logging
from apps.system.throttles import AskQuestionRateThrottle

logger = logging.getLogger(__name__)
AGENTS_LIST_CACHE_TTL_SECONDS = 120

MAX_STUDIO_DRAFT_REVISIONS = 50


def _trim_studio_draft_revisions(draft: StudioDraft, keep: int = MAX_STUDIO_DRAFT_REVISIONS) -> None:
    qs = StudioDraftRevision.objects.filter(draft=draft).order_by("-revision_index")
    pks = list(qs.values_list("pk", flat=True))
    if len(pks) <= keep:
        return
    to_drop = pks[keep:]
    if to_drop:
        StudioDraftRevision.objects.filter(pk__in=to_drop).delete()


def _normalize_references(raw_refs):
    """规范化前端传入 references，仅保留 draft/kb。"""
    if not isinstance(raw_refs, list):
        return []
    out = []
    for r in raw_refs[:20]:
        if not isinstance(r, dict):
            continue
        t = str(r.get("type") or "").strip().lower()
        if t not in {"draft", "kb"}:
            continue
        rid = str(r.get("id") or "").strip()
        label = str(r.get("label") or "").strip()
        if not rid:
            continue
        out.append({"type": t, "id": rid, "label": label})
    return out


# MVP-B：主编排下由前端或调用方指定专项子 Agent（仅改写实际编排用的 agent_id）
from apps.chat.english_intent_routing import (
    ENGLISH_DELEGATE_TO_AGENT as _ENGLISH_DELEGATE_TO_AGENT,
    is_auto_delegate_value,
    resolve_english_delegate_auto,
)


def _build_reference_hint(references):
    """把 references 压缩成提示前缀，注入问题供编排器感知。"""
    if not references:
        return ""
    parts = []
    for r in references:
        name = r.get("label") or r.get("id") or ""
        parts.append(f"{r.get('type')}:{name}")
    return " [refs:" + " | ".join(parts) + "]"


def _prepare_ask_from_request(request):
    """
    解析并校验问答请求，创建/复用会话，准备检索参数与进化路径。
    成功返回 (ctx, None)，失败返回 (None, Response)。
    """
    question = request.data.get("question")
    knowledge_base_id = request.data.get("knowledge_base_id")
    session_id = request.data.get("session_id")
    model_name = request.data.get("model", "deepseek")
    agent_id = request.data.get("agent_id", "qa")
    english_delegate = (request.data.get("english_delegate") or "").strip().lower()
    english_intent = {"slot": None, "source": "none"}
    scene = (request.data.get("mode") or "").strip().lower()
    references = _normalize_references(request.data.get("references"))
    use_agent = request.data.get("use_agent", True)
    english_phase = (request.data.get("english_phase") or "").strip().lower()
    english_profile_id = request.data.get("english_profile_id")
    if english_profile_id not in (None, ""):
        english_profile_id = str(english_profile_id).strip() or None
    else:
        english_profile_id = None

    if english_phase:
        from apps.chat.english_learning_context import VALID_ENGLISH_PHASES

        if english_phase not in VALID_ENGLISH_PHASES:
            return None, Response(
                {"error": f"不支持的 english_phase: {english_phase}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if english_delegate and not is_auto_delegate_value(english_delegate):
        if agent_id != "english_orchestrator":
            return None, Response(
                {"error": "english_delegate 仅可与 agent_id=english_orchestrator 同时使用"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mapped = _ENGLISH_DELEGATE_TO_AGENT.get(english_delegate)
        if not mapped:
            return None, Response(
                {"error": f"不支持的 english_delegate: {english_delegate}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        agent_id = mapped
        english_intent = {"slot": english_delegate, "source": "explicit"}

    if scene and scene not in {"novel", "paper", "contract"}:
        return None, Response({"error": f"不支持的模式: {scene}"}, status=status.HTTP_400_BAD_REQUEST)

    strategy = request.data.get("strategy", "hybrid")
    top_k = request.data.get("top_k", 5)
    score_threshold = request.data.get("score_threshold", 0.15)
    alpha = request.data.get("alpha", 0.5)
    auxiliary_knowledge_base_ids = request.data.get("auxiliary_knowledge_base_ids")

    if not question or not knowledge_base_id:
        return None, Response({"error": "缺少必要字段"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.system.content_safety.guards import require_safe_user_text
    from apps.system.embed_hooks import apply_ask_text_transformers

    blocked = require_safe_user_text(request, str(question), channel="chat")
    if blocked is not None:
        return None, blocked

    question = apply_ask_text_transformers(
        request,
        str(question),
        {"channel": "chat", "agent_id": agent_id, "knowledge_base_id": knowledge_base_id},
    )

    model_mapping = {
        "deepseek": "deepseek-chat",
        "qwen": "qwen-turbo",
        "glm": "glm-4",
    }
    if model_name in model_mapping:
        model_name = model_mapping[model_name]

    valid_models = [
        "deepseek-chat",
        "deepseek-coder",
        "deepseek-reasoner",
        "deepseek-v3",
        "qwen-max",
        "qwen-plus",
        "qwen-turbo",
        "qwen-long",
        "glm-4",
        "glm-4v",
        "glm-3-turbo",
        "cogview-3",
    ]

    if model_name not in valid_models:
        return None, Response({"error": f"不支持的模型: {model_name}"}, status=status.HTTP_400_BAD_REQUEST)

    if (
        agent_id == "english_orchestrator"
        and is_auto_delegate_value(english_delegate)
    ):
        resolved = resolve_english_delegate_auto(question or "", model=model_name)
        if resolved.get("agent_id"):
            agent_id = resolved["agent_id"]
        english_intent = {
            "slot": resolved.get("slot"),
            "source": resolved.get("source") or "none",
        }

    if session_id:
        try:
            session = ChatSession.objects.get(id=session_id, user=request.user, is_active=True)
        except ChatSession.DoesNotExist:
            return None, Response({"error": "会话不存在或已失效"}, status=status.HTTP_404_NOT_FOUND)
    else:
        session = ChatSession.objects.create(
            user=request.user,
            knowledge_base_id=knowledge_base_id,
            title=question[:50] + "..." if len(question) > 50 else question,
        )

    try:
        top_k = min(20, max(1, int(top_k)))
    except (TypeError, ValueError):
        top_k = 5
    try:
        score_threshold = min(1.0, max(0.0, float(score_threshold)))
    except (TypeError, ValueError):
        score_threshold = 0.15
    try:
        alpha = min(1.0, max(0.0, float(alpha)))
    except (TypeError, ValueError):
        alpha = 0.5
    file_paths = request.data.get("file_paths")
    if file_paths and isinstance(file_paths, list):
        file_paths = [str(p).strip() for p in file_paths if p]
    else:
        file_paths = []
    scar_mode_raw = request.data.get("scar_mode", None)
    if scar_mode_raw is None:
        scar_mode = None
    elif isinstance(scar_mode_raw, bool):
        scar_mode = scar_mode_raw
    else:
        scar_mode = str(scar_mode_raw).strip().lower() in {"1", "true", "yes", "on"}
    scar_domain = str(request.data.get("scar_domain") or request.data.get("domain") or "").strip()
    dsrag_mode_raw = request.data.get("dsrag_mode", None)
    if dsrag_mode_raw is None:
        dsrag_mode = None
    elif isinstance(dsrag_mode_raw, bool):
        dsrag_mode = dsrag_mode_raw
    else:
        dsrag_mode = str(dsrag_mode_raw).strip().lower() in {"1", "true", "yes", "on"}
    dsrag_config = str(request.data.get("dsrag_config") or "").strip()
    retrieval_params = {
        "strategy": strategy,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "alpha": alpha,
        "file_paths": file_paths,
        "references": references,
    }
    if scar_mode is not None:
        retrieval_params["scar_mode"] = scar_mode
    if scar_domain:
        retrieval_params["scar_domain"] = scar_domain
    if dsrag_mode is not None:
        retrieval_params["dsrag_mode"] = dsrag_mode
    if dsrag_config:
        retrieval_params["dsrag_config"] = dsrag_config
    aux_ids = None
    if auxiliary_knowledge_base_ids and isinstance(auxiliary_knowledge_base_ids, list):
        aux_ids = [str(k) for k in auxiliary_knowledge_base_ids]

    # 先走标准「失败+纠正」触发路径（普通/PRO 都可触发）
    evolution_path = "standard_evolution"
    try:
        schedule_evolution_after_user_turn(
            user=request.user,
            session_id=session.id,
            user_message=question,
        )
    except Exception:
        pass
    # PRO 用户额外补充沙盒模拟路径（并行触发，不覆盖标准路径）
    if getattr(request.user, "is_pro", False):
        evolution_path = "pro_sandbox"
        try:
            from apps.skills.tasks import pro_sandbox_simulation

            pro_sandbox_simulation.delay(request.user.id)
        except Exception:
            pass

    ctx = {
        "question": question,
        "knowledge_base_id": knowledge_base_id,
        "session": session,
        "model_name": model_name,
        "agent_id": agent_id,
        "scene": scene,
        "references": references,
        "use_agent": use_agent,
        "retrieval_params": retrieval_params,
        "aux_ids": aux_ids,
        "evolution_path": evolution_path,
        "english_phase": english_phase,
        "english_profile_id": english_profile_id,
        "english_intent": english_intent,
    }
    # P0-08：日配额 / 全局预算熔断（在昂贵编排前拦截）
    from .usage import check_ask_allowed

    quota_block = check_ask_allowed(request.user)
    if quota_block is not None:
        return None, quota_block
    return ctx, None


def _normalize_knowledge_sources(result: dict) -> list:
    """T3.7：优先落 SCAR citations（file+path+unit_id），否则退回 sources。"""
    cites = result.get("citations")
    if isinstance(cites, list) and cites:
        out = []
        for c in cites:
            if not isinstance(c, dict):
                continue
            item = {
                "file": c.get("file") or "",
                "file_id": str(c.get("file_id") or ""),
                "path": c.get("path") or "",
                "unit_id": c.get("unit_id") or "",
            }
            if item["path"] or item["file_id"]:
                out.append(item)
        if out:
            return out
    sources = result.get("sources") or []
    if isinstance(sources, list):
        return sources
    return []


def _compute_and_store_answer(request, ctx):
    """执行编排/问答，写入会话与消息，返回附带 session_id 等的 result 字典。"""
    question = ctx["question"]
    knowledge_base_id = ctx["knowledge_base_id"]
    session = ctx["session"]
    model_name = ctx["model_name"]
    agent_id = ctx["agent_id"]
    scene = ctx["scene"]
    references = ctx["references"]
    use_agent = ctx["use_agent"]
    retrieval_params = ctx["retrieval_params"]
    aux_ids = ctx["aux_ids"]
    evolution_path = ctx["evolution_path"]

    question_for_processing = question + _build_reference_hint(references)
    result = None
    if use_agent:
        try:
            from apps.chat.english_learning_context import (
                build_english_learning_orchestrator_context,
            )

            english_learning = build_english_learning_orchestrator_context(
                user=request.user,
                knowledge_base_id=str(knowledge_base_id),
                agent_id=agent_id,
                english_phase=ctx.get("english_phase") or "",
                english_profile_id=ctx.get("english_profile_id"),
            )
            orchestrator = get_orchestrator_by_tier(request.user, agent_id)
            result = orchestrator.process(
                question_for_processing,
                knowledge_base_id,
                request.user,
                retrieval_params=retrieval_params,
                auxiliary_knowledge_base_ids=aux_ids,
                session_id=session.id,
                scene=scene or None,
                english_learning=english_learning,
            )
            result["qa_id"] = None
            result["model"] = orchestrator.agent.default_model
        except Exception:
            use_agent = False
            result = None
    if not use_agent or result is None:
        qa_service = QAService(model=model_name)
        result = qa_service.ask_question(
            question_for_processing,
            knowledge_base_id,
            request.user,
            retrieval_params=retrieval_params,
            auxiliary_knowledge_base_ids=aux_ids,
            scene=scene or None,
        )
        result["skills_used"] = result.get("skills_used", [])
        result["agent_name"] = result.get("agent_name", "")
        result["agent_id"] = result.get("agent_id", "")

    from apps.system.content_safety.guards import apply_output_safety

    result = apply_output_safety(
        result,
        channel="chat",
        user=request.user,
        request=request,
    )

    message_order = session.messages.count()
    QARecord.objects.create(
        session=session,
        question=question,
        message_type="user",
        message_order=message_order,
    )
    assistant_message = QARecord.objects.create(
        session=session,
        question=question,
        answer=result["answer"],
        knowledge_sources=_normalize_knowledge_sources(result),
        skills_used=result.get("skills_used", []),
        agent_id=result.get("agent_id", ""),
        confidence_score=0.8,
        message_type="assistant",
        message_order=message_order + 1,
    )

    session.last_activity = timezone.now()
    session.save()

    try:
        from apps.learning.services import LearningService

        learning_service = LearningService()
        learning_service.update_knowledge_learning_progress(
            user_id=request.user.id,
            knowledge_base_id=knowledge_base_id,
            activity_type="question",
            activity_data={"time_spent": 1},
        )
        learning_service.update_knowledge_learning_progress(
            user_id=request.user.id,
            knowledge_base_id=knowledge_base_id,
            activity_type="answer",
            activity_data={"time_spent": 1},
        )
    except ImportError:
        pass
    except Exception as e:
        logger.warning("更新学习进度失败: %s", e)

    result["session_id"] = str(session.id)
    result["message_id"] = str(assistant_message.id)
    result["references"] = references
    result["evolution_path"] = evolution_path
    intent = ctx.get("english_intent") or {}
    if intent.get("slot"):
        result["english_delegate"] = intent.get("slot")
    if intent.get("source"):
        result["english_intent_source"] = intent.get("source")

    try:
        schedule_agent_evolution_after_turn(
            agent_id=result.get("agent_id"),
            session_id=session.id,
            user=request.user,
            question=question,
            answer=result.get("answer") or "",
            skills_used=result.get("skills_used") or [],
            studio_context={
                "mode": scene or "",
                "agent_id": result.get("agent_id") or agent_id or "qa",
                "knowledge_base_id": str(knowledge_base_id),
                "references": references,
            },
        )
    except Exception:
        pass

    from .usage import record_ask_success

    quota = record_ask_success(
        request.user,
        question=question,
        answer=result.get("answer") or "",
    )
    result["quota"] = quota

    return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agents_list(request):
    """获取可用的智能体列表"""
    is_pro = bool(getattr(request.user, "is_pro", False))
    cache_key = f"chat:agents:list:is_pro:{int(is_pro)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)
    agents = Agent.objects.filter(is_active=True).order_by('id')
    if not is_pro:
        agents = agents.exclude(id__in=["studio_pro"])
    data = [
        {
            'id': a.id,
            'name': a.name,
            'description': a.description or '',
            'skills': a.skills or [],
            'default_model': a.default_model or 'deepseek-chat',
            'evolution_enabled': getattr(a, 'evolution_enabled', False),
            'evolution_governance': getattr(a, 'evolution_governance', 'supervised'),
        }
        for a in agents
    ]
    cache.set(cache_key, data, AGENTS_LIST_CACHE_TTL_SECONDS)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_config(request):
    """订阅配置占位（P0-07：首发免费，永久返回 enabled=false）。"""
    return Response({
        'upgrade_url': '',
        'callback_url': '',
        'enabled': False,
        'tier': 'free',
        'message': '当前为免费版，未开放付费订阅',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_bootstrap(request):
    """Phase 2 文字工作室占位 API：统一走 PRO 权限校验。"""
    return Response({
        'enabled': True,
        'user_id': str(request.user.id),
        'tier': 'pro',
        'message': 'writing studio api ready',
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_drafts(request):
    """工作室草稿列表/创建。"""
    if request.method == 'GET':
        rows = StudioDraft.objects.filter(user=request.user, is_deleted=False).order_by('-updated_at')[:100]
        return Response(StudioDraftSerializer(rows, many=True).data)

    serializer = StudioDraftSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    obj = serializer.save(
        user=request.user,
        path=request.data.get("path") or f"/drafts/{request.data.get('title') or 'untitled'}.md",
    )
    return Response(StudioDraftSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_draft_detail(request, draft_id):
    obj = StudioDraft.objects.filter(id=draft_id, user=request.user, is_deleted=False).first()
    if not obj:
        return Response({'error': '草稿不存在'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(StudioDraftSerializer(obj).data)

    if request.method == 'PUT':
        serializer = StudioDraftSerializer(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        merged_title = serializer.validated_data.get('title', obj.title)
        merged_content = serializer.validated_data.get('content', obj.content)
        merged_mode = serializer.validated_data.get('mode', obj.mode)
        changed = (
            merged_title != obj.title
            or merged_content != obj.content
            or merged_mode != obj.mode
        )
        if changed:
            StudioDraftRevision.objects.create(
                draft=obj,
                revision_index=obj.version,
                title=obj.title,
                content=obj.content,
                mode=obj.mode,
            )
            _trim_studio_draft_revisions(obj)
        new_version = obj.version + 1
        serializer.save(version=new_version)
        return Response(StudioDraftSerializer(obj).data)

    obj.is_deleted = True
    obj.save(update_fields=["is_deleted", "updated_at"])
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_draft_revisions(request, draft_id):
    """列出草稿历史版本（P3-T01）。"""
    obj = StudioDraft.objects.filter(id=draft_id, user=request.user, is_deleted=False).first()
    if not obj:
        return Response({'error': '草稿不存在'}, status=status.HTTP_404_NOT_FOUND)
    rows = StudioDraftRevision.objects.filter(draft=obj).order_by('-revision_index')[:100]
    return Response(StudioDraftRevisionListSerializer(rows, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_draft_revision_detail(request, draft_id, revision_index):
    """单条历史快照全文。"""
    obj = StudioDraft.objects.filter(id=draft_id, user=request.user, is_deleted=False).first()
    if not obj:
        return Response({'error': '草稿不存在'}, status=status.HTTP_404_NOT_FOUND)
    rev = StudioDraftRevision.objects.filter(draft=obj, revision_index=revision_index).first()
    if not rev:
        return Response({'error': '该版本不存在'}, status=status.HTTP_404_NOT_FOUND)
    return Response(StudioDraftRevisionDetailSerializer(rev).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsProUser])
def studio_draft_revision_restore(request, draft_id, revision_index):
    """恢复到指定历史版本（当前内容会先作为新快照入库）。"""
    obj = StudioDraft.objects.filter(id=draft_id, user=request.user, is_deleted=False).first()
    if not obj:
        return Response({'error': '草稿不存在'}, status=status.HTTP_404_NOT_FOUND)
    rev = StudioDraftRevision.objects.filter(draft=obj, revision_index=revision_index).first()
    if not rev:
        return Response({'error': '该版本不存在'}, status=status.HTTP_404_NOT_FOUND)
    StudioDraftRevision.objects.create(
        draft=obj,
        revision_index=obj.version,
        title=obj.title,
        content=obj.content,
        mode=obj.mode,
    )
    _trim_studio_draft_revisions(obj)
    obj.title = rev.title
    obj.content = rev.content
    obj.mode = rev.mode
    obj.version = obj.version + 1
    obj.save(update_fields=["title", "content", "mode", "version", "updated_at"])
    return Response(StudioDraftSerializer(obj).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AskQuestionRateThrottle])
def ask_question(request):
    """发送问题（同步 JSON）。"""
    ctx, err = _prepare_ask_from_request(request)
    if err is not None:
        return err
    try:
        result = _compute_and_store_answer(request, ctx)
        return Response(result)
    except Exception as e:
        return Response({'error': f'处理问题时出现错误：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AskQuestionRateThrottle])
def ask_question_stream(request):
    """
    SSE 流式展示：与 ask_question 共用同一套编排与会话落库逻辑；
    生成完成后按字符推送 chunk，便于前端做类 Cursor 的逐字呈现。
    （首字仍须等待整段答案生成完毕，与当前编排实现一致。）
    """
    ctx, err = _prepare_ask_from_request(request)
    if err is not None:
        return err
    try:
        result = _compute_and_store_answer(request, ctx)
    except Exception as e:
        return Response({'error': f'流式生成失败：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    answer = (result or {}).get('answer') or ''
    skills = (result or {}).get('skills_used') or []
    agent_name = (result or {}).get('agent_name') or ''

    def event_stream():
        yield "event: start\ndata: {}\n\n"
        for ch in answer:
            yield f"event: chunk\ndata: {json.dumps({'delta': ch}, ensure_ascii=False)}\n\n"
        final_payload = {
            "answer": answer,
            "skills_used": skills,
            "agent_name": agent_name,
            "evolution_path": result.get("evolution_path"),
            "session_id": result.get("session_id"),
            "message_id": result.get("message_id"),
            "references": result.get("references"),
            "sources": result.get("sources") or [],
            "citations": result.get("citations") or [],
            "answer_source": result.get("answer_source") or "",
            "abstained": bool(result.get("abstained")),
        }
        yield f"event: end\ndata: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

    resp = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    resp['X-Accel-Buffering'] = 'no'
    return resp

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_sessions(request):
    """获取用户的聊天会话列表"""
    sessions = ChatSession.objects.filter(user=request.user, is_active=True).order_by('-last_activity')[:20]
    serializer = ChatSessionListSerializer(sessions, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_session_detail(request, session_id):
    """获取特定会话的详细信息"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user, is_active=True)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)
    except ChatSession.DoesNotExist:
        return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_session(request):
    """创建新的聊天会话"""
    knowledge_base_id = request.data.get('knowledge_base_id')
    title = request.data.get('title', '新对话')
    
    if not knowledge_base_id:
        return Response({'error': '缺少知识库ID'}, status=status.HTTP_400_BAD_REQUEST)
    
    session = ChatSession.objects.create(
        user=request.user,
        knowledge_base_id=knowledge_base_id,
        title=title
    )
    
    serializer = ChatSessionSerializer(session)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    """删除聊天会话"""
    try:
        session = ChatSession.objects.get(id=session_id, user=request.user)
        session.is_active = False
        session.save()
        return Response({'message': '会话已删除'})
    except ChatSession.DoesNotExist:
        return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def duplicate_session(request, session_id):
    """复制会话（含消息），用于工作室历史对话复用。"""
    try:
        src = ChatSession.objects.get(id=session_id, user=request.user, is_active=True)
    except ChatSession.DoesNotExist:
        return Response({'error': '会话不存在'}, status=status.HTTP_404_NOT_FOUND)

    dst = ChatSession.objects.create(
        user=request.user,
        knowledge_base=src.knowledge_base,
        title=f"{(src.title or '未命名会话')} (副本)",
        is_active=True,
    )
    msgs = list(src.messages.order_by('message_order'))
    for m in msgs:
        QARecord.objects.create(
            session=dst,
            user=request.user,
            question=m.question,
            answer=m.answer,
            knowledge_sources=m.knowledge_sources,
            skills_used=m.skills_used,
            agent_id=m.agent_id,
            confidence_score=m.confidence_score,
            feedback=m.feedback,
            message_type=m.message_type,
            message_order=m.message_order,
        )
    dst.last_activity = timezone.now()
    dst.save(update_fields=['last_activity'])
    return Response({'ok': True, 'session_id': str(dst.id)})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_history(request):
    """获取聊天历史 - 保持向后兼容"""
    # 获取最近活跃的会话
    recent_sessions = ChatSession.objects.filter(
        user=request.user, 
        is_active=True
    ).order_by('-last_activity')[:5]
    
    all_messages = []
    for session in recent_sessions:
        messages = session.messages.order_by('message_order')[:10]  # 每个会话最多10条消息
        all_messages.extend(messages)
    
    # 按时间排序并限制数量
    all_messages.sort(key=lambda x: x.created_at, reverse=True)
    all_messages = all_messages[:50]
    
    serializer = QARecordSerializer(all_messages, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request):
    """提交反馈"""
    qa_id = request.data.get('qa_id')
    feedback = request.data.get('feedback')
    
    if not qa_id or not feedback:
        return Response({'error': '缺少必要字段'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        qa_record = QARecord.objects.get(id=qa_id, user=request.user)
        qa_record.feedback = feedback
        qa_record.save()
        return Response({'message': '反馈提交成功'})
    except QARecord.DoesNotExist:
        return Response({'error': '问答记录不存在'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_models(request):
    """获取可用的AI模型列表"""
    models = AIServiceFactory.get_available_models()
    return Response(models)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def providers(request):
    """获取所有提供商列表"""
    providers = AIConfig.get_providers()
    return Response(providers)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def provider_models(request, provider_key):
    """获取指定提供商的所有模型"""
    models = AIConfig.get_provider_models(provider_key)
    return Response(models)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_api_key(request):
    """测试API Key"""
    provider_key = request.data.get('provider_key')
    api_key = request.data.get('api_key')
    
    if not provider_key or not api_key:
        return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)
    
    result = APIConfigService.test_api_key(provider_key, api_key)
    return Response(result)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_api_key(request):
    """保存API Key"""
    provider_key = request.data.get('provider_key')
    api_key = request.data.get('api_key')
    
    if not provider_key or not api_key:
        return Response({'error': '缺少必要参数'}, status=status.HTTP_400_BAD_REQUEST)
    
    # 保存API Key（包含测试）
    success = APIConfigService.save_api_key(provider_key, api_key)
    
    if success:
        return Response({'message': 'API Key保存成功'})
    else:
        # 即使测试失败，也返回成功，但包含错误信息
        return Response({
            'message': 'API Key已保存，但测试失败',
            'error': 'API Key测试失败，请检查密钥是否正确'
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def configured_providers(request):
    """获取已配置的提供商和模型"""
    providers = APIConfigService.get_configured_providers()
    return Response(providers)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """获取仪表板统计：默认当前用户；?scope=global 且 staff 时返回全站汇总（管理后台用）"""
    from apps.knowledge.models import KnowledgeBase, Document

    scope = (request.GET.get('scope') or '').strip().lower()
    if scope == 'global':
        if not getattr(request.user, 'is_staff', False):
            return Response({'detail': '需要管理员权限查看全站统计'}, status=status.HTTP_403_FORBIDDEN)
        try:
            knowledge_bases_count = KnowledgeBase.objects.count()
            documents_count = Document.objects.count()
            questions_count = QARecord.objects.count()
            try:
                from apps.workflows.models import GeneratedContent
                content_generated_count = GeneratedContent.objects.count()
            except ImportError:
                try:
                    from apps.learning.models import LearningContent
                    content_generated_count = LearningContent.objects.count()
                except ImportError:
                    content_generated_count = 0
            return Response({
                'knowledgeBases': knowledge_bases_count,
                'documents': documents_count,
                'questions': questions_count,
                'content_generated': content_generated_count,
                'scope': 'global',
            })
        except Exception as e:
            return Response({
                'knowledgeBases': 0,
                'documents': 0,
                'questions': 0,
                'content_generated': 0,
                'scope': 'global',
                'error': str(e)
            })

    try:
        knowledge_bases_count = KnowledgeBase.objects.filter(owner=request.user).count()
        documents_count = Document.objects.filter(knowledge_base__owner=request.user).count()
        questions_count = QARecord.objects.filter(user=request.user).count()

        try:
            from apps.workflows.models import GeneratedContent
            content_generated_count = GeneratedContent.objects.filter(
                knowledge_base__owner=request.user
            ).count()
        except ImportError:
            try:
                from apps.learning.models import LearningContent
                content_generated_count = LearningContent.objects.filter(
                    knowledge_base__owner=request.user
                ).count()
            except ImportError:
                content_generated_count = 0

        return Response({
            'knowledgeBases': knowledge_bases_count,
            'documents': documents_count,
            'questions': questions_count,
            'content_generated': content_generated_count,
            'scope': 'user',
        })
    except Exception as e:
        return Response({
            'knowledgeBases': 0,
            'documents': 0,
            'questions': 0,
            'content_generated': 0,
            'scope': 'user',
            'error': str(e)
        })
