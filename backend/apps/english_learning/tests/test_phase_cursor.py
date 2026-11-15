"""`phase` → 占位 `node_cursor` 规则单测。"""
from django.test import SimpleTestCase

from apps.english_learning.graph.phase_cursor import apply_phase_cursor_to_checkpoint, node_cursor_for_session_phase


class PhaseCursorLogicTests(SimpleTestCase):
    def test_node_cursor_for_known_phases(self):
        self.assertEqual(node_cursor_for_session_phase({"phase": "tutor"}), 8)
        self.assertEqual(node_cursor_for_session_phase({"phase": "ROADMAP_REVIEW"}), 6)
        self.assertEqual(node_cursor_for_session_phase({"phase": "assessment"}), 2)

    def test_apply_only_advances_cursor(self):
        cur, ch = apply_phase_cursor_to_checkpoint(session_state={"phase": "intake"}, current_cursor=3)
        self.assertFalse(ch)
        self.assertEqual(cur, 3)

    def test_apply_advances_when_phase_ahead(self):
        cur, ch = apply_phase_cursor_to_checkpoint(session_state={"phase": "tutor"}, current_cursor=0)
        self.assertTrue(ch)
        self.assertEqual(cur, 8)
