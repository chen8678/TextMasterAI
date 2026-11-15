from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.cet.models import CETQuestion, Vocabulary, VocabularyNotebook


User = get_user_model()


@override_settings(DEBUG=True)
class CET4FlowTests(TestCase):
    def setUp(self):
        call_command("seed_cet4")
        self.user = User.objects.create_user(
            email="cet4_tester@example.com",
            username="cet4_tester",
            password="Cet4Test!Pass9",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_seed_has_cet4_content(self):
        self.assertGreaterEqual(Vocabulary.objects.filter(exam_type="cet4").count(), 50)
        self.assertGreaterEqual(CETQuestion.objects.filter(exam__exam_type="cet4").count(), 20)

    def test_practice_generate_and_submit(self):
        gen = self.client.post(
            "/api/v1/cet/practice/",
            {"question_type": "vocabulary", "count": 5, "difficulty": 2},
            format="json",
        )
        self.assertEqual(gen.status_code, 200, gen.content)
        questions = gen.data.get("questions") or []
        self.assertGreaterEqual(len(questions), 1)
        self.assertNotIn("correct_answer", questions[0])

        answers = {}
        for q in questions:
            # 故意交空，验证接口可落库
            answers[str(q["id"])] = "A"
        sub = self.client.post(
            "/api/v1/cet/practice/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(sub.status_code, 200, sub.content)
        self.assertIn("total", sub.data)
        self.assertGreaterEqual(sub.data["total"], 1)
        self.assertIn("radar_delta", sub.data)
        self.assertIn("before", sub.data["radar_delta"])
        self.assertIn("after", sub.data["radar_delta"])
        self.assertIn("summary", sub.data["radar_delta"])

    def test_radar_is_per_dimension(self):
        res = self.client.get("/api/v1/cet/analysis/ability-radar/")
        self.assertEqual(res.status_code, 200)
        for key in ("listening", "reading", "vocabulary", "grammar", "writing", "translation"):
            self.assertIn(key, res.data)

    def test_import_core_vocab_and_review(self):
        imp = self.client.post(
            "/api/v1/cet/vocabulary/notebooks/import-core/",
            {"limit": 20},
            format="json",
        )
        self.assertEqual(imp.status_code, 201, imp.content)
        nb_id = imp.data["id"]
        self.assertTrue(VocabularyNotebook.objects.filter(id=nb_id, user=self.user).exists())

        plan = self.client.get(f"/api/v1/cet/vocabulary/notebooks/{nb_id}/review-plan/")
        self.assertEqual(plan.status_code, 200)
        words = plan.data.get("review_words") or []
        self.assertGreaterEqual(len(words), 1)
        vid = words[0]["vocabulary_id"]

        rev = self.client.post(
            "/api/v1/cet/vocabulary/review/",
            {"vocabulary_id": vid, "remembered": True},
            format="json",
        )
        self.assertEqual(rev.status_code, 200, rev.content)
        self.assertEqual(rev.data.get("review_count"), 1)

    def test_mock_exam_cet4_only(self):
        create = self.client.post("/api/v1/cet/exam/create-mock/", {"exam_type": "cet6"}, format="json")
        self.assertEqual(create.status_code, 201, create.content)
        self.assertEqual(create.data.get("exam_type"), "cet4")
        questions = create.data.get("questions") or []
        self.assertGreaterEqual(len(questions), 1)
        self.assertNotIn("correct_answer", questions[0])

        answers = {str(q["id"]): "A" for q in questions if q.get("options")}
        submit = self.client.post(
            f"/api/v1/cet/exam/{create.data['mock_exam_id']}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(submit.status_code, 200, submit.content)
        self.assertIn("total_score", submit.data)
        self.assertIn("radar_delta", submit.data)
        self.assertIn("delta", submit.data["radar_delta"])
        self.assertIn("weak_points", submit.data)

    def test_learner_snapshot_has_diagnosis_and_missions(self):
        # 先制造弱项样本
        gen = self.client.post(
            "/api/v1/cet/practice/",
            {"question_type": "reading", "count": 3},
            format="json",
        )
        self.assertEqual(gen.status_code, 200, gen.content)
        answers = {str(q["id"]): "Z" for q in (gen.data.get("questions") or [])}
        self.client.post("/api/v1/cet/practice/submit/", {"answers": answers}, format="json")

        snap = self.client.get("/api/v1/cet/analysis/learner-snapshot/")
        self.assertEqual(snap.status_code, 200, snap.content)
        self.assertIn("diagnosis", snap.data)
        self.assertIn("line", snap.data["diagnosis"])
        self.assertTrue(snap.data["diagnosis"]["line"].startswith("诊断依据"))
        self.assertIn("basis_tags", snap.data["diagnosis"])
        self.assertIn("today_missions", snap.data)
        self.assertGreaterEqual(len(snap.data["today_missions"]), 1)
        mission = snap.data["today_missions"][0]
        self.assertIn("diagnosis_line", mission)
        self.assertIn("path", mission)
        self.assertIn("review", snap.data)
        self.assertIn("suggested_review_date", snap.data["review"])
        self.assertIn("weak_practice", snap.data)
        self.assertEqual(snap.data["weak_practice"]["query"].get("count"), "8")

    def test_writing_grade_includes_evidence_line_without_llm(self):
        from apps.cet.models import CETExam
        from apps.cet.services import CETWritingService

        exam, _ = CETExam.objects.get_or_create(
            exam_type="cet4",
            year=2099,
            defaults={"title": "snap writing"},
        )
        q = CETQuestion.objects.create(
            exam=exam,
            question_type="writing",
            question_number=1,
            content="Write a short essay on campus life and teamwork.",
            difficulty=2,
        )
        # 无 API Key 时仍应返回结构化字段与 evidence_line
        result = CETWritingService(model="deepseek-chat").grade_writing(q, "Campus life is busy.")
        self.assertIn("evidence_line", result)
        self.assertTrue(result["evidence_line"].startswith("对照题目要求"))
        self.assertIn("campus life", result["evidence_line"].lower())

    def test_tutor_ask_enforces_turn_budget_and_closer(self):
        # 未达上限：可答，未强制收束
        r1 = self.client.post(
            "/api/v1/cet/tutor/ask/",
            {"message": "阅读长难句怎么拆？", "prior_user_turns": 0, "max_turns": 3},
            format="json",
        )
        self.assertEqual(r1.status_code, 200, r1.content)
        self.assertEqual(r1.data["user_turn_count"], 1)
        self.assertEqual(r1.data["turns_remaining"], 2)
        self.assertFalse(r1.data["session_closed"])
        self.assertIsNone(r1.data.get("closer"))

        # 最后一轮：关闭并给出练习 CTA
        r2 = self.client.post(
            "/api/v1/cet/tutor/ask/",
            {"message": "再讲一下主谓一致", "prior_user_turns": 2, "max_turns": 3},
            format="json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.data["session_closed"])
        self.assertEqual(r2.data["turns_remaining"], 0)
        self.assertIn("closer", r2.data)
        self.assertEqual(r2.data["closer"]["path"], "/cet/practice")
        self.assertEqual(r2.data["closer"]["query"].get("count"), "8")

        # 超额：只收束，不再新开聊
        r3 = self.client.post(
            "/api/v1/cet/tutor/ask/",
            {"message": "还想再问", "prior_user_turns": 3, "max_turns": 3},
            format="json",
        )
        self.assertEqual(r3.status_code, 200, r3.content)
        self.assertTrue(r3.data["session_closed"])
        self.assertIn("预算", r3.data["reply"])
