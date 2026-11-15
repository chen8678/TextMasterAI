from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

try:
    from celery import shared_task
except ImportError:

    def shared_task(*args, **kwargs):
        def decorator(f):
            return f

        return decorator(args[0]) if args and callable(args[0]) else decorator


logger = logging.getLogger(__name__)


def _build_agent_payload(agent, **kwargs):
    """模板 + 可选 LLM；统一规范化 skill id。"""
    from apps.agents.evolution.proposer import propose_agent_payload
    from apps.agents.evolution.proposer_llm import propose_agent_payload_llm
    from apps.skills.evolution.guard import agent_payload_passes_domain_guard
    from apps.skills.evolution.validation import normalize_suggested_skill_ids
    from apps.skills.registry import SkillRegistry

    allowed_pool = normalize_suggested_skill_ids(list(SkillRegistry.list_ids()))
    use_llm = os.getenv("AGENT_EVOLUTION_USE_LLM", "").lower() in ("1", "true", "yes")

    if use_llm:
        llm_payload = propose_agent_payload_llm(
            agent_id=agent.id,
            current_skills=list(agent.skills or []),
            skills_used=kwargs.get("skills_used") or [],
            question_snippet=kwargs.get("question_snippet") or "",
            answer_snippet=kwargs.get("answer_snippet") or "",
            allowed_skill_ids=allowed_pool,
            studio_context=kwargs.get("studio_context") or {},
        )
        if llm_payload:
            llm_payload["suggested_skills"] = normalize_suggested_skill_ids(
                llm_payload.get("suggested_skills") or []
            )
            if agent_payload_passes_domain_guard(llm_payload):
                return llm_payload, "llm_deepseek"

    tpl = propose_agent_payload(
        agent_id=agent.id,
        current_skills=list(agent.skills or []),
        skills_used=kwargs.get("skills_used") or [],
        question_snippet=kwargs.get("question_snippet") or "",
        answer_snippet=kwargs.get("answer_snippet") or "",
        studio_context=kwargs.get("studio_context") or {},
    )
    tpl["suggested_skills"] = normalize_suggested_skill_ids(tpl.get("suggested_skills") or [])
    if not tpl.get("domain_tags"):
        tpl["domain_tags"] = ["qa_enhancement"]
    return tpl, "template_mvp"


@shared_task(bind=True, acks_late=True)
def run_agent_evolution_task(
    self,
    agent_id: str,
    session_id: str,
    user_id: Optional[int],
    question_snippet: str,
    answer_snippet: str,
    skills_used: List[str],
    studio_context: Optional[dict] = None,
):
    from uuid import UUID

    from django.contrib.auth import get_user_model

    from apps.agents.evolution.governance import should_auto_apply_agent_payload, system_user_for_auto_apply
    from apps.agents.models import Agent, AgentEvolutionProposal

    User = get_user_model()
    user = User.objects.filter(id=user_id).first() if user_id else None

    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return

    payload, provenance = _build_agent_payload(
        agent,
        skills_used=skills_used,
        question_snippet=question_snippet,
        answer_snippet=answer_snippet,
        studio_context=studio_context or {},
    )
    if studio_context:
        try:
            payload["studio_context"] = json.loads(json.dumps(studio_context))
        except Exception:
            payload["studio_context"] = {}

    sid = None
    try:
        sid = UUID(session_id)
    except (ValueError, TypeError):
        pass

    prop = AgentEvolutionProposal.objects.create(
        agent=agent,
        session_id=sid,
        payload=payload,
        status=AgentEvolutionProposal.Status.PENDING,
        provenance=provenance,
        created_by=user,
    )

    if should_auto_apply_agent_payload(agent, payload, provenance):
        reviewer = system_user_for_auto_apply()
        if apply_agent_proposal(prop.id, reviewer, force=True):
            logger.info("agent evolution auto-applied proposal %s", prop.id)


def apply_agent_proposal(proposal_id, reviewer, force: bool = False) -> bool:
    """将提案中的 suggested_skills 写入 Agent。无 reviewer 时须 force=True（自动合并）。"""
    from django.utils import timezone

    from apps.agents.models import AgentEvolutionProposal
    from apps.skills.evolution.guard import agent_payload_passes_domain_guard
    from apps.skills.evolution.validation import normalize_suggested_skill_ids

    if reviewer is None and not force:
        return False

    try:
        prop = AgentEvolutionProposal.objects.select_related("agent").get(id=proposal_id)
    except AgentEvolutionProposal.DoesNotExist:
        return False
    if prop.status != AgentEvolutionProposal.Status.PENDING:
        return False
    if not agent_payload_passes_domain_guard(prop.payload or {}):
        return False
    raw = prop.payload.get("suggested_skills")
    if not isinstance(raw, list):
        return False
    skills = normalize_suggested_skill_ids(raw)
    if not skills and raw:
        return False
    agent = prop.agent
    agent.skills = skills
    agent.save(update_fields=["skills"])
    prop.status = AgentEvolutionProposal.Status.APPLIED
    prop.reviewed_by = reviewer
    prop.reviewed_at = timezone.now()
    prop.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return True
