"""可选：LLM 生成 Agent 配置提案（JSON）。需 DEEPSEEK_API_KEY + AGENT_EVOLUTION_USE_LLM。"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from django.conf import settings


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    t = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t)
    if m:
        t = m.group(1).strip()
    try:
        data = json.loads(t)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def propose_agent_payload_llm(
    *,
    agent_id: str,
    current_skills: List[str],
    skills_used: List[str],
    question_snippet: str,
    answer_snippet: str,
    allowed_skill_ids: List[str],
    studio_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    studio_context = studio_context or {}
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from apps.chat.ai_services import AIServiceFactory

        svc = AIServiceFactory.create_service("deepseek-chat", key)
    except Exception:
        return None

    allowed = [x for x in allowed_skill_ids[:80]]
    domain_list = sorted(getattr(settings, "EVOLUTION_ALLOWED_DOMAINS", frozenset()))
    system = (
        "你是智能体配置助手。产品为「本地私有知识库 + 纯文字智能问答」，"
        "禁止建议与文字问答无关的能力（如图像、视频、游戏、任意识别爬公网等）。"
        "只输出一个 JSON 对象，不要 Markdown 表头或解释。"
        "字段：suggested_skills（字符串数组，顺序有意义）、notes（中文简短说明）、"
        "confidence（0到1的小数）、domain_tags（字符串数组，"
        f"每个元素必须从以下领域标签中选取：{domain_list}，至少一个，通常用 qa_enhancement）。"
        "suggested_skills 必须只使用下面「允许列表」中的 id。"
    )
    user = (
        f"agent_id={agent_id}\n"
        f"当前 skills 顺序: {current_skills}\n"
        f"本轮实际使用到的 skills: {skills_used}\n"
        f"允许使用的 skill id 列表: {allowed}\n"
        f"用户问题摘要:\n{question_snippet[:1200]}\n"
        f"助手回答摘要:\n{answer_snippet[:1200]}\n"
        f"工作室上下文(JSON): {json.dumps(studio_context, ensure_ascii=False)[:500]}\n"
        "若无需调整，suggested_skills 可与当前一致，notes 说明维持原因。"
    )
    try:
        raw = svc.generate_response(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
    except Exception:
        return None
    if not raw or raw.startswith("API调用失败") or raw.startswith("生成回复时出现错误"):
        return None
    data = _parse_json_object(raw)
    if not data:
        return None
    ss = data.get("suggested_skills")
    if not isinstance(ss, list):
        return None
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        notes = str(notes)
    conf = data.get("confidence", 0.5)
    try:
        confidence = float(conf)
    except (TypeError, ValueError):
        confidence = 0.5

    raw_tags = data.get("domain_tags")
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]
    tags: List[str] = []
    if isinstance(raw_tags, list):
        allow = getattr(settings, "EVOLUTION_ALLOWED_DOMAINS", frozenset())
        for x in raw_tags:
            t = str(x).strip().lower()
            if t in allow:
                tags.append(t)
    if not tags:
        tags = ["qa_enhancement"]

    return {
        "domain_tags": tags,
        "suggested_skills": [str(x).strip() for x in ss if str(x).strip()],
        "previous_skills": list(current_skills),
        "skills_used_this_turn": list(skills_used or []),
        "notes": notes[:2000],
        "confidence": max(0.0, min(1.0, confidence)),
        "question_preview": (question_snippet or "")[:500],
        "answer_preview": (answer_snippet or "")[:500],
        "studio_context": studio_context,
    }
