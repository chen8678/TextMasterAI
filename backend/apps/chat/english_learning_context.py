"""
英语学习对话上下文：按 phase 收紧可调 Skill，并在 tutor 阶段注入当前路线文档摘录。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set

from apps.chat.agent_service import RAG_LIKE_SKILLS

VALID_ENGLISH_PHASES = frozenset(
    {"tutor", "intake", "assessment", "roadmap", "roadmap_review"}
)

# 主编排 + MVP-B 专项（与 init_skills_agents / 前端 delegate 对齐）
ENGLISH_LEARNING_AGENT_IDS = frozenset(
    {"english_orchestrator", "english_vocab", "english_grammar", "english_listen"}
)

_ASSESSMENT_EXTRA_DENY = frozenset(
    {
        "content_generation",
        "english_roadmap_draft",
        "summarize",
        "compare_docs",
        "read_local_file",
        "skill_creator",
        "cite_snippets",
        "novel_continuer",
        "paper_section_generator",
        "contract_filler",
    }
)

_ROADMAP_LIKE_DENY = frozenset({"content_generation", "english_roadmap_draft", "skill_creator"})


def skill_denylist_for_english_phase(phase: str) -> Set[str]:
    """纯函数，便于单测。"""
    if phase == "assessment":
        return set(RAG_LIKE_SKILLS) | set(_ASSESSMENT_EXTRA_DENY)
    if phase in ("roadmap", "roadmap_review", "intake"):
        return set(_ROADMAP_LIKE_DENY)
    return set()


def build_english_learning_orchestrator_context(
    *,
    user,
    knowledge_base_id: str,
    agent_id: str,
    english_phase: str,
    english_profile_id: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    返回传给 AgentOrchestrator.process(english_learning=...) 的上下文；
    非英语学习会话返回 None。
    """
    phase = (english_phase or "").strip().lower()
    if phase and phase not in VALID_ENGLISH_PHASES:
        raise ValueError(f"unsupported english_phase: {phase}")

    if not phase:
        if agent_id in ENGLISH_LEARNING_AGENT_IDS:
            phase = "tutor"
        else:
            return None

    skill_denylist = skill_denylist_for_english_phase(phase)
    roadmap_excerpt = ""

    if agent_id in ENGLISH_LEARNING_AGENT_IDS and phase == "tutor":
        try:
            from apps.english_learning.models import EnglishLearningProfile

            profile = None
            pid = english_profile_id
            if pid not in (None, ""):
                profile = EnglishLearningProfile.objects.filter(pk=pid, user=user).first()
            if profile is None:
                profile = EnglishLearningProfile.objects.filter(user=user).first()
            if profile and profile.active_roadmap_document_id:
                doc = profile.active_roadmap_document
                if doc and str(doc.knowledge_base_id) == str(knowledge_base_id):
                    raw = (doc.content or "").strip()
                    if raw:
                        roadmap_excerpt = raw[:8000]
        except Exception:
            roadmap_excerpt = ""

    return {
        "phase": phase,
        "skill_denylist": skill_denylist,
        "roadmap_excerpt": roadmap_excerpt,
    }
