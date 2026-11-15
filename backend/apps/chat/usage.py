"""
P0-08：用户日问答配额与全局 token 预算（DB 计数，跨 worker 安全）。
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .models import UsageDaily

logger = logging.getLogger(__name__)


def estimate_tokens(*parts: str) -> int:
    """粗估 token：中英混排约 2 字 ≈ 1 token；无真实 tokenizer 依赖。"""
    total = 0
    for p in parts:
        if p:
            total += len(p)
    return max(1, total // 2) if total else 0


def _today():
    return timezone.localdate()


def _user_limit() -> int:
    return int(getattr(settings, "USER_DAILY_ASK_LIMIT", 50))


def _global_budget():
    raw = getattr(settings, "GLOBAL_DAILY_TOKEN_BUDGET", None)
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def remaining_asks(user) -> int:
    limit = _user_limit()
    usage = UsageDaily.objects.filter(user=user, date=_today()).first()
    used = usage.ask_count if usage else 0
    return max(0, limit - used)


def check_ask_allowed(user):
    """
    问答前校验。通过返回 None；否则返回应直接写出的 Response。
    - 超用户日次数 → 429
    - 超全局日 token 预算 → 503 + logger.error
    """
    budget = _global_budget()
    if budget is not None:
        total = (
            UsageDaily.objects.filter(date=_today()).aggregate(s=Sum("token_count")).get("s")
            or 0
        )
        if total >= budget:
            logger.error(
                "GLOBAL_DAILY_TOKEN_BUDGET exceeded date=%s tokens=%s budget=%s",
                _today(),
                total,
                budget,
            )
            return Response(
                {
                    "detail": "今日系统问答额度已用尽，请明日再试",
                    "code": "global_budget_exhausted",
                    "remaining": 0,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    limit = _user_limit()
    usage = UsageDaily.objects.filter(user=user, date=_today()).first()
    used = usage.ask_count if usage else 0
    if used >= limit:
        return Response(
            {
                "detail": "今日免费问答次数已用尽，请明日再试",
                "code": "daily_ask_limit",
                "remaining": 0,
                "limit": limit,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return None


def record_ask_success(user, question: str, answer: str) -> dict:
    """问答成功后 F() 自增 ask_count / token_count，返回当日用量摘要。"""
    tokens = estimate_tokens(question or "", answer or "")
    today = _today()
    obj, created = UsageDaily.objects.get_or_create(
        user=user,
        date=today,
        defaults={"ask_count": 1, "token_count": tokens},
    )
    if not created:
        UsageDaily.objects.filter(pk=obj.pk).update(
            ask_count=F("ask_count") + 1,
            token_count=F("token_count") + tokens,
        )
        obj.refresh_from_db()
    limit = _user_limit()
    return {
        "ask_count": obj.ask_count,
        "token_count": obj.token_count,
        "limit": limit,
        "remaining": max(0, limit - obj.ask_count),
    }
