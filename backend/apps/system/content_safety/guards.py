"""视图层便捷封装。"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from rest_framework.response import Response

from .checker import guard_user_text, sanitize_output
from .http import blocked_input_response, merge_output_safety_result


def require_safe_user_text(
    request,
    text: str,
    *,
    channel: str,
) -> Optional[Response]:
    allowed, detail = guard_user_text(
        text or "",
        user=getattr(request, "user", None),
        direction="input",
        channel=channel,
        request=request,
    )
    if allowed:
        return None
    return blocked_input_response(detail or {})


def require_safe_user_texts(
    request,
    texts: Iterable[str],
    *,
    channel: str,
) -> Optional[Response]:
    for t in texts:
        blocked = require_safe_user_text(request, t, channel=channel)
        if blocked is not None:
            return blocked
    return None


def apply_output_safety(
    result: dict,
    *,
    channel: str = "chat",
    user=None,
    request=None,
) -> dict:
    answer = result.get("answer")
    if answer is None:
        return result
    safe, replaced, detail = sanitize_output(str(answer), channel=channel)
    if replaced and detail:
        from .checker import log_content_safety_event

        log_content_safety_event(
            user=user,
            direction="output",
            channel=channel,
            category=detail.get("category", "unknown"),
            category_label=detail.get("category_label", ""),
            matched_hint=detail.get("matched_hint", ""),
            blocked=True,
            request=request,
            text_preview=str(answer),
        )
        result = dict(result)
        result["answer"] = safe
    return merge_output_safety_result(result, replaced=replaced, detail=detail)


def apply_markdown_output_safety(
    markdown: str,
    *,
    channel: str,
    user=None,
    request=None,
) -> tuple[str, bool]:
    safe, replaced, detail = sanitize_output(markdown or "", channel=channel)
    if replaced and detail:
        from .checker import log_content_safety_event

        log_content_safety_event(
            user=user,
            direction="output",
            channel=channel,
            category=detail.get("category", "unknown"),
            category_label=detail.get("category_label", ""),
            matched_hint=detail.get("matched_hint", ""),
            blocked=True,
            request=request,
            text_preview=markdown or "",
        )
    return safe, replaced
