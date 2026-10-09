"""Review queue for context signals without a disease keyword."""
from datetime import datetime
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..evaluation.models import ArticleEvaluation
from . import models
from .event_service import resolve_event_for_article
from .router_signals import require_analyst

router = APIRouter(prefix="/api/context-signals", tags=["context-signals"])
Decision = Literal["dismissed", "monitoring_unknown", "disease_identified", "ruled_out"]


class ContextReviewRequest(BaseModel):
    request_id: UUID
    expected_review_version: int = Field(ge=0)
    decision: Decision
    reason: str = Field(min_length=1, max_length=500)
    signal_evidence: str | None = Field(default=None, max_length=5000)
    disease_name: str | None = Field(default=None, max_length=255)
    disease_source: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=255)


def _review_dict(review: models.ContextSignalReview) -> dict:
    return {
        "id": review.id, "article_id": review.article_id,
        "version": review.version, "decision": review.decision,
        "reason": review.reason, "signal_evidence": review.signal_evidence,
        "disease_name": review.disease_name, "disease_source": review.disease_source,
        "location": review.location, "event_id": review.event_id,
        "reviewer_id": review.reviewer_id, "reviewed_at": review.reviewed_at,
    }


def _payload_matches(review: models.ContextSignalReview, body: ContextReviewRequest) -> bool:
    return all((
        review.decision == body.decision,
        review.reason == body.reason.strip(),
        (review.signal_evidence or None) == (body.signal_evidence.strip() if body.signal_evidence else None),
        (review.disease_name or None) == (body.disease_name.strip() if body.disease_name else None),
        (review.disease_source or None) == (body.disease_source.strip() if body.disease_source else None),
        (review.location or None) == (body.location.strip() if body.location else None),
    ))


def _article_dict(article: models.ArticleIdentity, review: models.ContextSignalReview | None, llm_label: str | None) -> dict:
    details = article.details
    try:
        phrases = json.loads(details.context_matched_phrases or "[]")
    except (TypeError, ValueError):
        phrases = []
    return {
        "article_id": article.id, "title": article.title, "link": article.link,
        "summary": details.summary, "source": details.source,
        "published_date": article.published_date,
        "signal_type": details.context_signal_type,
        "matched_phrases": phrases,
        "evidence_text": details.context_evidence_text,
        "llm_label": llm_label, "llm_reason": details.llm_reason,
        "review_version": details.review_version,
        "current_review": _review_dict(review) if review else None,
    }


@router.get("/queue")
def list_context_signals(
    view: Literal["pending", "monitoring"] = "pending",
    limit: int = 50,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    query = (
        db.query(models.ArticleIdentity, models.ContextSignalReview)
        .join(models.ArticleDetails)
        .outerjoin(
            models.ContextSignalReview,
            and_(
                models.ContextSignalReview.article_id == models.ArticleIdentity.id,
                models.ContextSignalReview.is_superseded.is_(False),
            ),
        )
        .filter(models.ArticleDetails.stage1_route == "context")
        .filter(models.ArticleIdentity.is_excluded.is_(True))
    )
    if view == "pending":
        query = query.filter(models.ContextSignalReview.id.is_(None))
    else:
        query = query.filter(models.ContextSignalReview.decision == "monitoring_unknown")
    rows = query.order_by(models.ArticleIdentity.published_date.desc()).limit(min(max(limit, 1), 200)).all()
    result = []
    for article, review in rows:
        evaluation = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id == article.id).first()
        result.append(_article_dict(article, review, evaluation.llm_label if evaluation else None))
    return result


@router.get("/{article_id}")
def get_context_signal(
    article_id: int,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    article = db.get(models.ArticleIdentity, article_id)
    if article is None or article.details is None or article.details.stage1_route != "context":
        raise HTTPException(status_code=404, detail="Context signal not found")
    current = (
        db.query(models.ContextSignalReview)
        .filter(models.ContextSignalReview.article_id == article_id)
        .filter(models.ContextSignalReview.is_superseded.is_(False))
        .first()
    )
    evaluation = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id == article_id).first()
    data = _article_dict(article, current, evaluation.llm_label if evaluation else None)
    data["history"] = [
        _review_dict(row) for row in (
            db.query(models.ContextSignalReview)
            .filter(models.ContextSignalReview.article_id == article_id)
            .order_by(models.ContextSignalReview.version)
            .all()
        )
    ]
    return data


@router.post("/{article_id}/review")
def review_context_signal(
    article_id: int,
    body: ContextReviewRequest,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    details = (
        db.query(models.ArticleDetails)
        .filter(models.ArticleDetails.article_id == article_id)
        .with_for_update()
        .first()
    )
    if details is None or details.stage1_route != "context":
        raise HTTPException(status_code=422, detail="Article is not a Gate B signal")
    article = db.get(models.ArticleIdentity, article_id)
    request_id = str(body.request_id)
    previous_request = (
        db.query(models.ContextSignalReview)
        .filter(models.ContextSignalReview.request_id == request_id)
        .first()
    )
    if previous_request:
        if previous_request.article_id != article_id or not _payload_matches(previous_request, body):
            raise HTTPException(status_code=409, detail="request_id belongs to another article or payload")
        return _review_dict(previous_request)
    current = (
        db.query(models.ContextSignalReview)
        .filter(models.ContextSignalReview.article_id == article_id)
        .filter(models.ContextSignalReview.is_superseded.is_(False))
        .first()
    )
    if details.review_version != body.expected_review_version:
        raise HTTPException(status_code=409, detail={
            "message": "Review version is stale",
            "current_version": details.review_version,
            "current_review": _review_dict(current) if current else None,
        })
    if current and current.decision != "monitoring_unknown":
        raise HTTPException(status_code=422, detail="Decision is final; use event workflow for published events")
    if not body.reason.strip():
        raise HTTPException(status_code=422, detail="Reason is required")
    evidence = body.signal_evidence.strip() if body.signal_evidence else None
    disease_name = body.disease_name.strip() if body.disease_name else None
    disease_source = body.disease_source.strip() if body.disease_source else None
    location = body.location.strip() if body.location else None
    if body.decision in {"monitoring_unknown", "disease_identified"} and not evidence:
        raise HTTPException(status_code=422, detail="Signal evidence is required")
    if body.decision == "disease_identified" and (not disease_name or not disease_source):
        raise HTTPException(status_code=422, detail="Disease name and confirmation source are required")

    evaluation = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id == article_id).first()
    if evaluation is None:
        evaluation = ArticleEvaluation(article_id=article_id)
        db.add(evaluation)
    evaluation.is_verified = True
    evaluation.verified_at = datetime.utcnow()
    evaluation.verified_by = analyst.id
    event = None
    if body.decision == "disease_identified":
        event, score, dedupe_reason, _ = resolve_event_for_article(
            db=db, title=article.title,
            normalized_title=details.llm_normalized_title or article.title,
            summary=details.summary or "", matched_keywords="",
            pub_date=article.published_date or datetime.utcnow(),
            location=location, cumulative_cases=0, new_cases=0,
            severity=None, override_disease_name=disease_name,
        )
        if event is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="Could not create disease event")
        article.is_excluded = False
        article.event_id = event.id
        article.event_match_score = score
        article.dedupe_reason = dedupe_reason
        evaluation.human_label = "relevant"
    else:
        article.is_excluded = True
        article.event_id = None
        evaluation.human_label = "unsure" if body.decision == "monitoring_unknown" else "irrelevant"

    if current:
        current.is_superseded = True
    details.review_version += 1
    review = models.ContextSignalReview(
        article_id=article_id, reviewer_id=analyst.id, reviewed_at=datetime.utcnow(),
        version=details.review_version, request_id=request_id, decision=body.decision,
        is_superseded=False, signal_evidence=evidence, reason=body.reason.strip(),
        disease_name=disease_name, disease_source=disease_source,
        location=location, event_id=event.id if event else None,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent review or duplicate request_id")
    except Exception:
        db.rollback()
        raise
    db.refresh(review)
    return _review_dict(review)

