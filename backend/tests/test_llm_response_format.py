import unittest

from app.modules.news.crawler import _build_llm_request_payload


class LlmResponseFormatTests(unittest.TestCase):
    def test_ling_model_omits_response_format(self):
        payload = _build_llm_request_payload(
            "inclusionai/ling-3.0-flash-sante:free",
            "classify this article",
        )
        self.assertNotIn("response_format", payload)

    def test_fallback_model_keeps_json_response_format(self):
        payload = _build_llm_request_payload(
            "google/gemma-4-26b-a4b-it:free",
            "classify this article",
        )
        self.assertEqual(payload["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
