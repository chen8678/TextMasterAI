"""T7：BIM 桥接与半结构轨纪律。"""

from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.scar.services.bim_bridge import bim_payload_to_construction_site
from apps.scar.services.schema_compiler import compile_construction_units
from apps.scar.services.semi_structure import SemiStructureError, parse_semi_structure_spans


class BimBridgeTests(SimpleTestCase):
    def test_bridge_extracts_whitelist_with_source_ref(self):
        sample = Path(__file__).resolve().parents[4] / "SCAR" / "data" / "construction" / "samples" / "sample_bim_site.json"
        # parents: tests->scar->apps->backend->repo = 4? 
        # __file__ = backend/apps/scar/tests/test_t7_bim.py
        # parents[0]=tests [1]=scar [2]=apps [3]=backend [4]=repo
        data = json.loads(sample.read_text(encoding="utf-8"))
        site = bim_payload_to_construction_site(data)
        self.assertTrue(site["buildings"])
        measures = site["buildings"][0]["floors"][0]["measures"]
        self.assertIn("window_width_mm", measures)
        self.assertEqual(measures["window_width_mm"]["value"], 1500)
        self.assertTrue(measures["window_width_mm"]["source_ref"])
        # LLM 建议 9999 不得入定案
        self.assertNotEqual(measures["window_width_mm"]["value"], 9999)

    def test_compile_preserves_source_ref(self):
        site = {
            "site_id": "x",
            "buildings": [
                {
                    "building_id": "B1",
                    "name": "1号楼",
                    "floors": [
                        {
                            "floor_id": "F1",
                            "name": "1层",
                            "measures": {
                                "window_width_mm": {
                                    "value": 1200,
                                    "unit": "mm",
                                    "source_ref": "$.elements[0].properties.window_width_mm#id=1",
                                }
                            },
                        }
                    ],
                }
            ],
        }
        units = compile_construction_units(site)
        self.assertEqual(units[0]["source_ref"], "$.elements[0].properties.window_width_mm#id=1")


class SemiStructureTests(SimpleTestCase):
    def test_rejects_without_spans(self):
        with self.assertRaises(SemiStructureError):
            parse_semi_structure_spans("窗宽 1500mm", spans=None)

    def test_accepts_with_span_binding(self):
        units = parse_semi_structure_spans(
            "窗宽1500",
            spans=[
                {
                    "field_key": "window_width_mm",
                    "value": 1500,
                    "start": 0,
                    "end": 6,
                    "path": "doc/窗宽",
                }
            ],
        )
        self.assertEqual(len(units), 1)
        self.assertTrue(units[0]["source_ref"])
