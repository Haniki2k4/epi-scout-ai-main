"""Analyst signal queue and auditable decisions."""
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..auth.security import get_current_active_user
from . import models

router = APIRouter(prefix="/api/signals", tags=["signals"])
SignalStatus = Literal[
    "pending_review", "under_verification", "verified_event",
    "monitoring", "rejected", "closed",
]


def require_analyst(user=Depends(get_current_active_user)):
    if user.role not in {"analyst", "admin"}:
        raise HTTPException(status_code=403, detail="Analyst role required")
    return user


class ReviewRequest(BaseModel):
    status: SignalStatus
    reason: str = Field(default="", max_length=500)
    notes: str | None = None
    verification_source: str | None = Field(default=None, max_length=500)
    reported_case_count: int | None = Field(default=None, ge=0)
    case_observation_id: int | None = Field(default=None, gt=0)


@router.get("")
def list_signals(
    status: SignalStatus | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    query = db.query(models.NewsEvent)
    if status:
        query = query.filter(models.NewsEvent.status == status)
    else:
        query = query.filter(models.NewsEvent.status.in_(["pending_review", "monitoring", "under_verification"]))
    events = query.order_by(models.NewsEvent.event_date.desc()).limit(min(max(limit, 1), 200)).all()
    items = []
    for event in events:
        articles = event.valid_articles
        # Queue priority is a triage aid, not an epidemiological risk score.
        recent_count = sum(bool(article.published_date and article.published_date >= datetime.utcnow() - timedelta(hours=24)) for article in articles)
        official_count = sum(source.endswith(".gov.vn") or source in {"moh.gov.vn", "who.int"} for source in event.unique_sources)
        priority = min(len(event.unique_sources), 5) * 10 + min(len(articles), 10) + min(recent_count, 5) * 3 + min(official_count, 2) * 20
        if (event.disease_name or "").lower() in {"h5n1", "cúm a/h5n1", "bạch hầu"}:
            priority += 50
        items.append({
            "id": event.id,
            "title": event.canonical_title,
            "disease": event.disease_name,
            "location": event.location,
            "event_date": event.event_date,
            "status": event.status,
            "article_count": len(articles),
            "source_count": len(event.unique_sources),
            "priority": priority,
        })
    return sorted(items, key=lambda item: (-item["priority"], -item["id"]))


@router.get("/{event_id}")
def get_signal(
    event_id: int,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    event = db.get(models.NewsEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    articles = []
    for article in event.articles:
        articles.append({
            "id": article.id,
            "title": article.title,
            "link": article.link,
            "published_date": article.published_date,
            "source": article.source,
            "summary": article.summary,
            "is_excluded": article.is_excluded,
            "observations": [
                {
                    "id": case.id,
                    "disease_name": case.disease_name,
                    "reported_value": case.reported_value,
                    "case_type": case.case_type,
                    "count_scope": case.count_scope,
                    "location": case.location,
                    "report_period_start": case.report_period_start,
                    "report_period_end": case.report_period_end,
                    "evidence_quote": case.evidence_quote,
                    "time_allocation": case.time_allocation,
                    "location_allocation": case.location_allocation,
                    "data_quality": case.data_quality,
                }
                for case in article.cases
            ],
        })
    history = (
        db.query(models.EventReviewLog)
        .filter(models.EventReviewLog.event_id == event_id)
        .order_by(models.EventReviewLog.created_at.desc())
        .all()
    )
    return {
        "id": event.id,
        "title": event.canonical_title,
        "disease": event.disease_name,
        "location": event.location,
        "event_date": event.event_date,
        "status": event.status,
        "case_count": event.case_count,
        "verified_case_source_id": event.verified_case_source_id,
        "verification_notes": event.verification_notes,
        "verification_source": event.verification_source,
        "rejection_reason": event.rejection_reason,
        "articles": articles,
        "history": [
            {
                "actor_id": row.actor_id,
                "old_status": row.old_status,
                "new_status": row.new_status,
                "reason": row.reason,
                "notes": row.notes,
                "verification_source": row.verification_source,
                "created_at": row.created_at,
            }
            for row in history
        ],
    }


@router.post("/{event_id}/review")
def review_signal(
    event_id: int,
    body: ReviewRequest,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    event = db.get(models.NewsEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    reason = body.reason.strip()
    source = body.verification_source.strip() if body.verification_source else None
    if not reason:
        raise HTTPException(status_code=422, detail="Decision reason required")
    if body.status == "verified_event" and not source:
        raise HTTPException(status_code=422, detail="Verification source required")
    if body.reported_case_count is not None and body.status != "verified_event":
        raise HTTPException(status_code=422, detail="Case count requires verified_event status")
    if body.reported_case_count is not None:
        case = db.get(models.DiseaseCase, body.case_observation_id) if body.case_observation_id else None
        if (
            case is None or case.article.event_id != event.id
            or case.article not in event.valid_articles
            or case.data_quality is not None or case.case_type != "confirmed"
            or case.count_scope != "cumulative"
            or case.report_period_start is None or case.report_period_end is None
            or not case.evidence_quote or not case.location
            or case.evidence_quote not in f"{case.article.title} {case.article.summary}"
            or case.report_period_start > case.report_period_end
            or case.reported_value != body.reported_case_count
        ):
            raise HTTPException(status_code=422, detail="Case count needs a confirmed cumulative observation with source, period, location and matching value")
    elif body.case_observation_id is not None:
        raise HTTPException(status_code=422, detail="Observation ID requires a case count")
    old_status = event.status
    now = datetime.utcnow()
    event.status = body.status
    event.analyst_reviewed_by = analyst.id
    event.analyst_reviewed_at = now
    event.verification_notes = body.notes
    event.verification_source = source if body.status == "verified_event" else None
    event.rejection_reason = reason if body.status == "rejected" else None
    if body.status == "verified_event":
        event.verified_by = analyst.id
        event.verified_at = now
        event.case_count = body.reported_case_count
        event.verified_case_source_id = body.case_observation_id
    else:
        event.case_count = None
        event.verified_by = None
        event.verified_at = None
        event.verified_case_source_id = None
    db.add(models.EventReviewLog(
        event_id=event.id,
        actor_id=analyst.id,
        old_status=old_status,
        new_status=body.status,
        reason=reason or None,
        notes=body.notes,
        verification_source=source,
        created_at=now,
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"id": event.id, "status": event.status, "case_count": event.case_count}

class MergeRequest(BaseModel):
    target_event_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)


class SplitRequest(BaseModel):
    article_ids: list[int] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=500)


@router.post("/{event_id}/merge")
def merge_signal(
    event_id: int,
    body: MergeRequest,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    if event_id == body.target_event_id:
        raise HTTPException(status_code=422, detail="Source and target must differ")
    source = db.get(models.NewsEvent, event_id)
    target = db.get(models.NewsEvent, body.target_event_id)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if source.disease_name.casefold() != target.disease_name.casefold():
        raise HTTPException(status_code=422, detail="Disease names must match")
    if source.status == "verified_event" or target.status == "verified_event":
        raise HTTPException(status_code=409, detail="Reopen verified events before merging")
    moved_ids = [article.id for article in source.articles]
    if not moved_ids:
        raise HTTPException(status_code=422, detail="Source has no articles")
    old_status = source.status
    target_old_status = target.status
    for article in source.articles:
        article.event_id = target.id
    source.status = "closed"
    source.case_count = None
    target.status = "pending_review"
    target.case_count = None
    now = datetime.utcnow()
    source.analyst_reviewed_by = analyst.id
    source.analyst_reviewed_at = now
    target.analyst_reviewed_by = analyst.id
    target.analyst_reviewed_at = now
    db.add(models.EventReviewLog(
        event_id=source.id, actor_id=analyst.id, old_status=old_status,
        new_status="closed", reason=body.reason,
        notes=f"Merged into event {target.id}; article_ids={moved_ids}", created_at=now,
    ))
    db.add(models.EventReviewLog(
        event_id=target.id, actor_id=analyst.id, old_status=target_old_status,
        new_status="pending_review", reason=body.reason,
        notes=f"Received articles from event {source.id}; article_ids={moved_ids}", created_at=now,
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"source_event_id": source.id, "target_event_id": target.id, "moved_article_ids": moved_ids}


@router.post("/{event_id}/split")
def split_signal(
    event_id: int,
    body: SplitRequest,
    db: Session = Depends(get_db),
    analyst=Depends(require_analyst),
):
    source = db.get(models.NewsEvent, event_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if source.status == "verified_event":
        raise HTTPException(status_code=409, detail="Reopen verified event before splitting")
    selected = [article for article in source.articles if article.id in set(body.article_ids)]
    if len(selected) != len(set(body.article_ids)) or len(selected) == len(source.articles):
        raise HTTPException(status_code=422, detail="Select a nonempty proper subset of event articles")
    old_status = source.status
    first = selected[0]
    new_event = models.NewsEvent(
        canonical_title=first.title or source.canonical_title,
        disease_name=source.disease_name,
        location=source.location,
        event_date=first.published_date or source.event_date,
        case_count=None,
        severity=source.severity,
        status="pending_review",
        fingerprint=f"split:{event_id}:{first.id}:{int(datetime.utcnow().timestamp())}",
    )
    db.add(new_event)
    db.flush()
    for article in selected:
        article.event_id = new_event.id
    source.status = "pending_review"
    source.case_count = None
    now = datetime.utcnow()
    source.analyst_reviewed_by = analyst.id
    source.analyst_reviewed_at = now
    moved_ids = [article.id for article in selected]
    db.add(models.EventReviewLog(
        event_id=source.id, actor_id=analyst.id, old_status=old_status,
        new_status="pending_review", reason=body.reason,
        notes=f"Split into event {new_event.id}; article_ids={moved_ids}", created_at=now,
    ))
    db.add(models.EventReviewLog(
        event_id=new_event.id, actor_id=analyst.id, old_status=None,
        new_status="pending_review", reason=body.reason,
        notes=f"Split from event {source.id}; article_ids={moved_ids}", created_at=now,
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"source_event_id": source.id, "new_event_id": new_event.id, "moved_article_ids": moved_ids}

