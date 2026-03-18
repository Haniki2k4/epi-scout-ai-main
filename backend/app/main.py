from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import re
from .core import database
from .core.database import get_db
from .modules.news import crawler, crud, models, schemas, stats

app = FastAPI()

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
    # Trigger scan logic
    return crawler.scan_news(db, request.fetch_unknown)

@app.get("/api/articles", response_model=List[schemas.ArticleDTO])
def read_articles(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    articles = crud.get_articles(db, skip=skip, limit=limit)
    return articles

@app.post("/api/articles/save", response_model=schemas.ArticleDTO)
def save_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
    # Check if exists
    existing = crud.get_article_by_link(db, article.link)
    if existing:
        raise HTTPException(status_code=400, detail="Article already saved")
    return crud.create_article(db, article)

# --- Stats ---

@app.get("/api/stats/overview")
def get_stats_overview(db: Session = Depends(get_db)):
    return stats.get_overview_stats(db)

@app.get("/api/stats/trends")
def get_stats_trends(days: int = 7, db: Session = Depends(get_db)):
    return stats.get_trend_data(db, days)

# --- Resources ---

@app.get("/api/keywords", response_model=List[schemas.KeywordDTO])
def read_keywords(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_keywords(db, skip=skip, limit=limit)

@app.post("/api/keywords", response_model=schemas.KeywordDTO | List[schemas.KeywordDTO])
def create_keyword(keyword: schemas.KeywordCreate, db: Session = Depends(get_db)):
    keywords = parse_keywords_input(keyword.text)
    if not keywords:
        raise HTTPException(status_code=400, detail="Keyword is required")

    too_long = [item for item in keywords if len(item) > KEYWORD_MAX_LENGTH]
    if too_long:
        raise HTTPException(
            status_code=400,
            detail=f"Keyword exceeds {KEYWORD_MAX_LENGTH} characters: {too_long[0][:60]}",
        )

    created_keywords = []
    for item in keywords:
        existing = crud.get_keyword_by_text(db, item)
        if existing:
            continue
        created_keywords.append(crud.create_keyword(db, schemas.KeywordCreate(text=item)))

    if not created_keywords:
        raise HTTPException(status_code=400, detail="Keyword already exists")

    return created_keywords[0] if len(created_keywords) == 1 else created_keywords

@app.delete("/api/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    success = crud.delete_keyword(db, keyword_id)
    if not success:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"status": "success", "id": keyword_id}

@app.get("/api/whitelist", response_model=List[schemas.WhitelistDTO])
def read_whitelist(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_whitelisted_domains(db, skip=skip, limit=limit)

@app.post("/api/whitelist", response_model=schemas.WhitelistDTO)
def create_whitelist(domain: schemas.WhitelistCreate, db: Session = Depends(get_db)):
    existing = crud.get_whitelist_by_name(db, domain.domain)
    if existing:
        raise HTTPException(status_code=400, detail="Domain already whitelisted")
    return crud.create_whitelist_domain(db, domain)
