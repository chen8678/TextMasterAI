"""根据会话片段生成 Agent 配置提案（模板 MVP；可扩展 LLM）。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def propose_agent_payload(
    *,
    agent_id: str,
    current_skills: List[str],
    skills_used: List[str],
    question_snippet: str,
    answer_snippet: str,
    studio_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    返回可存入 AgentEvolutionProposal.payload 的结构。
    MVP：若本轮使用的 skills 已是 Agent 子集，则建议「保持」；否则列出观察说明供人工判断。
    """
    su = list(skills_used or [])
    cur = list(current_skills or [])
    merged = list(dict.fromkeys(cur + su))
    unchanged = merged == cur
    context = studio_context or {}
    mode = str(context.get("mode") or "").strip().lower()
    mode_to_domain = {"novel": "novel_writing", "paper": "paper_writing", "contract": "law"}
    domain = mode_to_domain.get(mode, "qa_enhancement")
    return {
        "domain_tags": [domain],
        "suggested_skills": merged if not unchanged else cur,
        "previous_skills": cur,
        "skills_used_this_turn": su,
        "notes": (
            "本轮执行未引入新 Skill ID，维持配置。"
            if unchanged
            else "观测到本轮实际使用的 Skill 与配置列表不完全一致，合并建议供人工审核。"
        ),
        "question_preview": (question_snippet or "")[:500],
        "answer_preview": (answer_snippet or "")[:500],
        "studio_context": context,
    }


def payload_summary(payload: Dict[str, Any]) -> str:
    return (payload.get("notes") or "")[:200]
