"""
临时嵌入 / 扩展钩子（后端）。

赛场改动优先走环境变量与本模块常量，避免大面积改 views。
详见：比赛材料/文档/07-临时改动与嵌入对接文档.md
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# 问答请求前处理：可挂自定义过滤器（在 content_safety 之后、业务之前）
# 签名: (request, text: str, context: dict) -> Optional[str]
# 返回非空 str 表示改写后的用户文本；返回 None 表示不改写。
# ---------------------------------------------------------------------------
AskTextTransformer = Callable[[Any, str, Dict[str, Any]], Optional[str]]

_ask_text_transformers: List[AskTextTransformer] = []


def register_ask_text_transformer(fn: AskTextTransformer) -> None:
    _ask_text_transformers.append(fn)


def clear_ask_text_transformers() -> None:
    _ask_text_transformers.clear()


def apply_ask_text_transformers(request, text: str, context: Optional[Dict[str, Any]] = None) -> str:
    ctx = context or {}
    out = text
    for fn in _ask_text_transformers:
        rewritten = fn(request, out, ctx)
        if rewritten is not None:
            out = rewritten
    return out


# ---------------------------------------------------------------------------
# 场景助手展示白名单扩展（前端列表一般来自 API；此处供服务端过滤演示用）
# ---------------------------------------------------------------------------
EXTRA_AGENT_IDS_VISIBLE: List[str] = [
    # 例: "law_kb",
]

# ---------------------------------------------------------------------------
# 演示用响应头 / 特性标记（健康检查或配置接口可读取）
# ---------------------------------------------------------------------------
EMBED_FEATURE_FLAGS: Dict[str, Any] = {
    "contest_patch_ready": True,
    "custom_input_framework": False,
}
