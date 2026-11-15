"""Agent 进化治理：自动合并条件（低风险仅增量）。"""
from __future__ import annotations

import os
from typing import Any, Dict

from django.contrib.auth import get_user_model

from apps.skills.evolution.guard import agent_payload_passes_domain_guard


def should_auto_apply_agent_payload(agent, payload: Dict[str, Any], provenance: str) -> bool:
    """
    evolution_governance=auto 时：仅当
    - LLM 置信度 >= AGENT_EVOLUTION_AUTO_MIN_CONFIDENCE（默认 0.85）
    - suggested 相对当前仅为「增量」（不删已有 id）
    - 新增 id 个数 <= AGENT_EVOLUTION_AUTO_MAX_ADD（默认 5）
    """
    if getattr(agent, "evolution_governance", "") != "auto":
        return False
    if not agent_payload_passes_domain_guard(payload):
        return False
    if provenance != "llm_deepseek":
        # 模板提案不自动合并，避免误伤
        return False
    try:
        min_conf = float(os.getenv("AGENT_EVOLUTION_AUTO_MIN_CONFIDENCE", "0.85") or "0.85")
    except ValueError:
        min_conf = 0.85
    try:
        max_add = int(os.getenv("AGENT_EVOLUTION_AUTO_MAX_ADD", "5") or "5")
    except ValueError:
        max_add = 5

    conf = float(payload.get("confidence") or 0)
    if conf < min_conf:
        return False

    prev = list(agent.skills or [])
    sug = list(payload.get("suggested_skills") or [])
    if prev == sug:
        return False
    pset, sset = set(prev), set(sug)
    if not pset.issubset(sset):
        return False
    if len(sset - pset) > max_add:
        return False
    return True


def system_user_for_auto_apply():
    """自动合并时 reviewed_by 占位（取首个超管，否则 None）。"""
    User = get_user_model()
    u = User.objects.filter(is_superuser=True).order_by("id").first()
    return u
