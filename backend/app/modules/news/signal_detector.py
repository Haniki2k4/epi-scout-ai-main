"""Deterministic context signals for RSS entries without a disease keyword."""

from dataclasses import dataclass
import re


DETECTOR_VERSION = "1"


@dataclass(frozen=True)
class SignalMatch:
    signal_type: str
    matched_phrases: tuple[str, ...]
    evidence_text: str


_RULES = (
    (
        "unexplained_cluster",
        ("chùm ca", "nhiều người cùng mắc", "hàng chục người", "nhiều học sinh", "chùm bệnh nhân", "học sinh nghỉ hàng loạt", "học sinh nghỉ học hàng loạt"),
        ("sốt", "nhập viện", "tử vong", "triệu chứng", "nghi lây", "điều tra", "chưa rõ nguyên nhân", "bất thường"),
        ("vì mưa bão", "vì nghỉ hè", "vì đình công", "vì kỳ thi", "vì lũ lụt"),
    ),
    (
        "animal_signal",
        ("gia cầm chết hàng loạt", "chó dại cắn", "gà vịt chết", "lợn chết", "bò chết", "động vật nghi nhiễm", "thú y lấy mẫu"),
        ("tại xã", "tại huyện", "tại thôn", "tại tỉnh", "tại ấp", "đang điều tra", "lấy mẫu", "xử lý"),
        ("mua bán", "giá cả", "chợ gia súc", "xuất khẩu gia cầm"),
    ),
    (
        "environment_signal",
        ("nguồn nước nhiễm", "nước ô nhiễm", "thực phẩm nhiễm khuẩn", "ngộ độc thực phẩm", "nước sinh hoạt bị nhiễm", "ngộ độc sau ăn", "ngộ độc tập thể", "nhiều người bị sau khi ăn", "ăn cỗ bị ngộ độc", "nhiều người tiêu chảy", "bệnh sau bữa ăn tập thể"),
        ("nhiều hộ dân", "nhiều người", "đang điều tra", "cơ quan chức năng", "lấy mẫu", "chưa rõ nguồn", "chưa rõ nguyên nhân", "tập thể"),
        ("dịch vụ lọc nước", "mua thiết bị", "quảng cáo", "giá lọc nước"),
    ),
    (
        "field_response",
        ("phong tỏa ổ dịch", "lập chốt kiểm dịch", "khử khuẩn diện rộng", "phun hóa chất", "cách ly tập trung", "cách ly bắt buộc"),
        ("dịch bệnh", "nguy cơ lây", "ổ dịch", "kiểm dịch", "diện rộng", "tại xã", "tại huyện", "tại thôn", "tại tỉnh"),
        ("dịch vụ phun khử khuẩn", "giá", "đặt lịch", "tư vấn"),
    ),
)


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def detect_context_signal(title: str, summary: str) -> SignalMatch | None:
    """Require a signal phrase and supporting context; never infer disease."""
    original_title, original_summary = title or "", summary or ""
    title = " ".join(original_title.casefold().split())
    summary = " ".join(original_summary.casefold().split())
    text = f"{title} {summary}"
    for signal_type, triggers, context, exclusions in _RULES:
        found_triggers = tuple(phrase for phrase in triggers if _contains(text, phrase))
        if not found_triggers or not any(_contains(text, phrase) for phrase in context):
            continue
        if any(_contains(title, phrase) for phrase in exclusions):
            continue
        matched = found_triggers + tuple(phrase for phrase in context if _contains(text, phrase))
        return SignalMatch(signal_type, tuple(dict.fromkeys(matched)), (original_title + ". " + original_summary).strip(". ")[:1000])
    return None
