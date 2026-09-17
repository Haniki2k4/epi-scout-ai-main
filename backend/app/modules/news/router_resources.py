"""
Router: Keywords & RSS Sources — tách từ app/main.py (Issue #12).
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ...core.logger import get_logger
from ..auth import security
from . import crud, schemas

logger = get_logger("backend.router.resources")
router = APIRouter(prefix="/api", tags=["resources"])

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


# --- Keywords ---

@router.get("/keywords", response_model=List[schemas.KeywordDTO])
def read_keywords(
    skip: int = 0,
    limit: int = 100,
    only_active: bool = True,
    db: Session = Depends(get_db),
):
    logger.info("Read keywords requested | skip={} limit={} only_active={}", skip, limit, only_active)
    if only_active:
        keywords = crud.get_active_keywords(db)
    else:
        keywords = crud.get_keywords(db, skip=skip, limit=limit)
    logger.info("Read keywords completed | count={}", len(keywords))
    return keywords


@router.post("/keywords", response_model=schemas.KeywordDTO | List[schemas.KeywordDTO])
def create_keyword(
    keyword: schemas.KeywordCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
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


@router.delete("/keywords/{keyword_id}")
def delete_keyword(
    keyword_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Delete keyword requested | keyword_id={}", keyword_id)
    success = crud.delete_keyword(db, keyword_id)
    if not success:
        logger.warning("Delete keyword failed | keyword_id={} reason=not_found", keyword_id)
        raise HTTPException(status_code=404, detail="Keyword not found")
    logger.info("Delete keyword completed | keyword_id={}", keyword_id)
    return {"status": "success", "id": keyword_id}


@router.put("/keywords/{keyword_id}", response_model=schemas.KeywordDTO)
def update_keyword_api(
    keyword_id: int,
    keyword: schemas.KeywordCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
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


@router.patch("/keywords/{keyword_id}/toggle", response_model=schemas.KeywordDTO)
def toggle_keyword_active_api(
    keyword_id: int,
    body: schemas.RssSourceToggleRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Toggle keyword requested | keyword_id={} is_active={}", keyword_id, body.is_active)
    db_keyword = crud.toggle_keyword_active(db, keyword_id, body.is_active)
    if not db_keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return db_keyword


# --- RSS Sources ---

@router.get("/rss-sources", response_model=List[schemas.RssSourceDTO])
def read_rss_sources(db: Session = Depends(get_db)):
    logger.info("Read RSS sources requested")
    sources = crud.get_all_rss_sources(db)
    logger.info("Read RSS sources completed | count={}", len(sources))
    return sources


@router.post("/rss-sources", response_model=schemas.RssSourceDTO, status_code=201)
def create_rss_source(
    source: schemas.RssSourceCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
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


@router.delete("/rss-sources/{source_id}")
def delete_rss_source_api(
    source_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Delete RSS source requested | source_id={}", source_id)
    success = crud.delete_rss_source(db, source_id)
    if not success:
        logger.warning("Delete RSS source failed | source_id={} reason=not_found", source_id)
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Delete RSS source completed | source_id={}", source_id)
    return {"status": "success", "id": source_id}


@router.patch("/rss-sources/{source_id}/toggle", response_model=schemas.RssSourceDTO)
def toggle_rss_source_api(
    source_id: int,
    body: schemas.RssSourceToggleRequest,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Toggle RSS source | source_id={} is_active={}", source_id, body.is_active)
    updated = crud.toggle_rss_source_active(db, source_id, body.is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Toggle RSS source completed | source_id={} is_active={}", source_id, updated.is_active)
    return updated


@router.put("/rss-sources/{source_id}", response_model=schemas.RssSourceDTO)
def update_rss_source_api(
    source_id: int,
    body: schemas.RssSourceUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Update RSS source | source_id={}", source_id)
    updated = crud.update_rss_source(db, source_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="RSS Source not found")
    logger.info("Update RSS source completed | source_id={}", source_id)
    return updated
