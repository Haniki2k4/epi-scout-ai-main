from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import re
import os
from .core import database
from .core.database import get_db, Base, engine
from .core.logger import get_logger
from .modules.news import crawler, crud, models, schemas, stats
from .modules.auth import router as auth_router, security
from .modules.auth import router_alerts as alerts_router
from .modules.admin import router_users as admin_users_router
from .modules.admin import router_scheduler as admin_scheduler_router
from .modules.report import router as report_router
from .modules.report import router_ai_summary
from .modules.admin import router_llm_status
from .modules.evaluation import router as evaluation_router
from . import scheduler as app_scheduler

app = FastAPI(description="Hệ thống quét và tự động phân tích tin tức dịch tễ.")
logger = get_logger("backend.main")

KEYWORD_MAX_LENGTH = 255


def parse_keywords_input(text: str) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    has_separator = "," in normalized or "\n" in normalized
    raw_keywords = re.split(r"[\n,]", normalized) if has_separator else [normalized]

    seen: set[str] = set()
    keywords: list[str] = []
    for raw_keyword in raw_keywords:
        keyword = raw_keyword.strip()
        keyword_key = keyword.lower()
        if keyword and keyword_key not in seen:
            seen.add(keyword_key)
            keywords.append(keyword)

    return keywords


@app.on_event("startup")
def init_database() -> None:
    with database.SessionLocal() as db:
        try:
            # Migration data: Đồng bộ is_excluded cho các bài viết đã bị đánh nhãn
            from sqlalchemy import text
            db.execute(text("UPDATE article_identity SET is_excluded = 1 WHERE id IN (SELECT article_id FROM article_evaluation WHERE human_label IN ('noise', 'irrelevant', 'unsure'))"))
            db.execute(text("UPDATE article_identity SET is_excluded = 0 WHERE id IN (SELECT article_id FROM article_evaluation WHERE human_label = 'relevant')"))
            db.commit()
            
            crud.seed_default_keywords(db)
            crud.seed_default_rss_sources(db)
            logger.info("Backend startup complete, default keywords and RSS sources seeded")
        finally:
            db.close()
    crawler.log_llm_preflight_status(force_refresh=True)
    # Khởi động APScheduler
    app_scheduler.start_scheduler()
    # Tự động tạo AI summary khi server start
    app_scheduler.trigger_ai_summary()


@app.on_event("shutdown")
def shutdown_scheduler() -> None:
    app_scheduler.stop_scheduler()


app.include_router(auth_router.router)
app.include_router(alerts_router.router)
app.include_router(admin_users_router.router)
app.include_router(admin_scheduler_router.router)
app.include_router(router_llm_status.router)
app.include_router(report_router.router)
app.include_router(router_ai_summary.router)
app.include_router(evaluation_router.router)

# CORS configuration
# Đọc từ env CORS_ORIGINS (dạng comma-separated), fallback về localhost khi dev
_cors_env = os.environ.get("CORS_ORIGINS", "")
_default_origins = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Scan & Articles ---

@app.post("/api/scan", response_model=schemas.ScanResult)
def scan_news(
    request: schemas.ScanRequest, 
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user)
):
    logger.info("Scan requested | start_date={} end_date={} keywords_count={}",
                request.start_date, request.end_date,
                len(request.keywords_to_scan) if request.keywords_to_scan is not None else "all")
    result = crawler.scan_news(
        db,
        request.start_date,
        request.end_date,
        keywords_to_scan=request.keywords_to_scan,
    )
    logger.info(
        "Scan completed | saved_trusted_count={}",
        result.saved_trusted_count,
    )
    return result

@app.get("/api/scan-status")
def get_scan_status(
    db: Session = Depends(get_db)
):
    """Lấy trạng thái scan hiện tại cho tất cả người dùng (hiển thị banner)."""
    from . import scheduler as app_scheduler
    config = app_scheduler._get_or_create_config(db)
    sched = app_scheduler.get_scheduler()
    return {
        "scheduler_running": sched.running,
        "is_scanning": getattr(crawler, "is_scanning_flag", False), # Ta sẽ thêm cờ is_scanning vào crawler
        "last_run_at": config.last_run_at,
        "last_run_saved_count": config.last_run_saved_count,
        "next_run_at": config.next_run_at,
    }

@app.get("/api/articles", response_model=schemas.PaginatedArticles)
def read_articles(
    skip: int = 0, 
    limit: int = 100, 
    keyword: str | None = None,
    date: str | None = None,
    include_excluded: bool = False,
    include_label: bool = False,
    db: Session = Depends(get_db)
):
    logger.info("Read articles requested | skip={} limit={} keyword={} date={} include_excluded={} include_label={}", skip, limit, keyword, date, include_excluded, include_label)
    articles = crud.get_articles(db, skip=skip, limit=limit, keyword=keyword, date=date, include_excluded=include_excluded)
    total = crud.count_articles(db, keyword=keyword, date=date, include_excluded=include_excluded)

    # Gắn nhãn evaluation nếu được yêu cầu
    if include_label:
        from .modules.evaluation.models import ArticleEvaluation
        article_ids = [a.id for a in articles]
        evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
        eval_map = {e.article_id: e for e in evals}
        for a in articles:
            e = eval_map.get(a.id)
            if e:
                a.llm_label = e.llm_label
                a.human_label = e.human_label

    logger.info("Read articles completed | count={} total={}", len(articles), total)
    return {
        "items": articles,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/api/page-data", response_model=schemas.PageDataResponse)
def get_page_data(
    skip: int = 0,
    limit: int = 20,
    keyword: str | None = None,
    date: str | None = None,
    include_excluded: bool = False,
    include_label: bool = False,
    events_limit: int = 20,
    db: Session = Depends(get_db),
):
    """Endpoint gộp: articles + events + keywords + scan_status — 1 request thay vì 4-5."""
    logger.info("Page data requested | skip={} limit={} keyword={} events_limit={}", skip, limit, keyword, events_limit)

    # 1. Articles (reuse logic from read_articles)
    articles_list = crud.get_articles(db, skip=skip, limit=limit, keyword=keyword, date=date, include_excluded=include_excluded)
    total = crud.count_articles(db, keyword=keyword, date=date, include_excluded=include_excluded)

    if include_label:
        from .modules.evaluation.models import ArticleEvaluation
        article_ids = [a.id for a in articles_list]
        if article_ids:
            evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
            eval_map = {e.article_id: e for e in evals}
            for a in articles_list:
                e = eval_map.get(a.id)
                if e:
                    a.llm_label = e.llm_label
                    a.human_label = e.human_label

    # 2. Events
    events_list = crud.get_events(db, skip=0, limit=events_limit)

    # 3. Keywords (active only)
    keywords_list = crud.get_active_keywords(db)

    # 4. Scan status
    from . import scheduler as app_scheduler
    config = app_scheduler._get_or_create_config(db)
    sched = app_scheduler.get_scheduler()
    scan_status = {
        "scheduler_running": sched.running,
        "is_scanning": getattr(crawler, "is_scanning_flag", False),
        "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
        "last_run_saved_count": config.last_run_saved_count,
        "next_run_at": config.next_run_at.isoformat() if config.next_run_at else None,
    }

    logger.info("Page data completed | articles={} events={} keywords={}", len(articles_list), len(events_list), len(keywords_list))
    return {
        "articles": {
            "items": articles_list,
            "total": total,
            "skip": skip,
            "limit": limit,
        },
        "events": events_list,
        "keywords": keywords_list,
        "scan_status": scan_status,
    }

@app.get("/api/articles/new-count")
def get_new_articles_count(hours: int = 24, db: Session = Depends(get_db)):
    """Đếm số bài báo mới được thu thập trong N giờ gần nhất (public, không cần auth)."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    count = db.query(models.ArticleIdentity).filter(
        models.ArticleIdentity.published_date >= since
    ).count()
    return {"count": count, "hours": hours}

@app.post("/api/articles/save", response_model=schemas.ArticleDTO)
def save_article(
    article: schemas.ArticleCreate, 
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user)
):
    logger.info("Save article requested | link={} title={}", article.link, article.title)
    existing = crud.get_article_by_link(db, article.link)
    if existing:
        logger.warning("Save article rejected, already exists | link={}", article.link)
        raise HTTPException(status_code=400, detail="Article already saved")
    matched_keywords = article.keywords_matched or ""
    if matched_keywords:
        cases = crawler.extract_case_count(
            f"{article.title} {article.summary or ''}",
            [kw.strip() for kw in matched_keywords.split(",") if kw.strip()],
        )
        inferred_event, event_match_score, dedupe_reason, _ = crawler.resolve_event_for_article(
            db=db,
            title=article.title,
            summary=article.summary or "",
            matched_keywords=matched_keywords,
            pub_date=article.published_date or datetime.utcnow(),
            location="Việt Nam",
            cumulative_cases=cases,
            new_cases=0,
            severity=None,
        )
        article.event_id = inferred_event.id if inferred_event else None
        article.event_match_score = event_match_score
        article.dedupe_reason = dedupe_reason
    saved_article = crud.create_article(db, article)
    logger.info("Article saved | id={} link={}", saved_article.id, article.link)
    return saved_article

@app.delete("/api/articles/{article_id}")
def delete_article_api(
    article_id: int, 
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Delete article requested | article_id={}", article_id)
    success = crud.delete_article(db, article_id)
    if not success:
        logger.warning("Delete article failed | article_id={} reason=not_found", article_id)
        raise HTTPException(status_code=404, detail="Article not found")
    logger.info("Delete article completed | article_id={}", article_id)
    return {"status": "success", "id": article_id}

# --- Bookmarks ---

@app.post("/api/bookmarks/{article_id}")
def add_bookmark(
    article_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user)
):
    from .modules.auth.models import UserBookmark
    article = db.query(models.ArticleIdentity).filter(models.ArticleIdentity.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
        
    existing = db.query(UserBookmark).filter(
        UserBookmark.user_id == current_user.id,
        UserBookmark.article_id == article_id
    ).first()
    if existing:
        return {"status": "success", "message": "Already bookmarked"}
        
    bookmark = UserBookmark(user_id=current_user.id, article_id=article_id)
    db.add(bookmark)
    db.commit()
    return {"status": "success", "message": "Bookmarked"}

@app.delete("/api/bookmarks/{article_id}")
def remove_bookmark(
    article_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user)
):
    from .modules.auth.models import UserBookmark
    bookmark = db.query(UserBookmark).filter(
        UserBookmark.user_id == current_user.id,
        UserBookmark.article_id == article_id
    ).first()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")
        
    db.delete(bookmark)
    db.commit()
    return {"status": "success"}

@app.get("/api/bookmarks", response_model=List[schemas.ArticleDTO])
def get_bookmarks(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user)
):
    from sqlalchemy.orm import joinedload
    from .modules.auth.models import UserBookmark
    bookmarks = db.query(UserBookmark).filter(UserBookmark.user_id == current_user.id).order_by(UserBookmark.created_at.desc()).offset(skip).limit(limit).all()
    article_ids = [b.article_id for b in bookmarks]
    if not article_ids:
        return []
        
    # Lấy articles theo ID và giữ nguyên thứ tự
    articles = db.query(models.ArticleIdentity).options(joinedload(models.ArticleIdentity.cases)).filter(models.ArticleIdentity.id.in_(article_ids)).all()
    article_map = {a.id: a for a in articles}
    return [article_map[aid] for aid in article_ids if aid in article_map]


# --- Stats ---

@app.get("/api/stats/overview")
def get_stats_overview(db: Session = Depends(get_db)):
    logger.info("Stats overview requested")
    result = stats.get_overview_stats(db)
    logger.info("Stats overview completed | total_articles={}", result.get("total_articles"))
    return result

@app.get("/api/stats/trends")
def get_stats_trends(days: int = 7, db: Session = Depends(get_db)):
    logger.info("Stats trends requested | days={}", days)
    result = stats.get_trend_data(db, days)
    logger.info("Stats trends completed | points={}", len(result))
    return result

@app.get("/api/stats/top-diseases")
def get_top_diseases(months: int = 1, days: int = None, db: Session = Depends(get_db)):
    if days is not None:
        logger.info("Top diseases requested | days={}", days)
        result = stats.disease_mention_counts(db, days=days)
    else:
        months = max(1, min(months, 12))
        logger.info("Top diseases requested | months={}", months)
        result = stats.disease_mention_counts(db, months=months)
    top10 = result[:10]
    logger.info("Top diseases completed | count={}", len(top10))
    return top10

@app.get("/api/stats/heatmap")
def get_heatmap(days: int = 30, month: int = None, year: int = None, db: Session = Depends(get_db)):
    logger.info("Location heatmap requested | days={} month={} year={}", days, month, year)
    result = stats.get_location_heatmap_data(db, days=days, month=month, year=year)
    logger.info("Location heatmap completed | locations={}", len(result))
    return result

@app.get("/api/stats/interest-trends")
def get_interest_trends_api(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Interest trends requested | days={}", days)
    result = stats.get_interest_trends(db, days)
    logger.info("Interest trends completed")
    return result

@app.get("/api/stats/stacked-trends")
def get_stacked_trends(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Stacked trends requested | days={}", days)
    result = stats.get_stacked_trend_data(db, days)
    logger.info("Stacked trends completed")
    return result

@app.get("/api/stats/zscore")
def get_zscore(disease: str = None, window: int = 14, days: int = 60, db: Session = Depends(get_db)):
    logger.info("Z-score spikes requested | disease={} window={} days={}", disease, window, days)
    result = stats.get_zscore_spikes(db, disease_name=disease, window=window, days=days)
    logger.info("Z-score spikes completed | items={}", len(result))
    return result

@app.get("/api/stats/keyword-timeseries")
def get_keyword_timeseries(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Keyword timeseries requested | days={}", days)
    result = stats.get_keyword_timeseries(db, days)
    logger.info("Keyword timeseries completed")
    return result

@app.get("/api/stats/keyword-zscore")
def get_keyword_zscore(window: int = 14, days: int = 60, db: Session = Depends(get_db)):
    logger.info("Keyword Z-score spikes requested | window={} days={}", window, days)
    result = stats.get_keyword_zscore_spikes(db, window=window, days=days)
    logger.info("Keyword Z-score spikes completed | items={}", len(result))
    return result

@app.get("/api/stats/keyword-bubble")
def get_keyword_bubble(days: int = 30, window: int = 14, db: Session = Depends(get_db)):
    logger.info("Keyword bubble requested | days={} window={}", days, window)
    result = stats.get_keyword_bubble_data(db, days=days, window=window)
    logger.info("Keyword bubble completed | items={}", len(result))
    return result

@app.get("/api/stats/forecast")
def get_forecast(disease: str = None, horizon: int = 7, db: Session = Depends(get_db)):
    logger.info("Prophet forecast requested | disease={} horizon={}", disease, horizon)
    result = stats.get_prophet_forecast(db, disease_name=disease, horizon_days=horizon)
    logger.info("Prophet forecast completed")
    return result

# --- Resources ---

@app.get("/api/rss-sources", response_model=List[schemas.RssSourceDTO])
def read_rss_sources(db: Session = Depends(get_db)):
    logger.info("Read RSS sources requested")
    sources = crud.get_all_rss_sources(db)
    logger.info("Read RSS sources completed | count={}", len(sources))
    return sources

@app.get("/api/keywords", response_model=List[schemas.KeywordDTO])
def read_keywords(
    skip: int = 0, 
    limit: int = 100, 
    only_active: bool = True,
    db: Session = Depends(get_db)
):
    logger.info("Read keywords requested | skip={} limit={} only_active={}", skip, limit, only_active)
    if only_active:
        keywords = crud.get_active_keywords(db)
    else:
        keywords = crud.get_keywords(db, skip=skip, limit=limit)
    logger.info("Read keywords completed | count={}", len(keywords))
    return keywords

@app.post("/api/keywords", response_model=schemas.KeywordDTO | List[schemas.KeywordDTO])
def create_keyword(
    keyword: schemas.KeywordCreate, 
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Create keyword requested | raw_text={}", keyword.text)
    keywords = parse_keywords_input(keyword.text)
    if not keywords:
        logger.warning("Create keyword rejected | reason=empty_input")
        raise HTTPException(status_code=400, detail="Keyword is required")

    too_long = [item for item in keywords if len(item) > KEYWORD_MAX_LENGTH]
    if too_long:
        logger.warning("Create keyword rejected | reason=keyword_too_long keyword={}", too_long[0][:60])
        raise HTTPException(
            status_code=400,
            detail=f"Keyword exceeds {KEYWORD_MAX_LENGTH} characters: {too_long[0][:60]}",
        )

    created_keywords = []
    for item in keywords:
        existing = crud.get_keyword_by_text(db, item)
        if existing:
            logger.info("Create keyword skipped | reason=already_exists keyword={}", item)
            continue
        created_keywords.append(crud.create_keyword(db, schemas.KeywordCreate(text=item)))

    if not created_keywords:
        logger.warning("Create keyword rejected | reason=all_keywords_exist")
        raise HTTPException(status_code=400, detail="Keyword already exists")

    logger.info("Create keyword completed | created_count={}", len(created_keywords))
    return created_keywords[0] if len(created_keywords) == 1 else created_keywords

@app.delete("/api/keywords/{keyword_id}")
def delete_keyword(
    keyword_id: int, 
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Delete keyword requested | keyword_id={}", keyword_id)
    success = crud.delete_keyword(db, keyword_id)
    if not success:
        logger.warning("Delete keyword failed | keyword_id={} reason=not_found", keyword_id)
        raise HTTPException(status_code=404, detail="Keyword not found")
    logger.info("Delete keyword completed | keyword_id={}", keyword_id)
    return {"status": "success", "id": keyword_id}

@app.put("/api/keywords/{keyword_id}", response_model=schemas.KeywordDTO)
def update_keyword_api(
    keyword_id: int, 
    keyword: schemas.KeywordCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Update keyword requested | keyword_id={} text={}", keyword_id, keyword.text)
    
    if len(keyword.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Vui lòng nhập từ khóa")
        
    if len(keyword.text) > KEYWORD_MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"Từ khóa vượt quá {KEYWORD_MAX_LENGTH} ký tự")
        
    updated = crud.update_keyword(db, keyword_id, keyword.text.strip())
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy từ khóa")
        
    logger.info("Update keyword completed | keyword_id={}", keyword_id)
    return updated

@app.patch("/api/keywords/{keyword_id}/toggle", response_model=schemas.KeywordDTO)
def toggle_keyword_active_api(
    keyword_id: int,
    body: schemas.RssSourceToggleRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Toggle keyword requested | keyword_id={} is_active={}", keyword_id, body.is_active)
    db_keyword = crud.toggle_keyword_active(db, keyword_id, body.is_active)
    if not db_keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return db_keyword


@app.get("/api/events", response_model=List[schemas.NewsEventDTO])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read events requested | skip={} limit={}", skip, limit)
    events = crud.get_events(db, skip=skip, limit=limit)
    for ev in events:
        if not ev.severity:
            ev.severity = crud.compute_event_severity(ev)
    logger.info("Read events completed | count={}", len(events))
    return events


@app.get("/api/events/{event_id}", response_model=schemas.NewsEventDetailDTO)
def read_event_detail(event_id: int, db: Session = Depends(get_db)):
    logger.info("Read event detail requested | event_id={}", event_id)
    event = crud.get_event_by_id(db, event_id)
    if not event:
        logger.warning("Read event detail failed | event_id={} reason=not_found", event_id)
        raise HTTPException(status_code=404, detail="Event not found")
        
    severity = event.severity or crud.compute_event_severity(event)
    
    # Load evaluation cho event articles
    from .modules.evaluation.models import ArticleEvaluation
    article_ids = [a.id for a in event.articles]
    evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all() if article_ids else []
    eval_map = {e.article_id: e for e in evals}
    
    valid_articles = []
    for a in event.articles:
        if getattr(a, "is_excluded", False):
            continue
            
        e = eval_map.get(a.id)
        hl = e.human_label if e else None
        llm = e.llm_label if e else ("relevant" if a.event_id else "irrelevant")
        
        # Lọc các bài báo không phù hợp
        if (hl in ["noise", "irrelevant", "unsure"]) or (not hl and llm in ["noise", "irrelevant", "unsure"]):
            continue
            
        a.human_label = hl
        a.llm_label = llm
        valid_articles.append(a)
    
    logger.info("Read event detail completed | event_id={} valid_article_count={}", event_id, len(valid_articles))
    
    return {
        "id": event.id,
        "canonical_title": event.canonical_title,
        "disease_name": event.disease_name,
        "location": event.location,
        "event_date": event.event_date,
        "case_count": event.case_count,
        "severity": severity,
        "status": event.status,
        "fingerprint": event.fingerprint,
        "article_count": len(valid_articles),
        "source_count": len(set(a.source for a in valid_articles if a.source)),
        "sources_preview": sorted(list(set(a.source for a in valid_articles if a.source)))[:5],
        "articles": valid_articles,
    }


@app.get("/api/rss-sources", response_model=List[schemas.RssSourceDTO])
def read_rss_sources(db: Session = Depends(get_db)):
    logger.info("Read RSS sources requested")
    sources = crud.get_all_rss_sources(db)
    logger.info("Read RSS sources completed | count={}", len(sources))
    return sources

@app.post("/api/rss-sources", response_model=schemas.RssSourceDTO, status_code=201)
def create_rss_source(
    source: schemas.RssSourceCreate, 
    response: Response, 
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Create RSS source requested | url={}", source.url)
    existing = crud.get_rss_source_by_url(db, source.url)
    if existing:
        logger.info("Create RSS source skipped | url={} reason=already_exists", source.url)
        response.status_code = 200
        return existing
    created = crud.create_rss_source(db, source)
    logger.info("Create RSS source completed | id={} url={}", created.id, created.url)
    return created

@app.delete("/api/rss-sources/{source_id}")
def delete_rss_source_api(
    source_id: int, 
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Delete RSS source requested | source_id={}", source_id)
    success = crud.delete_rss_source(db, source_id)
    if not success:
        logger.warning("Delete RSS source failed | source_id={} reason=not_found", source_id)
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Delete RSS source completed | source_id={}", source_id)
    return {"status": "success", "id": source_id}

@app.patch("/api/rss-sources/{source_id}/toggle", response_model=schemas.RssSourceDTO)
def toggle_rss_source_api(
    source_id: int,
    body: schemas.RssSourceToggleRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Toggle RSS source | source_id={} is_active={}", source_id, body.is_active)
    updated = crud.toggle_rss_source_active(db, source_id, body.is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Toggle RSS source completed | source_id={} is_active={}", source_id, updated.is_active)
    return updated

@app.put("/api/rss-sources/{source_id}", response_model=schemas.RssSourceDTO)
def update_rss_source_api(
    source_id: int,
    body: schemas.RssSourceUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role)
):
    logger.info("Update RSS source | source_id={}", source_id)
    updated = crud.update_rss_source(db, source_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Update RSS source completed | source_id={}", source_id)
    return updated
