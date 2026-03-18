import feedparser
from sqlalchemy.orm import Session
from . import crud, models, schemas
from datetime import datetime, timedelta
from urllib.parse import urlparse
import re
import html
import json
import os

import requests
from ...core.logger import get_logger

logger = get_logger("backend.news.crawler")

# List of common Vietnamese RSS feeds.
# Health-only feeds miss some outbreak articles that are published under
# current affairs or world sections, so we include a broader news mix.
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
    "http://cand.com.vn/rss/suc-khoe-c-5"
]

# Keywords to exclude articles that are advice/QA/general discussions
EXCLUDED_KEYWORDS = [
    "tư vấn", "hỏi đáp", "lời khuyên", "có nên", 
    "thực phẩm chức năng", "giảm cân", "làm đẹp", 
    "bí quyết", "mẹo", "ăn gì", "uống gì"
]

# Terms that indicate the article is actually about disease surveillance,
# not just containing a keyword string incidentally.
EPIDEMIC_CONTEXT_TERMS = [
    "bệnh", "dịch", "ổ dịch", "ca bệnh", "ca mắc", "nhiễm", "lây", "lây lan",
    "virus", "vi rút", "xét nghiệm", "dương tính", "tử vong", "nhập viện",
    "điều trị", "triệu chứng", "bùng phát", "kiểm soát", "giám sát", "khẩn cấp",
    "cảnh báo", "y tế", "truyền nhiễm", "nghi nhiễm", "ca tử vong", "ngộ độc",
]

# Terms that often produce false positives for disease keywords in lifestyle
# or body-part contexts.
NON_EPIDEMIC_CONTEXT_TERMS = [
    "đau", "nhức", "vùng kín", "tinh hoàn", "sinh lý", "nam sinh", "quan hệ",
    "thẩm mỹ", "làm đẹp", "giảm cân", "thực đơn", "món ăn", "ăn uống", "tâm lý",
    "chuyện ấy", "sẹo", "da mặt", "mụn", "xương khớp", "phòng the",
]

LLM_RECHECK_ENABLED = os.getenv("LLM_RECHECK_ENABLED", "false").lower() == "true"
LLM_RECHECK_MODEL = os.getenv("LLM_RECHECK_MODEL", "").strip()
LLM_RECHECK_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_RECHECK_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_RECHECK_TIMEOUT_SECONDS = int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20"))

_LLM_PREFLIGHT_CHECKED = False
_LLM_PREFLIGHT_STATUS: dict[str, str | bool] = {
    "ok": False,
    "message": "LLM preflight has not run",
}

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().replace("www.", "")
    except:
        return ""

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def text_contains_term(text: str, term: str) -> bool:
    normalized_term = re.escape(term.lower().strip())
    if not normalized_term:
        return False
    # For multi-word keywords, allow flexible whitespace between tokens.
    normalized_term = normalized_term.replace(r"\ ", r"\s+")
    pattern = rf"(?<!\w){normalized_term}(?!\w)"
    return re.search(pattern, text) is not None

def score_keyword_context(text: str, keyword: str) -> int:
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
    if status.get("ok"):
        logger.info(
            "LLM preflight | enabled={} model={} base_url={} api_key={} status={}",
            status.get("enabled"),
            status.get("model"),
            status.get("base_url"),
            status.get("api_key"),
            status.get("message"),
        )
    else:
        logger.warning(
            "LLM preflight | enabled={} model={} base_url={} api_key={} status={}",
            status.get("enabled"),
            status.get("model"),
            status.get("base_url"),
            status.get("api_key"),
            status.get("message"),
        )
    return status

def build_llm_recheck_prompt(title: str, summary: str, keywords: list[str]) -> str:
    keyword_block = "\n".join(f"- {keyword}" for keyword in keywords)
    return f"""Bạn là bộ lọc tin dịch tễ.

Nhiệm vụ:
- Đọc tiêu đề và tóm tắt bài báo.
- Xác định bài có thực sự liên quan đến bệnh truyền nhiễm / ổ dịch / ca bệnh / cảnh báo y tế công cộng hay không.
- Nếu có, chọn keyword phù hợp nhất từ danh sách.
- Nếu không, trả về irrelevant.

Danh sách keyword:
{keyword_block}

Tiêu đề:
{title}

Tóm tắt:
{summary}

Trả JSON:
{{
  "label": "relevant | irrelevant | unsure",
  "matched_keywords": [],
  "reason": "..."
}}"""

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

def llm_recheck_article(title: str, summary: str, candidate_keywords: list[str]) -> tuple[str, list[str], str]:
    if not candidate_keywords:
        return "irrelevant", [], "No candidate keywords"

    preflight = get_llm_preflight_status()
    if not preflight.get("ok"):
        logger.warning("LLM re-check skipped | reason={}", preflight.get("message"))
        return "unsure", candidate_keywords, str(preflight.get("message"))

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
                    {"role": "system", "content": "You are a precise epidemiological news relevance classifier."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=LLM_RECHECK_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        parsed = extract_json_object(content)
    except Exception as exc:
        logger.warning("LLM re-check failed | error={}", exc)
        return "unsure", candidate_keywords, f"LLM error: {exc}"

    if not parsed:
        return "unsure", candidate_keywords, "LLM returned invalid JSON"

    label = str(parsed.get("label", "unsure")).strip().lower()
    matched_keywords = parsed.get("matched_keywords") or []
    reason = str(parsed.get("reason", "")).strip()

    if not isinstance(matched_keywords, list):
        matched_keywords = []

    normalized_keywords = []
    candidate_map = {keyword.lower(): keyword for keyword in candidate_keywords}
    for keyword in matched_keywords:
        keyword_text = str(keyword).strip()
        if keyword_text.lower() in candidate_map:
            normalized_keywords.append(candidate_map[keyword_text.lower()])

    normalized_keywords = list(dict.fromkeys(normalized_keywords))

    if label not in {"relevant", "irrelevant", "unsure"}:
        label = "unsure"

    if label == "relevant" and not normalized_keywords:
        normalized_keywords = candidate_keywords

    return label, normalized_keywords, reason

def matches_keywords(title: str, summary: str, keywords: list[str]) -> str | None:
    combined_text = normalize_text(f"{title}\n{summary}")
    if not combined_text:
        return None
    text_lower = combined_text.lower()
    
    # Check exclusion first
    for ex in EXCLUDED_KEYWORDS:
        if ex in text_lower:
            return None

    matched = []
    for kw in keywords:
        title_lower = normalize_text(title).lower()
        summary_lower = normalize_text(summary).lower()

        title_score = score_keyword_context(title_lower, kw)
        summary_score = score_keyword_context(summary_lower, kw)

        # Strong match if keyword is in title with disease context, or appears
        # in summary with enough surrounding epidemiological context.
        if title_score >= 3 or summary_score >= 4 or (title_score + summary_score) >= 5:
            matched.append(kw)
    return ", ".join(matched) if matched else None

def parse_date(entry) -> datetime:
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6])
    return datetime.utcnow()

def extract_case_count(text: str, disease_keywords: list[str]) -> int:
    """
    Simulated NLP: regex to find 'X ca mắc', 'X trường hợp' near keywords.
    """
    if not text: return 0
    
    # Regex for "X cases"
    # Examples: "15 ca mắc", "thêm 20 trường hợp", "gần 100 người nhiễm"
    patterns = [
        r"(\d+)\s+(ca\s+mắc|trường\s+hợp|người\s+nhiễm|ca\s+dương\s+tính)",
        r"(phát\s+hiện|ghi\s+nhận)\s+(\d+)\s+(ca|trường\s+hợp)"
    ]
    
    for pat in patterns:
        match = re.search(pat, text.lower())
        if match:
            # Check if group 1 is digit or group 2 is digit (depending on pattern)
            val1 = match.group(1)
            val2 = match.group(2)
            if val1.isdigit(): return int(val1)
            if val2.isdigit(): return int(val2)
            
    return 0

def detect_tags(title: str, pub_date: datetime) -> list[str]:
    tags = []
    # 1. "Mới" tag: < 5 hours
    if datetime.utcnow() - pub_date < timedelta(hours=5):
        tags.append("Mới")
        
    # 2. "Cảnh báo" tag: Keywords
    alert_keywords = ["bùng phát", "ổ dịch", "khẩn cấp", "tử vong", "nguy kịch", "lây lan nhanh"]
    title_lower = title.lower()
    if any(k in title_lower for k in alert_keywords):
        tags.append("Cảnh báo")
        
    return tags

def scan_news(db: Session, fetch_unknown: bool) -> schemas.ScanResult:
    # 1. Get Keywords and Whitelist
    if LLM_RECHECK_ENABLED:
        log_llm_preflight_status()

    keywords_obj = crud.get_keywords(db)
    keywords = [k.text for k in keywords_obj]
    logger.info("Scan crawl started | keyword_count={} fetch_unknown={}", len(keywords), fetch_unknown)
    
    if not keywords:
        logger.warning("Scan crawl skipped | reason=no_keywords")
        return schemas.ScanResult(saved_trusted_count=0, unknown_articles=[])

    whitelist_objs = crud.get_whitelisted_domains(db)
    whitelist = [w.domain.lower() for w in whitelist_objs]

    # Add default VN trusted domains if whitelist is empty
    if not whitelist:
        whitelist = [
            "vnexpress.net", "dantri.com.vn", "tuoitre.vn", "thanhnien.vn", 
            "suckhoedoisong.vn", "tienphong.vn", "laodong.vn", 
            "vietnamnet.vn", "nhandan.vn", "cand.com.vn"
        ]

    saved_count = 0
    unknown_articles_list = []
    seen_links = set()
    
    # 2. Crawl Feeds
    for feed_url in RSS_FEEDS:
        try:
            logger.info("Parsing feed | feed_url={}", feed_url)
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                link = entry.get('link', '')
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                # Publish Date
                pub_date = parse_date(entry)
                
                # Limit to 14 days to avoid missing slower-moving outbreak reports.
                if pub_date < datetime.utcnow() - timedelta(days=14):
                    continue

                title = normalize_text(entry.get('title', ''))
                summary = normalize_text(entry.get('summary', '') or entry.get('description', ''))

                # Keyword check on both title and summary.
                matched_kw_str = matches_keywords(title, summary, keywords)
                if not matched_kw_str:
                    continue

                candidate_keywords = [kw.strip() for kw in matched_kw_str.split(",") if kw.strip()]
                llm_label, llm_keywords, llm_reason = llm_recheck_article(title, summary, candidate_keywords)
                if llm_label == "irrelevant":
                    logger.info("LLM filtered article as irrelevant | title={} reason={}", title, llm_reason)
                    continue
                if llm_label == "relevant" and llm_keywords:
                    matched_kw_str = ", ".join(llm_keywords)

                # Prepare Data
                source_domain = get_domain(link)
                
                # Tags
                tags_list = detect_tags(title, pub_date)
                tags_str = ", ".join(tags_list) if tags_list else None
                
                # Case Extraction
                case_count = extract_case_count(title + " " + summary, keywords)

                article_dto = schemas.ArticleCreate(
                    title=title,
                    link=link,
                    summary=summary[:500] + "..." if len(summary) > 500 else summary, 
                    source=source_domain,
                    published_date=pub_date,
                    keywords_matched=matched_kw_str,
                    is_whitelisted=False,
                    tags=tags_str
                )

                # Whitelist Check
                is_trusted = any(w in source_domain for w in whitelist)
                
                if is_trusted:
                    article_dto.is_whitelisted = True
                    # Auto Save
                    existing = crud.get_article_by_link(db, link)
                    if not existing:
                        # Save Article
                        saved_article = crud.create_article(db, article_dto)
                        
                        # Save DiseaseCase if count > 0
                        if case_count > 0:
                            # Primary disease from matched string (take first one)
                            first_kw = matched_kw_str.split(", ")[0]
                            crud.create_disease_case(db, models.DiseaseCase(
                                article_id=saved_article.id,
                                disease_name=first_kw,
                                case_count=case_count,
                                location="Việt Nam", # Placeholder, would need NER for location
                                report_date=pub_date
                            ))
                        
                        saved_count += 1
                else:
                    if fetch_unknown:
                        unknown_articles_list.append(article_dto) # Cases not saved until user approves
                        
        except Exception as e:
            logger.error("Error parsing feed | feed_url={} error={}", feed_url, e)
            continue

    logger.info(
        "Scan crawl completed | saved_trusted_count={} unknown_articles={} seen_links={}",
        saved_count,
        len(unknown_articles_list),
        len(seen_links),
    )
    return schemas.ScanResult(
        saved_trusted_count=saved_count,
        unknown_articles=unknown_articles_list
    )
