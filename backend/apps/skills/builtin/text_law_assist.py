"""法律/合同类知识库检索辅助（纯文字；自进化 domain=law）。"""
from __future__ import annotations

from .rag_answer import execute as _rag_execute


def execute(**kwargs):
    return _rag_execute(**kwargs)
