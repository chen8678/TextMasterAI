"""Skill 过滤工具，移植自 OpenClaw skills/filter.ts"""
from typing import Optional


def normalize_skill_filter(skill_filter: Optional[list]) -> Optional[list]:
    """归一化 skill 白名单列表：trim、去空、去重"""
    if skill_filter is None:
        return None
    return list(
        dict.fromkeys(s.strip() for s in skill_filter if s and str(s).strip())
    )
