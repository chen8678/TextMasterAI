"""用户输入 / 模型输出内容安全检测（敏感词、越狱提示、有害内容）。"""

from .checker import (
    BLOCKED_INPUT_MESSAGE,
    BLOCKED_OUTPUT_MESSAGE,
    check_text,
    sanitize_output,
)

__all__ = [
    "check_text",
    "sanitize_output",
    "BLOCKED_INPUT_MESSAGE",
    "BLOCKED_OUTPUT_MESSAGE",
]
