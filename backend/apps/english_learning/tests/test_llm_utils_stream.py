"""G3+：llm_utils 流式补全。"""
import unittest
from unittest.mock import MagicMock, patch

from apps.english_learning.skill_handlers.llm_utils import stream_chat_completion
from apps.english_learning.skill_handlers.stream_context import (
    reset_wizard_token_callback,
    set_wizard_token_callback,
)


class LlmUtilsStreamTests(unittest.TestCase):
    @patch("apps.english_learning.skill_handlers.llm_utils._get_api_key", return_value="test-key")
    @patch("apps.english_learning.skill_handlers.llm_utils._model_config")
    @patch("apps.english_learning.skill_handlers.llm_utils.requests.post")
    def test_stream_openai_compatible_emits_tokens(self, mock_post, mock_cfg, _mock_key):
        mock_cfg.return_value = {
            "api_base": "https://api.example.com/v1",
            "max_tokens": 100,
            "temperature": 0.2,
        }
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.raise_for_status = MagicMock()
        resp.iter_lines = MagicMock(
            return_value=[
                'data: {"choices":[{"delta":{"content":"Hel"}}]}',
                'data: {"choices":[{"delta":{"content":"lo"}}]}',
                "data: [DONE]",
            ]
        )
        mock_post.return_value = resp

        seen = []
        tok = set_wizard_token_callback(lambda t, n: seen.append(t))
        try:
            out = stream_chat_completion("sys", "user", model="deepseek-chat")
        finally:
            reset_wizard_token_callback(tok)

        self.assertEqual(out, "Hello")
        self.assertEqual(seen, ["Hel", "lo"])
