"""用户纠正类话术检测（对应技术拆解中的 SignalDetector 关键词）。"""

import re
from typing import FrozenSet

# 可后续改为配置或 DB
_CORRECTION_SUBSTRINGS: FrozenSet[str] = frozenset(
    (
        "不对",
        "错了",
        "不是这个",
        "不应该",
        "应该是",
        "你理解错",
        "重新",
        "纠正",
        "不是我要",
    )
)


def user_hints_correction(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    t = text.strip()
    if len(t) < 2:
        return False
    return any(s in t for s in _CORRECTION_SUBSTRINGS)


def looks_like_failure_followup(user_message: str, last_assistant_answer: str) -> bool:
    """轻量启发：用户极短回复 + 纠正词，视为对上一轮回答的修正（可选扩展）。"""
    if not user_hints_correction(user_message):
        return False
    if len(user_message) < 80:
        return True
    return bool(re.search(r"(答案|回复|上面|刚才)", user_message))
