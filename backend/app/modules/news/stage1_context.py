"""Context guards for the keyword route (Gate A)."""
import re

ADVISORY_TITLE_PATTERN = re.compile(
    r"(\?|\b(có (mắc|bị|lây|nguy cơ).+không|"
    r"(ai|người lớn|trẻ em|phụ nữ|bà bầu).+(có mắc|có bị|nên|không)|"
    r"(bệnh|triệu chứng).+(là gì|thế nào)|"
    r"(nên ăn gì|kiêng gì|uống gì|phải làm sao|điều trị tại nhà)|"
    r"(hỏi đáp|chuyên gia giải đáp|bác sĩ giải đáp))\b)",
    re.IGNORECASE,
)
STRONG_OUTBREAK_EVIDENCE_PATTERN = re.compile(
    r"(\d+[\d.,]*\s*(ca|trường hợp|người)\s*(mắc|nhiễm|tử vong|nhập viện)|"
    r"ổ dịch|chùm ca|bùng phát|mới ghi nhận|vừa phát hiện|dương tính|"
    r"phong tỏa|khoanh vùng|phun (hóa chất|khử khuẩn)|lập chốt kiểm dịch|"
    r"(gia cầm|động vật|học sinh)\s+(chết|nghỉ học)\s+hàng loạt)",
    re.IGNORECASE,
)


def is_advisory_without_outbreak_evidence(title: str, summary: str) -> bool:
    """True for advice/FAQ headlines that contain no concrete outbreak signal."""
    return bool(
        ADVISORY_TITLE_PATTERN.search(title)
        and not STRONG_OUTBREAK_EVIDENCE_PATTERN.search(f"{title} {summary}")
    )

