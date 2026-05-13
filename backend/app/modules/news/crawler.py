import feedparser
from sqlalchemy.orm import Session
from . import crud, models, schemas
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, unquote
from email.utils import parsedate_to_datetime
import re
import html
import json
import os
import time
import unicodedata
import base64
from dateutil import parser
import pytz
from bs4 import BeautifulSoup

# -------- GITHUB HELPERS (rs.py from nghait) --------
TZ_INFOS = {
    "UTC": pytz.utc,
    "EDT": pytz.timezone("America/New_York"),
    "EST": pytz.timezone("America/New_York"),
    "PDT": pytz.timezone("America/Los_Angeles"),
    "PST": pytz.timezone("America/Los_Angeles"),
    "CST": pytz.timezone("America/Chicago"),
    "CDT": pytz.timezone("America/Chicago"),
    "MST": pytz.timezone("America/Denver"),
    "MDT": pytz.timezone("America/Denver"),
    "BST": pytz.timezone("Europe/London"),
    "GMT": pytz.utc,
    "CET": pytz.timezone("Europe/Paris"),
    "CEST": pytz.timezone("Europe/Paris"),
    "ICT": pytz.timezone("Asia/Bangkok"),
    "SGT": pytz.timezone("Asia/Singapore"),
    "JST": pytz.timezone("Asia/Tokyo"),
    "IST": pytz.timezone("Asia/Kolkata"),
}

def parse_date_advanced(entry) -> datetime:
    """Tự viết hàm giải mã date bằng dateutil chống lỗi thư viện feedparser"""
    hcm_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    date_string = entry.get("published", "") or entry.get("updated", "")
    if not date_string:
        return datetime.now(hcm_tz)
    try:
        dt = parser.parse(date_string, tzinfos=TZ_INFOS)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.utc)
        return dt.astimezone(hcm_tz)
    except ValueError:
        return datetime.now(hcm_tz)

def get_source_url(source_url: str) -> str:
    """Decode Google News Base64 link thành link báo nguyên bản."""
    try:
        url = urlparse(source_url)
        path = url.path.split('/')
        if url.hostname == "news.google.com" and len(path) > 1 and path[-2] == "articles":
            base64_str = path[-1]
            decoded_bytes = base64.urlsafe_b64decode(base64_str + '==')
            decoded_str = decoded_bytes.decode('latin1')
            prefix = bytes([0x08, 0x13, 0x22]).decode('latin1')
            if decoded_str.startswith(prefix):
                decoded_str = decoded_str[len(prefix):]
            suffix = bytes([0xd2, 0x01, 0x00]).decode('latin1')
            if decoded_str.endswith(suffix):
                decoded_str = decoded_str[:-len(suffix)]
            bytes_array = bytearray(decoded_str, 'latin1')
            length = bytes_array[0]
            decoded_str = decoded_str[2:length+1] if length >= 0x80 else decoded_str[1:length+1]
            return decoded_str
    except Exception:
        pass
    return source_url
# --------------------------------

import requests
from ...core.logger import get_logger
from sentence_transformers import SentenceTransformer, util

logger = get_logger("backend.news.crawler")

# --- Global Flags ---
is_scanning_flag = False

# --- Global Embedding Model (Lazy Loaded) ---
_embedding_model = None

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Initializing SentenceTransformer (MiniLM-L12-v2)...")
        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model

def fetch_sapo(url: str) -> str | None:
    """
    Fetch URL bài báo và trả về đoạn sapo thực sự.
    Ưu tiên: class .sapo / .lead / .article-sapo / .article_sapo > <p> đầu trong content
    Trả về None nếu lỗi (network / timeout / parse fail)
    """
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Xóa các script, style, header, footer và các thành phần không mong muốn
        for el in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            el.decompose()
        
        # Xóa các khối tin liên quan, quảng cáo, bình luận thường gặp
        NOISY_SELECTORS = [
            ".article_footer", ".article-footer", ".related-news", ".related_news",
            ".article_tag", ".article-tag", "#comment", "#ads", ".ads",
            "div[id*='adsweb']", "div[class*='related']",
            ".box_comment_vne", ".box-tinlienquanv2", ".box-item-vne"
        ]
        for selector in NOISY_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        # Ưu tiên 1: sapo class phổ biến của các báo VN
        SAPO_CLASSES = ["sapo", "lead", "article-sapo", "article_sapo",
                        "article-desc", "article_description", "description", "detail-sapo"]
        for cls in SAPO_CLASSES:
            # Match element nào có class chứa tên hoặc khớp toàn bộ tên class
            for el in soup.find_all(class_=lambda x: x and cls in x.lower() if isinstance(x, str) else x and [c for c in x if cls in c.lower()]):
                text = el.get_text(separator=" ", strip=True)
                if len(text) > 30:
                    return text[:500]

        # Ưu tiên 2: <p> đầu tiên trong content block
        CONTENT_CLASSES = ["article-body", "article_body", "article-content",
                           "content", "post-content", "entry-content", "detail-content"]
        for cls in CONTENT_CLASSES:
            for block in soup.find_all(class_=lambda x: x and cls in x.lower() if isinstance(x, str) else x and [c for c in x if cls in c.lower()]):
                p = block.find("p")
                if p:
                    text = p.get_text(separator=" ", strip=True)
                    if len(text) > 30:
                        return text[:500]
        return None
    except Exception as e:
        logger.debug(f"Failed to fetch sapo for {url}: {e}")
        return None

# ---------------------------------------------------------------------------
# Keyword filter lists
# ---------------------------------------------------------------------------

# Hard-exclude on title only — lifestyle / ads / personal advice.
# Intentionally narrow: loại sai còn nguy hiểm hơn giữ thừa,
# vì LLM sẽ xử lý phần còn lại.
HARD_EXCLUDE_TITLE_TERMS = [
    "nên ăn gì", "uống gì", "làm đẹp", "giảm cân",
    "thực phẩm chức năng", "bí quyết", "mẹo hay", "mẹo vặt",
    "review ", "quảng cáo", "khuyến mãi", "24/7", "infographic",
    "dấu hiệu sớm", "dấu hiệu", "tư vấn bác sĩ", "kinh nghiệm",
    "hướng dẫn", "linh vật", "lao động", "bài thuốc dân gian",
    "lao lý", "lao đao", "lao vào", "lao đến", "lao đi", "loa từ",
    "lao xuống", "lao lên", "lao về", "lao bảo", "lao thẳng", "lao vào",
    "có chữa khỏi không", "đề cử", "hiệu quả", "giúp trị khỏi", 
    "tin tức sáng", "tin tức 24h", "tin tức hôm nay", "tin tức chiều",
    "hồi sinh", "hội thảo", "hội nghị", "lao như", "giành giật",
    "clip", "nổ súng", "lao sang", "lao ra", "lao thẳng", "lao về phía",
    "lao tới", "kết thúc ", "nâng cao", "lao khỏi", "video", "lao qua",
]

# Context terms that raise the epidemiological signal score
EPIDEMIC_CONTEXT_TERMS = [
    "bệnh", "dịch", "ổ dịch", "ca bệnh", "ca mắc", "nhiễm", "lây", "lây lan",
    "virus", "vi rút", "xét nghiệm", "dương tính", "tử vong", "nhập viện",
    "điều trị", "triệu chứng", "bùng phát", "kiểm soát", "giám sát", "khẩn cấp",
    "y tế", "truyền nhiễm", "nghi nhiễm", "ca tử vong", "ngộ độc",
]

# Context terms that reduce the signal score (lifestyle / non-epidemic / advisory usage)
NON_EPIDEMIC_CONTEXT_TERMS = [
    "đau", "nhức", "vùng kín", "tinh hoàn", "sinh lý", "nam sinh", "quan hệ",
    "thẩm mỹ", "làm đẹp", "giảm cân", "thực đơn", "món ăn", "ăn uống", "tâm lý",
    "chuyện ấy", "sẹo", "da mặt", "mụn", "xương khớp", "phòng the",
    "tư vấn", "hướng dẫn", "cách phòng", "nhầm với", "bài thuốc", 
    "chữa bệnh", "tự chữa", "cách giải quyết", "có gì đặc biệt",
    "cách tốt nhất", "dễ nhầm lẫn"
]

# ---------------------------------------------------------------------------
# Extended Scan deduplication config
# ---------------------------------------------------------------------------
MATCH_THRESHOLD_EXTENDED = 0.8  # Tự động lọc các bài báo mở rộng có độ tương đồng > 0.8

# ---------------------------------------------------------------------------
# LLM re-check config
# ---------------------------------------------------------------------------
LLM_RECHECK_ENABLED = os.getenv("LLM_RECHECK_ENABLED", "false").lower() == "true"
LLM_RECHECK_MODEL = os.getenv("LLM_RECHECK_MODEL", "").strip()
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "").strip()
LLM_RECHECK_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_RECHECK_BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
LLM_RECHECK_TIMEOUT_SECONDS = int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20"))
LLM_CIRCUIT_BREAKER_THRESHOLD = max(int(os.getenv("LLM_CIRCUIT_BREAKER_THRESHOLD", "3")), 1)
LLM_MAX_RETRIES = max(int(os.getenv("LLM_MAX_RETRIES", "2")), 1)
LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS = int(
    os.getenv("LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS", "300")
)
LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS = int(
    os.getenv("LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS", "60")
)
LLM_FEW_SHOT_DATASET_PATH = os.getenv("LLM_FEW_SHOT_DATASET_PATH", "data/llm_evaluation_dataset.xlsx").strip()
LLM_FEW_SHOT_DATASET_MAX_EXAMPLES = min(
    max(int(os.getenv("LLM_FEW_SHOT_DATASET_MAX_EXAMPLES", "5")), 0),
    5,
)

# ---------------------------------------------------------------------------
# LLM prompt constants  (defined at module level → zero per-call overhead)
# ---------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = (
    "Bạn là chuyên gia dịch tễ học AI. "
    "Nhiệm vụ: phân tích bài báo, TỰ ĐỘNG DỊCH/HIỂU NỘI DUNG NƯỚC NGOÀI (nếu có) sang Tiếng Việt và trả về JSON hợp lệ. "
    "Lưu ý: Mọi text trong JSON (tên bệnh, location, reason...) BẰNG TIẾNG VIỆT hoặc TIẾNG ANH tùy theo chủ đề nhưng phải TƯƠNG ĐƯƠNG với từ khóa y tế Việt Nam. Không giải thích thêm ngoài JSON."
)

# Few-shot examples (7 examples covering 4 labels):
#   2 relevant  (ổ dịch cụ thể + nhiều bệnh cùng lúc)
#   2 noise     (tư vấn cá nhân + bài dịch vụ/so sánh)
#   1 irrelevant (tổng kết lịch sử hoàn toàn không liên quan)
#   1 unsure    (thông tin mơ hồ, chưa xác nhận)
_FEW_SHOT_BLOCK = """
## Ví dụ tham khảo

### Ví dụ 1 — relevant (ổ dịch cụ thể, có số liệu mới)
Tiêu đề: Hà Nội, TP.HCM ghi nhận thêm 23 ca sốt xuất huyết trong một tuần, cảnh báo bùng phát
Tóm tắt: CDC xác nhận phát sinh 23 ca mắc mới bệnh sốt xuất huyết tại hai thành phố.
→ {"label":"relevant","matched_keywords":["sốt xuất huyết"],"location":"Hà Nội, TP.HCM","diseases":[{"disease_name":"sốt xuất huyết","cumulative_cases":0,"new_cases":23,"event_start_date":null,"event_end_date":null}],"severity":"medium","reason":"Ổ dịch cụ thể, nói rõ số ca phát sinh mới tại nhiều tỉnh."}

### Ví dụ 2 — relevant (bài đề cập NHIỀU BỆNH cùng lúc — TÁCH RIÊNG từng bệnh)
Tiêu đề: Phát hiện ổ dịch thuỷ đậu tại một điểm trường tiểu học ở Đắk Lắk
Tóm tắt: Đến nay, tại ổ dịch này đã ghi nhận 26 trường hợp mắc bệnh thủy đậu (23 học sinh, 3 giáo viên), 1 trường hợp mắc bệnh tay chân miệng.
→ {"label":"relevant","matched_keywords":["thủy đậu","tay chân miệng"],"location":"Đắk Lắk","diseases":[{"disease_name":"thủy đậu","cumulative_cases":26,"new_cases":0,"event_start_date":null,"event_end_date":null},{"disease_name":"tay chân miệng","cumulative_cases":0,"new_cases":1,"event_start_date":null,"event_end_date":null}],"severity":"medium","reason":"Ổ dịch trường học, nhiều loại bệnh cùng được ghi nhận."}

### Ví dụ 3 — noise (tư vấn điều trị cá nhân — có đề cập bệnh nhưng không có sự kiện dịch tễ)
Tiêu đề: 5 sai lầm thường gặp khi điều trị sốt xuất huyết tại nhà
Tóm tắt: Nhiều người tự ý uống thuốc hạ sốt gây nguy hiểm, chuyên gia chỉ ra 5 lỗi phổ biến.
→ {"label":"noise","matched_keywords":[],"location":"unknown","diseases":[],"severity":null,"reason":"Bài tư vấn điều trị cá nhân, tên bệnh chỉ là ngữ cảnh, không có ổ dịch."}

### Ví dụ 4 — noise (bài dịch vụ / dinh dưỡng — dùng tên bệnh để so sánh hoặc tiếp thị)
Tiêu đề: Bị sốt xuất huyết nên ăn gì để mau khỏi?
Tóm tắt: Chuyên gia dinh dưỡng gợi ý thực đơn cho bệnh nhân sốt xuất huyết đang hồi phục tại nhà.
→ {"label":"noise","matched_keywords":[],"location":"unknown","diseases":[],"severity":null,"reason":"Bài dịch vụ/dinh dưỡng, tên bệnh chỉ là bối cảnh tư vấn."}

### Ví dụ 5 — noise (thảo luận / so sánh — đề cập bệnh như ví dụ minh họa)
Tiêu đề: Vì sao sốt xuất huyết nguy hiểm hơn COVID-19 ở trẻ em?
Tóm tắt: Bài viết phân tích, so sánh mức độ nguy hiểm của hai bệnh, không báo cáo ca bệnh cụ thể.
→ {"label":"noise","matched_keywords":[],"location":"unknown","diseases":[],"severity":null,"reason":"Bài thảo luận/so sánh, đề cập bệnh để minh họa, không có sự kiện dịch tễ."}

### Ví dụ 6 — irrelevant (bài hoàn toàn không liên quan — tổng kết lịch sử xa)
Tiêu đề: Nhìn lại đại dịch COVID-19: 3 năm Việt Nam ứng phó như thế nào?
Tóm tắt: Bài viết tổng kết quá trình chống dịch COVID 2020–2023, các bài học cho tương lai.
→ {"label":"irrelevant","matched_keywords":[],"location":"unknown","diseases":[],"severity":null,"reason":"Tổng kết lịch sử xa, không có sự kiện đang diễn ra."}

### Ví dụ 7 — unsure (thông tin mơ hồ, chưa xác nhận chính thức)
Tiêu đề: Xuất hiện bệnh lạ tại miền Trung khiến nhiều người lo ngại
Tóm tắt: Một số người dân phản ánh triệu chứng bất thường, ngành y tế địa phương đang xác minh.
→ {"label":"unsure","matched_keywords":["bệnh lạ"],"location":"miền Trung","diseases":[{"disease_name":"bệnh lạ","cumulative_cases":0,"new_cases":0,"event_start_date":null,"event_end_date":null}],"severity":null,"reason":"Chưa có xác nhận chính thức, cần theo dõi thêm."}
""".strip()

_CRITERIA_BLOCK = """
## Tiêu chí phân loại

**relevant** — bài phải có ÍT NHẤT MỘT trong:
1. Ca bệnh / ổ dịch tại địa điểm + thời gian cụ thể
2. Cảnh báo chính thức từ Bộ Y tế / CDC / WHO / chính quyền
3. Số liệu ca mắc, tử vong, nhập viện được công bố
4. Bùng phát bệnh truyền nhiễm đang diễn ra

**noise** — Bài CÓ ĐỀ CẬP tên dịch bệnh nhưng không có sự kiện dịch tễ thực. Gồm:
- Tư vấn cá nhân: "nên ăn gì", "uống gì", "mẹo hay", "bí quyết", "kinh nghiệm", "hướng dẫn", "5 sai lầm", "7 lưu ý".
- Bài dịch vụ / quảng cáo / review sản phẩm có nhắc đến bệnh như ngữ cảnh.
- Bài thảo luận, so sánh hoặc giải thích triệu chứng — bệnh được nhắc để minh họa, không có ca mắc.
- Bài thuốc dân gian, trị mẹo không có bằng chứng dịch tễ cụ thể.
- **PHÂN BIỆT noise vs irrelevant:** Nếu tên bệnh XUẤT HIỆN trong bài → noise. Nếu bài hoàn toàn không liên quan đến y tế / dịch bệnh → irrelevant.

**irrelevant** — Bài KHÔNG liên quan đến dịch bệnh (PHẢI LOẠI BỎ):
- Tổng kết lịch sử lâu đời, hồi ký, không có sự kiện đang diễn ra.
- Bài xã hội/hành động: "lao động", "lao lý", "lao đao", "lao vào"...
- Không có keyword dịch bệnh nào trong bài.
- **QUY TẮC BỆNH CHÍNH:** Nếu bệnh chính của bài (ví dụ: Melioidosis) KHÔNG trong danh sách keyword → irrelevant, dù có nhắc biến chứng trùng keyword.

**unsure** — thông tin quá mơ hồ, chưa có xác nhận chính thức
""".strip()

_SCHEMA_BLOCK = """
## Output schema (JSON hợp lệ — không thêm bất kỳ text nào ngoài JSON)
{
  "label": "relevant" | "noise" | "irrelevant" | "unsure",
  "matched_keywords": [<chỉ chọn từ danh sách keyword bên dưới, mảng rỗng nếu irrelevant>],
  "location": "<Tỉnh/thành phố ghi cách nhau bằng dấu phẩy. Nếu không có địa điểm mắc bệnh, ghi 'unknown'>",
  "diseases": [
    {
      "disease_name": "<tên bệnh, PHẢI nằm trong danh sách keyword bên dưới>",
      "cumulative_cases": <số nguyên, 0 nếu không đề cập>,
      "new_cases": <số nguyên, số ca ghi nhận mới, 0 nếu không đề cập>,
      "new_cases": <số nguyên, số ca ghi nhận mới, 0 nếu không đề cập>,
      "event_start_date": "<YYYY-MM-DD tương ứng với thời gian bắt đầu sự kiện thực tế được nhắc đến, null nếu không rõ>",
      "event_end_date": "<YYYY-MM-DD tương ứng với thời gian kết thúc sự kiện, null nếu không rõ>"
    }
  ],
  "validation_note": "<Giải thích ngắn tại sao bạn chọn các số liệu này>",
  "severity": "low" | "medium" | "high" | null,
  "reason": "<tối đa 20 từ tiếng Việt>"
}

**QUY TẮC BÓC TÁCH SỐ CA CỦA MẢNG 'diseases' (CỰC KỲ QUAN TRỌNG):**
- NẾU báo cáo là TỔNG HỢP lũy kế tính từ quá khứ (ví dụ: "từ đầu năm đến nay", "tích lũy từ đầu năm tới 21 tháng 1"): TUYỆT ĐỐI BỎ QUA số ca đó (đặt cumulative_cases = 0, new_cases = 0).
- CHỈ LẤY số liệu nếu bài báo báo cáo số ca TRONG MỘT CHU KỲ/KHOẢNG THỜI GIAN NGẮN (ví dụ: "từ 23/1 đến 29/1", "trong tuần 12", "tuần qua").
- CHÚ Ý VỀ THỜI GIAN SỰ KIỆN (event_start_date, event_end_date): Trích xuất chính xác thời gian thực tế mà sự kiện bùng phát (vd: "hôm qua", "tuần trước" phải được quy đổi ra ngày YYYY-MM-DD dựa trên ngữ cảnh). Nếu sự kiện đã quá cũ, hệ thống sẽ tự động lọc. Mọi từ khóa ngoại ngữ (ví dụ flu, dengue) phải được quy chuẩn thành tiếng Việt (cúm, sốt xuất huyết).
- **QUY TẮC VỀ BIẾN CHỨNG/TRIỆU CHỨNG (QUAN TRỌNG):** Tuyệt đối KHÔNG đưa các triệu chứng hoặc biến chứng (ví dụ: sốc nhiễm khuẩn, suy thận) vào danh sách 'diseases' nếu bài báo đang nói về một bệnh chính khác (ví dụ: Melioidosis, Sốt xuất huyết). Chỉ ghi nhận bệnh chính là đối tượng đang được giám sát.
- Nếu bài chỉ đề cập MỘT bệnh: mảng có 1 phần tử.
- Nếu bài đề cập NHIỀU bệnh: tạo một phần tử riêng cho MỖI bệnh. KHÔNG gộp số ca.
- Mỗi phần tử PHẢI có trường 'disease_name' khớp với một keyword.
""".strip()

# ---------------------------------------------------------------------------
# LLM preflight cache
# ---------------------------------------------------------------------------
_LLM_PREFLIGHT_CHECKED = False
_LLM_PREFLIGHT_STATUS: dict[str, str | bool] = {
    "ok": False,
    "message": "LLM preflight has not run",
}
_LLM_COOLDOWN_UNTIL: datetime | None = None
_LLM_COOLDOWN_REASON = ""
_llm_active_model: str = LLM_RECHECK_MODEL
_llm_session_is_fallback = False
_llm_session_fallback_count = 0
_llm_session_id: str | None = None
_llm_session_fallback_reason = ""
_llm_recent_sessions: list[dict] = []
_llm_circuit_failures = 0
_llm_circuit_state = "CLOSED"
_llm_last_fallback_at: datetime | None = None
_llm_primary_attempts_today = 0
_llm_primary_failures_today = 0
_LABELED_DATASET_FEW_SHOT_CACHE: dict[str, object] = {
    "path": "",
    "mtime": None,
    "block": "",
}

# ===========================================================================
# Utility helpers
# ===========================================================================

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().replace("www.", "")
    except Exception:
        return ""

def get_domain_and_path(url: str) -> str:
    """Trả về domain + path, loại bỏ query params và fragment để chuẩn hóa link fetch sapo."""
    try:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return url



# ---------------------------------------------------------------------------
# Danh sách các từ ghép "Lao" gây nhiễu (Pre-processing compound blacklist)
# ---------------------------------------------------------------------------
# Các từ ghép này được xóa khỏi title/summary TRƯỚC khi dò keywords,
# tránh nhầm "lao động", "lao lực"... với bệnh "Lao" (Tuberculosis).
LAO_COMPOUND_BLACKLIST = [
    "người lao động", "lao động", "lao lực", "lao lý", "thù lao",
    "gian lao", "công lao", "lao đao", "lao dốc", "lao vào",
    "lao đến", "lao đi", "lao xuống", "lao lên", "lao về",
    "lao bảo", "lao thẳng", "lao ra", "lao theo", "lao tới",
    "lao nhanh", "lao phóng", "cật lao", "lao tâm", "lao khổ",
    "lao nhọc", "hao lao", "thao lao", "lao từ"
]


def _strip_structural_noise(soup) -> None:
    """
    Bước 1: Loại bỏ toàn bộ nội dung trong các thẻ cấu trúc trang
    (header, footer, nav, aside) và các khối "xem thêm / tin liên quan"
    TRƯỚC KHI lấy text thuần.

    Quy trình:
      1a. Xóa các thẻ HTML5 ngữ nghĩa tiêu chuẩn: header, footer, nav, aside
      1b. Xóa các div/section/ul/li có class/id trùng pattern báo quản
      1c. Xóa các liên kết/nút "Xem thêm", "Tin liên quan", "Đọc thêm"
    """
    # 1a. Thẻ cấu trúc HTML5 — xóa toàn bộ nội dung bên trong
    for tag_name in ("header", "footer", "nav", "aside"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # 1b. Khối class/id/role trông giống sidebar, footer, widget quảng cáo...
    junk_class_pattern = re.compile(
        r"(relat|sidebar|footer|widget|comment|breadcrumb|social|share"
        r"|recommend|trending|popular|doc[-_]them|xem[-_]them|tin[-_]lien[-_]quan"
        r"|bai[-_]viet[-_]lien[-_]quan|cung[-_]chu[-_]de|tin[-_]khac"
        r"|nav|menu|ads|banner|advert|promo|signup|subscribe|newsletter"
        r"|tag[-_]cloud|author[-_]bio|related[-_]post|most[-_]read"
        r"|box[-_]category|box[-_]tag|box[-_]related|zone[-_]article"
        r"|article[-_]related|cate[-_]new|other[-_]news|more[-_]news)",
        re.IGNORECASE,
    )
    for tag in soup.find_all(True):
        if tag.parent is None:
            continue  # đã bị decompose bởi bước trước
        classes = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "") or ""
        tag_role = tag.get("role", "") or ""
        combined = f"{classes} {tag_id} {tag_role}"
        if junk_class_pattern.search(combined):
            tag.decompose()

    # 1c. Thẻ chứa text "Xem thêm / Tin liên quan / Đọc thêm" (ngắn, < 120 ký tự)
    junk_text_pattern = re.compile(
        r"^(xem\s+thêm|tin\s+liên\s+quan|đọc\s+thêm|bài\s+liên\s+quan"
        r"|bài\s+viết\s+liên\s+quan|cùng\s+chuyên\s+mục|bạn\s+có\s+thể\s+quan\s+tâm"
        r"|mời\s+đọc\s+thêm|xem\s+chi\s+tiết|đọc\s+tiếp|tin\s+khác"
        r"|xem\s+thêm\s+nhiều|đọc\s+thêm\s+bài|xem\s+toàn\s+bộ|có\s+thể\s+bạn\s+thích)",
        re.IGNORECASE,
    )
    for tag in soup.find_all(["a", "li", "p", "h2", "h3", "h4", "div", "span", "strong", "button"]):
        if tag.parent is None:
            continue
        text_content = tag.get_text(separator=" ", strip=True)
        if 0 < len(text_content) < 120 and junk_text_pattern.search(text_content):
            tag.decompose()


def normalize_text(text: str) -> str:
    """
    Trích xuất nội dung text thuần từ HTML theo 2 bước tách biệt:

    Bước 1 (_strip_structural_noise):
        Xóa toàn bộ nội dung bên trong thẻ header, footer, nav, aside,
        các div sidebar/widget/ads và các cụm "Xem thêm / Tin liên quan"
        TRƯỚC KHI tước bỏ thẻ HTML.

    Bước 2 (normalize):
        Sau khi Bước 1 hoàn tất, mới loại bỏ script/style/noscript còn sót
        rồi lấy text thuần (plain text) sạch cuối cùng.
    """
    if not text:
        return ""
    from bs4 import BeautifulSoup

    decoded = html.unescape(text)

    # Nếu không có HTML tag → trả luôn, không cần parse
    if "<" not in decoded:
        return re.sub(r"\s+", " ", decoded).strip()

    soup = BeautifulSoup(decoded, "html.parser")

    # =========================================================
    # BƯỚC 1: Loại bỏ cấu trúc rác (header, footer, xem thêm)
    # =========================================================
    _strip_structural_noise(soup)

    # =========================================================
    # BƯỚC 2: Dọn sạch thẻ kỹ thuật còn sót, lấy text thuần
    # =========================================================
    for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    clean_text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", clean_text).strip()




def slugify_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(text).lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def _normalize_excel_key(value) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _normalize_dataset_label(value) -> str | None:
    label = _normalize_excel_key(value)
    if label in {"relevant", "lien quan"}:
        return "relevant"
    if label in {"noise", "nhieu", "nhieu lieu", "tap am", "co de cap nhung khong co su kien", "khong phu hop noi dung"}:
        return "noise"
    if label in {"irrelevant", "khong lien quan", "khong phu hop"}:
        return "irrelevant"
    if label in {"unsure", "khong chac", "khong ro", "chua ro", "can xem lai"}:
        return "unsure"
    return None


def _truncate_prompt_text(value, max_length: int = 500) -> str:
    text = normalize_text(str(value or ""))
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def _resolve_labeled_dataset_path() -> str | None:
    if not LLM_FEW_SHOT_DATASET_PATH:
        return None

    candidates = [LLM_FEW_SHOT_DATASET_PATH]
    if not os.path.isabs(LLM_FEW_SHOT_DATASET_PATH):
        candidates.extend([
            os.path.join(os.getcwd(), LLM_FEW_SHOT_DATASET_PATH),
            os.path.join(os.getcwd(), "backend", LLM_FEW_SHOT_DATASET_PATH),
            os.path.join(os.getcwd(), "data", LLM_FEW_SHOT_DATASET_PATH),
            os.path.join(os.getcwd(), "backend", "data", LLM_FEW_SHOT_DATASET_PATH),
        ])

    for candidate in dict.fromkeys(candidates):
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def _find_labeled_dataset_columns(header_row) -> dict[str, int] | None:
    aliases = {
        "title": {"title", "headline", "tieu de"},
        "summary": {"summary", "description", "sapo", "tom tat", "mo ta"},
        "llm_label": {"llm label", "nhan llm", "du doan", "label llm"},
        "human_label": {"human label", "nhan thu cong", "nhan nguoi dung", "ground truth", "label dung"},
    }
    normalized_headers = [_normalize_excel_key(cell) for cell in header_row]
    columns: dict[str, int] = {}

    for field, field_aliases in aliases.items():
        for index, header in enumerate(normalized_headers):
            if any(alias == header or alias in header for alias in field_aliases):
                columns[field] = index
                break

    required = {"title", "summary", "llm_label", "human_label"}
    return columns if required.issubset(columns.keys()) else None


def _select_labeled_examples(examples: list[dict[str, str]], max_examples: int) -> list[dict[str, str]]:
    if max_examples <= 0:
        return []

    selected: list[dict[str, str]] = []
    selected_ids: set[int] = set()
    # Thêm bucket "noise" để đảm bảo luôn có ví dụ noise trong few-shot
    by_label: dict[str, list[tuple[int, dict[str, str]]]] = {
        "relevant": [],
        "noise": [],
        "irrelevant": [],
        "unsure": [],
    }

    for index, example in enumerate(examples):
        label = example.get("label", "")
        if label in by_label:
            by_label[label].append((index, example))

    for label in ("relevant", "noise", "irrelevant", "unsure"):
        if by_label[label] and len(selected) < max_examples:
            index, example = by_label[label][0]
            selected.append(example)
            selected_ids.add(index)

    for index, example in enumerate(examples):
        if len(selected) >= max_examples:
            break
        if index in selected_ids:
            continue
        selected.append(example)

    return selected


def _format_labeled_dataset_few_shot_block(examples: list[dict[str, str]]) -> str:
    lines = [
        "## Ví dụ bổ sung từ Labeled Dataset",
        "Các ví dụ này lấy từ mẫu mà LLM và người đánh giá đồng thuận; dùng để hiệu chỉnh nhãn, vẫn phải trả JSON theo schema bên dưới.",
    ]

    for index, example in enumerate(examples, start=1):
        lines.extend([
            "",
            f"### Ví dụ Excel {index} — {example['label']}",
            f"Tiêu đề: {example['title']}",
            f"Tóm tắt: {example['summary']}",
            f"Nhãn đúng: {example['label']}",
        ])

    return "\n".join(lines).strip()


def _get_excel_row_value(row, index: int):
    return row[index] if index < len(row) else None


def get_labeled_dataset_few_shot_block() -> str:
    global _LABELED_DATASET_FEW_SHOT_CACHE

    dataset_path = _resolve_labeled_dataset_path()
    if not dataset_path:
        return ""

    mtime = os.path.getmtime(dataset_path)
    if (
        _LABELED_DATASET_FEW_SHOT_CACHE.get("path") == dataset_path
        and _LABELED_DATASET_FEW_SHOT_CACHE.get("mtime") == mtime
    ):
        return str(_LABELED_DATASET_FEW_SHOT_CACHE.get("block") or "")

    try:
        import openpyxl

        workbook = openpyxl.load_workbook(dataset_path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)
            header_row = next(rows, None)
            columns = _find_labeled_dataset_columns(header_row or [])
            if not columns:
                logger.warning("Few-shot dataset skipped | reason=missing_required_columns path={}", dataset_path)
                block = ""
            else:
                examples: list[dict[str, str]] = []
                for row in rows:
                    llm_label = _normalize_dataset_label(_get_excel_row_value(row, columns["llm_label"]))
                    human_label = _normalize_dataset_label(_get_excel_row_value(row, columns["human_label"]))
                    title = _truncate_prompt_text(_get_excel_row_value(row, columns["title"]), max_length=240)
                    summary = _truncate_prompt_text(_get_excel_row_value(row, columns["summary"]), max_length=500)

                    if not human_label or not title or not summary:
                        continue

                    examples.append({
                        "title": title,
                        "summary": summary,
                        "llm_label": llm_label or "",
                        "label": human_label,
                    })

                selected_examples = _select_labeled_examples(examples, LLM_FEW_SHOT_DATASET_MAX_EXAMPLES)
                block = _format_labeled_dataset_few_shot_block(selected_examples) if selected_examples else ""
                logger.info(
                    "Few-shot dataset loaded | path={} valid_examples={} selected_examples={}",
                    dataset_path,
                    len(examples),
                    len(selected_examples),
                )
        finally:
            workbook.close()
    except Exception as exc:
        logger.warning("Few-shot dataset skipped | path={} error={}", dataset_path, exc)
        block = ""

    _LABELED_DATASET_FEW_SHOT_CACHE = {
        "path": dataset_path,
        "mtime": mtime,
        "block": block,
    }
    return block


def text_contains_term(text: str, term: str) -> bool:
    normalized_term = re.escape(term.lower().strip())
    if not normalized_term:
        return False
    # Allow flexible whitespace between tokens for multi-word terms
    normalized_term = normalized_term.replace(r"\ ", r"\s+")
    pattern = rf"(?<!\w){normalized_term}(?!\w)"
    return re.search(pattern, text) is not None


def score_keyword_context(text: str, keyword: str) -> int:
    """
    Returns an integer score indicating how epidemiologically relevant
    the keyword appears within the given text.

    Positive signals  : keyword present (+3), epidemic context terms (+2 each hit)
    Negative signals  : non-epidemic / lifestyle context terms (-2 each hit)
    """
    score = 0
    if text_contains_term(text, keyword):
        score += 3
    if any(text_contains_term(text, term) for term in EPIDEMIC_CONTEXT_TERMS):
        score += 2
    if any(text_contains_term(text, term) for term in NON_EPIDEMIC_CONTEXT_TERMS):
        score -= 2
    return score


CASE_COUNT_PATTERN = re.compile(
    r"\d+[\d.,]*\s*(ca mắc|trường hợp|người mắc|ca tử vong|tử vong|f0|nhiễm|dương tính)",
    re.IGNORECASE,
)
HISTORICAL_PATTERN = re.compile(
    r"(năm 20[0-2][0-9]|từ đầu năm đến nay|nhìn lại|hồi tưởng|trong đại dịch covid 2020)",
    re.IGNORECASE,
)
COMPARATIVE_PATTERN = re.compile(
    r"(như bệnh|tương tự|giống như trường hợp)",
    re.IGNORECASE,
)
CURRENT_OUTBREAK_PATTERN = re.compile(
    r"(hôm nay|tuần này|vừa phát hiện|mới ghi nhận)",
    re.IGNORECASE,
)
DISCUSSION_PATTERN = re.compile(
    r"(hội thảo|hội nghị|tổng kết|nhìn lại)",
    re.IGNORECASE,
)
PREVENTION_PATTERN = re.compile(
    r"(hướng dẫn|kinh nghiệm|bí quyết|tư vấn|cách phòng)",
    re.IGNORECASE,
)


def calculate_outbreak_relevance_score(title: str, summary: str, keywords: list[str]) -> float:
    text = normalize_text(f"{title} {summary}").lower()
    title_text = normalize_text(title).lower()
    score = 0
    if any(text_contains_term(title_text, keyword.lower()) for keyword in keywords):
        score += 3
    if any(text_contains_term(text, term) for term in EPIDEMIC_CONTEXT_TERMS):
        score += 2
    if CASE_COUNT_PATTERN.search(text):
        score += 2
    if CURRENT_OUTBREAK_PATTERN.search(text):
        score += 1
    if DISCUSSION_PATTERN.search(text):
        score -= 2
    if PREVENTION_PATTERN.search(text):
        score -= 2
    if COMPARATIVE_PATTERN.search(text):
        score -= 2
    if HISTORICAL_PATTERN.search(text):
        score -= 3
    return float(max(score, 0))


def _redact_api_key(api_key: str) -> str:
    if not api_key:
        return "<missing>"
    if len(api_key) <= 8:
        return f"{api_key[:2]}***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def extract_potential_numbers(text: str) -> list[str]:
    """
    Tìm tất cả các cụm từ chứa số và ngữ cảnh xung quanh để gợi ý cho LLM.
    Ví dụ: ['858 trường hợp', 'tăng 66,9%', '29 trường hợp', '17 ca']
    """
    if not text:
        return []
    # Tìm các con số đi kèm với các từ khóa dịch tễ
    patterns = [
        r"(\d+[\d.,]*)\s*(ca mắc|trường hợp|người mắc|ca tử vong|tử vong|f0|nhiễm|dương tính)",
        r"(tăng|giảm|thêm)\s*(\d+[\d.,]*)",
        r"ghi nhận\s*(\d+[\d.,]*)"
    ]
    suggestions = []
    for p in patterns:
        matches = re.finditer(p, text, re.IGNORECASE)
        for m in matches:
            suggestions.append(m.group(0))
    return list(set(suggestions)) # Xóa trùng


def extract_case_count(text: str, keywords: list[str]) -> int:
    # Hàm này giữ lại làm fallback dự phòng nếu LLM lỗi hoàn toàn
    if not text:
        return 0
    pattern = r"(\d+[\d.,]*)\s*(ca mắc|trường hợp|người mắc|ca tử vong|tử vong|f0)"
    matches = re.finditer(pattern, text, re.IGNORECASE)
    for m in matches:
        start_idx = max(0, m.start() - 30)
        context = text[start_idx:m.end()].lower()
        if "lũy kế" in context or "tích lũy" in context or "từ đầu năm" in context:
            continue
        try:
            num_str = m.group(1).replace(".", "").replace(",", "")
            return int(num_str)
        except (ValueError, IndexError):
            continue
    return 0


def parse_date(entry) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6])
        if dt.year > 2000:
            return dt
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6])
        if dt.year > 2000:
            return dt
            
    # Try parsing string directly if feedparser wasn't able to extract tuples
    if hasattr(entry, "published") and entry.published:
        try:
            return parsedate_to_datetime(entry.published).replace(tzinfo=None)
        except Exception:
            pass
    if hasattr(entry, "pubDate") and entry.pubDate:
        try:
            return parsedate_to_datetime(entry.pubDate).replace(tzinfo=None)
        except Exception:
            pass

    return datetime.utcnow()


def extract_primary_keyword(matched_keywords: str | None) -> str | None:
    if not matched_keywords:
        return None
    first = matched_keywords.split(",")[0].strip()
    return first or None


def compute_title_similarity(title_a: str, title_b: str) -> float:
    if not title_a or not title_b:
        return 0.0
    
    model = get_embedding_model()
    # Tính toán vector embedding bên trong vòng lặp (không tối ưu số lần gọi encode đối với bài báo mới theo yêu cầu)
    emb_a = model.encode(title_a, convert_to_tensor=True)
    emb_b = model.encode(title_b, convert_to_tensor=True)
    
    cos_sim = float(util.cos_sim(emb_a, emb_b)[0][0])
    return max(0.0, min(cos_sim, 1.0))


def build_event_fingerprint(
    primary_keyword: str,
    location: str | None,
    pub_date: datetime,
) -> str:
    location_part = slugify_text(location or "unknown") or "unknown"
    disease_part = slugify_text(primary_keyword) or "unknown"
    return f"{disease_part}|{location_part}|{pub_date.strftime('%Y-%m-%d')}"


def compute_event_similarity_score(
    title: str,
    summary: str,
    pub_date: datetime,
    location: str | None,
    case_count: int,
    event,
) -> tuple[float, dict[str, float]]:
    title_similarity = compute_title_similarity(title, event.canonical_title)
    title_score = title_similarity * 0.35

    # Lấy summary của bài viết mẫu (sự kiện) bằng cách fallback về canonical_title nếu chưa có
    # Tuy nhiên NewsEvent không lưu summary, nên ta so sánh summary bài mới với title của Event
    summary_similarity = compute_title_similarity(summary[:200], event.canonical_title)
    summary_score = summary_similarity * 0.25

    normalized_location = normalize_text(location or "")
    event_location = normalize_text(event.location or "")
    if normalized_location and event_location:
        if normalized_location == event_location:
            location_score = 0.20
        elif normalized_location in event_location or event_location in normalized_location:
            location_score = 0.10
        else:
            location_score = 0.0
    elif not normalized_location and not event_location:
        location_score = 0.10
    else:
        location_score = 0.05

    day_diff = abs((pub_date.date() - event.event_date.date()).days)
    if day_diff == 0:
        date_score = 0.15
    elif day_diff == 1:
        date_score = 0.10
    elif day_diff == 2:
        date_score = 0.05
    else:
        date_score = 0.0

    if case_count > 0 and (event.case_count or 0) > 0:
        delta = abs(case_count - event.case_count)
        tolerance = max(3, int(max(case_count, event.case_count) * 0.3))
        if delta == 0:
            case_score = 0.05
        elif delta <= tolerance:
            case_score = 0.03
        else:
            case_score = 0.0
    else:
        case_score = 0.02

    breakdown = {
        "title": round(title_score, 3),
        "summary": round(summary_score, 3),
        "location": round(location_score, 3),
        "date": round(date_score, 3),
        "case_count": round(case_score, 3),
    }
    return round(sum(breakdown.values()), 3), breakdown


def format_dedupe_reason(breakdown: dict[str, float], matched: bool) -> str:
    status = "matched_existing_event" if matched else "new_event_created"
    parts = ", ".join(f"{key}={value}" for key, value in breakdown.items())
    return f"{status}: {parts}"


def resolve_event_for_article(
    db: Session,
    title: str,
    summary: str,
    matched_keywords: str,
    pub_date: datetime,
    location: str | None,
    cumulative_cases: int,
    new_cases: int,
    severity: str | None,
) -> tuple[models.NewsEvent | None, float | None, str | None, int]:
    MATCH_SCORE_THRESHOLD = 0.75
    primary_keyword = extract_primary_keyword(matched_keywords)
    if not primary_keyword:
        return None, None, None, 0

    normalized_location = normalize_text(location or "") or None
    
    # -------------------------------------------------------------
    # PHÁC THẢO TÍCH HỢP QDRANT VECTOR SEARCH
    # Bước 1: Sinh vector embedding cho title
    # text_embedding = generate_embedding_for_text(title)
    #
    # Bước 2: Truy vấn Qdrant tìm Event có Similarity score > 0.85 
    #         và cùng primary_keyword, trong khoảng thời gian mở rộng.
    # similar_events = qdrant_client.search(collection_name="events", query_vector=text_embedding)
    # 
    # Bước 3: Cập nhật best_match từ Vector thay vì vòng lặp tính điểm
    # -------------------------------------------------------------

    start_date = pub_date - timedelta(days=3)
    end_date = pub_date + timedelta(days=3)
    recent_events = crud.get_recent_events(
        db,
        disease_name=primary_keyword,
        location=normalized_location,
        start_date=start_date,
        end_date=end_date,
    )
    if not recent_events and normalized_location not in {None, "Việt Nam"}:
        recent_events = crud.get_recent_events(
            db,
            disease_name=primary_keyword,
            location=None,
            start_date=start_date,
            end_date=end_date,
        )

    best_match = None
    best_score = 0.0
    best_breakdown: dict[str, float] | None = None
    search_cases = max(cumulative_cases, new_cases)
    for event in recent_events:
        score, breakdown = compute_event_similarity_score(
            title=title,
            summary=summary,
            pub_date=pub_date,
            location=normalized_location,
            case_count=search_cases,
            event=event,
        )
        if score > best_score:
            best_match = event
            best_score = score
            best_breakdown = breakdown

    if best_match and best_score >= MATCH_SCORE_THRESHOLD:
        updated_event_cases = best_match.case_count or 0
        plot_cases = 0
        
        # Chỉ rải lên đồ thị "số ca mới" hoặc "số ca chênh lệch dương"
        if new_cases > 0:
            updated_event_cases += new_cases
            plot_cases = new_cases
        elif cumulative_cases > 0 and cumulative_cases > updated_event_cases:
            plot_cases = cumulative_cases - updated_event_cases
            updated_event_cases = cumulative_cases
            
        logger.debug(
            "Event matched | event_id={} score={} breakdown={} title={}",
            best_match.id,
            best_score,
            best_breakdown,
            title,
        )
        updated_event = crud.update_news_event(
            db,
            best_match,
            canonical_title=title,
            case_count=updated_event_cases,
            severity=severity,
        )
        return updated_event, best_score, format_dedupe_reason(best_breakdown or {}, True), plot_cases

    if best_match:
        logger.debug(
            "Event below threshold | candidate_event_id={} score={} threshold={} breakdown={} title={}",
            best_match.id,
            best_score,
            MATCH_SCORE_THRESHOLD,
            best_breakdown,
            title,
        )

    # Ưu tiên số ca mới để thả vào đồ thị (chống dội boom cumulative_cases)
    plot_cases = new_cases if new_cases > 0 else cumulative_cases
    initial_event_cases = max(cumulative_cases, new_cases)
    
    created_event = crud.create_news_event(
        db,
        canonical_title=title,
        disease_name=primary_keyword,
        location=normalized_location,
        event_date=pub_date,
        case_count=initial_event_cases,
        severity=severity,
        fingerprint=build_event_fingerprint(primary_keyword, normalized_location, pub_date),
    )
    
    # -------------------------------------------------------------
    # PHÁC THẢO: Nếu là Event mới, lưu véc tơ vào Qdrant để tương lai tìm kiếm.
    # qdrant_client.upsert(
    #    collection_name="events", 
    #    points=[PointStruct(id=created_event.id, vector=text_embedding, payload={...})]
    # )
    # -------------------------------------------------------------
    
    return created_event, None, format_dedupe_reason(best_breakdown or {}, False), plot_cases


def find_similar_event(
    db: Session,
    title: str,
    summary: str,
    matched_keywords: str,
    pub_date: datetime,
    location: str | None,
    case_count: int,
) -> tuple[models.NewsEvent | None, float | None, dict | None]:

    primary_keyword = extract_primary_keyword(matched_keywords)
    if not primary_keyword:
        return None, None, None

    normalized_location = normalize_text(location or "") or None

    start_date = pub_date - timedelta(days=3)
    end_date = pub_date + timedelta(days=3)

    # Tìm kiếm lần 1: theo bệnh + địa điểm + khoảng thời gian
    recent_events = crud.get_recent_events(
        db,
        disease_name=primary_keyword,
        location=normalized_location,
        start_date=start_date,
        end_date=end_date,
    )

    # Tìm kiếm lần 2 (fallback): bỏ location nếu không tìm thấy
    if not recent_events and normalized_location not in {None, "Việt Nam"}:
        recent_events = crud.get_recent_events(
            db,
            disease_name=primary_keyword,
            location=None,
            start_date=start_date,
            end_date=end_date,
        )

    best_match = None
    best_score = 0.0
    best_breakdown: dict | None = None

    for event in recent_events:
        score, breakdown = compute_event_similarity_score(
            title=title,
            summary=summary,
            pub_date=pub_date,
            location=normalized_location,
            case_count=case_count,
            event=event,
        )
        if score > best_score:
            best_match = event
            best_score = score
            best_breakdown = breakdown

    if best_match:
        return best_match, best_score, best_breakdown

    return None, None, None


# ===========================================================================
# LLM preflight
# ===========================================================================

def get_llm_preflight_status(force_refresh: bool = False) -> dict[str, str | bool]:
    global _LLM_PREFLIGHT_CHECKED, _LLM_PREFLIGHT_STATUS

    if _LLM_PREFLIGHT_CHECKED and not force_refresh:
        return _LLM_PREFLIGHT_STATUS

    status: dict[str, str | bool] = {
        "ok": False,
        "enabled": LLM_RECHECK_ENABLED,
        "model": LLM_RECHECK_MODEL or "<missing>",
        "base_url": LLM_RECHECK_BASE_URL,
        "api_key": _redact_api_key(LLM_RECHECK_API_KEY),
        "message": "",
    }

    if not LLM_RECHECK_ENABLED:
        status["ok"] = True
        status["message"] = "LLM re-check is disabled"
        _LLM_PREFLIGHT_CHECKED = True
        _LLM_PREFLIGHT_STATUS = status
        return status

    if not LLM_RECHECK_MODEL:
        status["message"] = "Missing LLM_RECHECK_MODEL"
        _LLM_PREFLIGHT_CHECKED = True
        _LLM_PREFLIGHT_STATUS = status
        return status

    if not LLM_RECHECK_API_KEY:
        status["message"] = "Missing OPENAI_API_KEY / Gemini API key"
        _LLM_PREFLIGHT_CHECKED = True
        _LLM_PREFLIGHT_STATUS = status
        return status

    try:
        response = requests.get(
            f"{LLM_RECHECK_BASE_URL}/models/{LLM_RECHECK_MODEL}",
            headers={"Authorization": f"Bearer {LLM_RECHECK_API_KEY}"},
            timeout=LLM_RECHECK_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        status["message"] = f"LLM preflight network error: {exc}"
        _LLM_PREFLIGHT_CHECKED = True
        _LLM_PREFLIGHT_STATUS = status
        return status

    if response.status_code == 200:
        status["ok"] = True
        status["message"] = "LLM preflight OK"
    elif response.status_code in {401, 403}:
        status["message"] = "LLM preflight failed: API key rejected or unauthorized"
    elif response.status_code == 404:
        status["message"] = "LLM preflight failed: model or base URL not found"
    else:
        preview = response.text[:300].replace("\n", " ").strip()
        status["message"] = f"LLM preflight failed: HTTP {response.status_code} - {preview}"

    _LLM_PREFLIGHT_CHECKED = True
    _LLM_PREFLIGHT_STATUS = status
    return status


def log_llm_preflight_status(force_refresh: bool = False) -> dict[str, str | bool]:
    status = get_llm_preflight_status(force_refresh=force_refresh)
    log_fn = logger.info if status.get("ok") else logger.warning
    log_fn(
        "LLM preflight | enabled={} model={} base_url={} api_key={} status={}",
        status.get("enabled"),
        status.get("model"),
        status.get("base_url"),
        status.get("api_key"),
        status.get("message"),
    )
    return status


# ===========================================================================
# LLM prompt builder
# ===========================================================================

def build_llm_recheck_prompt(title: str, summary: str, keywords: list[str], suggestions: list[str] = []) -> str:
    """
    Assemble the user-turn prompt for the LLM classifier.
    """
    few_shot_blocks = [_FEW_SHOT_BLOCK]
    labeled_dataset_block = get_labeled_dataset_few_shot_block()
    if labeled_dataset_block:
        few_shot_blocks.extend(["---", labeled_dataset_block])
    few_shot_section = "\n\n".join(few_shot_blocks)

    keyword_block = "\n".join(f"- {kw}" for kw in keywords)
    keyword_section = f"## Keyword được phép chọn (CHỈ từ danh sách này)\n{keyword_block}"

    suggestion_block = ""
    if suggestions:
        suggestion_block = f"## Gợi ý số liệu từ Regex (Hãy thẩm định kỹ):\n" + "\n".join([f"- {s}" for s in suggestions])

    article_block = (
        f"## Bài báo cần phân tích\n"
        f"Tiêu đề: {title}\n"
        f"Tóm tắt: {summary}"
    )

    return "\n\n".join([
        few_shot_section,
        "---",
        _CRITERIA_BLOCK,
        keyword_section,
        suggestion_block,
        _SCHEMA_BLOCK,
        article_block,
    ])


# ===========================================================================
# JSON extraction helper
# ===========================================================================

def extract_json_object(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_llm_location(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned[:255] if cleaned else None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _normalize_llm_case_count(value) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return 0


def _normalize_llm_severity(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned if cleaned in {"low", "medium", "high"} else None


def _parse_retry_after_seconds(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return max(int(value), 0)
    return None


def _get_llm_cooldown_status() -> tuple[bool, str]:
    global _LLM_COOLDOWN_UNTIL, _LLM_COOLDOWN_REASON

    if not _LLM_COOLDOWN_UNTIL:
        return False, ""

    now = datetime.utcnow()
    if now >= _LLM_COOLDOWN_UNTIL:
        _LLM_COOLDOWN_UNTIL = None
        _LLM_COOLDOWN_REASON = ""
        return False, ""

    remaining = int((_LLM_COOLDOWN_UNTIL - now).total_seconds())
    return True, f"{_LLM_COOLDOWN_REASON} ({remaining}s remaining)"


def _activate_llm_cooldown(seconds: int, reason: str) -> None:
    global _LLM_COOLDOWN_UNTIL, _LLM_COOLDOWN_REASON

    seconds = max(seconds, 1)
    until = datetime.utcnow() + timedelta(seconds=seconds)
    if _LLM_COOLDOWN_UNTIL and _LLM_COOLDOWN_UNTIL >= until:
        return

    _LLM_COOLDOWN_UNTIL = until
    _LLM_COOLDOWN_REASON = reason
    logger.warning(
        "LLM cooldown activated | seconds={} reason={}",
        seconds,
        reason,
    )


class LLMError(Exception):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


def _start_llm_session() -> None:
    global _llm_active_model, _llm_session_is_fallback, _llm_session_fallback_count
    global _llm_session_id, _llm_session_fallback_reason

    _llm_active_model = LLM_RECHECK_MODEL
    _llm_session_is_fallback = False
    _llm_session_fallback_count = 0
    _llm_session_fallback_reason = ""
    _llm_session_id = datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _finish_llm_session() -> None:
    global _llm_active_model, _llm_session_is_fallback, _llm_recent_sessions
    if not _llm_session_id:
        return
    _llm_recent_sessions.append({
        "session_id": _llm_session_id,
        "used_fallback": _llm_session_is_fallback,
        "fallback_reason": _llm_session_fallback_reason,
        "fallback_count": _llm_session_fallback_count,
        "timestamp": datetime.utcnow().isoformat(),
    })
    _llm_recent_sessions = _llm_recent_sessions[-3:]
    _llm_active_model = LLM_RECHECK_MODEL
    _llm_session_is_fallback = False


def _activate_llm_fallback(reason: str) -> None:
    global _llm_active_model, _llm_session_is_fallback, _llm_session_fallback_count
    global _llm_session_fallback_reason, _llm_last_fallback_at, _llm_circuit_state

    if not LLM_FALLBACK_MODEL:
        return
    was_fallback = _llm_session_is_fallback
    _llm_active_model = LLM_FALLBACK_MODEL
    _llm_session_is_fallback = True
    if not was_fallback:
        _llm_session_fallback_count += 1
        _llm_session_fallback_reason = reason
        _llm_last_fallback_at = datetime.utcnow()
    _llm_circuit_state = "OPEN"
    logger.warning(
        "LLM fallback activated | from={} to={} reason={} session_fallback_count={}",
        LLM_RECHECK_MODEL,
        LLM_FALLBACK_MODEL,
        reason,
        _llm_session_fallback_count,
    )


def _call_llm_api(model: str, api_key: str, base_url: str, prompt: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://epi-scout-ai-main.vercel.app",
                    "X-Title": "EpiScout AI",
                },
                json={
                    "model": model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": LLM_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=LLM_RECHECK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = extract_json_object(content)
            if not parsed:
                raise LLMError("LLM returned invalid JSON")
            return parsed
        except requests.exceptions.Timeout as exc:
            last_error = exc
            if attempt >= LLM_MAX_RETRIES:
                raise LLMTimeoutError(str(exc)) from exc
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code == 429:
                raise LLMRateLimitError(str(exc)) from exc
            last_error = exc
            if attempt >= LLM_MAX_RETRIES:
                raise LLMError(str(exc)) from exc
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt >= LLM_MAX_RETRIES:
                raise LLMError(str(exc)) from exc
        wait_seconds = min(2 ** attempt, 30)
        logger.warning("LLM retry scheduled | model={} attempt={} wait_seconds={} error={}", model, attempt, wait_seconds, last_error)
        time.sleep(wait_seconds)
    raise LLMError(str(last_error) if last_error else "LLM request failed")


def get_llm_runtime_status() -> dict:
    fallback_count = sum(1 for item in _llm_recent_sessions if item.get("used_fallback"))
    error_rate = (
        _llm_primary_failures_today / _llm_primary_attempts_today
        if _llm_primary_attempts_today
        else 0.0
    )
    return {
        "current_model": _llm_active_model or LLM_RECHECK_MODEL,
        "primary_model": LLM_RECHECK_MODEL,
        "fallback_model": LLM_FALLBACK_MODEL,
        "circuit_state": _llm_circuit_state,
        "fallback_count_today": fallback_count,
        "primary_error_rate": round(error_rate, 4),
        "last_fallback_at": _llm_last_fallback_at.isoformat() if _llm_last_fallback_at else None,
        "recent_sessions": _llm_recent_sessions,
    }


# ===========================================================================
# LLM re-check
# ===========================================================================

def llm_recheck_article(
    title: str,
    summary: str,
    candidate_keywords: list[str],
    suggestions: list[str] = [],
) -> tuple[str, list[str], str, dict]:
    """
    Call the LLM to classify an article and extract structured metadata.

    Returns:
        label            : "relevant" | "irrelevant" | "unsure"
        matched_keywords : subset of candidate_keywords confirmed by LLM
        reason           : short Vietnamese explanation
        meta             : {
                             "location"             : str | None,
                             "estimated_case_count" : int,
                             "severity"             : "low"|"medium"|"high"|None,
                           }

    On any failure the function returns ("unsure", candidate_keywords, <reason>, EMPTY_META)
    so the article is not silently dropped.
    """
    EMPTY_META: dict = {"location": None, "cumulative_cases": 0, "new_cases": 0, "severity": None}

    if not candidate_keywords:
        return "irrelevant", [], "No candidate keywords", EMPTY_META

    if not LLM_RECHECK_ENABLED:
        return "unsure", candidate_keywords, "LLM re-check disabled", EMPTY_META

    in_cooldown, cooldown_reason = _get_llm_cooldown_status()
    if in_cooldown:
        if not LLM_FALLBACK_MODEL:
            return "unsure", candidate_keywords, f"LLM cooldown active: {cooldown_reason}", EMPTY_META
        _activate_llm_fallback(cooldown_reason)

    preflight = get_llm_preflight_status()
    if not preflight.get("ok"):
        logger.warning("LLM re-check skipped | reason={}", preflight.get("message"))
        return "unsure", candidate_keywords, str(preflight.get("message")), EMPTY_META

    prompt = build_llm_recheck_prompt(title, summary, candidate_keywords, suggestions)

    try:
        global _llm_circuit_failures, _llm_circuit_state
        global _llm_primary_attempts_today, _llm_primary_failures_today

        if _llm_session_is_fallback or _llm_circuit_state == "OPEN":
            _activate_llm_fallback(_llm_session_fallback_reason or "circuit open")
            parsed = _call_llm_api(LLM_FALLBACK_MODEL, LLM_RECHECK_API_KEY, LLM_RECHECK_BASE_URL, prompt)
        else:
            _llm_circuit_state = "CLOSED"
            _llm_primary_attempts_today += 1
            try:
                parsed = _call_llm_api(LLM_RECHECK_MODEL, LLM_RECHECK_API_KEY, LLM_RECHECK_BASE_URL, prompt)
                _llm_circuit_failures = 0
            except (LLMRateLimitError, LLMTimeoutError) as exc:
                _llm_primary_failures_today += 1
                _llm_circuit_failures += 1
                if _llm_circuit_failures >= LLM_CIRCUIT_BREAKER_THRESHOLD:
                    _llm_circuit_state = "OPEN"
                if not LLM_FALLBACK_MODEL:
                    raise
                _activate_llm_fallback(str(exc))
                parsed = _call_llm_api(LLM_FALLBACK_MODEL, LLM_RECHECK_API_KEY, LLM_RECHECK_BASE_URL, prompt)
            except LLMError as exc:
                _llm_primary_failures_today += 1
                raise exc
    except LLMTimeoutError as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM timeout: {exc}", EMPTY_META
    except LLMRateLimitError as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM rate limit: {exc}", EMPTY_META
    except LLMError as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM error: {exc}", EMPTY_META
    except Exception as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM error: {exc}", EMPTY_META

    # --- label ---
    label = str(parsed.get("label", "unsure")).strip().lower()
    if label not in {"relevant", "irrelevant", "unsure"}:
        label = "unsure"

    reason = str(parsed.get("reason", "")).strip()

    # --- keywords: only keep items that exist in candidate_keywords ---
    candidate_map = {kw.lower(): kw for kw in candidate_keywords}
    raw_matched = parsed.get("matched_keywords") or []
    normalized_keywords: list[str] = list(dict.fromkeys(
        candidate_map[kw.strip().lower()]
        for kw in raw_matched
        if isinstance(kw, str) and kw.strip().lower() in candidate_map
    ))
    # Safety fallback: if LLM says relevant but returned no valid keywords,
    # keep the full candidate list rather than silently losing context.
    if label == "relevant" and not normalized_keywords:
        normalized_keywords = candidate_keywords

    # --- extra metadata ---
    meta: dict = {
        "location": _normalize_llm_location(parsed.get("location")),
        "cumulative_cases": _normalize_llm_case_count(parsed.get("cumulative_cases")),
        "new_cases": _normalize_llm_case_count(parsed.get("new_cases")),
        "diseases": parsed.get("diseases") if isinstance(parsed.get("diseases"), list) else [],
        "event_start_date": str(parsed.get("event_start_date", ""))[:10] if parsed.get("event_start_date") else None,
        "event_end_date": str(parsed.get("event_end_date", ""))[:10] if parsed.get("event_end_date") else None,
        "severity": _normalize_llm_severity(parsed.get("severity")),
    }

    logger.debug(
        "LLM recheck | label={} keywords={} location={} cases={} severity={} reason={}",
        label,
        normalized_keywords,
        meta["location"],
        f"cum={meta['cumulative_cases']}/new={meta['new_cases']}",
        meta["severity"],
        reason,
    )

    return label, normalized_keywords, reason, meta


# ===========================================================================
# Keyword matching (stage-1 regex filter)
# ===========================================================================

def matches_keywords(title: str, summary: str, keywords: list[str]) -> str | None:
    """
    Stage-1 pre-filter using regex + context scoring.

    Philosophy: cast a WIDE net here (high recall) and let the LLM handle
    precision in stage 2.  We only hard-exclude articles whose TITLE
    clearly marks them as lifestyle / ads — checking the summary would
    risk dropping legitimate outbreak articles that include advisory
    paragraphs at the end.

    Scoring thresholds are intentionally lower than before:
        title_score >= 2  OR  summary_score >= 3  OR  combined >= 4
    """
    if not title and not summary:
        return None

    title_lower = normalize_text(title).lower()
    summary_lower = normalize_text(summary).lower()

    # Hard-exclude on title only
    if any(ex in title_lower for ex in HARD_EXCLUDE_TITLE_TERMS):
        return None
    
    # New: Regex-based hard exclude for lifestyle lists (e.g. "5 mistakes", "10 measures")
    list_advice_pattern = r"\d+\s+(sai lầm|biện pháp|cách|lưu ý|mẹo|bí quyết|sai sot)"
    if re.search(list_advice_pattern, title_lower):
        return None

    # Pre-processing: Xóa nhiễu các từ ghép của "lao" để tránh nhầm bệnh Lao
    # Dùng hằng số LAO_COMPOUND_BLACKLIST đã khai báo ở cấp module
    for term in LAO_COMPOUND_BLACKLIST:
        title_lower = title_lower.replace(term, " ")
        summary_lower = summary_lower.replace(term, " ")

    matched: list[str] = []
    for kw in keywords:
        kw_lower = kw.lower()
        if not (
            text_contains_term(title_lower, kw_lower)
            or text_contains_term(summary_lower, kw_lower)
        ):
            continue
        title_score = score_keyword_context(title_lower, kw_lower)
        summary_score = score_keyword_context(summary_lower, kw_lower)
        combined_score = title_score + summary_score

        if not LLM_RECHECK_ENABLED:
            if title_score >= 3 or summary_score >= 5 or combined_score >= 6:
                matched.append(kw)
        else:
            if title_score >= 2 or summary_score >= 3 or combined_score >= 4:
                matched.append(kw)

    return ", ".join(matched) if matched else None


# ===========================================================================
# Main scan entry-point
# ===========================================================================

is_scanning_flag = False

def scan_news(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    keywords_to_scan: list[str] | None = None,
) -> schemas.ScanResult:
    """
    Crawl all RSS feeds, filter articles by keyword + LLM, and persist
    articles from trusted domains.

    Args:
        db               : SQLAlchemy session
        keywords_to_scan : Danh sách keyword được chọn từ UI.
                           None = dùng hết keywords trong DB.
                           ["a","b"] = chỉ quét các keyword này.

    Returns:
        ScanResult with saved_trusted_count, disease_counts.
    """
    global is_scanning_flag
    is_scanning_flag = True
    _start_llm_session()
    try:
        # ------------------------------------------------------------------
        # 1. Bootstrap: keywords + whitelist
        # ------------------------------------------------------------------
        if LLM_RECHECK_ENABLED:
            log_llm_preflight_status()

        # Convert and ensure all compare dates use Ho Chi Minh timezone
        hcm_tz = pytz.timezone("Asia/Ho_Chi_Minh")
        if start_date:
            start_date = start_date.replace(tzinfo=hcm_tz) if start_date.tzinfo is None else start_date.astimezone(hcm_tz)
        if end_date:
            end_date = end_date.replace(tzinfo=hcm_tz) if end_date.tzinfo is None else end_date.astimezone(hcm_tz)

        # Lấy keywords is_active=True từ DB (cho auto-scan và scan thủ công không lọc)
        keywords_obj = crud.get_active_keywords(db)
        all_db_keywords = [k.text for k in keywords_obj]

        # Lọc từ khóa theo yêu cầu UI nếu có — chỉ quét các từ đang được chọn
        if keywords_to_scan is not None and len(keywords_to_scan) > 0:
            kw_lower_set = {k.lower() for k in keywords_to_scan}
            keywords = [k for k in all_db_keywords if k.lower() in kw_lower_set]
            logger.info("Scan filtered by UI selection | selected={} matched_in_db={}",
                        len(keywords_to_scan), len(keywords))
        else:
            keywords = all_db_keywords

        logger.info(
            "Scan crawl started | keyword_count={}",
            len(keywords),
        )

        if not keywords:
            logger.warning("Scan crawl skipped | reason=no_keywords")
            return schemas.ScanResult(saved_trusted_count=0, execution_time=0, disease_counts={})

        start_time = datetime.now()

        # Trích xuất danh sách domain uy tín từ bảng rss_sources
        rss_sources = crud.get_active_rss_sources(db)
        whitelist = list(set(
            get_domain(src.url) for src in rss_sources
            if get_domain(src.url)
        ))

        # Fallback mặc định nếu DB chưa có RSS sources
        if not whitelist:
            whitelist = [
                "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn",
                "suckhoedoisong.vn", "tienphong.vn", "laodong.vn",
                "vietnamnet.vn", "nhandan.vn", "cand.com.vn",
            ]

        saved_count = 0
        seen_links: set[str] = set()
        disease_counts: dict[str, int] = {}  # {"sốt xuất huyết": 3, ...}

        # Pattern phát hiện tiêu đề bài video (loại trừ hoàn toàn)
        VIDEO_TITLE_PATTERN = re.compile(
            r"^\s*(\[video\]|\(video\)|video\s*:|video\s*-|\[clip\]|\(clip\))",
            re.IGNORECASE
        )

        # ------------------------------------------------------------------
        # 2. Xây dựng URLs & Nguồn quét
        # ------------------------------------------------------------------
        all_feeds = [src.url for src in rss_sources]
        logger.info("RSS sources loaded from DB | count={} whitelist_domains={}", len(all_feeds), len(whitelist))

        # 2.A Cú pháp ngày tháng để quét lùi về lịch sử (nếu có Start/End Date từ UI)
        date_filter_str = ""
        if start_date:
            date_filter_str += f" after:{start_date.strftime('%Y-%m-%d')}"
        if end_date:
            date_filter_str += f" before:{end_date.strftime('%Y-%m-%d')}"

        # Cú pháp éo Google News tìm riêng ở các trang Báo Uy Tín 
        trusted_sites_query = " OR ".join([f"site:{w}" for w in whitelist])

        for kw in keywords:
            # Nếu người dùng có chọn ngày quét cũ -> BẬT TỰ ĐỘNG THU THẬP GOOGLE NEWS LỊCH SỬ CHO BÁO UY TÍN
            if start_date or end_date:
                trusted_query = f'"{kw}" ({trusted_sites_query}){date_filter_str}'
                encoded_trusted = quote(trusted_query.encode('utf-8'))
                all_feeds.append(f"https://news.google.com/rss/search?q={encoded_trusted}&hl=vi&gl=VN&ceid=VN:vi")

        for feed_url in all_feeds:
            try:
                logger.info("Parsing feed | feed_url={}", feed_url)
                feed = feedparser.parse(feed_url)

                for entry in feed.entries:
                    raw_link = entry.get("link", "")
                    link = get_source_url(raw_link)
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)

                    pub_date = parse_date_advanced(entry)
                    if not pub_date:
                        continue
                    if pub_date.tzinfo:
                        pub_date = pub_date.replace(tzinfo=None)
                    
                    if start_date:
                        s_date = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
                        if pub_date < s_date:
                            continue
                    else:
                        if pub_date < (datetime.now() - timedelta(days=14)):
                            continue

                    if end_date:
                        e_date = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
                        if pub_date > e_date:
                            continue

                    title = normalize_text(entry.get("title", ""))

                    # ---- Loại bỏ bài video ngay tại đây ----
                    if VIDEO_TITLE_PATTERN.search(title):
                        logger.debug("Skipped video article | title={}", title)
                        continue
                    summary = normalize_text(
                        entry.get("summary", "") or entry.get("description", "")
                    )

                    # ---- Stage 1: regex keyword filter (wide net) ----
                    matched_kw_str = matches_keywords(title, summary, keywords)
                    if not matched_kw_str:
                        continue

                    candidate_keywords = [
                        kw.strip() for kw in matched_kw_str.split(",") if kw.strip()
                    ]

                    # ---- Fetch Sapo ----
                    target_url = get_domain_and_path(link)
                    sapo = fetch_sapo(target_url)
                    effective_summary = sapo if sapo else summary

                    # ---- Stage 2: LLM classifier with Regex context ----
                    suggestions = extract_potential_numbers(title + " " + effective_summary)
                    
                    llm_label, llm_keywords, llm_reason, llm_meta = llm_recheck_article(
                        title, effective_summary, candidate_keywords, suggestions
                    )

                    if llm_label == "irrelevant":
                        logger.info(
                            "LLM filtered article as irrelevant | title={} reason={}",
                            title,
                            llm_reason,
                        )
                        continue

                    if llm_label == "relevant" and llm_keywords:
                        matched_kw_str = ", ".join(llm_keywords)

                    # ---- Parse mảng diseases từ LLM ----
                    # Mỗi bệnh là 1 phần tử, cho phép xử lý bài đề cập nhiều bệnh cùng lúc
                    diseases_list = llm_meta.get("diseases", [])
                    
                    # Fallback backward compat: nếu LLM cũ trả về field cũ (không phải mảng)
                    if not diseases_list:
                        llm_cumulative = llm_meta.get("cumulative_cases", 0)
                        llm_new = llm_meta.get("new_cases", 0)
                        
                        if llm_cumulative == 0 and llm_new == 0:
                            regex_cases = extract_case_count(title + " " + summary, keywords)
                            fallback_cum = regex_cases
                            fallback_new = 0
                        else:
                            fallback_cum = llm_cumulative
                            fallback_new = llm_new
                        
                        # Tạo mảng diseases giả từ field cũ (chỉ 1 bệnh)
                        diseases_list = [{
                            "disease_name": (llm_keywords[0] if llm_keywords else matched_kw_str.split(", ")[0]),
                            "cumulative_cases": fallback_cum,
                            "new_cases": fallback_new,
                            "event_start_date": llm_meta.get("event_start_date"),
                            "event_end_date": llm_meta.get("event_end_date"),
                        }]
                    
                    # Tính tổng số ca để hiển thị trên UI
                    total_cases_all_diseases = sum(
                        max(d.get("cumulative_cases", 0), d.get("new_cases", 0))
                        for d in diseases_list
                    )

                    # Cập nhật keywords_matched cho bài nhiều bệnh
                    if llm_label == "relevant" and diseases_list:
                        disease_names_from_llm = [d["disease_name"] for d in diseases_list if d.get("disease_name")]
                        if disease_names_from_llm:
                            matched_kw_str = ", ".join(disease_names_from_llm)
                        elif llm_keywords:
                            matched_kw_str = ", ".join(llm_keywords)

                    # Tổng số ca của bệnh đầu tiên (dùng để resolve_event)
                    primary_disease = diseases_list[0] if diseases_list else {}
                    cumulative_cases = primary_disease.get("cumulative_cases", 0)
                    new_cases = primary_disease.get("new_cases", 0)

                    # ---- Location: LLM first, multiple location parsing ----
                    raw_location = llm_meta.get("location")
                    if not raw_location or str(raw_location).strip().lower() in ["", "null", "none", "không rõ", "việt nam"]:
                        raw_location = "unknown"
                    
                    location_list = [loc.strip() for loc in str(raw_location).split(",") if loc.strip()]
                    if not location_list:
                        location_list = ["unknown"]
                    
                    # Biểu thị cho file NewsEvent (gộp chuỗi)
                    location_merged = ", ".join(location_list)

                    source_domain = get_domain(link)

                    is_trusted = source_domain in whitelist
                    if not is_trusted:
                        logger.debug("Article skipped | reason=non_whitelisted_domain domain={}", source_domain)
                        continue

                    article_dto = schemas.ArticleCreate(
                        title=title,
                        link=link,
                        summary=effective_summary[:500] + "..." if len(effective_summary) > 500 else effective_summary,
                        source=source_domain,
                        published_date=pub_date,
                        keywords_matched=matched_kw_str,
                        is_whitelisted=True,
                        outbreak_relevance_score=calculate_outbreak_relevance_score(
                            title,
                            effective_summary,
                            [kw.strip() for kw in matched_kw_str.split(",") if kw.strip()],
                        ),
                        tags=None,
                    )
                    article_dto.is_suspected_false_positive = article_dto.outbreak_relevance_score < 3

                    # Sync logic: Kiểm tra link trùng lặp cho tất cả các nguồn
                    existing = crud.get_article_by_link(db, link)
                    if existing:
                        logger.debug("Article link already exists | link={}", link)
                        continue

                    event, event_match_score, dedupe_reason, event_current_total = resolve_event_for_article(
                        db=db,
                        title=title,
                        summary=effective_summary,
                        matched_keywords=matched_kw_str,
                        pub_date=pub_date,
                        location=location_merged,
                        cumulative_cases=cumulative_cases,
                        new_cases=new_cases,
                        severity=llm_meta.get("severity"),
                    )
                    article_dto.event_id = event.id if event else None
                    article_dto.event_match_score = event_match_score
                    article_dto.dedupe_reason = dedupe_reason
                    # Lưu số ca tổng vào tags để hiển thị trên UI (dùng tags làm carrier field)
                    article_dto.tags = f"cases:{total_cases_all_diseases}" if total_cases_all_diseases > 0 else None
                    saved_article = crud.create_article(db, article_dto)

                    # -------------------------------------------------------------------
                    # Iterate từng bệnh trong mảng diseases, tạo DiseaseCase riêng cho mỗi bệnh
                    # -------------------------------------------------------------------
                    hcm_tz = pytz.timezone("Asia/Ho_Chi_Minh")
                    for disease_entry in diseases_list:
                        d_name = disease_entry.get("disease_name") or (matched_kw_str.split(", ")[0])
                        d_cumulative = disease_entry.get("cumulative_cases", 0)
                        d_new = disease_entry.get("new_cases", 0)
                        d_total = max(d_cumulative, d_new)
                        start_str = disease_entry.get("event_start_date")
                        end_str = disease_entry.get("event_end_date")

                        if d_total == 0:
                            continue  # Không có số liệu, bỏ qua

                        report_start_date = pub_date
                        report_end_date = pub_date
                        if start_str and end_str:
                            try:
                                s_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=hcm_tz)
                                e_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=hcm_tz)
                                if s_dt <= e_dt <= pub_date:
                                    report_start_date = s_dt
                                    report_end_date = e_dt
                            except ValueError:
                                pass

                        days_diff = (report_end_date.date() - report_start_date.date()).days + 1
                        loc_count = len(location_list)
                        cases_per_day = max(1, d_total // days_diff) if days_diff > 1 else d_total
                        cases_per_day_per_loc = cases_per_day // loc_count if loc_count > 0 else cases_per_day

                        for j in range(days_diff):
                            current_iter_date = report_start_date + timedelta(days=j)
                            for loc in location_list:
                                existing_case = crud.get_disease_case_by_evd(db, event.id, current_iter_date, location=loc)
                                if existing_case:
                                    old_art = db.query(models.ArticleIdentity).filter(
                                        models.ArticleIdentity.id == existing_case.article_id
                                    ).first()
                                    if old_art and pub_date >= old_art.published_date:
                                        crud.update_disease_case(db, existing_case.id, cases_per_day_per_loc, saved_article.id)
                                else:
                                    crud.create_disease_case(
                                        db,
                                        models.DiseaseCase(
                                            article_id=saved_article.id,
                                            disease_name=d_name,
                                            case_count=cases_per_day_per_loc,
                                            location=loc,
                                            report_date=current_iter_date,
                                        ),
                                    )
                        logger.info(
                            "DiseaseCase | disease={} event_id={} from={} to={} total={} days={} locs={}",
                            d_name, event.id, report_start_date.date(), report_end_date.date(),
                            d_total, days_diff, len(location_list)
                        )

                    saved_count += 1

                    # Theo dõi số bài theo từng bệnh (disease_counts)
                    for d_entry in diseases_list:
                        d_name_key = d_entry.get("disease_name") or matched_kw_str.split(", ")[0]
                        d_name_key = d_name_key.strip().lower()
                        disease_counts[d_name_key] = disease_counts.get(d_name_key, 0) + 1

            except Exception as exc:
                logger.error("Error parsing feed | feed_url={} error={}", feed_url, exc)
                continue

        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            "Scan crawl completed | saved_trusted_count={} seen_links={} duration={:.2f}s",
            saved_count,
            len(seen_links),
            execution_time
        )
        
        result = schemas.ScanResult(
            saved_trusted_count=saved_count,
            execution_time=execution_time,
            disease_counts=disease_counts,
        )
        return result
    finally:
        _finish_llm_session()
        is_scanning_flag = False
