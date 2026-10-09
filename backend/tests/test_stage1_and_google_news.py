import base64
import json
import requests
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.app.modules.news.google_news import resolve_google_news_url
from backend.app.modules.news.stage1_context import is_advisory_without_outbreak_evidence


class Stage1ContextTests(TestCase):
    def test_rejects_personal_health_question(self):
        self.assertTrue(is_advisory_without_outbreak_evidence(
            "Người lớn có mắc tay chân miệng không?",
            "Bác sĩ giải đáp triệu chứng và cách chăm sóc.",
        ))

    def test_rejects_food_safety_question_like_sample_577(self):
        self.assertTrue(is_advisory_without_outbreak_evidence(
            "Thịt hộp ăn không hết, mai ăn tiếp có nguy cơ ngộ độc botulinum không?",
            "Hướng dẫn bảo quản thức ăn.",
        ))

    def test_keeps_question_when_summary_reports_concrete_cases(self):
        self.assertFalse(is_advisory_without_outbreak_evidence(
            "Vì sao sốt xuất huyết tăng?",
            "Hà Nội mới ghi nhận 25 ca mắc và đang khoanh vùng ổ dịch.",
        ))

    def test_keeps_regular_outbreak_report(self):
        self.assertFalse(is_advisory_without_outbreak_evidence(
            "Hà Nội ghi nhận ổ dịch sởi",
            "Ba trường hợp dương tính tại một trường học.",
        ))


class GoogleNewsResolverTests(TestCase):
    def setUp(self):
        resolve_google_news_url.cache_clear()

    def test_decodes_legacy_embedded_url_without_network(self):
        source = "https://thanhnien.vn/example.htm"
        payload = b"\x08\x13\x22" + bytes([len(source)]) + source.encode() + b"\xd2\x01\x00"
        token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        url = f"https://news.google.com/rss/articles/{token}?oc=5"
        with patch("backend.app.modules.news.google_news.requests.Session") as session:
            self.assertEqual(resolve_google_news_url(url), source)
            session.assert_not_called()

    @patch("backend.app.modules.news.google_news.requests.Session")
    def test_decodes_dynamic_token_with_signature_and_timestamp(self, session_class):
        source = "https://thanhnien.vn/bai-viet.htm"
        page = Mock()
        page.text = '<div data-n-a-sg="signature" data-n-a-ts="123456" data-n-a-id="opaque"></div>'
        page.raise_for_status.return_value = None
        outer = [["wrb.fr", "Fbv4je", json.dumps(["garturlres", source])]]
        response = Mock()
        response.text = ")]}'\n\n" + json.dumps(outer)
        response.raise_for_status.return_value = None
        session = session_class.return_value
        session.get.return_value = page
        session.post.return_value = response

        url = "https://news.google.com/rss/articles/opaque?oc=5"
        self.assertEqual(resolve_google_news_url(url), source)
        request_payload = session.post.call_args.kwargs["data"]["f.req"]
        self.assertIn("signature", request_payload)
        self.assertIn("123456", request_payload)

    @patch("backend.app.modules.news.google_news.requests.Session")
    def test_returns_google_url_when_dynamic_resolution_fails(self, session_class):
        session_class.return_value.get.side_effect = requests.RequestException("network error")
        url = "https://news.google.com/rss/articles/opaque?oc=5"
        self.assertEqual(resolve_google_news_url(url), url)
