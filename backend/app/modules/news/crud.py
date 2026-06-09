from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, exists, and_, or_, select, not_
from . import models, schemas
from datetime import datetime

# --- Articles ---

def _article_query(db: Session, keyword: str | None = None, date: str | None = None, include_excluded: bool = False):
    query = db.query(models.ArticleIdentity).options(joinedload(models.ArticleIdentity.cases))
    if not include_excluded:
        query = query.filter(
            models.ArticleIdentity.is_excluded.isnot(True)
        )
    if keyword:
        query = query.join(models.ArticleDetails, models.ArticleIdentity.details).filter(
            models.ArticleDetails.keywords_matched.ilike(f"%{keyword}%")
        )
        # Match by DiseaseCase.disease_name when available, fall back to keywords_matched only
        # Avoids broad-context false positives (eg. "Ebola" articles under "virus" filter)
        has_matching_case = exists(
            select(models.DiseaseCase.id).where(
                and_(
                    models.DiseaseCase.article_id == models.ArticleIdentity.id,
                    models.DiseaseCase.disease_name.ilike(f"%{keyword}%"),
                )
            )
        )
        has_any_case = exists(
            select(models.DiseaseCase.id).where(
                models.DiseaseCase.article_id == models.ArticleIdentity.id
            )
        )
        query = query.filter(or_(has_matching_case, ~has_any_case))
    if date:
        query = query.filter(func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d") == date)
    return query


def get_articles(db: Session, skip: int = 0, limit: int = 100, keyword: str | None = None, date: str | None = None, include_excluded: bool = False):
    return _article_query(db, keyword=keyword, date=date, include_excluded=include_excluded)\
        .order_by(models.ArticleIdentity.published_date.desc(), models.ArticleIdentity.id.desc())\
        .offset(skip).limit(limit).all()

def count_articles(db: Session, keyword: str | None = None, date: str | None = None, include_excluded: bool = False):
    """Count query riêng, KHÔNG joinedload(cases) — nhẹ hơn nhiều so với _article_query."""
    query = db.query(func.count(models.ArticleIdentity.id))
    if not include_excluded:
        query = query.filter(models.ArticleIdentity.is_excluded.isnot(True))
    if keyword:
        query = query.join(models.ArticleDetails, models.ArticleIdentity.details).filter(
            models.ArticleDetails.keywords_matched.ilike(f"%{keyword}%")
        )
        has_matching_case = exists(
            select(models.DiseaseCase.id).where(
                and_(
                    models.DiseaseCase.article_id == models.ArticleIdentity.id,
                    models.DiseaseCase.disease_name.ilike(f"%{keyword}%"),
                )
            )
        )
        has_any_case = exists(
            select(models.DiseaseCase.id).where(
                models.DiseaseCase.article_id == models.ArticleIdentity.id
            )
        )
        query = query.filter(or_(has_matching_case, ~has_any_case))
    if date:
        query = query.filter(func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d") == date)
    return query.scalar()

def get_article_by_link(db: Session, link: str):
    return db.query(models.ArticleIdentity).filter(models.ArticleIdentity.link == link).first()

def create_article(db: Session, article: schemas.ArticleCreate):
    # 1. Create Identity
    db_identity = models.ArticleIdentity(
        title=article.title,
        link=article.link,
        published_date=article.published_date,
        event_id=article.event_id,
        event_match_score=article.event_match_score,
        dedupe_reason=article.dedupe_reason,
    )
    db.add(db_identity)
    db.commit()
    db.refresh(db_identity)

    # 2. Create Details
    db_details = models.ArticleDetails(
        article_id=db_identity.id,
        summary=article.summary,
        source=article.source,
        keywords_matched=article.keywords_matched,
        tags=article.tags,
        llm_normalized_title=article.llm_normalized_title,
        is_whitelisted=article.is_whitelisted,
        outbreak_relevance_score=article.outbreak_relevance_score,
        is_suspected_false_positive=article.is_suspected_false_positive,
    )
    db.add(db_details)
    db.commit()
    
    return db_identity


def get_recent_events(
    db: Session,
    disease_name: str,
    location: str | None,
    start_date: datetime,
    end_date: datetime,
):
    query = db.query(models.NewsEvent).filter(
        models.NewsEvent.disease_name == disease_name,
        models.NewsEvent.event_date >= start_date,
        models.NewsEvent.event_date <= end_date,
    )
    if location:
        query = query.filter(models.NewsEvent.location == location)
    return query.order_by(models.NewsEvent.event_date.desc()).all()


def compute_event_severity(event) -> str:
    score = 0
    if event.case_count >= 100:
        score += 5
    elif event.case_count >= 50:
        score += 4
    elif event.case_count >= 10:
        score += 3
    elif event.case_count >= 1:
        score += 1
    if event.event_date:
        days_old = (datetime.utcnow() - event.event_date).days
        if days_old <= 7:
            score += 1
    if score >= 6:
        return "critical"
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"

def get_events(db: Session, skip: int = 0, limit: int = 100):
    from ..evaluation.models import ArticleEvaluation
    
    # Một bài báo có nhãn rác (noise, irrelevant, unsure) từ evaluation
    is_trash_evaluation = exists().where(
        and_(
            ArticleEvaluation.article_id == models.ArticleIdentity.id,
            or_(
                ArticleEvaluation.human_label.in_(["noise", "irrelevant", "unsure"]),
                and_(
                    ArticleEvaluation.human_label.is_(None),
                    ArticleEvaluation.llm_label.in_(["noise", "irrelevant", "unsure"])
                )
            )
        )
    )
    
    # Bài báo hợp lệ: không bị loại trừ và không có nhãn rác
    is_valid_article = and_(
        models.ArticleIdentity.is_excluded.isnot(True),
        not_(is_trash_evaluation)
    )
    
    # Sự kiện hợp lệ: có ít nhất một bài báo hợp lệ
    has_valid_article = exists().where(
        and_(
            models.ArticleIdentity.event_id == models.NewsEvent.id,
            is_valid_article
        )
    )
    
    return db.query(models.NewsEvent).filter(has_valid_article).order_by(models.NewsEvent.event_date.desc(), models.NewsEvent.id.desc()).offset(skip).limit(limit).all()


def delete_article(db: Session, article_id: int):
    article = db.query(models.ArticleIdentity).filter(models.ArticleIdentity.id == article_id).first()
    if article:
        from ..evaluation.models import ArticleEvaluation
        
        # Xóa các liên kết (evaluation, details, cases) để tránh lỗi NoneType khi thống kê/đồng bộ
        db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id == article_id).delete(synchronize_session=False)
        db.query(models.ArticleDetails).filter(models.ArticleDetails.article_id == article_id).delete(synchronize_session=False)
        db.query(models.DiseaseCase).filter(models.DiseaseCase.article_id == article_id).delete(synchronize_session=False)
        
        db.delete(article)
        db.commit()
        return True
    return False

def get_event_by_id(db: Session, event_id: int):
    return db.query(models.NewsEvent).filter(models.NewsEvent.id == event_id).first()


def create_news_event(
    db: Session,
    canonical_title: str,
    disease_name: str,
    location: str | None,
    event_date: datetime,
    case_count: int,
    severity: str | None,
    fingerprint: str,
):
    event = models.NewsEvent(
        canonical_title=canonical_title,
        disease_name=disease_name,
        location=location,
        event_date=event_date,
        case_count=case_count,
        severity=severity,
        fingerprint=fingerprint,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_news_event(
    db: Session,
    event: models.NewsEvent,
    canonical_title: str | None = None,
    case_count: int | None = None,
    severity: str | None = None,
):
    db_event = db.query(models.NewsEvent).filter(models.NewsEvent.id == event.id).first()
    if not db_event:
        return event

    has_changed = False
    if canonical_title and len(canonical_title) > len(db_event.canonical_title or ""):
        db_event.canonical_title = canonical_title
        has_changed = True
    if case_count is not None and case_count > (db_event.case_count or 0):
        db_event.case_count = case_count
        has_changed = True
    if severity and not db_event.severity:
        db_event.severity = severity
        has_changed = True

    if not has_changed:
        # Avoid hitting the database if there are no real changes
        return db_event
    
    db.commit()
    db.refresh(db_event)
    return db_event

# --- Disease Cases ---

def create_disease_case(db: Session, case: models.DiseaseCase):
    db.add(case)
    db.commit()
    db.refresh(case)
    return case

def get_disease_case_by_evd(db: Session, event_id: int, report_date: datetime, location: str = None):
    # Lọc theo event thông qua bài báo và cùng ngày (không tính giờ)
    date_only = report_date.date()
    q = db.query(models.DiseaseCase).join(models.ArticleIdentity).filter(
        models.ArticleIdentity.event_id == event_id,
        models.DiseaseCase.report_date >= datetime.combine(date_only, datetime.min.time()),
        models.DiseaseCase.report_date <= datetime.combine(date_only, datetime.max.time())
    )
    if location:
        q = q.filter(models.DiseaseCase.location == location)
    return q.first()

def update_disease_case(db: Session, case_id: int, new_count: int, article_id: int):
    db_case = db.query(models.DiseaseCase).filter(models.DiseaseCase.id == case_id).first()
    if db_case:
        db_case.case_count = new_count
        db_case.article_id = article_id
        db.commit()
        db.refresh(db_case)
    return db_case


# --- Keywords ---

def get_keywords(db: Session, skip: int = 0, limit: int = 100):
    """Lấy tất cả keywords (admin quản lý, bắt kể is_active)."""
    return db.query(models.Keyword).order_by(models.Keyword.id.desc()).offset(skip).limit(limit).all()

def get_active_keywords(db: Session):
    """Lấy keyword is_active=True — dùng cho auto-scan và manual scan (keywords_to_scan=None)."""
    return db.query(models.Keyword).filter(models.Keyword.is_active == True).order_by(models.Keyword.id.desc()).all()

def toggle_keyword_active(db: Session, keyword_id: int, is_active: bool) -> models.Keyword | None:
    """Admin bật/tắt keyword khỏi auto-scan."""
    db_keyword = db.query(models.Keyword).filter(models.Keyword.id == keyword_id).first()
    if db_keyword:
        db_keyword.is_active = is_active
        db.commit()
        db.refresh(db_keyword)
    return db_keyword

def create_keyword(db: Session, keyword: schemas.KeywordCreate):
    db_keyword = models.Keyword(text=keyword.text)
    db.add(db_keyword)
    db.commit()
    db.refresh(db_keyword)
    return db_keyword

def delete_keyword(db: Session, keyword_id: int):
    db_keyword = db.query(models.Keyword).filter(models.Keyword.id == keyword_id).first()
    if db_keyword:
        db.delete(db_keyword)
        db.commit()
        return True
    return False

def update_keyword(db: Session, keyword_id: int, new_text: str):
    db_keyword = db.query(models.Keyword).filter(models.Keyword.id == keyword_id).first()
    if db_keyword:
        db_keyword.text = new_text
        db.commit()
        db.refresh(db_keyword)
        return db_keyword
    return None

def get_keyword_by_text(db: Session, text: str):
    return db.query(models.Keyword).filter(models.Keyword.text == text).first()
    
def add_keyword(db: Session, text: str):
    existing = get_keyword_by_text(db, text)
    if not existing:
        create_keyword(db, schemas.KeywordCreate(text=text))

def seed_default_keywords(db: Session):
    defaults = [
        "cúm A", "cúm B", "cúm mùa", 
        "não mô cầu", "bạch hầu", "sốt xuất huyết", 
        "covid-19", "sởi", "tay chân miệng"
    ]
    for text in defaults:
        add_keyword(db, text)


# --- RSS Sources ---

_DEFAULT_RSS_SOURCES = [
    {"url": "http://cand.com.vn/rss/suc-khoe-c-5", "label": "Công An Nhân Dân", "category": "suc-khoe"},
    {"url": "https://congan.com.vn/rss/tin-chinh", "label": "Công An TP.HCM", "category": "thoi-su"},
    {"url": "https://dantri.com.vn/rss/suc-khoe.rss", "label": "Dân Trí - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://dantri.com.vn/rss/the-gioi.rss", "label": "Dân Trí - Thế Giới", "category": "the-gioi"},
    {"url": "https://doisongphapluat.com.vn/rss/tin-tuc.rss", "label": "Đời Sống Pháp Luật", "category": "thoi-su"},
    {"url": "https://infonet.vietnamnet.vn/rss/khoe-dep.rss", "label": "Infonet - Khỏe Đẹp", "category": "suc-khoe"},
    {"url": "https://laodong.vn/rss/suc-khoe.rss", "label": "Lao Động - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://laodong.vn/rss/the-gioi.rss", "label": "Lao Động - Thế Giới", "category": "the-gioi"},
    {"url": "https://laodong.vn/rss/thoi-su.rss", "label": "Lao Động - Thời Sự", "category": "thoi-su"},
    {"url": "https://nhandan.vn/rss/the-gioi.rss", "label": "Nhân Dân - Thế Giới", "category": "the-gioi"},
    {"url": "https://nhandan.vn/rss/y-te.rss", "label": "Nhân Dân - Y Tế", "category": "suc-khoe"},
    {"url": "https://nld.com.vn/rss/suc-khoe.rss", "label": "NLĐ - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://phaply.net.vn/rss/tin-moi.rss", "label": "Pháp Lý", "category": "thoi-su"},
    {"url": "https://plo.vn/rss/home.rss", "label": "Pháp Luật TP.HCM", "category": "thoi-su"},
    {"url": "https://plo.vn/rss/suc-khoe-17.rss", "label": "PLO - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://suckhoedoisong.vn/rss", "label": "Sức Khỏe Đời Sống", "category": "suc-khoe"},
    {"url": "https://suckhoedoisong.vn/rss/suc-khoe.rss", "label": "SKĐS - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://suckhoedoisong.vn/suc-khoe-tv.rss", "label": "SKĐS TV", "category": "suc-khoe"},
    {"url": "https://suckhoedoisong.vn/thoi-su.rss", "label": "SKĐS - Thời Sự", "category": "thoi-su"},
    {"url": "https://suckhoedoisong.vn/y-hoc-360.rss", "label": "Y Học 360", "category": "suc-khoe"},
    {"url": "https://suckhoedoisong.vn/y-te.rss", "label": "SKĐS - Y Tế", "category": "suc-khoe"},
    {"url": "https://thanhnien.vn/rss/suc-khoe.rss", "label": "Thanh Niên - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://thanhnien.vn/rss/the-gioi.rss", "label": "Thanh Niên - Thế Giới", "category": "the-gioi"},
    {"url": "https://tienphong.vn/rss/home.rss", "label": "Tiền Phong", "category": "thoi-su"},
    {"url": "https://tienphong.vn/rss/suc-khoe-210.rss", "label": "Tiền Phong - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://tienphong.vn/rss/y-khoa-304.rss", "label": "Tiền Phong - Y Khoa", "category": "suc-khoe"},
    {"url": "https://tuoitre.vn/rss/suc-khoe.rss", "label": "Tuổi Trẻ - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://tuoitre.vn/rss/the-gioi.rss", "label": "Tuổi Trẻ - Thế Giới", "category": "the-gioi"},
    {"url": "https://tuoitre.vn/rss/tin-moi-nhat.rss", "label": "Tuổi Trẻ - Mới Nhất", "category": "thoi-su"},
    {"url": "https://vietnamnet.vn/rss/suc-khoe.rss", "label": "VietnamNet - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://vietnamnet.vn/rss/the-gioi.rss", "label": "VietnamNet - Thế Giới", "category": "the-gioi"},
    {"url": "https://vietnamnet.vn/rss/thoi-su.rss", "label": "VietnamNet - Thời Sự", "category": "thoi-su"},
    {"url": "https://vnanet.vn/vi/rss/suc-khoe-7.rss", "label": "Thông Tấn Xã VN - Y Tế", "category": "suc-khoe"},
    {"url": "https://vnexpress.net/rss/suc-khoe.rss", "label": "VnExpress - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://vnexpress.net/rss/the-gioi.rss", "label": "VnExpress - Thế Giới", "category": "the-gioi"},
    {"url": "https://vnexpress.net/rss/thoi-su.rss", "label": "VnExpress - Thời Sự", "category": "thoi-su"},
    {"url": "https://vov.gov.vn/Rss/RssCategoryExport?chuyendeId=27", "label": "VOV Gov - Y Tế", "category": "suc-khoe"},
    {"url": "https://vov.vn/rss/suc-khoe.rss", "label": "VOV - Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://vov.vn/rss/the-gioi.rss", "label": "VOV - Thế Giới", "category": "the-gioi"},
    {"url": "https://www.sggp.org.vn/rss/ytesuckhoe-212.rss", "label": "SGGP - Y Tế Sức Khỏe", "category": "suc-khoe"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "label": "NYTimes HomePage", "category": "global"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "label": "NYTimes World", "category": "global"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml", "label": "NYTimes Health", "category": "global"},
    {"url": "https://moxie.foxnews.com/google-publisher/health.xml", "label": "FoxNews Health", "category": "global"},
    {"url": "https://moxie.foxnews.com/google-publisher/latest.xml", "label": "FoxNews Latest", "category": "global"},
    {"url": "https://moxie.foxnews.com/google-publisher/science.xml", "label": "FoxNews Science", "category": "global"},
    {"url": "https://www.cidrap.umn.edu/news/49/rss", "label": "CIDRAP News 49", "category": "global"},
    {"url": "https://www.cidrap.umn.edu/news/232663/rss", "label": "CIDRAP News 232663", "category": "global"},
    {"url": "https://www.cidrap.umn.edu/news/all/rss", "label": "CIDRAP All News", "category": "global"},
    {"url": "https://moxie.foxnews.com/google-publisher/videos.xml", "label": "FoxNews Videos", "category": "global"},
    {"url": "https://www.who.int/rss-feeds/news-english.xml", "label": "WHO News", "category": "global"},
    {"url": "https://www.afro.who.int/rss/emergencies.xml", "label": "WHO AFRO Emergencies", "category": "global"},
    {"url": "https://www.afro.who.int/rss/featured-news.xml", "label": "WHO AFRO News", "category": "global"},
]

def get_active_rss_sources(db: Session):
    return db.query(models.RssSource).filter(models.RssSource.is_active == True).all()

def get_all_rss_sources(db: Session):
    return db.query(models.RssSource).order_by(models.RssSource.category, models.RssSource.label).all()

def seed_default_rss_sources(db: Session):
    """Seed danh sách RSS mặc định vào DB nếu bảng còn trống."""
    if db.query(models.RssSource).count() > 0:
        return  # Đã có dữ liệu, không cần seed lại
    for item in _DEFAULT_RSS_SOURCES:
        url = item["url"].lower()
        default_type = "INTERNATIONAL" if "nytimes" in url or "foxnews" in url or "cidrap" in url or "who" in url else "DOMESTIC"
        
        db_src = models.RssSource(
            url=item["url"],
            label=item.get("label"),
            category=item.get("category"),
            source_type=item.get("source_type", default_type),
            is_active=True,
        )
        db.add(db_src)
    db.commit()

def create_rss_source(db: Session, source: schemas.RssSourceCreate):
    db_src = models.RssSource(
        url=source.url,
        label=source.label,
        category=source.category,
        source_type=source.source_type,
        is_active=source.is_active,
    )
    db.add(db_src)
    db.commit()
    db.refresh(db_src)
    return db_src

def get_rss_source_by_url(db: Session, url: str):
    return db.query(models.RssSource).filter(models.RssSource.url == url).first()

def delete_rss_source(db: Session, source_id: int) -> bool:
    source = db.query(models.RssSource).filter(models.RssSource.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
        return True
    return False

def toggle_rss_source_active(db: Session, source_id: int, is_active: bool):
    """Bật/tắt mềm nguồn RSS (soft toggle) — không xóa khỏi DB."""
    source = db.query(models.RssSource).filter(models.RssSource.id == source_id).first()
    if not source:
        return None
    source.is_active = is_active
    db.commit()
    db.refresh(source)
    return source

def update_rss_source(db: Session, source_id: int, update_data: schemas.RssSourceUpdate):
    db_source = db.query(models.RssSource).filter(models.RssSource.id == source_id).first()
    if not db_source:
        return None
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(db_source, key, value)
    db.commit()
    db.refresh(db_source)
    return db_source
