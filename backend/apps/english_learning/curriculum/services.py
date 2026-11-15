"""系统预置英语 curriculum 知识库：创建、导入、用户只读挂载。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.knowledge.models import Document, KnowledgeBase, KnowledgeBaseMember

from .constants import (
    CURRICULUM_TIERS,
    DEFAULT_CHUNK_SIZE,
    MANIFEST_PATH,
    RAW_DIR,
    SYSTEM_KB_FLAG,
    SYSTEM_KB_SETTINGS_KEY,
    SYSTEM_USERNAME,
    TIER_BY_SLUG,
    CurriculumTier,
    tier_for_level_tags,
)
from .parsers import chunk_entries, entries_to_markdown, parse_tier_file

logger = logging.getLogger(__name__)


def get_curriculum_system_user():
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=SYSTEM_USERNAME,
        defaults={
            "email": "curriculum@system.local",
            "is_active": False,
            "is_staff": True,
        },
    )
    if created or user.has_usable_password():
        user.set_unusable_password()
        user.is_active = False
        user.save(update_fields=["password", "is_active"])
    return user


def _kb_settings(tier: CurriculumTier) -> dict:
    return {
        SYSTEM_KB_FLAG: True,
        SYSTEM_KB_SETTINGS_KEY: tier.slug,
        "curriculum_title": tier.title,
        "curriculum_source": tier.source,
    }


def get_system_curriculum_kbs():
    owner = get_curriculum_system_user()
    return KnowledgeBase.objects.filter(owner=owner, settings__is_system_curriculum=True).order_by("title")


def _find_tier_kb(tier: CurriculumTier) -> Optional[KnowledgeBase]:
    owner = get_curriculum_system_user()
    return KnowledgeBase.objects.filter(
        owner=owner,
        settings__is_system_curriculum=True,
        settings__curriculum_slug=tier.slug,
    ).first()


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()


def _vectorize_document(document: Document, *, skip_vectorize: bool) -> None:
    if skip_vectorize:
        return
    try:
        from apps.knowledge.vectorization_service import VectorizationService

        vectorizer = VectorizationService()
        embedding = vectorizer.vectorize_text(document.content)
        document.vector_embedding = embedding.tolist()
        document.save(update_fields=["vector_embedding", "updated_at"])
    except Exception as exc:
        logger.warning("curriculum doc vectorize failed %s: %s", document.title, exc)


def import_tier_into_kb(
    tier: CurriculumTier,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    skip_vectorize: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """将 tier 对应 raw 文件导入系统 KB；已存在且 manifest 未变则跳过。"""
    source_path = RAW_DIR / tier.source_file
    entries = parse_tier_file(source_path, tier.source)
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()

    owner = get_curriculum_system_user()
    kb = _find_tier_kb(tier)
    if kb is None:
        kb = KnowledgeBase.objects.create(
            title=tier.title,
            description=tier.description,
            owner=owner,
            category="education",
            settings=_kb_settings(tier),
        )
        created_kb = True
    else:
        created_kb = False
        st = dict(kb.settings or {})
        if st.get("source_sha256") == source_sha and not force:
            doc_count = kb.documents.count()
            return {
                "slug": tier.slug,
                "kb_id": str(kb.id),
                "created_kb": False,
                "skipped": True,
                "documents": doc_count,
                "words": st.get("word_count", 0),
            }

    if force:
        kb.documents.all().delete()

    batches = chunk_entries(entries, chunk_size)
    created_docs = 0
    for idx, batch in enumerate(batches, start=1):
        md = entries_to_markdown(tier.title, idx, batch)
        title = f"{tier.title} · 第{idx}批"
        ch = _content_hash(md)
        existing = Document.objects.filter(knowledge_base=kb, content_hash=ch).first()
        if existing:
            continue
        doc = Document.objects.create(
            knowledge_base=kb,
            title=title,
            content=md,
            content_type="markdown",
            file_path=f"curriculum/{tier.slug}/{idx:03d}.md",
            content_hash=ch,
            metadata={
                "curriculum_slug": tier.slug,
                "batch_index": idx,
                "word_count": len(batch),
            },
        )
        _vectorize_document(doc, skip_vectorize=skip_vectorize)
        created_docs += 1

    st = dict(kb.settings or {})
    st.update(_kb_settings(tier))
    st["source_sha256"] = source_sha
    st["word_count"] = len(entries)
    st["document_count"] = kb.documents.count()
    st["chunk_size"] = chunk_size
    kb.settings = st
    kb.save(update_fields=["settings", "updated_at"])

    return {
        "slug": tier.slug,
        "kb_id": str(kb.id),
        "created_kb": created_kb,
        "skipped": False,
        "documents_created": created_docs,
        "documents": kb.documents.count(),
        "words": len(entries),
    }


def init_all_curriculum_kbs(
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    skip_vectorize: bool = False,
    force: bool = False,
    slugs: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    tiers = CURRICULUM_TIERS
    if slugs:
        tiers = [TIER_BY_SLUG[s] for s in slugs if s in TIER_BY_SLUG]
    results = []
    for tier in tiers:
        results.append(
            import_tier_into_kb(
                tier,
                chunk_size=chunk_size,
                skip_vectorize=skip_vectorize,
                force=force,
            )
        )
    _write_manifest(results)
    return results


def _write_manifest(results: List[Dict[str, Any]]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tiers": results,
        "sources": [
            {
                "slug": t.slug,
                "title": t.title,
                "source": t.source,
                "file": t.source_file,
            }
            for t in CURRICULUM_TIERS
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_user_curriculum_access(user) -> int:
    """为 user 挂载全部系统预置库（viewer）。返回新建 membership 数。"""
    if not user or not getattr(user, "id", None):
        return 0
    if getattr(user, "username", None) == SYSTEM_USERNAME:
        return 0
    created = 0
    for kb in get_system_curriculum_kbs():
        _, was_created = KnowledgeBaseMember.objects.get_or_create(
            knowledge_base=kb,
            user=user,
            defaults={"role": KnowledgeBaseMember.Role.VIEWER},
        )
        if was_created:
            created += 1
    if created:
        try:
            from apps.knowledge.views import _invalidate_kb_list_cache_for_user

            _invalidate_kb_list_cache_for_user(user.id)
        except Exception:
            pass
    return created


def backfill_all_users_curriculum_access() -> int:
    User = get_user_model()
    total = 0
    for user in User.objects.exclude(username=SYSTEM_USERNAME).iterator():
        total += ensure_user_curriculum_access(user)
    return total


def list_curriculum_for_user(user) -> List[Dict[str, Any]]:
    rows = []
    for kb in get_system_curriculum_kbs():
        slug = (kb.settings or {}).get(SYSTEM_KB_SETTINGS_KEY, "")
        rows.append(
            {
                "slug": slug,
                "title": kb.title,
                "knowledge_base_id": str(kb.id),
                "document_count": kb.documents.count(),
                "word_count": (kb.settings or {}).get("word_count"),
                "description": kb.description,
            }
        )
    return rows


def get_recommended_curriculum_kb(user, level_tags: Optional[List[str]] = None) -> Optional[KnowledgeBase]:
    tier = tier_for_level_tags(level_tags)
    kb = _find_tier_kb(tier)
    if kb is None:
        return None
    ensure_user_curriculum_access(user)
    return kb


def curriculum_payload_for_user(user, level_tags: Optional[List[str]] = None) -> Dict[str, Any]:
    ensure_user_curriculum_access(user)
    tier = tier_for_level_tags(level_tags)
    rec = _find_tier_kb(tier)
    return {
        "libraries": list_curriculum_for_user(user),
        "recommended_slug": tier.slug,
        "recommended_knowledge_base_id": str(rec.id) if rec else None,
    }
