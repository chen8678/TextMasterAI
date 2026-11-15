from django.test import SimpleTestCase

from apps.chat.english_learning_context import (
    skill_denylist_for_english_phase,
    VALID_ENGLISH_PHASES,
)
from apps.chat.agent_service import RAG_LIKE_SKILLS


class EnglishLearningContextTests(SimpleTestCase):
    def test_assessment_denies_rag_and_content_generation(self):
        deny = skill_denylist_for_english_phase("assessment")
        self.assertIn("rag_answer", deny)
        self.assertIn("content_generation", deny)
        self.assertIn("english_roadmap_draft", deny)

    def test_tutor_no_deny(self):
        self.assertEqual(skill_denylist_for_english_phase("tutor"), set())

    def test_roadmap_denies_draft_skill(self):
        deny = skill_denylist_for_english_phase("roadmap")
        self.assertIn("english_roadmap_draft", deny)
        self.assertNotIn("rag_answer", deny)

    def test_valid_phases_cover_expected(self):
        self.assertTrue({"tutor", "assessment", "roadmap"} <= VALID_ENGLISH_PHASES)
        self.assertTrue(RAG_LIKE_SKILLS <= skill_denylist_for_english_phase("assessment"))

    def test_english_learning_agent_ids_includes_subagents(self):
        from apps.chat.english_learning_context import ENGLISH_LEARNING_AGENT_IDS

        self.assertTrue({"english_vocab", "english_grammar", "english_listen"} <= ENGLISH_LEARNING_AGENT_IDS)
