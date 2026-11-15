"""
english_roadmap_finalize：定稿 Markdown → KnowledgeBase Document + 向量化。
"""

import hashlib

from django.shortcuts import get_object_or_404

from apps.knowledge.models import Document, KnowledgeBase
from apps.knowledge.vectorization_service import VectorizationService


def execute(
    roadmap_markdown: str,
    kb_id: str,
    title: str = "我的英语学习路线",
    revision_note: str = "",
    user_id=None,
    **kwargs,
) -> dict:
    content = (roadmap_markdown or "").strip()
    if not content:
        raise ValueError("roadmap_markdown 不能为空")

    kb = get_object_or_404(KnowledgeBase, id=kb_id)
    if user_id is not None and str(kb.owner_id) != str(user_id):
        raise PermissionError("无权写入该知识库")

    safe_title = (title or "English Roadmap").strip()[:200]
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    meta = {
        "source": "english_learning_roadmap",
        "revision_note": (revision_note or "")[:500],
    }
    document = Document.objects.create(
        knowledge_base=kb,
        title=safe_title,
        content=content,
        content_type="markdown",
        file_path="",
        content_hash=content_hash,
        metadata=meta,
    )

    try:
        vz = VectorizationService()
        emb = vz.vectorize_text(content)
        document.vector_embedding = emb.tolist()
        document.save(update_fields=["vector_embedding", "updated_at"])
    except Exception:
        pass

    return {
        "document_id": str(document.id),
        "version": 1,
        "knowledge_base_id": str(kb.id),
    }
