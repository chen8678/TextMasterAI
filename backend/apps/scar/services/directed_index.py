"""将 StructureUnit 写入定向 IndexEntry（可选向量化）。"""

from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

from apps.scar.models import IndexEntry, StructureUnit

logger = logging.getLogger(__name__)


def build_embed_text(unit: StructureUnit) -> str:
    parts = [unit.path, unit.value_norm]
    if unit.unit:
        parts.append(unit.unit)
    meta = unit.metadata or {}
    if meta.get("field_key"):
        parts.append(str(meta["field_key"]))
    return " ".join(parts)


@transaction.atomic
def rebuild_index_for_document(document, units: Iterable[StructureUnit], *, vectorize: bool = True) -> int:
    IndexEntry.objects.filter(document=document).delete()
    entries: list[IndexEntry] = []
    for unit in units:
        if unit.provenance == StructureUnit.Provenance.LLM_SUGGEST:
            continue
        entries.append(
            IndexEntry(
                document=document,
                unit=unit,
                embed_text=build_embed_text(unit),
                domain=unit.domain,
            )
        )
    IndexEntry.objects.bulk_create(entries)

    if not vectorize:
        return len(entries)

    try:
        from apps.knowledge.vectorization_service import VectorizationService

        vectorizer = VectorizationService()
    except Exception as e:
        logger.warning("SCAR 定向向量化跳过（服务不可用）: %s", e)
        return len(entries)

    for entry in IndexEntry.objects.filter(document=document):
        try:
            emb = vectorizer.vectorize_text(entry.embed_text)
            entry.vector_embedding = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            entry.save(update_fields=["vector_embedding", "updated_at"])
        except Exception as e:
            logger.warning("IndexEntry %s 向量化失败: %s", entry.id, e)
    return len(entries)
