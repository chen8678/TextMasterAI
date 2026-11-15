"""格式提取、表格与引用结构辅助（纯文字；自进化 domain=format_extraction）。"""
from __future__ import annotations

from .rag_answer import execute as _rag_execute


def execute(**kwargs):
    return _rag_execute(**kwargs)
