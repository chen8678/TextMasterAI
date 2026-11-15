"""
MVP-B M1：english_orchestrator 自动 intent 路由（keyword 优先，可选 LLM 增强）。
显式 english_delegate 仍由 views 优先处理。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from apps.english_learning.skill_handlers.llm_utils import chat_completion

ENGLISH_DELEGATE_TO_AGENT = {
    "vocab": "english_vocab",
    "grammar": "english_grammar",
    "listen": "english_listen",
}

VALID_ENGLISH_DELEGATE_SLOTS = frozenset(ENGLISH_DELEGATE_TO_AGENT.keys())

_AUTO_DELEGATE_ALIASES = frozenset({"", "default", "auto"})

# (slot, keywords) — 先匹配先返回；简版规则与蓝图 F2 一致
_KEYWORD_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "grammar",
        (
            "语法",
            "时态",
            "从句",
            "句型",
            "语态",
            "冠词",
            "介词",
            "grammar",
            "tense",
            "clause",
        ),
    ),
    (
        "listen",
        (
            "听力",
            "听写",
            "listening",
            "听懂",
            "耳朵",
            "audio",
        ),
    ),
    (
        "vocab",
        (
            "单词",
            "词汇",
            "vocabulary",
            "背单词",
            "生词",
            "释义",
            "拼写",
            "phrase",
        ),
    ),
)


def is_auto_delegate_value(raw: str) -> bool:
    return (raw or "").strip().lower() in _AUTO_DELEGATE_ALIASES


def classify_english_delegate_by_keywords(question: str) -> Optional[str]:
    """规则 intent：命中则返回 vocab / grammar / listen。"""
    text = (question or "").strip().lower()
    if not text:
        return None
    for slot, keywords in _KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in text:
                return slot
    return None


def _parse_delegate_json(raw: str) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        lines = text.splitlines()
        if lines and not lines[0].lstrip().startswith("{"):
            text = "\n".join(lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'"delegate"\s*:\s*"(\w+)"', text, re.I)
        if not m:
            return None
        data = {"delegate": m.group(1)}
    slot = str(data.get("delegate") or "").strip().lower()
    if slot in ("default", "none", ""):
        return None
    if slot in VALID_ENGLISH_DELEGATE_SLOTS:
        return slot
    return None


def classify_english_delegate_by_llm(question: str, *, model: str = "deepseek-chat") -> Optional[str]:
    """LLM intent（无 API Key 或失败时返回 None）。"""
    q = (question or "").strip()
    if not q:
        return None
    system = (
        "You classify English learning user questions for routing to specialist tutors. "
        'Reply with JSON only: {"delegate":"vocab"|"grammar"|"listen"|"default"}. '
        "vocab=words/phrases; grammar=grammar/tense/clauses; listen=listening comprehension; "
        "default=general or unclear."
    )
    raw = chat_completion(system=system, user=q[:2000], model=model, max_chars=2000)
    return _parse_delegate_json(raw)


def resolve_english_delegate_auto(
    question: str,
    *,
    model: str = "deepseek-chat",
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    自动路由：keyword →（可选）LLM → 无匹配则保持主编排。
    返回 slot、source、agent_id（可 None）。
    """
    slot = classify_english_delegate_by_keywords(question)
    if slot:
        return {
            "slot": slot,
            "source": "keyword",
            "agent_id": ENGLISH_DELEGATE_TO_AGENT.get(slot),
        }
    if use_llm:
        slot = classify_english_delegate_by_llm(question, model=model)
        if slot:
            return {
                "slot": slot,
                "source": "llm",
                "agent_id": ENGLISH_DELEGATE_TO_AGENT.get(slot),
            }
    return {"slot": None, "source": "none", "agent_id": None}
