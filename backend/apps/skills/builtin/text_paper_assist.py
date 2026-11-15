"""论文/学术资料检索与大纲辅助（纯文字；自进化 domain=paper_writing）。"""
from __future__ import annotations

from .rag_answer import execute as _rag_execute


def execute(**kwargs):
    return _rag_execute(**kwargs)
