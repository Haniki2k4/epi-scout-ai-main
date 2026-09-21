import importlib.util
from pathlib import Path
import sys
import unittest

path = Path(__file__).resolve().parents[1] / "app" / "modules" / "news" / "signal_detector.py"
spec = importlib.util.spec_from_file_location("signal_detector", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
detect_context_signal = module.detect_context_signal


class SignalDetectorTests(unittest.TestCase):
    def test_unexplained_cluster(self):
        match = detect_context_signal("Chùm ca sốt chưa rõ nguyên nhân tại trường A", "")
        self.assertIsNotNone(match)
        self.assertEqual(match.signal_type, "unexplained_cluster")
        self.assertIn("Chùm ca", match.evidence_text)

    def test_animal_signal(self):
        match = detect_context_signal("Gia cầm chết hàng loạt tại xã X", "Thú y lấy mẫu")
        self.assertEqual(match.signal_type, "animal_signal")

    def test_environment_signal(self):
        match = detect_context_signal("Nhiều người tiêu chảy sau ăn cỗ đám giỗ tại thôn Z", "Đang điều tra")
        self.assertEqual(match.signal_type, "environment_signal")

    def test_field_response(self):
        match = detect_context_signal("Phong tỏa ổ dịch tại xã X", "Cơ quan chức năng điều tra")
        self.assertEqual(match.signal_type, "field_response")

    def test_mass_poisoning_without_disease_name(self):
        match = detect_context_signal("Ngộ độc tập thể chưa rõ nguồn lây tại trường X", "")
        self.assertEqual(match.signal_type, "environment_signal")

    def test_wide_disinfection_without_disease_name(self):
        match = detect_context_signal("Phun hóa chất khử khuẩn diện rộng tại huyện X", "")
        self.assertEqual(match.signal_type, "field_response")

    def test_conference_does_not_veto_real_cluster(self):
        match = detect_context_signal("Hội nghị khẩn sau chùm ca sốt lạ tại trường X", "")
        self.assertEqual(match.signal_type, "unexplained_cluster")
        self.assertIn("Hội nghị", match.evidence_text)

    def test_advice_is_not_signal(self):
        self.assertIsNone(detect_context_signal("Tư vấn phun hóa chất tại nhà", "Dịch vụ giá rẻ"))

    def test_unrelated_school_absence_is_not_signal(self):
        self.assertIsNone(detect_context_signal("Nhiều học sinh nghỉ vì kỳ thi", "Sinh hoạt bình thường"))

    def test_no_single_phrase_detection(self):
        self.assertIsNone(detect_context_signal("Nhiều người trong lễ hội", ""))


if __name__ == "__main__":
    unittest.main()

