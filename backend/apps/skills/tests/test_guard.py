"""定向进化 guard。"""
from django.test import TestCase, override_settings

from apps.skills.evolution.guard import (
    agent_payload_passes_domain_guard,
    draft_markdown_allowed,
    skill_allowed_for_evolution,
)
from apps.skills.models import Skill


class SkillDomainGuardTests(TestCase):
    def test_default_domain_allows(self):
        s = Skill(id="t1", name="T", metadata={})
        ok, _ = skill_allowed_for_evolution(s)
        self.assertTrue(ok)

    @override_settings(EVOLUTION_ENFORCE_DOMAIN_GUARD=True, EVOLUTION_ALLOWED_DOMAINS=frozenset({"law"}))
    def test_explicit_domain_must_match(self):
        s = Skill(id="t2", name="T", metadata={"evolution_domain": "law"})
        self.assertTrue(skill_allowed_for_evolution(s)[0])
        s2 = Skill(id="t3", name="T", metadata={"evolution_domain": "qa_enhancement"})
        self.assertFalse(skill_allowed_for_evolution(s2)[0])


class DraftMarkdownGuardTests(TestCase):
    @override_settings(EVOLUTION_ENFORCE_DOMAIN_GUARD=True)
    def test_forbidden_marker_blocks(self):
        ok, _ = draft_markdown_allowed("建议接入 stable diffusion 生图")
        self.assertFalse(ok)

    def test_clean_passes(self):
        ok, _ = draft_markdown_allowed("## Troubleshooting\n- 引用格式核对")
        self.assertTrue(ok)


class AgentPayloadGuardTests(TestCase):
    @override_settings(EVOLUTION_ENFORCE_DOMAIN_GUARD=True)
    def test_explicit_bad_domain_fails(self):
        p = {"domain_tags": ["not_a_real_domain_tag_xyz"], "suggested_skills": []}
        self.assertFalse(agent_payload_passes_domain_guard(p))

    def test_default_empty_tags_passes(self):
        p = {"suggested_skills": ["rag_answer"]}
        self.assertTrue(agent_payload_passes_domain_guard(p))
