"""
定向自进化守卫：领域白名单 + 草案内容禁区（私有知识库文字问答产品边界）。

对齐《自进化 Skill 与 Agent 的定向控制方案》：禁止向多模态/游戏/任意外部能力漂移。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

# 日志检索前缀（P1-T42）：grep 「evolution_guard」
LOG_PREFIX = "[evolution_guard]"

# 未显式标注 evolution_domain 的 Skill 默认归入「通用文字问答增强」
DEFAULT_SKILL_EVOLUTION_DOMAIN = "qa_enhancement"

# 草案中若出现下列片段，视为超出「纯文字知识库」产品边界，拒绝落库
_DEFAULT_FORBIDDEN_MARKERS = (
    "图像生成",
    "视频生成",
    "文生图",
    "图生视频",
    "游戏引擎",
    "外挂",
    "多模态",
    "stable diffusion",
    "midjourney",
    "dall-e",
    "语音合成",
    "语音识别",
    "视频剪辑",
    "调用公网",
    "爬取互联网",
)


def _forbidden_markers() -> Tuple[str, ...]:
    extra = getattr(settings, "EVOLUTION_FORBIDDEN_MARKERS", None)
    if isinstance(extra, (list, tuple)) and extra:
        return tuple(str(x) for x in extra)
    return _DEFAULT_FORBIDDEN_MARKERS


def evolution_domains_allowed() -> frozenset:
    return frozenset(getattr(settings, "EVOLUTION_ALLOWED_DOMAINS", frozenset()))


def evolution_guard_enabled() -> bool:
    return getattr(settings, "EVOLUTION_ENFORCE_DOMAIN_GUARD", True)


def get_skill_evolution_domain(skill) -> str:
    m = getattr(skill, "metadata", None) or {}
    if not isinstance(m, dict):
        m = {}
    d = (m.get("evolution_domain") or m.get("domain_tag") or "").strip().lower()
    return d or DEFAULT_SKILL_EVOLUTION_DOMAIN


def skill_allowed_for_evolution(skill) -> Tuple[bool, str]:
    """Skill 是否允许进入自进化调度（按 metadata.evolution_domain 与白名单）。"""
    if not evolution_guard_enabled():
        return True, "guard_off"
    dom = get_skill_evolution_domain(skill)
    allowed = evolution_domains_allowed()
    if dom in allowed:
        return True, "ok"
    logger.warning("%s skill evolution blocked: skill_id=%s domain=%s", LOG_PREFIX, getattr(skill, "id", ""), dom)
    return False, f"domain_not_allowed:{dom}"


def draft_markdown_allowed(markdown: str) -> Tuple[bool, str]:
    """进化草案 Markdown 是否允许写入 staging（禁区词）。"""
    if not evolution_guard_enabled():
        return True, "guard_off"
    text = markdown or ""
    for marker in _forbidden_markers():
        if marker.lower() in text.lower():
            logger.warning("%s skill evolution draft blocked: forbidden_marker=%s", LOG_PREFIX, marker)
            return False, f"forbidden_marker:{marker}"
    return True, "ok"


def effective_domain_tags(payload: Dict[str, Any]) -> List[str]:
    """从 Agent 提案 payload 解析领域标签（兼容 domain_tag 单值）。"""
    t = payload.get("domain_tags")
    if t is None and payload.get("domain_tag") is not None:
        t = [payload["domain_tag"]]
    if isinstance(t, str):
        t = [t]
    if not isinstance(t, list):
        return []
    return [str(x).strip().lower() for x in t if str(x).strip()]


def agent_payload_passes_domain_guard(payload: Dict[str, Any]) -> bool:
    """Agent 提案是否至少命中一个允许领域（无标签时默认 qa_enhancement）。"""
    if not evolution_guard_enabled():
        return True
    tags = effective_domain_tags(payload)
    if not tags:
        tags = [DEFAULT_SKILL_EVOLUTION_DOMAIN]
    allowed = evolution_domains_allowed()
    return bool(allowed.intersection(tags))
