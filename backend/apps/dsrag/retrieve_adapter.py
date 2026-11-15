"""检索适配器：封装 index.retrieve，固定 top_k（P06/P13）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apps.dsrag.config import load_base_config
from apps.dsrag.index import build_context, retrieve
from apps.dsrag.schema import Candidate

__all__ = ["retrieve_chunks", "build_context"]


def retrieve_chunks(
    query: str,
    k: int | None = None,
    *,
    index_dir: Path | str | None = None,
    base: dict[str, Any] | None = None,
) -> list[Candidate]:
    """q → top-k Candidate；k 默认读 base.yaml top_k。"""
    base = base or load_base_config()
    return retrieve(query, k=k, index_dir=index_dir, base=base)
