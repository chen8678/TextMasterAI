"""Agent 进化 API：gated 仅超管可 apply。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.agents.models import Agent, AgentEvolutionProposal
from apps.skills.models import Skill

User = get_user_model()


class AgentEvolutionApplyPermissionTests(APITestCase):
    def setUp(self):
        Skill.objects.update_or_create(
            id="rag_answer",
            defaults={"name": "知识库", "is_active": True},
        )
        self.agent = Agent.objects.create(
            id="gated-test-agent",
            name="G",
            skills=["rag_answer"],
            evolution_governance="gated",
        )
        self.prop = AgentEvolutionProposal.objects.create(
            agent=self.agent,
            payload={"suggested_skills": ["rag_answer"]},
            status=AgentEvolutionProposal.Status.PENDING,
            provenance="test",
        )
        self.staff = User.objects.create_user(
            username="staff_only", email="staff_only@test.local", password="p"
        )
        self.staff.is_staff = True
        self.staff.is_superuser = False
        self.staff.save()
        self.superuser = User.objects.create_user(
            username="su", email="su@test.local", password="p"
        )
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()

    def _url(self):
        return reverse(
            "agent-evolution-proposal-apply",
            kwargs={"agent_id": self.agent.id, "proposal_id": self.prop.id},
        )

    def test_gated_staff_forbidden(self):
        self.client.force_authenticate(user=self.staff)
        r = self.client.post(self._url(), {}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_gated_superuser_ok(self):
        self.client.force_authenticate(user=self.superuser)
        r = self.client.post(self._url(), {}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.get("ok"))
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.skills, ["rag_answer"])
