"""
从当前用户知识库采样纯文本段落，供 PRO 沙盒自进化使用（P2-T21）。
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import List

from apps.knowledge.models import Document


@dataclass
class SampleCase:
    doc_id: str
    title: str
    snippet: str


def _slice_snippet(text: str, max_chars: int = 600) -> str:
    s = (text or "").strip().replace("\r\n", "\n")
    if len(s) <= max_chars:
        return s
    return s[:max_chars].rstrip() + "..."


def sample_user_kb_segments(
    *,
    user,
    limit: int = 12,
    min_chars: int = 80,
    max_chars: int = 600,
) -> List[SampleCase]:
    """
    从 user 拥有的知识库文档中抽样文本片段（仅 content_type=text/markdown/pdf/code）。
    """
    docs = list(
        Document.objects.select_related("knowledge_base")
        .filter(
            knowledge_base__owner=user,
            content__isnull=False,
        )
        .exclude(content="")
        .filter(content_type__in=["text", "markdown", "pdf", "code"])
        .order_by("-updated_at")[:200]
    )
    random.shuffle(docs)

    out: List[SampleCase] = []
    for d in docs:
        content = (d.content or "").strip()
        if len(content) < min_chars:
            continue
        out.append(
            SampleCase(
                doc_id=str(d.id),
                title=d.title or "",
                snippet=_slice_snippet(content, max_chars=max_chars),
            )
        )
        if len(out) >= limit:
            break
    return out

