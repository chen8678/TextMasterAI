"""Agent 提案领域守卫。"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.agents.models import Agent, AgentEvolutionProposal
from apps.agents.tasks import apply_agent_proposal
from apps.skills.models import Skill

User = get_user_model()


class ApplyDomainGuardTests(TestCase):
    def setUp(self):
        Skill.objects.update_or_create(
            id="rag_answer",
            defaults={"name": "知识库", "is_active": True},
        )
        self.agent = Agent.objects.create(
            id="dom-agent",
            name="D",
            skills=["rag_answer"],
        )
        self.user = User.objects.create_user(
            username="r", email="r@test.local", password="p"
        )
        self.user.is_staff = True
        self.user.save()

    def test_rejects_when_domain_tags_outside_allowlist(self):
        prop = AgentEvolutionProposal.objects.create(
            agent=self.agent,
            payload={
                "domain_tags": ["invalid_domain_tag_zzz"],
                "suggested_skills": ["rag_answer"],
            },
            status=AgentEvolutionProposal.Status.PENDING,
            provenance="test",
        )
        self.assertFalse(apply_agent_proposal(prop.id, self.user, force=False))

    @override_settings(EVOLUTION_ENFORCE_DOMAIN_GUARD=False)
    def test_guard_off_allows_bad_tag(self):
        prop = AgentEvolutionProposal.objects.create(
            agent=self.agent,
            payload={
                "domain_tags": ["invalid_domain_tag_zzz"],
                "suggested_skills": ["rag_answer"],
            },
            status=AgentEvolutionProposal.Status.PENDING,
            provenance="test",
        )
        self.assertTrue(apply_agent_proposal(prop.id, self.user, force=False))
