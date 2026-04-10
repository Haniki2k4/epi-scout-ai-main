from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import re
from .core import database
from .core.database import get_db, Base, engine
from .core.logger import get_logger
from .modules.news import crawler, crud, models, schemas, stats
from .modules.auth import router as auth_router, security
from .modules.admin import router_users as admin_users_router

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
            crud.seed_default_keywords(db)
            crud.seed_default_rss_sources(db)
            logger.info("Backend startup complete, default keywords and RSS sources seeded")
        finally:
            db.close()
    crawler.log_llm_preflight_status(force_refresh=True)

app.include_router(auth_router.router)
app.include_router(admin_users_router.router)

# CORS configuration
origins = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

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
    logger.info("Scan requested | fetch_unknown={} start_date={} end_date={} keywords_count={}",
                request.fetch_unknown, request.start_date, request.end_date,
                len(request.keywords_to_scan) if request.keywords_to_scan is not None else "all")
    result = crawler.scan_news(
        db,
        request.fetch_unknown,
        request.start_date,
        request.end_date,
        keywords_to_scan=request.keywords_to_scan,
    )
    logger.info(
        "Scan completed | saved_trusted_count={} unknown_articles={}",
        result.saved_trusted_count,
        len(result.unknown_articles),
    )
    return result

@app.get("/api/articles", response_model=List[schemas.ArticleDTO])
def read_articles(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    logger.info("Read articles requested | skip={} limit={}", skip, limit)
    articles = crud.get_articles(db, skip=skip, limit=limit)
    logger.info("Read articles completed | count={}", len(articles))
    return articles

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
        inferred_event, event_match_score, dedupe_reason = crawler.resolve_event_for_article(
            db=db,
            title=article.title,
            matched_keywords=matched_keywords,
            pub_date=article.published_date or datetime.utcnow(),
            location="Việt Nam",
            case_count=crawler.extract_case_count(
                f"{article.title} {article.summary or ''}",
                [kw.strip() for kw in matched_keywords.split(",") if kw.strip()],
            ),
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
def get_top_diseases(months: int = 1, db: Session = Depends(get_db)):
    months = max(1, min(months, 12))
    logger.info("Top diseases requested | months={}", months)
    result = stats.disease_mention_counts(db, months)
    top10 = result[:10]
    logger.info("Top diseases completed | count={} months={}", len(top10), months)
    return top10

@app.get("/api/stats/heatmap")
def get_heatmap(days: int = 30, month: int = None, year: int = None, db: Session = Depends(get_db)):
    logger.info("Location heatmap requested | days={} month={} year={}", days, month, year)
    result = stats.get_location_heatmap_data(db, days=days, month=month, year=year)
    logger.info("Location heatmap completed | locations={}", len(result))
    return result

@app.get("/api/stats/bow")
def get_bow(days: int = 30, db: Session = Depends(get_db)):
    logger.info("BoW requested | days={}", days)
    result = stats.get_bow_data(db, days)
    logger.info("BoW completed | items={}", len(result))
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
def read_keywords(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read keywords requested | skip={} limit={}", skip, limit)
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


@app.get("/api/events", response_model=List[schemas.NewsEventDTO])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read events requested | skip={} limit={}", skip, limit)
    events = crud.get_events(db, skip=skip, limit=limit)
    logger.info("Read events completed | count={}", len(events))
    return events


@app.get("/api/events/{event_id}", response_model=schemas.NewsEventDetailDTO)
def read_event_detail(event_id: int, db: Session = Depends(get_db)):
    logger.info("Read event detail requested | event_id={}", event_id)
    event = crud.get_event_by_id(db, event_id)
    if not event:
        logger.warning("Read event detail failed | event_id={} reason=not_found", event_id)
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info("Read event detail completed | event_id={} article_count={}", event_id, len(event.articles))
    return event


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
