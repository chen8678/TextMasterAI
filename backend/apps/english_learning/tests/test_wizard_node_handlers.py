"""G1：向导节点 handler 与 phase 对齐。"""
import unittest

from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES
from apps.english_learning.graph.wizard_node_handlers import apply_wizard_node


class WizardNodeHandlerTests(unittest.TestCase):
    def test_each_node_sets_expected_phase(self):
        state = {"phase": "intake", "poc_trace": []}
        expected = {
            "intake_tags": "intake",
            "placement_or_confirm": "intake",
            "assessment_run": "assessment",
            "assessment_score": "assessment",
            "gap_feedback": "roadmap",
            "roadmap_draft_skill": "roadmap",
            "roadmap_hitl": "roadmap_editing",
            "roadmap_finalize_skill": "tutor",
            "tutor_runtime": "tutor",
        }
        for i, name in enumerate(WIZARD_GRAPH_NODE_NAMES):
            out = apply_wizard_node(name, state, is_last=(i == len(WIZARD_GRAPH_NODE_NAMES) - 1))
            self.assertEqual(out["phase"], expected[name])
            state = {**state, **out}

    def test_trace_accumulates(self):
        out = apply_wizard_node("intake_tags", {"poc_trace": []})
        self.assertEqual(out["poc_trace"], ["intake_tags"])
