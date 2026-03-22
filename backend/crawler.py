import feedparser
from sqlalchemy.orm import Session
from . import schemas, crud, models
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)

# List of common Vietnamese health RSS feeds
RSS_FEEDS = [
    "https://vnexpress.net/rss/suc-khoe.rss",
    "https://dantri.com.vn/rss/suc-khoe.rss",
    "https://tuoitre.vn/rss/suc-khoe.rss",
    "https://thanhnien.vn/rss/suc-khoe.rss",
    "https://suckhoedoisong.vn/rss/suc-khoe.rss",
    "https://vov.vn/rss/suc-khoe.rss",
    "https://tienphong.vn/rss/suc-khoe-210.rss",
    "https://laodong.vn/rss/suc-khoe.rss",
    "https://vietnamnet.vn/rss/suc-khoe.rss",
    "https://nhandan.vn/rss/y-te.rss",
    "http://cand.com.vn/rss/suc-khoe-c-5"
]

# Keywords to exclude articles that are advice/QA/general discussions
EXCLUDED_KEYWORDS = [
    "tư vấn", "hỏi đáp", "lời khuyên", "có nên", 
    "thực phẩm chức năng", "giảm cân", "làm đẹp", 
    "bí quyết", "mẹo", "ăn gì", "uống gì"
]

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.lower().replace("www.", "")
    except:
        return ""

def matches_keywords(text: str, keywords: list[str]) -> str | None:
    if not text:
        return None
    text_lower = text.lower()
    
    # Check exclusion first
    for ex in EXCLUDED_KEYWORDS:
        if ex in text_lower:
            return None

    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return ", ".join(matched) if matched else None

def parse_date(entry) -> datetime:
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return datetime(*entry.published_parsed[:6])
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

def scan_news(db: Session, fetch_unknown: bool, days_limit: int, max_execution_time: int) -> schemas.ScanResult:
    start_time = datetime.utcnow()
    
    # 1. Get Keywords and Whitelist
    keywords_obj = crud.get_keywords(db)
    # ... (existing setup)
    keywords = [k.text for k in keywords_obj]
    
    if not keywords:
        logger.warning("No keywords found to scan.")
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
        # Check Execution Time Check
        if max_execution_time > 0:
            elapsed_minutes = (datetime.utcnow() - start_time).total_seconds() / 60
            if elapsed_minutes >= max_execution_time:
                logger.info(f"Max execution time ({max_execution_time}m) reached. Stopping scan.")
                break

        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Inner loop time check (granularity)
                if max_execution_time > 0:
                    elapsed_minutes = (datetime.utcnow() - start_time).total_seconds() / 60
                    if elapsed_minutes >= max_execution_time:
                        break

                link = entry.get('link', '')
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                
                # Keyword check
                matched_kw_str = matches_keywords(title, keywords)
                if not matched_kw_str:
                     # Check summary if title failed? (Optional simplification: focus on title for accuracy)
                     pass
                
                if not matched_kw_str:
                    continue

                # Publish Date
                pub_date = parse_date(entry)
                
                # Limit by configured days
                if pub_date < datetime.utcnow() - timedelta(days=days_limit):
                    continue

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
            logger.error(f"Error parsing feed {feed_url}: {e}")
            continue

    return schemas.ScanResult(
        saved_trusted_count=saved_count,
        unknown_articles=unknown_articles_list
    )
