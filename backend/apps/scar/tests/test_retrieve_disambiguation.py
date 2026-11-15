"""T3.9：窗宽 vs 窗高同值消歧单测。"""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model

from apps.scar.services.retrieve import _detect_field_key, retrieve_evidence_pack
from apps.scar.services.schema_compiler import compile_construction_units, repo_construction_data_dir
from apps.scar.services.scoring import score_case


class OfflineDisambiguationTests(SimpleTestCase):
    def test_detect_prefers_window_width_over_height(self):
        self.assertEqual(_detect_field_key("2号楼3层窗宽是多少"), "window_width_mm")
        self.assertEqual(_detect_field_key("2号楼3层窗高是多少"), "window_height_mm")

    def test_compile_filter_width_not_height(self):
        raw = (repo_construction_data_dir() / "samples" / "site_A.json").read_text(encoding="utf-8")
        units = compile_construction_units(raw)
        # 同值 1500：按 field_key 过滤不得落到窗高
        width_units = [
            u
            for u in units
            if u["path"].startswith("2号楼/")
            and "/3层/" in u["path"]
            and u.get("metadata", {}).get("field_key") == "window_width_mm"
        ]
        self.assertTrue(width_units)
        self.assertEqual(width_units[0]["path"], "2号楼/3层/窗宽")
        self.assertEqual(str(width_units[0]["value_norm"]), "1500")
        # 评分：错指窗高不得 field_accuracy
        bad = score_case(
            predicted_path="2号楼/3层/窗高",
            predicted_value=1500,
            gold_path="2号楼/3层/窗宽",
            gold_value=1500,
            match_rule="numeric_tolerance",
        )
        self.assertFalse(bad["field_accuracy"])


class InDbDisambiguationTests(TestCase):
    def test_retrieve_width_not_height_when_compiled(self):
        from apps.knowledge.models import Document, KnowledgeBase
        from apps.scar.services.ingest import compile_document, ensure_construction_template

        User = get_user_model()
        user = User.objects.create_user(username="scar_disambig", password="x")
        ensure_construction_template()
        kb = KnowledgeBase.objects.create(
            title="scar disambig",
            owner=user,
            category="engineering",
        )
        raw = (repo_construction_data_dir() / "samples" / "site_A.json").read_text(encoding="utf-8")
        doc = Document.objects.create(
            knowledge_base=kb,
            title="site_A",
            content=raw,
            content_type="text",
        )
        result = compile_document(doc, domain="construction", raw_text=raw, vectorize=False)
        self.assertTrue(result.get("ok"), result)

        pack = retrieve_evidence_pack(
            "2号楼3层窗宽是多少毫米？",
            knowledge_base_id=str(kb.id),
            domain="construction",
        )
        primary = pack.primary()
        self.assertIsNotNone(primary)
        self.assertIn("窗宽", primary.path)
        self.assertNotIn("窗高", primary.path)
