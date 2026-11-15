"""PRO：论文分节生成辅助（纯文字）。"""
from __future__ import annotations

import os

from apps.chat.ai_services import AIServiceFactory


def execute(question: str, knowledge_base_id: str, user=None, **kwargs):
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return {"triggered": True, "answer": "未配置 DEEPSEEK_API_KEY，无法执行论文分节生成。"}
    svc = AIServiceFactory.create_service("deepseek-chat", key)
    system = "你是论文写作助手。按学术中文风格输出：小节标题 + 段落 + 关键引用提示。"
    user_prompt = f"请生成论文小节草稿：{question}"
    answer = svc.generate_response(
        [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]
    )
    return {"triggered": True, "answer": answer}

