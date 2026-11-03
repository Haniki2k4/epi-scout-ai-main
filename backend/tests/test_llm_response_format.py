import unittest
from unittest.mock import patch

from app.modules.news.crawler import _build_llm_request_payload


class LlmResponseFormatTests(unittest.TestCase):
    def test_local_profile_keeps_json_and_disables_thinking(self):
        with patch('app.modules.news.crawler.LLM_REASONING_EFFORT', 'none'):
            payload = _build_llm_request_payload('episcout-local', 'classify this article')
        self.assertEqual(payload['reasoning_effort'], 'none')
        self.assertEqual(payload['response_format'], {'type': 'json_object'})

    def test_oversized_input_is_not_silently_sent_to_a_small_context(self):
        from app.modules.news.crawler import _call_llm_api, LLMError
        with patch('app.modules.news.crawler.LLM_MAX_INPUT_BYTES', 100), patch('app.modules.news.crawler.requests.post') as post:
            with self.assertRaises(LLMError):
                _call_llm_api('episcout-local', 'ollama', 'http://127.0.0.1:11434/v1', 'x' * 101)
            post.assert_not_called()

    def test_ling_model_omits_response_format(self):
        payload = _build_llm_request_payload(
            "inclusionai/ling-3.0-flash-sante:free",
            "classify this article",
        )
        self.assertNotIn("response_format", payload)

    def test_output_cut_off_by_token_budget_is_rejected_even_if_json_parses(self):
        from unittest.mock import Mock
        from app.modules.news.crawler import _call_llm_api, LLMError
        response = Mock()
        response.json.return_value = {"choices": [{"finish_reason": "length", "message": {"content": '{"label":"relevant"}'}}]}
        with patch('app.modules.news.crawler.requests.post', return_value=response), patch('app.modules.news.crawler.LLM_MAX_INPUT_BYTES', 0):
            with self.assertRaisesRegex(LLMError, 'output budget'):
                _call_llm_api('episcout-local', 'ollama', 'http://127.0.0.1:11434/v1', 'article')

    def test_fallback_model_keeps_json_response_format(self):
        payload = _build_llm_request_payload(
            "google/gemma-4-26b-a4b-it:free",
            "classify this article",
        )
        self.assertEqual(payload["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
