"""
Router: Articles & Bookmarks — tách từ app/main.py (Issue #12).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime, timezone

from ...core.database import get_db
from ...core.logger import get_logger
from ..auth import security
from ..auth.models import UserBookmark
from ..evaluation.models import ArticleEvaluation
from . import crawler, event_service, crud, models, schemas

logger = get_logger("backend.router.articles")
router = APIRouter(prefix="/api", tags=["articles"])


# --- Articles ---

@router.get("/articles", response_model=schemas.PaginatedArticles)
def read_articles(
    skip: int = 0,
    limit: int = 100,
    keyword: str | None = None,
    date: str | None = None,
    include_excluded: bool = False,
    include_label: bool = False,
    db: Session = Depends(get_db),
):
    logger.info(
        "Read articles requested | skip={} limit={} keyword={} date={} include_excluded={} include_label={}",
        skip, limit, keyword, date, include_excluded, include_label,
    )
    articles = crud.get_articles(db, skip=skip, limit=limit, keyword=keyword, date=date, include_excluded=include_excluded)
    total = crud.count_articles(db, keyword=keyword, date=date, include_excluded=include_excluded)

    if include_label:
        article_ids = [a.id for a in articles]
        evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
        eval_map = {e.article_id: e for e in evals}
        for a in articles:
            e = eval_map.get(a.id)
            if e:
                a.llm_label = e.llm_label
                a.human_label = e.human_label

    logger.info("Read articles completed | count={} total={}", len(articles), total)
    return {"items": articles, "total": total, "skip": skip, "limit": limit}


@router.get("/articles/new-count")
def get_new_articles_count(hours: int = 24, db: Session = Depends(get_db)):
    """Đếm số bài báo mới được thu thập trong N giờ gần nhất (public, không cần auth)."""
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    count = db.query(models.ArticleIdentity).filter(
        models.ArticleIdentity.published_date >= since
    ).count()
    return {"count": count, "hours": hours}


@router.post("/articles/save", response_model=schemas.ArticleDTO)
def save_article(
    article: schemas.ArticleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user),
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
        inferred_event, event_match_score, dedupe_reason, _ = event_service.resolve_event_for_article(
            db=db,
            title=article.title,
            summary=article.summary or "",
            matched_keywords=matched_keywords,
            pub_date=article.published_date or datetime.now(timezone.utc),
            location="Việt Nam",
            cumulative_cases=cases,
            new_cases=0,
            severity=None,
        )
        article.event_id = inferred_event.id if inferred_event else None
        article.event_match_score = event_match_score
        article.dedupe_reason = dedupe_reason
    saved_article = crud.create_article(db, article)
    db.commit()
    db.refresh(saved_article)
    logger.info("Article saved | id={} link={}", saved_article.id, article.link)
    return saved_article


@router.delete("/articles/{article_id}")
def delete_article_api(
    article_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(security.require_admin_role),
):
    logger.info("Delete article requested | article_id={}", article_id)
    verified_source = (
        db.query(models.NewsEvent.id)
        .join(models.DiseaseCase, models.NewsEvent.verified_case_source_id == models.DiseaseCase.id)
        .filter(models.DiseaseCase.article_id == article_id)
        .filter(models.NewsEvent.status == "verified_event")
        .first()
    )
    if verified_source:
        raise HTTPException(status_code=409, detail="Reopen the verified event before deleting its evidence article")
    labeled_pair = db.query(models.EventPairLabel.id).filter(
        (models.EventPairLabel.article_a_id == article_id) |
        (models.EventPairLabel.article_b_id == article_id)
    ).first()
    if labeled_pair:
        raise HTTPException(status_code=409, detail="This article is part of labeled event-pair ground truth")
    success = crud.delete_article(db, article_id)
    if not success:
        logger.warning("Delete article failed | article_id={} reason=not_found", article_id)
        raise HTTPException(status_code=404, detail="Article not found")
    logger.info("Delete article completed | article_id={}", article_id)
    return {"status": "success", "id": article_id}


# --- Bookmarks ---

@router.post("/bookmarks/{article_id}")
def add_bookmark(
    article_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user),
):
    article = db.query(models.ArticleIdentity).filter(models.ArticleIdentity.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    existing = db.query(UserBookmark).filter(
        UserBookmark.user_id == current_user.id,
        UserBookmark.article_id == article_id,
    ).first()
    if existing:
        return {"status": "success", "message": "Already bookmarked"}

    bookmark = UserBookmark(user_id=current_user.id, article_id=article_id)
    db.add(bookmark)
    db.commit()
    return {"status": "success", "message": "Bookmarked"}


@router.delete("/bookmarks/{article_id}")
def remove_bookmark(
    article_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user),
):
    bookmark = db.query(UserBookmark).filter(
        UserBookmark.user_id == current_user.id,
        UserBookmark.article_id == article_id,
    ).first()
    if not bookmark:
        raise HTTPException(status_code=404, detail="Bookmark not found")

    db.delete(bookmark)
    db.commit()
    return {"status": "success"}


@router.get("/bookmarks", response_model=List[schemas.ArticleDTO])
def get_bookmarks(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user),
):
    bookmarks = db.query(UserBookmark).filter(
        UserBookmark.user_id == current_user.id,
    ).order_by(UserBookmark.created_at.desc()).offset(skip).limit(limit).all()
    article_ids = [b.article_id for b in bookmarks]
    if not article_ids:
        return []

    articles = db.query(models.ArticleIdentity).options(
        joinedload(models.ArticleIdentity.cases),
    ).filter(models.ArticleIdentity.id.in_(article_ids)).all()
    article_map = {a.id: a for a in articles}
    return [article_map[aid] for aid in article_ids if aid in article_map]
