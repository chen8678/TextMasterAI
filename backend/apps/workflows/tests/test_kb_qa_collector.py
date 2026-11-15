from django.test import SimpleTestCase

from apps.workflows.kb_qa_collector_workflow import (
    format_sft_record,
    format_training_record,
    _normalize_questions,
)
from apps.workflows.kb_collector_personas import (
    build_workflow_config_from_persona,
    resolve_persona_for_kb,
)


class KbQaCollectorFormatTests(SimpleTestCase):
    def test_normalize_questions_from_strings(self):
        self.assertEqual(_normalize_questions(["  a  ", "", "b"]), ["a", "b"])

    def test_normalize_questions_from_dicts(self):
        raw = [{"question": "Q1"}, {"q": "Q2"}]
        self.assertEqual(_normalize_questions(raw), ["Q1", "Q2"])

    def test_format_sft_record_with_context(self):
        sft = format_sft_record(
            "测试问题",
            "测试答案",
            [{"title": "文档A", "content": "上下文内容"}],
        )
        self.assertIn("测试问题", sft["input"])
        self.assertIn("上下文内容", sft["input"])
        self.assertEqual(sft["output"], "测试答案")

    def test_format_training_record(self):
        record = format_training_record(
            question="Q",
            result={
                "answer": "A",
                "sources": ["doc1"],
                "context_docs": [{"title": "doc1", "content": "c"}],
                "skills_used": ["rag_answer"],
                "agent_id": "qa",
                "agent_name": "知识问答助手",
                "answer_source": "rag",
            },
            knowledge_base_id="kb-1",
            agent_id="qa",
            retrieval_params={"top_k": 5},
        )
        self.assertEqual(record["question"], "Q")
        self.assertEqual(record["answer"], "A")
        self.assertEqual(record["sft"]["output"], "A")

    def test_resolve_persona_for_cet4_kb(self):
        persona = resolve_persona_for_kb(
            knowledge_base_id="e34d217d-161e-4995-995d-5caabdc19a5f",
        )
        self.assertIsNotNone(persona)
        self.assertEqual(persona.id, "english_cet4_student")
        self.assertEqual(persona.role_name, "大二 CET-4 备考者")

    def test_build_workflow_config_from_persona(self):
        persona = resolve_persona_for_kb(
            knowledge_base_title="初中英语词汇库",
        )
        self.assertIsNotNone(persona)
        cfg = build_workflow_config_from_persona(persona)
        self.assertEqual(cfg["persona_id"], "english_junior_student")
        self.assertIn("seeds/english_junior.json", cfg["seed_path"])
        self.assertIn("初中英语", cfg["instruction"])
