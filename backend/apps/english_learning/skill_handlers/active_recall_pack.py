"""
english_active_recall_pack：基于弱项与路线的轻量主动回忆包（MVP 规则模板，无 LLM）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from apps.english_learning.blackboard import normalize_weak_dimensions

_RECALL_BY_DIM: Dict[str, List[Dict[str, str]]] = {
    "vocabulary": [
        {
            "title": "搭配造句",
            "prompt": "从个人路线或错题本中选 3 个词，各写一句英文并自注中文释义。",
        },
        {
            "title": "词形联想",
            "prompt": "写出同一词根的 4 个派生词，并说明词性差异。",
        },
    ],
    "grammar": [
        {
            "title": "规则复述",
            "prompt": "用中文先口述一条薄弱语法规则，再各写一正一反两个英文例句。",
        },
        {
            "title": "纠错微练",
            "prompt": "故意写一句含常见错误的英文，再自行改正并说明依据。",
        },
    ],
    "reading": [
        {
            "title": "要点复述",
            "prompt": "用 3 句英文概括路线中本周阅读任务的主旨（可虚构材料标题）。",
        },
    ],
    "listening": [
        {
            "title": "听写步骤",
            "prompt": "无音频时：选一段 80 词内的英文短文，做「盲听→听写→对照」三步并记录生词。",
        },
    ],
    "writing": [
        {
            "title": "微写作",
            "prompt": "用 120 词以内写一段「昨日学习复盘」，包含 1 个让步状语从句。",
        },
    ],
}

_DEFAULT_PACK = [
    {
        "title": "综合回顾",
        "prompt": "结合当前学习路线，用英文列出今日 3 个可执行小目标（动词开头）。",
    },
]


def execute(
    weak_dimensions=None,
    learner_constraints=None,
    active_unit_id: str = "",
    gap_summary: str = "",
    **kwargs,
) -> dict:
    weak = normalize_weak_dimensions(weak_dimensions)
    lc = learner_constraints or {}
    level_hint = ""
    tags = lc.get("level_tags") or []
    if tags:
        level_hint = str(tags[0])

    pack_items: List[Dict[str, Any]] = []
    seen = set()
    for dim in weak:
        key = str(dim).lower().strip()
        for item in _RECALL_BY_DIM.get(key, _DEFAULT_PACK):
            pid = f"{key}:{item['title']}"
            if pid in seen:
                continue
            seen.add(pid)
            pack_items.append(
                {
                    "id": pid,
                    "dimension": key,
                    "title": item["title"],
                    "prompt": item["prompt"],
                }
            )
    if not pack_items:
        for item in _DEFAULT_PACK:
            pack_items.append(
                {
                    "id": f"general:{item['title']}",
                    "dimension": "general",
                    "title": item["title"],
                    "prompt": item["prompt"],
                }
            )

    unit = (active_unit_id or "").strip() or "current_unit"
    return {
        "schema_version": 1,
        "weak_dimensions": weak,
        "level_hint": level_hint,
        "active_unit_id": unit,
        "gap_excerpt": (gap_summary or "")[:400],
        "pack_items": pack_items[:6],
    }
