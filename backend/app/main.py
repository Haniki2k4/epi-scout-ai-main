from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import re
from .core import database
from .core.database import get_db
from .core.logger import get_logger
from .modules.news import crawler, crud, models, schemas, stats

app = FastAPI()
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
    models.Base.metadata.create_all(bind=database.engine)
    models.ensure_news_schema(database.engine)
    logger.info("Backend startup complete, database metadata ensured")
    crawler.log_llm_preflight_status(force_refresh=True)

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
def scan_news(request: schemas.ScanRequest, db: Session = Depends(get_db)):
    logger.info("Scan requested | fetch_unknown={}", request.fetch_unknown)
    result = crawler.scan_news(db, request.fetch_unknown)
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
def save_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
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

# --- Resources ---

@app.get("/api/keywords", response_model=List[schemas.KeywordDTO])
def read_keywords(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read keywords requested | skip={} limit={}", skip, limit)
    keywords = crud.get_keywords(db, skip=skip, limit=limit)
    logger.info("Read keywords completed | count={}", len(keywords))
    return keywords

@app.post("/api/keywords", response_model=schemas.KeywordDTO | List[schemas.KeywordDTO])
def create_keyword(keyword: schemas.KeywordCreate, db: Session = Depends(get_db)):
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
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    logger.info("Delete keyword requested | keyword_id={}", keyword_id)
    success = crud.delete_keyword(db, keyword_id)
    if not success:
        logger.warning("Delete keyword failed | keyword_id={} reason=not_found", keyword_id)
        raise HTTPException(status_code=404, detail="Keyword not found")
    logger.info("Delete keyword completed | keyword_id={}", keyword_id)
    return {"status": "success", "id": keyword_id}

@app.get("/api/whitelist", response_model=List[schemas.WhitelistDTO])
def read_whitelist(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read whitelist requested | skip={} limit={}", skip, limit)
    domains = crud.get_whitelisted_domains(db, skip=skip, limit=limit)
    logger.info("Read whitelist completed | count={}", len(domains))
    return domains


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

@app.post("/api/whitelist", response_model=schemas.WhitelistDTO, status_code=201)
def create_whitelist(domain: schemas.WhitelistCreate, response: Response, db: Session = Depends(get_db)):
    logger.info("Create whitelist requested | domain={}", domain.domain)
    existing = crud.get_whitelist_by_name(db, domain.domain)
    if existing:
        logger.info("Create whitelist skipped | domain={} reason=already_exists", domain.domain)
        response.status_code = 200
        return existing
    created_domain = crud.create_whitelist_domain(db, domain)
    logger.info("Create whitelist completed | id={} domain={}", created_domain.id, created_domain.domain)
    return created_domain
