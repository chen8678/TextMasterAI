"""apply_agent_proposal：规范化与边界。"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.models import Agent, AgentEvolutionProposal
from apps.agents.tasks import apply_agent_proposal
from apps.skills.models import Skill

User = get_user_model()


class ApplyAgentProposalTests(TestCase):
    def setUp(self):
        Skill.objects.update_or_create(
            id="rag_answer",
            defaults={"name": "知识库", "is_active": True},
        )
        self.agent = Agent.objects.create(
            id="test-agent",
            name="T",
            skills=["rag_answer"],
        )
        self.reviewer = User.objects.create_user(
            username="rev", email="rev@test.local", password="x"
        )
        self.reviewer.is_staff = True
        self.reviewer.save()

    def _proposal(self, payload: dict) -> AgentEvolutionProposal:
        return AgentEvolutionProposal.objects.create(
            agent=self.agent,
            payload=payload,
            status=AgentEvolutionProposal.Status.PENDING,
            provenance="test",
        )

    def test_rejects_when_all_ids_invalid_after_normalize(self):
        prop = self._proposal({"suggested_skills": ["totally_fake_id"]})
        ok = apply_agent_proposal(prop.id, self.reviewer, force=False)
        self.assertFalse(ok)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.skills, ["rag_answer"])
        prop.refresh_from_db()
        self.assertEqual(prop.status, AgentEvolutionProposal.Status.PENDING)

    def test_allows_explicit_empty_list_clears_skills(self):
        prop = self._proposal({"suggested_skills": []})
        ok = apply_agent_proposal(prop.id, self.reviewer, force=False)
        self.assertTrue(ok)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.skills, [])
        prop.refresh_from_db()
        self.assertEqual(prop.status, AgentEvolutionProposal.Status.APPLIED)

    def test_applies_normalized_subset(self):
        prop = self._proposal({"suggested_skills": ["rag_answer"]})
        ok = apply_agent_proposal(prop.id, self.reviewer, force=False)
        self.assertTrue(ok)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.skills, ["rag_answer"])

    def test_requires_reviewer_or_force(self):
        prop = self._proposal({"suggested_skills": []})
        self.assertFalse(apply_agent_proposal(prop.id, None, force=False))
        self.assertTrue(apply_agent_proposal(prop.id, None, force=True))
