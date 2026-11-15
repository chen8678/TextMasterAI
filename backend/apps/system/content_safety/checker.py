"""
内容安全检测：敏感词 / 越狱提示 / 有害内容分类拦截。

日志检索前缀：[content_safety]
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

LOG_PREFIX = "[content_safety]"

BLOCKED_INPUT_MESSAGE = (
    "您的输入包含不适合在学习平台讨论的内容，已被安全策略拦截。"
    "请围绕课程学习、英语练习或知识库相关内容提问。"
)
BLOCKED_OUTPUT_MESSAGE = (
    "抱歉，系统检测到回复内容可能包含不适宜信息，已自动拦截。"
    "请尝试换一种与学习相关的方式提问。"
)

_CATEGORY_LABELS = {
    "violence": "暴力有害",
    "pornography": "色情低俗",
    "drugs": "毒品违法",
    "illegal": "违法犯罪",
    "self_harm": "自残自杀",
    "hate": "仇恨歧视",
    "politics_sensitive": "敏感政治",
    "jailbreak": "越狱/绕过安全",
}

_KEYWORDS_CACHE: Optional[Dict[str, List[str]]] = None


def content_safety_enabled() -> bool:
    return getattr(settings, "CONTENT_SAFETY_ENABLED", True)


def _keywords_path() -> Path:
    custom = getattr(settings, "CONTENT_SAFETY_KEYWORDS_PATH", None)
    if custom:
        return Path(custom)
    return Path(__file__).resolve().parent / "keywords.json"


def load_keyword_map() -> Dict[str, List[str]]:
    global _KEYWORDS_CACHE
    if _KEYWORDS_CACHE is not None:
        return _KEYWORDS_CACHE
    path = _keywords_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ex:
        logger.warning("%s failed to load keywords from %s: %s", LOG_PREFIX, path, ex)
        raw = {}
    extra = getattr(settings, "CONTENT_SAFETY_EXTRA_KEYWORDS", None) or {}
    merged: Dict[str, List[str]] = {}
    for cat, words in {**raw, **extra}.items():
        if not isinstance(words, list):
            continue
        merged[str(cat)] = [str(w).strip() for w in words if str(w).strip()]
    _KEYWORDS_CACHE = merged
    return merged


def reload_keyword_cache() -> None:
    global _KEYWORDS_CACHE
    _KEYWORDS_CACHE = None
    load_keyword_map()


def normalize_text(text: str) -> str:
    """折叠空白、全角、零宽字符，便于匹配变体。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text))
    t = re.sub(r"[\u200b-\u200d\ufeff]", "", t)
    t = t.lower()
    t = re.sub(r"\s+", "", t)
    return t


def _match_keyword(norm: str, keyword: str) -> bool:
    kw = normalize_text(keyword)
    if not kw:
        return False
    if len(kw) <= 4:
        return kw in norm
    return kw in norm


def check_text(
    text: str,
    *,
    direction: str = "input",
    channel: str = "chat",
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
  检测文本是否通过安全策略。
  返回 (allowed, detail)；detail 含 category / matched_hint 等。
    """
    if not content_safety_enabled():
        return True, None
    raw = (text or "").strip()
    if not raw:
        return True, None
    if len(raw) > int(getattr(settings, "CONTENT_SAFETY_MAX_TEXT_LEN", 32000)):
        return False, {
            "category": "oversized",
            "category_label": "文本过长",
            "direction": direction,
            "channel": channel,
            "message": "输入内容过长，请缩短后重试。",
        }
    norm = normalize_text(raw)
    for category, words in load_keyword_map().items():
        for word in words:
            if _match_keyword(norm, word):
                return False, {
                    "category": category,
                    "category_label": _CATEGORY_LABELS.get(category, category),
                    "direction": direction,
                    "channel": channel,
                    "matched_hint": word[:32],
                    "message": BLOCKED_INPUT_MESSAGE
                    if direction == "input"
                    else BLOCKED_OUTPUT_MESSAGE,
                }
    return True, None


def sanitize_output(
    text: str,
    *,
    channel: str = "chat",
) -> Tuple[str, bool, Optional[Dict[str, Any]]]:
    """模型输出复检；若命中则替换为安全提示。"""
    if not getattr(settings, "CONTENT_SAFETY_CHECK_OUTPUT", True):
        return text or "", False, None
    allowed, detail = check_text(text, direction="output", channel=channel)
    if allowed:
        return text or "", False, None
    return BLOCKED_OUTPUT_MESSAGE, True, detail


def log_content_safety_event(
    *,
    user=None,
    direction: str,
    channel: str,
    category: str,
    category_label: str = "",
    matched_hint: str = "",
    blocked: bool = True,
    request=None,
    text_preview: str = "",
) -> None:
    """写入审计表与结构化日志（预览脱敏截断）。"""
    preview = (text_preview or "")[:120]
    if preview:
        preview = preview.replace("\n", " ")
    logger.warning(
        "%s blocked=%s direction=%s channel=%s category=%s user=%s hint=%s",
        LOG_PREFIX,
        blocked,
        direction,
        channel,
        category,
        getattr(user, "id", None),
        matched_hint[:32] if matched_hint else "",
    )
    if not getattr(settings, "CONTENT_SAFETY_AUDIT_ENABLED", True):
        return
    try:
        from apps.system.models import ContentSafetyEvent

        ip = None
        ua = ""
        if request is not None:
            ip = request.META.get("REMOTE_ADDR")
            ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]
        ContentSafetyEvent.objects.create(
            user=user if getattr(user, "id", None) else None,
            direction=direction,
            channel=channel,
            category=category,
            category_label=category_label or _CATEGORY_LABELS.get(category, category),
            matched_hint=(matched_hint or "")[:64],
            blocked=blocked,
            text_preview=preview,
            ip_address=ip,
            user_agent=ua,
        )
    except Exception as ex:
        logger.exception("%s audit persist failed: %s", LOG_PREFIX, ex)


def guard_user_text(
    text: str,
    *,
    user=None,
    direction: str = "input",
    channel: str = "chat",
    request=None,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """统一入口：检测 + 审计。"""
    allowed, detail = check_text(text, direction=direction, channel=channel)
    if allowed:
        return True, None
    assert detail is not None
    log_content_safety_event(
        user=user,
        direction=direction,
        channel=channel,
        category=detail.get("category", "unknown"),
        category_label=detail.get("category_label", ""),
        matched_hint=detail.get("matched_hint", ""),
        blocked=True,
        request=request,
        text_preview=text,
    )
    return False, detail
