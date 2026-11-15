"""Skill ID 列表规范化：仅保留「已注册 + DB 启用」的交集。"""
from __future__ import annotations

from typing import List

from apps.skills.models import Skill
from apps.skills.registry import SkillRegistry


def normalize_suggested_skill_ids(skill_ids: List[str]) -> List[str]:
    reg = set(SkillRegistry.list_ids())
    try:
        db_active = set(Skill.objects.filter(is_active=True).values_list("id", flat=True))
    except Exception:
        db_active = set()
    allowed = reg & db_active
    seen = set()
    out: List[str] = []
    for s in skill_ids or []:
        sid = str(s).strip()
        if sid in allowed and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out
