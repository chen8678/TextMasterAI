"""PRO：小说续写辅助（纯文字）。"""
from __future__ import annotations

import os

from apps.chat.ai_services import AIServiceFactory


def execute(question: str, knowledge_base_id: str, user=None, **kwargs):
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return {"triggered": True, "answer": "未配置 DEEPSEEK_API_KEY，无法执行小说续写。"}
    svc = AIServiceFactory.create_service("deepseek-chat", key)
    system = "你是小说续写助手。保持世界观与人物一致，输出中文正文，不要解释。"
    user_prompt = f"基于知识库上下文继续创作：{question}"
    answer = svc.generate_response(
        [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]
    )
    return {"triggered": True, "answer": answer}

