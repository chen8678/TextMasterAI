"""
与 `EnglishLearningProfile.session_state` 可双向映射的 TypedDict 草案（Phase-C G2 同步参考）。
不导入 LangGraph；字段与 `research/英语学习定制框架-设计稿-对齐仓库.markdown` §3 对齐。
"""

from __future__ import annotations

from typing import Any, List, TypedDict


class EnglishLearningState(TypedDict, total=False):
    user_id: str
    kb_id: str
    level_tags: List[str]
    placement_choice: str  # "quick" | "full_test"
    assessment_id: str
    assessment_items: List[dict]
    responses: List[dict]
    scores: dict[str, Any]
    gap_summary: str
    focus_dimensions: List[str]
    roadmap_draft_markdown: str
    roadmap_version: int
    roadmap_document_id: str
    active_unit_id: str
    last_turn_agent_trace: List[dict]
    phase: str
