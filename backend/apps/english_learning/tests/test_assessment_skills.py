from django.test import SimpleTestCase

from apps.english_learning.skill_handlers.assessment_build import execute as build_execute
from apps.english_learning.skill_handlers.assessment_score import execute as score_execute
from apps.english_learning.skill_handlers.profile_tags import execute as profile_execute


class EnglishProfileSkillTests(SimpleTestCase):
    def test_profile_normalizes_tags(self):
        r = profile_execute(level_tags=["CEFR:B1"], exam_goal="IELTS 6", weekly_minutes=90)
        self.assertIn("learner_constraints", r)
        self.assertEqual(r["learner_constraints"]["cefr_estimate"], "B1")


class EnglishAssessmentBuildTests(SimpleTestCase):
    def test_build_returns_public_and_scoring(self):
        r = build_execute(
            learner_constraints={"level_tags": ["B1"]},
            question_count=2,
            level_target="B1",
        )
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(len(r["items_scoring"]), 2)
        for pub in r["items"]:
            self.assertNotIn("answer_key", pub)
        for full in r["items_scoring"]:
            self.assertIn("answer_key", full)


class EnglishAssessmentScoreTests(SimpleTestCase):
    def test_full_credit(self):
        items = [
            {"id": "a", "type": "single_choice", "dimension": "grammar", "answer_key": "were"},
        ]
        responses = [{"item_id": "a", "answer": "were"}]
        r = score_execute(items=items, responses=responses, model="deepseek-chat")
        self.assertEqual(r["scores"]["overall_percent"], 100.0)

    def test_partial_weak_dimension(self):
        items = [
            {"id": "a", "type": "single_choice", "dimension": "grammar", "answer_key": "were"},
            {"id": "b", "type": "single_choice", "dimension": "grammar", "answer_key": "are"},
        ]
        responses = [{"item_id": "a", "answer": "were"}, {"item_id": "b", "answer": "wrong"}]
        r = score_execute(items=items, responses=responses, model="deepseek-chat")
        self.assertEqual(r["scores"]["overall_percent"], 50.0)
        self.assertIn("grammar", r["weak_dimensions"])
