"""G3+：向导 SSE 与 Skill LLM 流式之间的 token 回调（contextvar，线程安全）。"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Callable, Optional

TokenCallback = Callable[[str, str], None]

_token_cb: ContextVar[Optional[TokenCallback]] = ContextVar("wizard_token_cb", default=None)


def set_wizard_token_callback(cb: Optional[TokenCallback]):
    return _token_cb.set(cb)


def reset_wizard_token_callback(token) -> None:
    _token_cb.reset(token)


def get_wizard_token_callback() -> Optional[TokenCallback]:
    return _token_cb.get()


def emit_wizard_token(text: str, node: str = "roadmap_draft_skill") -> None:
    cb = _token_cb.get()
    if cb and text:
        cb(text, node)
