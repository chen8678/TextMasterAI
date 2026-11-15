from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model
import logging
import json
import hashlib
from typing import Any, Dict, List, Tuple, Optional
from .models import KnowledgeBase, Document, ImportJob, KnowledgeBaseMember
from .serializers import KnowledgeBaseSerializer, KnowledgeBaseListSerializer, DocumentSerializer, DocumentCreateSerializer
from .document_analyzer import DocumentAnalyzer, DocumentRelevance
from .pdf_processor import PDFProcessor
from .docx_processor import DOCXProcessor
from .vectorization_service import VectorizationService
from .retrieval_service import AdvancedRetrievalService, RetrievalStrategyManager
from .import_utils import normalize_json_entry
from .tasks import process_import_job
from django.db.models import F, Q
from django.conf import settings as django_settings
from django.core.cache import cache
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)
KB_LIST_CACHE_TTL_SECONDS = 120


def _kb_list_cache_version_key(user_id) -> str:
    return f"kb:list:version:{user_id}"


def _kb_list_cache_key(user_id) -> str:
    version = cache.get(_kb_list_cache_version_key(user_id), 1) or 1
    return f"kb:list:user:{user_id}:v{version}"


def _invalidate_kb_list_cache_for_user(user_id) -> None:
    key = _kb_list_cache_version_key(user_id)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 2, None)


def _to_bool(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


ROLE_LEVEL = {
    'viewer': 1,
    'editor': 2,
    'admin': 3,
}


def _membership_role(user, knowledge_base: KnowledgeBase) -> Optional[str]:
    row = KnowledgeBaseMember.objects.filter(knowledge_base=knowledge_base, user=user).first()
    return row.role if row else None


def _has_kb_access(user, knowledge_base: KnowledgeBase, min_role: str = 'viewer') -> bool:
    if knowledge_base.owner_id == user.id:
        return True
    role = _membership_role(user, knowledge_base)
    if not role:
        return False
    return ROLE_LEVEL.get(role, 0) >= ROLE_LEVEL.get(min_role, 1)


def _get_kb_or_404_for_user(user, knowledge_base_id, min_role: str = 'viewer') -> KnowledgeBase:
    kb = get_object_or_404(KnowledgeBase, pk=knowledge_base_id)
    if not _has_kb_access(user, kb, min_role=min_role):
        raise Http404("知识库不存在")
    return kb


def clean_file_content(raw_content: bytes) -> bytes:
    """
    清理文件内容，移除可能导致问题的字符
    
    Args:
        raw_content: 原始文件内容（字节）
        
    Returns:
        清理后的文件内容（字节）
    """
    # 过滤掉 NUL 字符 (0x00)
    content = raw_content.replace(b'\x00', b'')
    
    # 过滤掉其他控制字符（除了常见的换行符、制表符等）
    # 保留的字符：\t (0x09), \n (0x0A), \r (0x0D)
    cleaned_bytes = bytearray()
    for byte in content:
        if byte >= 32 or byte in [9, 10, 13]:  # 可打印字符 + TAB, LF, CR
            cleaned_bytes.append(byte)
        else:
            # 替换为空格
            cleaned_bytes.append(32)
    
    return bytes(cleaned_bytes)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def knowledge_base_list(request):
    """获取知识库列表或创建知识库"""
    if request.method == 'GET':
        try:
            cache_key = _kb_list_cache_key(request.user.id)
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached)
            knowledge_bases = KnowledgeBase.objects.filter(
                Q(owner=request.user) | Q(members__user=request.user)
            ).distinct()
            serializer = KnowledgeBaseListSerializer(
                knowledge_bases, many=True, context={'request': request}
            )
            payload = serializer.data
            cache.set(cache_key, payload, KB_LIST_CACHE_TTL_SECONDS)
            return Response(payload)
        except Exception as e:
            logger.exception("knowledge_base_list GET 失败: %s", e)
            return Response(
                {'error': str(e), 'detail': '获取知识库列表失败，请检查数据库连接或联系管理员'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    elif request.method == 'POST':
        serializer = KnowledgeBaseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(owner=request.user)
            _invalidate_kb_list_cache_for_user(request.user.id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def knowledge_base_detail(request, pk):
    """获取、更新或删除知识库"""
    if request.method == 'GET':
        knowledge_base = _get_kb_or_404_for_user(request.user, pk, min_role='viewer')
    elif request.method == 'PUT':
        knowledge_base = _get_kb_or_404_for_user(request.user, pk, min_role='admin')
    else:
        # 删除维持 owner 专属，避免成员误删整个知识库
        knowledge_base = get_object_or_404(KnowledgeBase, pk=pk, owner=request.user)

    if request.method == 'GET':
        serializer = KnowledgeBaseSerializer(knowledge_base)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = KnowledgeBaseSerializer(knowledge_base, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            _invalidate_kb_list_cache_for_user(request.user.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        try:
            # 按依赖顺序显式删除关联数据，避免级联顺序或 pgvector 等导致的 500
            from apps.chat.models import ChatSession
            ChatSession.objects.filter(knowledge_base_id=pk).delete()
            try:
                ImportJob.objects.filter(knowledge_base_id=pk).delete()
            except Exception:
                # 若 knowledge_import_jobs 表不存在（迁移未执行）则跳过
                pass
            knowledge_base.documents.all().delete()
            knowledge_base.delete()
            _invalidate_kb_list_cache_for_user(request.user.id)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.exception("删除知识库失败: pk=%s", pk)
            return Response(
                {'error': f'删除知识库失败：{str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def knowledge_base_members(request, pk):
    """知识库成员管理：仅 owner 或 admin 成员可查看/变更成员。"""
    knowledge_base = _get_kb_or_404_for_user(request.user, pk, min_role='admin')
    User = get_user_model()

    if request.method == 'GET':
        rows = KnowledgeBaseMember.objects.filter(knowledge_base=knowledge_base).select_related('user').order_by('-created_at')
        return Response([
            {
                'user_id': str(r.user_id),
                'username': r.user.username,
                'email': r.user.email,
                'role': r.role,
                'created_at': r.created_at,
            }
            for r in rows
        ])

    user_id = request.data.get('user_id')
    email = (request.data.get('email') or '').strip()
    role = str(request.data.get('role') or '').strip().lower()
    if role not in {'viewer', 'editor', 'admin'}:
        return Response({'error': 'role 必须是 viewer/editor/admin'}, status=status.HTTP_400_BAD_REQUEST)

    target_user = None
    if user_id:
        target_user = User.objects.filter(id=user_id).first()
    elif email:
        target_user = User.objects.filter(email=email).first()
    if not target_user:
        return Response({'error': '目标用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    if target_user.id == knowledge_base.owner_id:
        return Response({'error': 'owner 无需添加为成员'}, status=status.HTTP_400_BAD_REQUEST)

    row, created = KnowledgeBaseMember.objects.update_or_create(
        knowledge_base=knowledge_base,
        user=target_user,
        defaults={'role': role},
    )
    _invalidate_kb_list_cache_for_user(request.user.id)
    _invalidate_kb_list_cache_for_user(target_user.id)
    return Response({
        'ok': True,
        'created': created,
        'user_id': str(target_user.id),
        'role': row.role,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def knowledge_base_member_detail(request, pk, user_id):
    """移除知识库成员：仅 owner 或 admin 成员。"""
    knowledge_base = _get_kb_or_404_for_user(request.user, pk, min_role='admin')
    row = KnowledgeBaseMember.objects.filter(knowledge_base=knowledge_base, user_id=user_id).first()
    if not row:
        return Response({'error': '成员不存在'}, status=status.HTTP_404_NOT_FOUND)
    target_user_id = row.user_id
    row.delete()
    _invalidate_kb_list_cache_for_user(request.user.id)
    if target_user_id:
        _invalidate_kb_list_cache_for_user(target_user_id)
    return Response({'ok': True})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def document_list(request, knowledge_base_id):
    """获取文档列表或创建文档"""
    if request.method == 'GET':
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='viewer')
    else:
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')
    
    if request.method == 'GET':
        documents = knowledge_base.documents.all()
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        # 检查是否包含文件上传
        if 'file' in request.FILES:
            return handle_document_upload(request, knowledge_base)
        else:
            # 处理文本内容上传
            serializer = DocumentCreateSerializer(data=request.data, context={'knowledge_base_id': knowledge_base_id})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def document_detail(request, knowledge_base_id, pk):
    """获取、更新或删除文档"""
    if request.method == 'GET':
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='viewer')
    else:
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')
    document = get_object_or_404(Document, pk=pk, knowledge_base=knowledge_base)
    
    if request.method == 'GET':
        serializer = DocumentSerializer(document)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = DocumentSerializer(document, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _chunk_upload_storage_dir(user_id: int) -> Path:
    p = Path(django_settings.BASE_DIR) / "data" / "kb_chunk_uploads" / str(user_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cleanup_chunk_session(user_id: int, upload_id: str) -> None:
    base = Path(django_settings.BASE_DIR) / "data" / "kb_chunk_uploads" / str(user_id)
    for suffix in (".part", ".meta.json"):
        fp = base / f"{upload_id}{suffix}"
        try:
            if fp.is_file():
                fp.unlink()
        except OSError:
            pass


def _finalize_document_from_bytes(
    knowledge_base: KnowledgeBase,
    raw_content: bytes,
    filename: str,
    file_size: int,
    mime_type: str,
    force_upload: bool,
    scar_domain: str = "",
) -> Response:
    """从完整二进制内容创建文档（单文件上传与分片合并后共用）。"""
    filename = os.path.basename(filename) or "unnamed"
    if not raw_content or len(raw_content) == 0:
        return Response({"error": "文件内容为空，无法处理"}, status=status.HTTP_400_BAD_REQUEST)

    if PDFProcessor.is_pdf_file(raw_content):
        content = PDFProcessor.extract_text_from_pdf(raw_content)
        if not content:
            return Response(
                {"error": "PDF文件无法提取文本内容，可能是加密文件或损坏文件"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        file_info = PDFProcessor.get_pdf_info(raw_content)
        file_type = "pdf"
    elif DOCXProcessor.is_docx_file(raw_content):
        content = DOCXProcessor.extract_text_from_docx(raw_content)
        if not content:
            return Response(
                {"error": "DOCX文件无法提取文本内容，可能是损坏文件"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        file_info = DOCXProcessor.get_docx_info(raw_content)
        file_type = "docx"
    else:
        filtered_content = clean_file_content(raw_content)
        content = filtered_content.decode("utf-8", errors="ignore")
        file_info = None
        file_type = "text"

    analyzer = DocumentAnalyzer()
    analysis_result = analyzer.analyze_document(content, filename)

    if analysis_result.relevance == DocumentRelevance.IRRELEVANT:
        return Response(
            {
                "error": "文档内容与AI学习无关",
                "analysis": {
                    "relevance": analysis_result.relevance.value,
                    "content_type": analysis_result.content_type.value,
                    "confidence": analysis_result.confidence,
                    "quality_score": analysis_result.quality_score,
                    "issues": analysis_result.issues,
                    "suggestions": analysis_result.suggestions,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if analysis_result.quality_score < 50:
        warning_message = f"文档质量较低（{analysis_result.quality_score:.1f}分），建议改进后再上传"
    else:
        warning_message = None

    content_hash = hashlib.sha256((content or "").strip().encode("utf-8")).hexdigest()
    existing = (
        Document.objects.filter(knowledge_base=knowledge_base, content_hash=content_hash)
        .order_by("-created_at")
        .first()
    )
    if existing and not force_upload:
        return Response(
            {
                "error": "检测到重复文档：该内容已存在于知识库中",
                "duplicate": True,
                "existing_document": {
                    "id": str(existing.id),
                    "title": existing.title,
                    "created_at": existing.created_at,
                },
                "hint": "如需保留重复版本，请在请求中添加 force=true",
            },
            status=status.HTTP_409_CONFLICT,
        )

    same_name_exists = (
        Document.objects.filter(knowledge_base=knowledge_base, title=filename)
        .exclude(content_hash=content_hash)
        .exists()
    )

    document = Document.objects.create(
        knowledge_base=knowledge_base,
        title=filename,
        content=content,
        content_type=file_type,
        file_path=filename,
        file_size=file_size,
        content_hash=content_hash,
        metadata={
            "analysis": {
                "relevance": analysis_result.relevance.value,
                "content_type": analysis_result.content_type.value,
                "confidence": analysis_result.confidence,
                "quality_score": analysis_result.quality_score,
                "keywords": analysis_result.keywords,
                "issues": analysis_result.issues,
                "suggestions": analysis_result.suggestions,
            },
            "file_info": {
                "original_filename": filename,
                "mime_type": mime_type or "text/plain",
                "file_type": file_type,
            },
            "file_details": file_info if file_info else None,
        },
    )
    if existing and force_upload:
        md = document.metadata or {}
        md["duplicate_of"] = str(existing.id)
        md["duplicate_forced"] = True
        document.metadata = md
        document.save(update_fields=["metadata", "updated_at"])

    try:
        vectorizer = VectorizationService()
        embedding = vectorizer.vectorize_text(content)
        document.vector_embedding = embedding.tolist()
        document.save()
        logger.info("文档 %s 向量化成功", filename)
    except Exception as e:
        logger.error("文档 %s 向量化失败: %s", filename, e)

    # SCAR：可选结构编译。显式 scar_domain=construction 时始终编译；
    # 或 SCAR_ENABLED 且上传 JSON 时按默认领域编译。
    try:
        from django.conf import settings as dj_settings

        domain_hint = (scar_domain or "").strip().lower()
        scar_enabled = bool(getattr(dj_settings, "SCAR_ENABLED", False))
        is_json = (filename or "").lower().endswith(".json")
        should_compile = domain_hint == "construction" or (scar_enabled and is_json)
        if should_compile:
            from apps.scar.services.ingest import compile_document

            domain = domain_hint or getattr(dj_settings, "SCAR_DEFAULT_DOMAIN", "construction")
            compile_document(document, domain=domain, raw_text=content, vectorize=True)
            document.refresh_from_db()
    except Exception as e:
        logger.warning("SCAR 编译跳过/失败: %s", e)

    serializer = DocumentSerializer(document)
    response_data = serializer.data

    if warning_message:
        response_data["warning"] = warning_message
    if same_name_exists:
        response_data["same_name_warning"] = "检测到同名文件已存在（内容不同），已作为新文档保存"
    if existing and force_upload:
        response_data["duplicate_forced"] = True
        response_data["duplicate_of"] = str(existing.id)

    return Response(response_data, status=status.HTTP_201_CREATED)


def handle_document_upload(request, knowledge_base):
    """处理文档上传，包含智能分析"""
    try:
        # 检查文件是否存在
        if "file" not in request.FILES:
            return Response(
                {
                    "error": "未找到上传的文件，请确保使用 multipart/form-data 格式上传",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_file = request.FILES["file"]

        # 检查文件名
        if not uploaded_file.name:
            return Response({"error": "文件名不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        filename = os.path.basename(uploaded_file.name)

        max_file_size = int(getattr(django_settings, "KNOWLEDGE_UPLOAD_MAX_BYTES", 100 * 1024 * 1024))
        if uploaded_file.size > max_file_size:
            mb_limit = max_file_size / (1024 * 1024)
            return Response(
                {
                    "error": (
                        f"文件大小不能超过 {mb_limit:.0f}MB（可在环境变量 KNOWLEDGE_UPLOAD_MAX_BYTES 中调整），"
                        f"当前文件大小：{uploaded_file.size / 1024 / 1024:.2f}MB"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw_content = uploaded_file.read()
        except Exception as e:
            logger.error("读取文件内容失败: %s", e)
            return Response({"error": f"读取文件内容失败: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        force_upload = _to_bool(request.data.get("force"))
        scar_domain = str(request.data.get("scar_domain") or request.data.get("domain") or "").strip()
        return _finalize_document_from_bytes(
            knowledge_base,
            raw_content,
            filename,
            uploaded_file.size,
            uploaded_file.content_type or "text/plain",
            force_upload,
            scar_domain=scar_domain,
        )

    except KeyError as e:
        logger.error("文档上传失败 - 缺少必要参数: %s", e)
        return Response(
            {
                "error": f"请求参数错误: 缺少必要字段 {str(e)}",
                "detail": "请确保使用 multipart/form-data 格式，并包含 file 字段",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error("文档上传失败: %s", e, exc_info=True)
        return Response(
            {
                "error": f"文档上传失败: {str(e)}",
                "detail": "请检查文件格式是否正确，或联系管理员",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledge_upload_limits(request, knowledge_base_id):
    """返回当前环境的知识库上传上限（供前端分片与校验）。"""
    _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role="viewer")
    max_b = int(getattr(django_settings, "KNOWLEDGE_UPLOAD_MAX_BYTES", 100 * 1024 * 1024))
    chunk_b = int(getattr(django_settings, "KNOWLEDGE_CHUNK_MAX_BYTES", 8 * 1024 * 1024))
    return Response(
        {
            "max_file_bytes": max_b,
            "chunk_max_bytes": chunk_b,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def document_chunk_upload(request, knowledge_base_id):
    """
    分片上传：按顺序发送 chunk_index=0..total_chunks-1，每片不超过 KNOWLEDGE_CHUNK_MAX_BYTES，
    合并后总大小不超过 KNOWLEDGE_UPLOAD_MAX_BYTES，最后一片到达后走与单文件相同的解析与入库逻辑。
    """
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role="editor")

    max_total = int(getattr(django_settings, "KNOWLEDGE_UPLOAD_MAX_BYTES", 100 * 1024 * 1024))
    max_chunk = int(getattr(django_settings, "KNOWLEDGE_CHUNK_MAX_BYTES", 8 * 1024 * 1024))

    try:
        if "file" not in request.FILES:
            return Response({"error": "缺少分片文件 field=file"}, status=status.HTTP_400_BAD_REQUEST)
        part = request.FILES["file"]
        upload_id_raw = (request.POST.get("upload_id") or "").strip()
        filename_raw = (request.POST.get("filename") or "").strip()
        try:
            chunk_index = int(request.POST.get("chunk_index", "-1"))
            total_chunks = int(request.POST.get("total_chunks", "0"))
        except (TypeError, ValueError):
            return Response({"error": "chunk_index / total_chunks 无效"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            upload_uuid = uuid.UUID(upload_id_raw)
        except (ValueError, AttributeError):
            return Response({"error": "upload_id 必须为 UUID"}, status=status.HTTP_400_BAD_REQUEST)
        upload_id = str(upload_uuid)

        if total_chunks < 1 or chunk_index < 0 or chunk_index >= total_chunks:
            return Response({"error": "分片参数不合法"}, status=status.HTTP_400_BAD_REQUEST)

        if part.size > max_chunk:
            return Response(
                {
                    "error": (
                        f"单片不能超过 {max_chunk / (1024 * 1024):.0f}MB"
                        f"（KNOWLEDGE_CHUNK_MAX_BYTES），当前 {part.size / (1024 * 1024):.2f}MB"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uid = request.user.id
        storage = _chunk_upload_storage_dir(uid)
        part_path = storage / f"{upload_id}.part"
        meta_path = storage / f"{upload_id}.meta.json"

        if chunk_index == 0:
            if not filename_raw:
                return Response({"error": "第一片需携带 filename"}, status=status.HTTP_400_BAD_REQUEST)
            filename = os.path.basename(filename_raw)
            _cleanup_chunk_session(uid, upload_id)
            force_upload = _to_bool(request.POST.get("force"))
            scar_domain = str(
                request.POST.get("scar_domain") or request.POST.get("domain") or ""
            ).strip()
            meta = {
                "filename": filename,
                "total_chunks": total_chunks,
                "next_chunk_index": 0,
                "accumulated_bytes": 0,
                "user_id": uid,
                "knowledge_base_id": str(knowledge_base.id),
                "force": force_upload,
                "scar_domain": scar_domain,
                "domain": scar_domain,
            }
        else:
            if not meta_path.is_file():
                return Response({"error": "上传会话不存在或已过期，请从第一片重新上传"}, status=status.HTTP_400_BAD_REQUEST)
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("user_id") != uid:
                return Response({"error": "无权继续该上传会话"}, status=status.HTTP_403_FORBIDDEN)
            if str(meta.get("knowledge_base_id")) != str(knowledge_base.id):
                return Response({"error": "知识库与上传会话不一致"}, status=status.HTTP_400_BAD_REQUEST)
            if meta.get("total_chunks") != total_chunks:
                return Response({"error": "total_chunks 与会话不一致"}, status=status.HTTP_400_BAD_REQUEST)
            filename = meta.get("filename") or ""
            if filename_raw and os.path.basename(filename_raw) != filename:
                return Response({"error": "filename 与首片不一致"}, status=status.HTTP_400_BAD_REQUEST)

        if chunk_index != meta["next_chunk_index"]:
            return Response(
                {
                    "error": f"分片顺序错误：期望 chunk_index={meta['next_chunk_index']}，收到 {chunk_index}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        chunk_bytes = part.read()
        new_accumulated = meta["accumulated_bytes"] + len(chunk_bytes)
        if new_accumulated > max_total:
            _cleanup_chunk_session(uid, upload_id)
            return Response(
                {
                    "error": (
                        f"合并后大小将超过上限 {max_total / (1024 * 1024):.0f}MB"
                        f"（KNOWLEDGE_UPLOAD_MAX_BYTES）"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = "wb" if chunk_index == 0 else "ab"
        with open(part_path, mode) as out:
            out.write(chunk_bytes)

        meta["accumulated_bytes"] = new_accumulated
        meta["next_chunk_index"] = chunk_index + 1
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        is_last = chunk_index == total_chunks - 1
        if not is_last:
            return Response(
                {
                    "status": "chunk_received",
                    "chunk_index": chunk_index,
                    "next_chunk_index": meta["next_chunk_index"],
                    "accumulated_bytes": meta["accumulated_bytes"],
                },
                status=status.HTTP_200_OK,
            )

        # 最后一片：合并完成
        if meta["next_chunk_index"] != total_chunks:
            _cleanup_chunk_session(uid, upload_id)
            return Response({"error": "分片数量与声明不一致"}, status=status.HTTP_400_BAD_REQUEST)

        raw_content = part_path.read_bytes()
        _cleanup_chunk_session(uid, upload_id)

        if len(raw_content) != meta["accumulated_bytes"]:
            return Response({"error": "合并文件校验失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        fname = meta.get("filename") or "unnamed"
        force_upload = bool(meta.get("force", False))
        scar_domain = str(meta.get("scar_domain") or meta.get("domain") or "").strip()
        return _finalize_document_from_bytes(
            knowledge_base,
            raw_content,
            fname,
            len(raw_content),
            part.content_type or "application/octet-stream",
            force_upload,
            scar_domain=scar_domain,
        )

    except Exception as e:
        logger.error("分片上传失败: %s", e, exc_info=True)
        return Response(
            {"error": f"分片上传失败: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_bim_document(request, knowledge_base_id):
    """
    BIM/IFC/JSON 上传：bim_processor → construction schema → SCAR 编译（T7.1/T7.2）。
    LLM 标签无 source_ref 不得入定案。
    """
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role="editor")
    if "file" not in request.FILES:
        return Response({"error": "请上传 .json 或 .ifc 文件"}, status=status.HTTP_400_BAD_REQUEST)

    uploaded = request.FILES["file"]
    filename = os.path.basename(uploaded.name or "bim.json")
    lower = filename.lower()
    if not (lower.endswith(".json") or lower.endswith(".ifc")):
        return Response({"error": "仅支持 .json / .ifc"}, status=status.HTTP_400_BAD_REQUEST)

    raw = uploaded.read()
    try:
        from .bim_processor import (
            bim_json_to_elements_list,
            bim_json_to_searchable_text,
            bim_to_json,
        )
        from apps.scar.services.bim_bridge import bim_payload_to_construction_site
        from apps.scar.services.ingest import compile_document
    except Exception as e:
        return Response({"error": f"BIM 模块不可用: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        bim_json = bim_to_json(raw, filename)
        bim_json = _ensure_json_serializable(bim_json)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    scar_compile = None
    construction_site = None
    bridge_error = None
    try:
        construction_site = bim_payload_to_construction_site(bim_json)
        content = json.dumps(construction_site, ensure_ascii=False, indent=2)
    except ValueError as e:
        bridge_error = str(e)
        # 回退：仅入库可检索文本（不写 StructureUnit）
        content = bim_json_to_searchable_text(bim_json)
        construction_site = None

    content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
    force = _to_bool(request.data.get("force"))
    existing = Document.objects.filter(knowledge_base=knowledge_base, content_hash=content_hash).first()
    if existing and not force:
        return Response(
            {
                "error": "检测到重复 BIM 文档",
                "duplicate_of": str(existing.id),
                "hint": "传 force=true 可强制覆盖",
            },
            status=status.HTTP_409_CONFLICT,
        )

    meta = {
        "bim": True,
        "bim_meta": bim_json.get("bim_meta") or {},
        "bim_elements": bim_json_to_elements_list(bim_json)[:200],
        "bim_bridge_error": bridge_error,
        "source_file": filename,
    }

    if existing and force:
        document = existing
        document.title = filename
        document.content = content
        document.content_type = "text"
        document.file_path = filename
        document.file_size = len(raw)
        document.content_hash = content_hash
        document.metadata = {**(document.metadata or {}), **meta}
        document.save()
    else:
        document = Document.objects.create(
            knowledge_base=knowledge_base,
            title=filename,
            content=content,
            content_type="text",
            file_path=filename,
            file_size=len(raw),
            content_hash=content_hash,
            metadata=meta,
        )

    # 向量化（B0 基线）
    try:
        emb = VectorizationService().vectorize_text(content)
        document.vector_embedding = emb.tolist() if hasattr(emb, "tolist") else list(emb)
        document.save(update_fields=["vector_embedding", "updated_at"])
    except Exception as e:
        logger.warning("BIM 文档向量化失败: %s", e)

    if construction_site is not None:
        scar_compile = compile_document(
            document,
            domain="construction",
            raw_text=content,
            vectorize=True,
        )
        document.refresh_from_db()
    else:
        document.scar_domain = "construction"
        document.compile_status = "failed"
        md = document.metadata or {}
        md["scar_compile_error"] = bridge_error or "bim_bridge_failed"
        document.metadata = md
        document.save(update_fields=["scar_domain", "compile_status", "metadata", "updated_at"])

    serializer = DocumentSerializer(document)
    data = serializer.data
    data["bim_bridged"] = construction_site is not None
    data["scar_compile"] = scar_compile
    if bridge_error:
        data["warning"] = bridge_error
    return Response(data, status=status.HTTP_201_CREATED)


def _ensure_json_serializable(obj: Any) -> Any:
    """递归确保对象可被 JSON 序列化（避免 IFC/第三方返回的非标准类型导致 500）。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode('utf-8', errors='replace')
    if isinstance(obj, dict):
        return {str(k): _ensure_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_ensure_json_serializable(v) for v in obj]
    return str(obj)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_documents_from_json(request, knowledge_base_id):
    """异步批量导入 JSON 文档 - 创建 ImportJob 并触发后台任务"""
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')

    try:
        if 'file' not in request.FILES:
            return Response({
                'error': '请上传 JSON 文件'
            }, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['file']
        max_file_size = 100 * 1024 * 1024  # 100MB
        if uploaded_file.size > max_file_size:
            return Response({
                'error': f'JSON 文件不能超过 100MB，当前大小为 {uploaded_file.size / 1024 / 1024:.2f} MB'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证 JSON 格式
        raw_bytes = uploaded_file.read()
        try:
            data = json.loads(raw_bytes.decode('utf-8'))
            if isinstance(data, dict):
                entries = data.get('documents', [])
            else:
                entries = data
            if not isinstance(entries, list):
                return Response({
                    'error': 'JSON 顶层必须是数组或包含 documents 数组'
                }, status=status.HTTP_400_BAD_REQUEST)
        except json.JSONDecodeError as exc:
            return Response({
                'error': f'JSON 解析失败: {exc}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 保存文件到存储
        file_path = f'imports/{knowledge_base_id}/{uploaded_file.name}'
        saved_path = default_storage.save(file_path, ContentFile(raw_bytes))

        # 创建 ImportJob
        import_job = ImportJob.objects.create(
            knowledge_base=knowledge_base,
            owner=request.user,
            file_path=saved_path,
            original_filename=uploaded_file.name,
            total_documents=len(entries),
            status=ImportJob.Status.PENDING
        )

        # 触发任务：有 broker + worker 时用队列；否则 settings 中 CELERY_TASK_ALWAYS_EAGER 会在进程内执行
        job_id_str = str(import_job.id)
        try:
            process_import_job.delay(job_id_str)
        except Exception as exc:
            logger.warning("Celery delay 失败，尝试同步 apply: %s", exc)
            try:
                process_import_job.apply(args=[job_id_str])
            except Exception as sync_exc:
                logger.error("同步执行导入任务失败: %s", sync_exc, exc_info=True)
                import_job.mark_failed(f'无法执行导入任务: {sync_exc}')
                return Response({
                    'error': '无法启动后台导入任务，请稍后重试'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'message': 'JSON 导入任务已创建',
            'job_id': str(import_job.id),
            'status': import_job.status,
            'knowledge_base_id': str(knowledge_base.id)
        }, status=status.HTTP_201_CREATED)

    except Exception as exc:
        logger.error(f"JSON 导入失败: {exc}", exc_info=True)
        return Response({'error': f'JSON 导入失败: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_job_detail(request, knowledge_base_id, job_id):
    """查询 ImportJob 状态和进度"""
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='viewer')
    import_job = get_object_or_404(ImportJob, pk=job_id, knowledge_base=knowledge_base)

    return Response({
        'id': str(import_job.id),
        'status': import_job.status,
        'total_documents': import_job.total_documents,
        'created_documents': import_job.created_documents,
        'vectorized_documents': import_job.vectorized_documents,
        'skipped_documents': import_job.skipped_documents,
        'skipped_samples': import_job.skipped_samples,
        'error_message': import_job.error_message,
        'created_at': import_job.created_at,
        'started_at': import_job.started_at,
        'finished_at': import_job.finished_at,
        'progress_percentage': (
            int((import_job.created_documents / import_job.total_documents * 100))
            if import_job.total_documents > 0 else 0
        )
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_import_job(request, knowledge_base_id, job_id):
    """取消 ImportJob"""
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')
    import_job = get_object_or_404(ImportJob, pk=job_id, knowledge_base=knowledge_base)

    if import_job.is_final:
        return Response({
            'error': f'任务已结束，无法取消（状态：{import_job.status}）'
        }, status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason', '用户取消')
    import_job.mark_canceled(reason)

    return Response({
        'message': '导入任务已取消',
        'job_id': str(import_job.id),
        'status': import_job.status
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_job_list(request, knowledge_base_id):
    """获取知识库的所有 ImportJob 列表"""
    knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='viewer')
    jobs = ImportJob.objects.filter(knowledge_base=knowledge_base).order_by('-created_at')[:50]

    return Response({
        'results': [{
            'id': str(job.id),
            'status': job.status,
            'original_filename': job.original_filename,
            'total_documents': job.total_documents,
            'created_documents': job.created_documents,
            'vectorized_documents': job.vectorized_documents,
            'skipped_documents': job.skipped_documents,
            'created_at': job.created_at,
            'finished_at': job.finished_at,
            'progress_percentage': (
                int((job.created_documents / job.total_documents * 100))
                if job.total_documents > 0 else 0
            )
        } for job in jobs]
    })


class _AnalyzeDocumentPermission(IsAuthenticated):
    """默认需登录；仅 ENABLE_ANONYMOUS_DOC_ANALYZE=true 时允许匿名（公网默认关闭）。"""

    def has_permission(self, request, view):
        from django.conf import settings as dj_settings

        if getattr(dj_settings, "ENABLE_ANONYMOUS_DOC_ANALYZE", False):
            return True
        return super().has_permission(request, view)


@api_view(['POST'])
@permission_classes([_AnalyzeDocumentPermission])
def analyze_document(request):
    """分析文档内容（不保存）。公网默认需登录，避免匿名消耗算力。"""
    try:
        content = request.data.get('content', '')
        filename = request.data.get('filename', '')
        
        if not content:
            return Response({
                'error': '请提供文档内容'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        analyzer = DocumentAnalyzer()
        analysis_result = analyzer.analyze_document(content, filename)
        
        return Response({
            'relevance': analysis_result.relevance.value,
            'content_type': analysis_result.content_type.value,
            'confidence': analysis_result.confidence,
            'quality_score': analysis_result.quality_score,
            'keywords': analysis_result.keywords,
            'issues': analysis_result.issues,
            'suggestions': analysis_result.suggestions
        })
        
    except Exception as e:
        logger.error(f"文档分析失败: {e}")
        return Response({
            'error': f'文档分析失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vectorize_document(request, knowledge_base_id, document_id):
    """向量化指定文档"""
    try:
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')
        document = get_object_or_404(Document, pk=document_id, knowledge_base=knowledge_base)
        
        if not document.content:
            return Response({
                'error': '文档内容为空，无法向量化'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 向量化文档内容
        vectorizer = VectorizationService()
        embedding = vectorizer.vectorize_text(document.content)
        
        # 保存向量
        document.vector_embedding = embedding.tolist()
        document.save()
        
        return Response({
            'message': '文档向量化成功',
            'document_id': str(document.id),
            'vector_dimension': len(embedding)
        })
        
    except Exception as e:
        logger.error(f"文档向量化失败: {e}")
        return Response({
            'error': f'文档向量化失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vectorize_knowledge_base(request, knowledge_base_id):
    """批量向量化知识库中的所有文档"""
    try:
        knowledge_base = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='editor')
        documents = knowledge_base.documents.filter(content__isnull=False).exclude(content='')
        
        if not documents.exists():
            return Response({
                'error': '知识库中没有可向量化的文档'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        vectorizer = VectorizationService()
        success_count = 0
        error_count = 0
        
        for document in documents:
            try:
                embedding = vectorizer.vectorize_text(document.content)
                document.vector_embedding = embedding.tolist()
                document.save()
                success_count += 1
            except Exception as e:
                logger.error(f"文档 {document.id} 向量化失败: {e}")
                error_count += 1
        
        return Response({
            'message': f'批量向量化完成',
            'total_documents': documents.count(),
            'success_count': success_count,
            'error_count': error_count
        })
        
    except Exception as e:
        logger.error(f"批量向量化失败: {e}")
        return Response({
            'error': f'批量向量化失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def retrieval_strategies(request):
    """获取可用的检索策略配置"""
    try:
        strategy_manager = RetrievalStrategyManager()
        
        strategies = {}
        for strategy_name in ['hybrid', 'vector_only', 'bm25_only']:
            strategies[strategy_name] = strategy_manager.get_strategy_config(strategy_name)
        
        return Response({
            'strategies': strategies,
            'default_strategy': 'hybrid'
        })
    except Exception as e:
        logger.error(f"获取检索策略失败: {e}")
        return Response({'error': f'获取检索策略失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_retrieval(request):
    """检索策略与证据预览：返回证据条目（source/score/rank/dedupe_reason）"""
    try:
        query = request.data.get('query', '')
        knowledge_base_id = request.data.get('knowledge_base_id')
        top_k = int(request.data.get('top_k', 5))
        score_threshold = float(request.data.get('score_threshold', 0.2))
        alpha = float(request.data.get('alpha', 0.5))  # 融合权重 [0,1]
        strategy = request.data.get('strategy', 'hybrid')  # 检索策略

        if not query:
            return Response({'error': 'query 不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        # 验证知识库权限
        if knowledge_base_id:
            kb = _get_kb_or_404_for_user(request.user, knowledge_base_id, min_role='viewer')
        else:
            kb = None

        # 使用高级检索服务
        retrieval_service = AdvancedRetrievalService()
        strategy_manager = RetrievalStrategyManager()
        
        # 执行检索策略
        result = strategy_manager.execute_strategy(
            strategy_name=strategy,
            query=query,
            knowledge_base_id=knowledge_base_id,
            custom_params={
                'top_k': top_k,
                'score_threshold': score_threshold,
                'alpha': alpha,
                'enable_deduplication': True
            }
        )

        # 添加rank字段
        evidence = result.get('evidence', [])
        for i, item in enumerate(evidence):
            item['rank'] = i + 1

        return Response({
            'query': query,
            'strategy': strategy,
            'params': {
                'top_k': top_k,
                'score_threshold': score_threshold,
                'alpha': alpha
            },
            'evidence': evidence,
            'total_found': result.get('total_found', len(evidence)),
            'unique_found': result.get('unique_found', len([e for e in evidence if e.get('dedupe_reason') == 'unique']))
        })
    except Exception as e:
        logger.error(f"检索预览失败: {e}")
        return Response({'error': f'检索预览失败: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
