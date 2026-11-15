"""G3+：wizard_sse 流式 invoke 单元测试（无 DB）。"""
import unittest

from apps.english_learning.graph import wizard_sse
from apps.english_learning.skill_handlers.stream_context import emit_wizard_token


class WizardSseStreamInvokeTests(unittest.TestCase):
    def test_invoke_with_tokens_drains_queue(self):
        def fake_invoke(_arg, config=None):
            emit_wizard_token("alpha", "roadmap_draft_skill")
            emit_wizard_token("beta", "roadmap_draft_skill")
            return {"phase": "roadmap_review", "poc_trace": ["roadmap_draft_skill"]}

        app = type("App", (), {"invoke": staticmethod(fake_invoke)})()
        out, tokens = wizard_sse._invoke_with_tokens(app, {"configurable": {"thread_id": "t1"}}, None)
        self.assertEqual(out["phase"], "roadmap_review")
        self.assertEqual([t["text"] for t in tokens], ["alpha", "beta"])
        self.assertEqual(tokens[0]["type"], "token")
