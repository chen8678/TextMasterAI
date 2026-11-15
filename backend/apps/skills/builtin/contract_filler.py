"""PRO：合同条款补全辅助（纯文字）。"""
from __future__ import annotations

import os

from apps.chat.ai_services import AIServiceFactory


def execute(question: str, knowledge_base_id: str, user=None, **kwargs):
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return {"triggered": True, "answer": "未配置 DEEPSEEK_API_KEY，无法执行合同补全。"}
    svc = AIServiceFactory.create_service("deepseek-chat", key)
    system = (
        "你是合同条款助手。只输出可直接使用的合同文本建议，"
        "并标注【待法务复核】。不得提供法律结论。"
    )
    user_prompt = f"请补全/改写合同内容：{question}"
    answer = svc.generate_response(
        [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]
    )
    return {"triggered": True, "answer": answer}

