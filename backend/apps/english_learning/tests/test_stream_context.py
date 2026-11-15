"""G3+：stream_context token 回调。"""
import unittest

from apps.english_learning.skill_handlers.stream_context import (
    emit_wizard_token,
    reset_wizard_token_callback,
    set_wizard_token_callback,
)


class StreamContextTests(unittest.TestCase):
    def test_emit_wizard_token_with_callback(self):
        seen = []

        def cb(text, node):
            seen.append((text, node))

        tok = set_wizard_token_callback(cb)
        try:
            emit_wizard_token("hello", "roadmap_draft_skill")
            emit_wizard_token("", "roadmap_draft_skill")
        finally:
            reset_wizard_token_callback(tok)

        self.assertEqual(seen, [("hello", "roadmap_draft_skill")])

    def test_emit_without_callback_is_noop(self):
        emit_wizard_token("ignored")
