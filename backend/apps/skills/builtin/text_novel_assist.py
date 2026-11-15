"""小说/创意文本一致性检索辅助（纯文字；自进化 domain=novel_writing）。"""
from __future__ import annotations

from .rag_answer import execute as _rag_execute


def execute(**kwargs):
    return _rag_execute(**kwargs)
