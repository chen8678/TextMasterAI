from django.test import SimpleTestCase

from apps.scar.services.schema_compiler import compile_construction_units, repo_construction_data_dir
from apps.scar.services.compile_gate import compare_to_gold, load_gold_units
from apps.scar.services.scoring import score_case


class CompilerStabilityTests(SimpleTestCase):
    def test_compile_twice_same_paths(self):
        raw = (repo_construction_data_dir() / "samples" / "site_A.json").read_text(encoding="utf-8")
        a = compile_construction_units(raw)
        b = compile_construction_units(raw)
        self.assertEqual({u["path"] for u in a}, {u["path"] for u in b})
        self.assertEqual({u["unit_id"] for u in a}, {u["unit_id"] for u in b})

    def test_matches_gold(self):
        raw = (repo_construction_data_dir() / "samples" / "site_A.json").read_text(encoding="utf-8")
        compiled = compile_construction_units(raw)
        gold = load_gold_units(repo_construction_data_dir() / "gold" / "site_A.units.json")
        ok, errors = compare_to_gold(compiled, gold)
        self.assertTrue(ok, errors)

    def test_width_height_disambiguation_score(self):
        # 同值异字段：必须 path 对才算 field_accuracy
        s = score_case(
            predicted_path="2号楼/3层/窗高",
            predicted_value=1500,
            gold_path="2号楼/3层/窗宽",
            gold_value=1500,
            match_rule="numeric_tolerance",
        )
        self.assertFalse(s["field_accuracy"])
        self.assertFalse(s["path_hit"])
