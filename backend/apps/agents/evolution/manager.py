"""调度 Agent 进化分析任务（节流 + 开关）。"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def schedule_agent_evolution_after_turn(
    *,
    agent_id: Optional[str],
    session_id: Optional[UUID],
    user,
    question: str,
    answer: str,
    skills_used: List[str],
    studio_context: Optional[Dict[str, Any]] = None,
) -> bool:
    if not agent_id or not session_id:
        return False
    try:
        from apps.agents.models import Agent, AgentEvolutionProposal
    except Exception:
        return False

    agent = Agent.objects.filter(id=agent_id, is_active=True).first()
    if not agent or not getattr(agent, "evolution_enabled", False):
        return False

    min_interval = int(getattr(settings, "AGENT_EVOLUTION_MIN_INTERVAL_SECONDS", 300) or 300)
    recent = AgentEvolutionProposal.objects.filter(agent=agent).order_by("-created_at").first()
    if recent and (timezone.now() - recent.created_at) < timedelta(seconds=min_interval):
        return False

    try:
        from apps.agents.tasks import run_agent_evolution_task

        run_agent_evolution_task.delay(
            agent_id=agent.id,
            session_id=str(session_id),
            user_id=getattr(user, "id", None),
            question_snippet=(question or "")[:2500],
            answer_snippet=(answer or "")[:2500],
            skills_used=list(skills_used or []),
            studio_context=studio_context or {},
        )
    except Exception as exc:
        logger.exception("schedule_agent_evolution: %s", exc)
        return False
    return True
