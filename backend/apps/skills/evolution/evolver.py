"""
生成进化草案：默认模板；设置 SKILL_EVOLUTION_USE_LLM=true 且配置 DEEPSEEK_API_KEY 时用 LLM 生成 Markdown。
"""

from __future__ import annotations

import os
from typing import Optional

from .types import ChangeDraft


def _llm_troubleshooting_block(
    skill_id: str,
    user_message: str,
    failed_log_summary: str,
    skill_description: str,
) -> Optional[str]:
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from apps.chat.ai_services import AIServiceFactory

        svc = AIServiceFactory.create_service("deepseek-chat", key)
        system = (
            "你是技能文档编辑，产品为「私有知识库 + 纯文字智能问答」。"
            "只输出一段 Markdown，必须包含二级标题 ## Troubleshooting，"
            "用列表写出针对本次失败与用户反馈的注意事项。"
            "禁止建议：图像/视频/多模态、游戏、任意外部 API 调用、与知识库文字问答无关的能力。"
            "不要寒暄、不要代码块外壳以外的废话。"
        )
        user = (
            f"Skill ID: {skill_id}\n"
            f"技能说明: {skill_description[:800]}\n"
            f"失败/日志摘要: {failed_log_summary[:1200]}\n"
            f"用户纠正: {user_message[:1200]}\n"
        )
        out = svc.generate_response(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        if not out or out.startswith("API调用失败") or out.startswith("生成回复时出现错误"):
            return None
        return out.strip()
    except Exception:
        return None


def propose_staging_change(
    skill_id: str,
    *,
    user_message: str,
    failed_log_summary: str,
    skill_description: str = "",
) -> ChangeDraft:
    use_llm = os.getenv("SKILL_EVOLUTION_USE_LLM", "").lower() in ("1", "true", "yes")
    if use_llm:
        block = _llm_troubleshooting_block(
            skill_id, user_message, failed_log_summary, skill_description
        )
        if block:
            return ChangeDraft(
                skill_id=skill_id,
                markdown_section=block,
                provenance="llm_deepseek",
            )

    desc = (skill_description or "")[:200]
    ctx = (failed_log_summary or "")[:400]
    um = (user_message or "")[:800]
    md = (
        f"\n\n## Troubleshooting\n\n"
        f"- **来源**: 用户纠正触发（MVP 模板）\n"
        f"- **Skill**: `{skill_id}`\n"
        f"- **说明摘要**: {desc}\n"
        f"- **失败/日志上下文**: {ctx}\n"
        f"- **用户反馈**: {um}\n"
    )
    return ChangeDraft(skill_id=skill_id, markdown_section=md.strip(), provenance="template_mvp")
