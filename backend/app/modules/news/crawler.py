import feedparser
from sqlalchemy.orm import Session
from . import crud, models, schemas
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote
from email.utils import parsedate_to_datetime
import re
import html
import json
import os
import unicodedata

import requests
from ...core.logger import get_logger

logger = get_logger("backend.news.crawler")

# ---------------------------------------------------------------------------
# RSS Feed list
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    "https://vnexpress.net/rss/suc-khoe.rss",
    "https://vnexpress.net/rss/thoi-su.rss",
    "https://vnexpress.net/rss/the-gioi.rss",
    "https://dantri.com.vn/rss/suc-khoe.rss",
    "https://dantri.com.vn/rss/the-gioi.rss",
    "https://tuoitre.vn/rss/suc-khoe.rss",
    "https://tuoitre.vn/rss/the-gioi.rss",
    "https://thanhnien.vn/rss/suc-khoe.rss",
    "https://thanhnien.vn/rss/the-gioi.rss",
    "https://suckhoedoisong.vn/rss/suc-khoe.rss",
    "https://vov.vn/rss/suc-khoe.rss",
    "https://vov.vn/rss/the-gioi.rss",
    "https://tienphong.vn/rss/suc-khoe-210.rss",
    "https://laodong.vn/rss/suc-khoe.rss",
    "https://laodong.vn/rss/thoi-su.rss",
    "https://vietnamnet.vn/rss/suc-khoe.rss",
    "https://vietnamnet.vn/rss/thoi-su.rss",
    "https://vietnamnet.vn/rss/the-gioi.rss",
    "https://nhandan.vn/rss/y-te.rss",
    "https://nhandan.vn/rss/the-gioi.rss",
    "http://cand.com.vn/rss/suc-khoe-c-5",
]

# ---------------------------------------------------------------------------
# Keyword filter lists
# ---------------------------------------------------------------------------

# Hard-exclude on title only — lifestyle / ads / personal advice.
# Intentionally narrow: loại sai còn nguy hiểm hơn giữ thừa,
# vì LLM sẽ xử lý phần còn lại.
HARD_EXCLUDE_TITLE_TERMS = [
    "nên ăn gì", "uống gì", "làm đẹp", "giảm cân",
    "thực phẩm chức năng", "bí quyết", "mẹo hay",
    "review ", "quảng cáo", "khuyến mãi", "24/7",
    "dấu hiệu sớm", "dấu hiệu cảnh báo","tư vấn bác sĩ", "kinh nghiệm",
]

# Context terms that raise the epidemiological signal score
EPIDEMIC_CONTEXT_TERMS = [
    "bệnh", "dịch", "ổ dịch", "ca bệnh", "ca mắc", "nhiễm", "lây", "lây lan",
    "virus", "vi rút", "xét nghiệm", "dương tính", "tử vong", "nhập viện",
    "điều trị", "triệu chứng", "bùng phát", "kiểm soát", "giám sát", "khẩn cấp",
    "cảnh báo", "y tế", "truyền nhiễm", "nghi nhiễm", "ca tử vong", "ngộ độc",
]

# Context terms that reduce the signal score (lifestyle / non-epidemic / advisory usage)
NON_EPIDEMIC_CONTEXT_TERMS = [
    "đau", "nhức", "vùng kín", "tinh hoàn", "sinh lý", "nam sinh", "quan hệ",
    "thẩm mỹ", "làm đẹp", "giảm cân", "thực đơn", "món ăn", "ăn uống", "tâm lý",
    "chuyện ấy", "sẹo", "da mặt", "mụn", "xương khớp", "phòng the",
    "tư vấn", "hướng dẫn", "cách phòng", "dấu hiệu", "nhầm với", "bài thuốc", 
    "chữa bệnh", "tự chữa", "hiếm gặp", "cách giải quyết", "24/7", "dấu hiệu",
]

# ---------------------------------------------------------------------------
# LLM re-check config
# ---------------------------------------------------------------------------
LLM_RECHECK_ENABLED = os.getenv("LLM_RECHECK_ENABLED", "false").lower() == "true"
LLM_RECHECK_MODEL = os.getenv("LLM_RECHECK_MODEL", "").strip()
LLM_RECHECK_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_RECHECK_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_RECHECK_TIMEOUT_SECONDS = int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20"))
LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS = int(
    os.getenv("LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS", "300")
)
LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS = int(
    os.getenv("LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS", "60")
)

# ---------------------------------------------------------------------------
# LLM prompt constants  (defined at module level → zero per-call overhead)
# ---------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = (
    "Bạn là classifier dịch tễ học. "
    "Nhiệm vụ duy nhất: phân tích bài báo và trả JSON hợp lệ. "
    "Không giải thích thêm ngoài JSON."
)

# Five carefully chosen few-shot examples:
#   2 relevant  (ổ dịch cụ thể + cảnh báo quốc tế)
#   2 irrelevant (tư vấn cá nhân + tổng kết lịch sử)
#   1 unsure    (thông tin mơ hồ, chưa xác nhận)
_FEW_SHOT_BLOCK = """
## Ví dụ tham khảo

### Ví dụ 1 — relevant (ổ dịch cụ thể, có số liệu)
Tiêu đề: Hà Nội ghi nhận 23 ca sốt xuất huyết trong một tuần, cảnh báo bùng phát
Tóm tắt: CDC Hà Nội xác nhận 23 ca mắc sốt xuất huyết tại quận Đống Đa, khuyến cáo người dân diệt muỗi.
→ {"label":"relevant","matched_keywords":["sốt xuất huyết"],"location":"Hà Nội","estimated_case_count":23,"severity":"medium","reason":"Ổ dịch cụ thể, số liệu rõ, cơ quan chức năng xác nhận."}

### Ví dụ 2 — relevant (cảnh báo WHO, không có số ca cụ thể)
Tiêu đề: WHO cảnh báo nguy cơ lây lan cúm A/H5N1 sang người tại Đông Nam Á
Tóm tắt: Tổ chức Y tế Thế giới phát đi cảnh báo sau các ca bệnh trên gia cầm tại Campuchia.
→ {"label":"relevant","matched_keywords":["cúm A","H5N1"],"location":"Đông Nam Á","estimated_case_count":0,"severity":"high","reason":"Cảnh báo chính thức WHO, nguy cơ lây lan liên quốc gia."}

### Ví dụ 3 — irrelevant (tư vấn dinh dưỡng cá nhân)
Tiêu đề: Bị sốt xuất huyết nên ăn gì để mau khỏi?
Tóm tắt: Chuyên gia dinh dưỡng gợi ý thực đơn cho bệnh nhân sốt xuất huyết đang hồi phục tại nhà.
→ {"label":"irrelevant","matched_keywords":[],"location":null,"estimated_case_count":0,"severity":null,"reason":"Tư vấn dinh dưỡng cá nhân, không có sự kiện dịch tễ."}

### Ví dụ 4 — irrelevant (tổng kết / lịch sử)
Tiêu đề: Nhìn lại đại dịch COVID-19: 3 năm Việt Nam ứng phó như thế nào?
Tóm tắt: Bài viết tổng kết quá trình chống dịch COVID 2020–2023, các bài học cho tương lai.
→ {"label":"irrelevant","matched_keywords":[],"location":null,"estimated_case_count":0,"severity":null,"reason":"Tổng kết lịch sử, không phải sự kiện đang diễn ra."}

### Ví dụ 5 — unsure (thông tin mơ hồ, chưa xác nhận chính thức)
Tiêu đề: Xuất hiện bệnh lạ tại miền Trung khiến nhiều người lo ngại
Tóm tắt: Một số người dân phản ánh triệu chứng bất thường, ngành y tế địa phương đang xác minh.
→ {"label":"unsure","matched_keywords":["bệnh lạ"],"location":"miền Trung","estimated_case_count":0,"severity":null,"reason":"Chưa có xác nhận chính thức, cần theo dõi thêm."}
""".strip()

_CRITERIA_BLOCK = """
## Tiêu chí phân loại

**relevant** — bài phải có ÍT NHẤT MỘT trong:
1. Ca bệnh / ổ dịch tại địa điểm + thời gian cụ thể
2. Cảnh báo chính thức từ Bộ Y tế / CDC / WHO / chính quyền
3. Số liệu ca mắc, tử vong, nhập viện được công bố
4. Bùng phát bệnh truyền nhiễm đang diễn ra

**irrelevant** — bài thuộc bất kỳ loại sau:
- Tư vấn, hỏi đáp sức khỏe cá nhân
- Quảng cáo thuốc / thực phẩm chức năng / làm đẹp
- Giải thích triệu chứng thông thường (không có sự kiện)
- Tổng kết / lịch sử y tế (không phải sự kiện đang xảy ra)

**unsure** — thông tin quá mơ hồ, chưa có xác nhận chính thức
""".strip()

_SCHEMA_BLOCK = """
## Output schema (JSON hợp lệ — không thêm bất kỳ text nào ngoài JSON)
{
  "label": "relevant" | "irrelevant" | "unsure",
  "matched_keywords": [<chỉ chọn từ danh sách keyword bên dưới, mảng rỗng nếu irrelevant>],
  "location": "<tỉnh/thành/quốc gia nếu đề cập, null nếu không>",
  "estimated_case_count": <số nguyên, 0 nếu không đề cập>,
  "severity": "low" | "medium" | "high" | null,
  "reason": "<tối đa 20 từ tiếng Việt>"
}
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

# ===========================================================================
# Utility helpers
# ===========================================================================

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().replace("www.", "")
    except Exception:
        return ""


def normalize_text(text: str) -> str:
    if not text:
        return ""
    decoded = html.unescape(text)
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", without_tags).strip()


def slugify_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(text).lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


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


def _redact_api_key(api_key: str) -> str:
    if not api_key:
        return "<missing>"
    if len(api_key) <= 8:
        return f"{api_key[:2]}***"
    return f"{api_key[:4]}...{api_key[-4:]}"


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


def extract_case_count(text: str, disease_keywords: list[str]) -> int:
    """
    Regex fallback to extract case counts from text.
    Used when LLM returns estimated_case_count == 0.
    Examples matched: "15 ca mắc", "thêm 20 trường hợp", "gần 100 người nhiễm"
    """
    if not text:
        return 0
    patterns = [
        r"(\d+)\s+(ca\s+mắc|trường\s+hợp|người\s+nhiễm|ca\s+dương\s+tính)",
        r"(phát\s+hiện|ghi\s+nhận)\s+(\d+)\s+(ca|trường\s+hợp)",
    ]
    for pat in patterns:
        match = re.search(pat, text.lower())
        if match:
            val1, val2 = match.group(1), match.group(2)
            if val1.isdigit():
                return int(val1)
            if val2.isdigit():
                return int(val2)
    return 0


def extract_primary_keyword(matched_keywords: str | None) -> str | None:
    if not matched_keywords:
        return None
    first = matched_keywords.split(",")[0].strip()
    return first or None


def compute_title_similarity(title_a: str, title_b: str) -> float:
    stopwords = {
        "va", "voi", "cua", "cho", "sau", "tai", "tu", "tren", "trong", "khi",
        "the", "co", "da", "mot", "nhung", "nhieu", "nhu", "la", "bi",
    }
    tokens_a = {token for token in slugify_text(title_a).split("-") if len(token) > 2 and token not in stopwords}
    tokens_b = {token for token in slugify_text(title_b).split("-") if len(token) > 2 and token not in stopwords}
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


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
    pub_date: datetime,
    location: str | None,
    case_count: int,
    event,
) -> tuple[float, dict[str, float]]:
    title_similarity = compute_title_similarity(title, event.canonical_title)
    title_score = min(title_similarity / 0.6, 1.0) * 0.45

    normalized_location = normalize_text(location or "")
    event_location = normalize_text(event.location or "")
    if normalized_location and event_location:
        if normalized_location == event_location:
            location_score = 0.25
        elif normalized_location in event_location or event_location in normalized_location:
            location_score = 0.15
        else:
            location_score = 0.0
    elif not normalized_location and not event_location:
        location_score = 0.1
    else:
        location_score = 0.05

    day_diff = abs((pub_date.date() - event.event_date.date()).days)
    if day_diff == 0:
        date_score = 0.2
    elif day_diff == 1:
        date_score = 0.14
    elif day_diff == 2:
        date_score = 0.08
    else:
        date_score = 0.0

    if case_count > 0 and (event.case_count or 0) > 0:
        delta = abs(case_count - event.case_count)
        tolerance = max(3, int(max(case_count, event.case_count) * 0.3))
        if delta == 0:
            case_score = 0.1
        elif delta <= tolerance:
            case_score = 0.07
        else:
            case_score = 0.0
    else:
        case_score = 0.04

    breakdown = {
        "title": round(title_score, 3),
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
    matched_keywords: str,
    pub_date: datetime,
    location: str | None,
    case_count: int,
    severity: str | None,
) -> tuple[models.NewsEvent | None, float | None, str | None]:
    MATCH_SCORE_THRESHOLD = 0.6
    primary_keyword = extract_primary_keyword(matched_keywords)
    if not primary_keyword:
        return None, None, None

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

    start_date = pub_date - timedelta(days=2)
    end_date = pub_date + timedelta(days=2)
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
    for event in recent_events:
        score, breakdown = compute_event_similarity_score(
            title=title,
            pub_date=pub_date,
            location=normalized_location,
            case_count=case_count,
            event=event,
        )
        if score > best_score:
            best_match = event
            best_score = score
            best_breakdown = breakdown

    if best_match and best_score >= MATCH_SCORE_THRESHOLD:
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
            case_count=case_count if case_count > 0 else None,
            severity=severity,
        )
        return updated_event, best_score, format_dedupe_reason(best_breakdown or {}, True)

    if best_match:
        logger.debug(
            "Event below threshold | candidate_event_id={} score={} threshold={} breakdown={} title={}",
            best_match.id,
            best_score,
            MATCH_SCORE_THRESHOLD,
            best_breakdown,
            title,
        )

    created_event = crud.create_news_event(
        db,
        canonical_title=title,
        disease_name=primary_keyword,
        location=normalized_location,
        event_date=pub_date,
        case_count=case_count,
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
    
    return created_event, None, format_dedupe_reason(best_breakdown or {}, False)


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

def build_llm_recheck_prompt(title: str, summary: str, keywords: list[str]) -> str:
    """
    Assemble the user-turn prompt for the LLM classifier.

    Structure (token-efficient):
      1. Few-shot examples  — module-level constant, no per-call cost
      2. Separator
      3. Criteria           — module-level constant
      4. Keyword list       — varies per call (small)
      5. Output schema      — module-level constant
      6. Article to analyse — varies per call
    """
    keyword_block = "\n".join(f"- {kw}" for kw in keywords)
    keyword_section = f"## Keyword được phép chọn (CHỈ từ danh sách này)\n{keyword_block}"

    article_block = (
        f"## Bài báo cần phân tích\n"
        f"Tiêu đề: {title}\n"
        f"Tóm tắt: {summary}"
    )

    return "\n\n".join([
        _FEW_SHOT_BLOCK,
        "---",
        _CRITERIA_BLOCK,
        keyword_section,
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


# ===========================================================================
# LLM re-check
# ===========================================================================

def llm_recheck_article(
    title: str,
    summary: str,
    candidate_keywords: list[str],
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
    EMPTY_META: dict = {"location": None, "estimated_case_count": 0, "severity": None}

    if not candidate_keywords:
        return "irrelevant", [], "No candidate keywords", EMPTY_META

    if not LLM_RECHECK_ENABLED:
        return "unsure", candidate_keywords, "LLM re-check disabled", EMPTY_META

    in_cooldown, cooldown_reason = _get_llm_cooldown_status()
    if in_cooldown:
        return "unsure", candidate_keywords, f"LLM cooldown active: {cooldown_reason}", EMPTY_META

    preflight = get_llm_preflight_status()
    if not preflight.get("ok"):
        logger.warning("LLM re-check skipped | reason={}", preflight.get("message"))
        return "unsure", candidate_keywords, str(preflight.get("message")), EMPTY_META

    prompt = build_llm_recheck_prompt(title, summary, candidate_keywords)

    try:
        response = requests.post(
            f"{LLM_RECHECK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_RECHECK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_RECHECK_MODEL,
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
    except requests.exceptions.Timeout as exc:
        _activate_llm_cooldown(
            LLM_RECHECK_TIMEOUT_COOLDOWN_SECONDS,
            f"timeout after {LLM_RECHECK_TIMEOUT_SECONDS}s",
        )
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM timeout: {exc}", EMPTY_META
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code == 429:
            retry_after = _parse_retry_after_seconds(
                exc.response.headers.get("Retry-After") if exc.response is not None else None
            )
            cooldown_seconds = retry_after or LLM_RECHECK_RATE_LIMIT_COOLDOWN_SECONDS
            _activate_llm_cooldown(
                cooldown_seconds,
                f"rate limited by provider (HTTP 429)",
            )
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM error: {exc}", EMPTY_META
    except requests.exceptions.RequestException as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM request error: {exc}", EMPTY_META
    except Exception as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM error: {exc}", EMPTY_META

    if not parsed:
        return "unsure", candidate_keywords, "LLM returned invalid JSON", EMPTY_META

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
        "estimated_case_count": _normalize_llm_case_count(
            parsed.get("estimated_case_count")
        ),
        "severity": _normalize_llm_severity(parsed.get("severity")),
    }

    logger.debug(
        "LLM recheck | label={} keywords={} location={} cases={} severity={} reason={}",
        label,
        normalized_keywords,
        meta["location"],
        meta["estimated_case_count"],
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

def scan_news(db: Session, fetch_unknown: bool, start_date: datetime | None = None, end_date: datetime | None = None) -> schemas.ScanResult:
    """
    Crawl all RSS feeds, filter articles by keyword + LLM, and persist
    articles from trusted domains.

    Args:
        db            : SQLAlchemy session
        fetch_unknown : if True, also collect articles from non-whitelisted
                        domains and return them for manual review.

    Returns:
        ScanResult with saved_trusted_count and unknown_articles list.
    """
    # ------------------------------------------------------------------
    # 1. Bootstrap: keywords + whitelist
    # ------------------------------------------------------------------
    if LLM_RECHECK_ENABLED:
        log_llm_preflight_status()

    # Convert to naive datetimes if they arrive as aware
    if start_date and start_date.tzinfo is not None:
        start_date = start_date.replace(tzinfo=None)
    if end_date and end_date.tzinfo is not None:
        end_date = end_date.replace(tzinfo=None)

    keywords_obj = crud.get_keywords(db)
    keywords = [k.text for k in keywords_obj]
    logger.info(
        "Scan crawl started | keyword_count={} fetch_unknown={}",
        len(keywords),
        fetch_unknown,
    )

    if not keywords:
        logger.warning("Scan crawl skipped | reason=no_keywords")
        return schemas.ScanResult(saved_trusted_count=0, unknown_articles=[])

    whitelist_objs = crud.get_whitelisted_domains(db)
    whitelist = [w.domain.lower() for w in whitelist_objs]

    # Default Vietnamese trusted domains when the DB whitelist is empty
    if not whitelist:
        whitelist = [
            "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn",
            "suckhoedoisong.vn", "tienphong.vn", "laodong.vn",
            "vietnamnet.vn", "nhandan.vn", "cand.com.vn",
        ]

    saved_count = 0
    unknown_articles_list: list[schemas.ArticleCreate] = []
    seen_links: set[str] = set()

    # ------------------------------------------------------------------
    # 2. Crawl feeds
    # ------------------------------------------------------------------
    all_feeds = list(RSS_FEEDS)
    if fetch_unknown:
        for kw in keywords:
            encoded_kw = quote(kw.encode('utf-8'))
            google_news_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=vi&gl=VN&ceid=VN:vi"
            all_feeds.append(google_news_url)

    for feed_url in all_feeds:
        try:
            logger.info("Parsing feed | feed_url={}", feed_url)
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                link = entry.get("link", "")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                pub_date = parse_date(entry)

                if start_date:
                    if pub_date < start_date:
                        continue
                else:
                    # Keep a 14-day window to catch slower-moving outbreak reports if no start_date given
                    if pub_date < datetime.utcnow() - timedelta(days=14):
                        continue

                if end_date and pub_date > end_date:
                    continue

                title = normalize_text(entry.get("title", ""))
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

                # ---- Stage 2: LLM classifier ----
                llm_label, llm_keywords, llm_reason, llm_meta = llm_recheck_article(
                    title, summary, candidate_keywords
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

                # ---- Extract case count: LLM first, regex fallback ----
                case_count = llm_meta["estimated_case_count"] or extract_case_count(
                    title + " " + summary, keywords
                )

                # ---- Location: LLM first, generic fallback ----
                location = llm_meta.get("location") or "Việt Nam"

                source_domain = get_domain(link)

                article_dto = schemas.ArticleCreate(
                    title=title,
                    link=link,
                    summary=summary[:500] + "..." if len(summary) > 500 else summary,
                    source=source_domain,
                    published_date=pub_date,
                    keywords_matched=matched_kw_str,
                    is_whitelisted=False,
                    tags=None,
                )

                # ---- Whitelist check ----
                is_trusted = any(w in source_domain for w in whitelist)

                if is_trusted:
                    article_dto.is_whitelisted = True
                    existing = crud.get_article_by_link(db, link)
                    if not existing:
                        event, event_match_score, dedupe_reason = resolve_event_for_article(
                            db=db,
                            title=title,
                            matched_keywords=matched_kw_str,
                            pub_date=pub_date,
                            location=location,
                            case_count=case_count,
                            severity=llm_meta.get("severity"),
                        )
                        article_dto.event_id = event.id if event else None
                        article_dto.event_match_score = event_match_score
                        article_dto.dedupe_reason = dedupe_reason
                        saved_article = crud.create_article(db, article_dto)

                        if case_count > 0:
                            first_kw = matched_kw_str.split(", ")[0]
                            crud.create_disease_case(
                                db,
                                models.DiseaseCase(
                                    article_id=saved_article.id,
                                    disease_name=first_kw,
                                    case_count=case_count,
                                    location=location,
                                    report_date=pub_date,
                                ),
                            )

                        saved_count += 1
                else:
                    if fetch_unknown:
                        # Not persisted until a human approves
                        unknown_articles_list.append(article_dto)

        except Exception as exc:
            logger.error("Error parsing feed | feed_url={} error={}", feed_url, exc)
            continue

    logger.info(
        "Scan crawl completed | saved_trusted_count={} unknown_articles={} seen_links={}",
        saved_count,
        len(unknown_articles_list),
        len(seen_links),
    )
    return schemas.ScanResult(
        saved_trusted_count=saved_count,
        unknown_articles=unknown_articles_list,
    )
