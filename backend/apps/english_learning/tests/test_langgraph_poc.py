"""G1：LangGraph POC（无 langgraph 环境时跳过）。"""
import unittest

from django.test import SimpleTestCase

from apps.english_learning.graph.nodes import WIZARD_GRAPH_NODE_NAMES
from apps.english_learning.graph.langgraph_poc import (
    LANGGRAPH_AVAILABLE,
    SQLITE_SAVER_AVAILABLE,
    invoke_english_graph_poc,
)


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "需要安装 langgraph")
class LangGraphPocTests(SimpleTestCase):
    databases = []  # 不访问数据库

    def setUp(self):
        from apps.english_learning.graph.langgraph_poc import reset_langgraph_poc_runtime_for_tests

        reset_langgraph_poc_runtime_for_tests()

    @unittest.skipUnless(
        LANGGRAPH_AVAILABLE and SQLITE_SAVER_AVAILABLE,
        "需要 langgraph 与 langgraph-checkpoint-sqlite",
    )
    def test_checkpointer_is_sqlite_when_package_present(self):
        from langgraph.checkpoint.sqlite import SqliteSaver

        from apps.english_learning.graph.langgraph_poc import get_compiled_poc_app

        app = get_compiled_poc_app()
        self.assertIsInstance(app.checkpointer, SqliteSaver)

    def test_invoke_full_wizard_stub_chain(self):
        out, tip = invoke_english_graph_poc(thread_id="poc:test-thread", initial={"phase": "intake", "poc_trace": []})
        self.assertEqual(out.get("phase"), "tutor")
        self.assertEqual(out.get("poc_trace"), list(WIZARD_GRAPH_NODE_NAMES))
        self.assertIsNotNone(tip)
        self.assertIn("checkpoint_id", tip)

    def test_get_compiled_poc_app_is_singleton(self):
        from apps.english_learning.graph.langgraph_poc import get_compiled_poc_app

        a = get_compiled_poc_app()
        b = get_compiled_poc_app()
        self.assertIs(a, b)

    def test_list_checkpoint_summaries_after_invoke(self):
        from apps.english_learning.graph.langgraph_poc import (
            invoke_english_graph_poc,
            list_langgraph_checkpoint_summaries,
        )

        invoke_english_graph_poc(thread_id="poc:list-test", initial={"phase": "intake", "poc_trace": []})
        rows = list_langgraph_checkpoint_summaries(thread_id="poc:list-test", limit=10)
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("checkpoint_id", rows[0])

    def test_advance_step_by_step_reaches_tutor(self):
        from apps.english_learning.graph.langgraph_poc import advance_english_graph_poc_step

        tid = "poc:advance-chain"
        completed = False
        for _ in range(len(WIZARD_GRAPH_NODE_NAMES) + 2):
            out, _, completed, _ = advance_english_graph_poc_step(
                thread_id=tid,
                initial={"phase": "intake", "poc_trace": []},
            )
            if completed:
                break
        self.assertTrue(completed)
        self.assertEqual(out.get("phase"), "tutor")
        self.assertEqual(out.get("poc_trace"), list(WIZARD_GRAPH_NODE_NAMES))

    def test_delete_thread_clears_summaries_and_invoke_still_full_chain(self):
        from apps.english_learning.graph.langgraph_poc import (
            delete_langgraph_poc_thread,
            invoke_english_graph_poc,
            list_langgraph_checkpoint_summaries,
        )

        tid = "poc:delete-thread-test"
        out1, _ = invoke_english_graph_poc(thread_id=tid, initial={"phase": "intake", "poc_trace": []})
        self.assertEqual(out1.get("phase"), "tutor")
        self.assertGreater(len(list_langgraph_checkpoint_summaries(thread_id=tid, limit=5)), 0)
        delete_langgraph_poc_thread(thread_id=tid)
        self.assertEqual(list_langgraph_checkpoint_summaries(thread_id=tid, limit=5), [])
        out2, _ = invoke_english_graph_poc(thread_id=tid, initial={"phase": "intake", "poc_trace": []})
        self.assertEqual(out2.get("phase"), "tutor")
        self.assertEqual(out2.get("poc_trace"), list(WIZARD_GRAPH_NODE_NAMES))
