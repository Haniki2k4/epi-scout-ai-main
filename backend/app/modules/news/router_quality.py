"""Ground-truth sampling and crawl health. Metrics include their denominators."""
import json
from datetime import datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..auth.security import require_admin_role
from . import models
from .crawler import get_source_url
from .signal_detector import DETECTOR_VERSION

router = APIRouter(prefix="/api/quality", tags=["quality"])


class SampleLabel(BaseModel):
    human_relevant: bool | None = None
    human_signal_label: str | None = Field(default=None, pattern="^(confirmed_event|early_signal|noise|irrelevant)$")
    human_disease: str | None = Field(default=None, max_length=255)
    human_diseases: list[str] | None = Field(default=None, max_length=20)
    human_location: str | None = Field(default=None, max_length=255)
    human_event_date: datetime | None = None
    human_case_value: int | None = Field(default=None, ge=0)

    @field_validator("human_diseases")
    @classmethod
    def validate_diseases(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        result = []
        seen = set()
        for name in value:
            normalized = name.strip()
            if not normalized or len(normalized) > 255:
                raise ValueError("Each disease name must contain 1-255 characters")
            key = normalized.casefold()
            if key not in seen:
                result.append(normalized)
                seen.add(key)
        return result


@router.get("/samples")
def list_samples(
    unlabeled: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    query = db.query(models.RssEntrySample).filter(models.RssEntrySample.expires_at >= datetime.utcnow())
    if unlabeled:
        query = query.filter(models.RssEntrySample.human_relevant.is_(None))
    rows = query.order_by(models.RssEntrySample.sampled_at.desc()).limit(min(max(limit, 1), 200)).all()
    return [{
        "id": row.id, "link": get_source_url(row.link), "title": row.title, "summary": row.summary,
        "published_date": row.published_date, "sampled_at": row.sampled_at,
        "passed_stage1": row.passed_stage1, "human_relevant": row.human_relevant,
        "stage1_route": row.stage1_route, "gate_b_mode": row.gate_b_mode,
        "gate_b_evaluated": row.gate_b_evaluated,
        "detector_matched": row.detector_matched,
        "detector_version": row.detector_version,
        "context_signal_type": row.context_signal_type,
        "human_signal_label": row.human_signal_label,
        "human_diseases": row.human_diseases if row.human_diseases is not None else ([row.human_disease] if row.human_disease else []),
    } for row in rows]


@router.patch("/samples/{sample_id}")
def label_sample(
    sample_id: int,
    body: SampleLabel,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    row = db.get(models.RssEntrySample, sample_id)
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Sample not found or expired")
    is_context_sample = row.stage1_route == "context" or (row.stage1_route == "none" and row.gate_b_evaluated is True)
    if is_context_sample:
        if body.human_signal_label is None:
            raise HTTPException(status_code=422, detail="Gate B samples require human_signal_label")
        inferred = body.human_signal_label in {"confirmed_event", "early_signal"}
        if body.human_relevant is not None and body.human_relevant != inferred:
            raise HTTPException(status_code=422, detail="human_relevant conflicts with human_signal_label")
        row.human_relevant = inferred
        row.human_signal_label = body.human_signal_label
    else:
        if body.human_relevant is None:
            raise HTTPException(status_code=422, detail="human_relevant is required")
        row.human_relevant = body.human_relevant
        row.human_signal_label = None
    if body.human_diseases is not None and body.human_disease is not None:
        raise HTTPException(status_code=422, detail="Use human_diseases or legacy human_disease, not both")
    diseases = body.human_diseases if body.human_diseases is not None else (
        [body.human_disease.strip()] if body.human_disease and body.human_disease.strip() else []
    )
    row.human_diseases = diseases
    row.human_disease = diseases[0] if len(diseases) == 1 else None
    row.human_location = body.human_location
    row.human_event_date = body.human_event_date
    row.human_case_value = body.human_case_value
    row.labeled_by = admin.id
    row.labeled_at = datetime.utcnow()
    db.commit()
    return {"id": row.id, "labeled_at": row.labeled_at}


@router.get("/metrics")
def get_quality_metrics(
    days: int = 30,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    days = min(max(days, 1), 90)
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(models.RssEntrySample)
        .filter(models.RssEntrySample.sampled_at >= since)
        .filter(models.RssEntrySample.human_relevant.isnot(None))
        .filter(models.RssEntrySample.expires_at >= datetime.utcnow())
        .all()
    )
    gate_a_rows = [row for row in rows if row.human_signal_label is None]
    tp = sum(row.passed_stage1 and row.human_relevant for row in gate_a_rows)
    fp = sum(row.passed_stage1 and not row.human_relevant for row in gate_a_rows)
    fn = sum(not row.passed_stage1 and row.human_relevant for row in gate_a_rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else (0.0 if precision is not None and recall is not None else None)
    b_rows = [
        row for row in rows
        if row.gate_b_evaluated is True and row.detector_version == DETECTOR_VERSION and row.human_signal_label in {"confirmed_event", "early_signal", "noise", "irrelevant"}
        and row.stage1_route in {"context", "none"}
    ]
    b_tp = sum(bool(row.detector_matched and row.human_relevant) for row in b_rows)
    b_fp = sum(bool(row.detector_matched and not row.human_relevant) for row in b_rows)
    b_fn = sum(bool(not row.detector_matched and row.human_relevant) for row in b_rows)
    b_precision = b_tp / (b_tp + b_fp) if b_tp + b_fp else None
    b_unmatched_labeled = sum(not row.detector_matched for row in b_rows)
    b_recall = b_tp / (b_tp + b_fn) if b_tp + b_fn and b_unmatched_labeled else None
    active_rows = [row for row in b_rows if row.gate_b_mode == "active"]
    active_tp = sum(row.llm_label == "relevant" and row.human_relevant for row in active_rows)
    active_fp = sum(row.llm_label == "relevant" and not row.human_relevant for row in active_rows)
    current_scan = db.query(models.ScanRun).order_by(models.ScanRun.started_at.desc()).first()
    completed_scan = (
        db.query(models.ScanRun)
        .filter(models.ScanRun.status == "completed")
        .order_by(models.ScanRun.completed_at.desc())
        .first()
    )
    completed_feeds = (
        db.query(models.CrawlRun).filter(models.CrawlRun.scan_run_id == completed_scan.scan_run_id).all()
        if completed_scan else []
    )
    event_rows = db.query(models.NewsEvent).filter(models.NewsEvent.created_at >= since).all()
    latency_hours = []
    for event in event_rows:
        published = [article.published_date for article in event.articles if article.published_date]
        if published and event.created_at:
            delay = (event.created_at - min(published)).total_seconds() / 3600
            if delay >= 0:
                latency_hours.append(delay)
    pair_rows = db.query(models.EventPairLabel).filter(
        models.EventPairLabel.labeled_at >= since
    ).all()
    pair_tp = pair_fp = pair_fn = 0
    for pair in pair_rows:
        predicted = pair.predicted_same_event
        pair_tp += int(predicted and pair.same_event)
        pair_fp += int(predicted and not pair.same_event)
        pair_fn += int(not predicted and pair.same_event)
    pair_precision = pair_tp / (pair_tp + pair_fp) if pair_tp + pair_fp else None
    pair_recall = pair_tp / (pair_tp + pair_fn) if pair_tp + pair_fn else None
    pair_f1 = (
        2 * pair_precision * pair_recall / (pair_precision + pair_recall)
        if pair_precision is not None and pair_recall is not None and pair_precision + pair_recall
        else (0.0 if pair_precision is not None and pair_recall is not None else None)
    )
    return {
        "stage1": {
            "precision": precision, "recall": recall, "f1": f1,
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "labeled_sample_count": len(gate_a_rows),
        },
        "sample_source": "deterministic 10% of eligible RSS entries before Stage 1",
        "scan_status": {
            "current": current_scan.status if current_scan else None,
            "current_scan_run_id": current_scan.scan_run_id if current_scan else None,
            "current_started_at": current_scan.started_at if current_scan else None,
            "is_stale": bool(current_scan and current_scan.status == "running" and current_scan.started_at < datetime.utcnow() - timedelta(hours=2)),
        },
        "gate_b": {
            "based_on_scan_run_id": completed_scan.scan_run_id if completed_scan else None,
            "based_on_completed_at": completed_scan.completed_at if completed_scan else None,
            "eligible_entries_total": sum(row.eligible_entries_total or 0 for row in completed_feeds),
            "candidates_total": sum(row.gate_b_candidates_total or 0 for row in completed_feeds),
            "active_processed_total": sum(row.gate_b_active_total or 0 for row in completed_feeds),
            "by_type": {
                signal_type: sum(getattr(row, f"gate_b_{signal_type}") or 0 for row in completed_feeds)
                for signal_type in ("unexplained_cluster", "animal_signal", "environment_signal", "field_response")
            },
            "detector": {
                "true_positive": b_tp, "false_positive": b_fp, "false_negative": b_fn,
                "precision": b_precision, "recall": b_recall,
                "matched_labeled": b_tp + b_fp,
                "unmatched_labeled": b_unmatched_labeled,
                "detector_version": DETECTOR_VERSION,
                "definition": "Among A-failed entries where B was evaluated; labels positive = confirmed_event or early_signal.",
                "sampling_note": "Deterministic URL sample is 10% in both groups. Precision/recall remain provisional if manual labeling is selective.",
            },
            "active_llm": {
                "true_positive": active_tp, "false_positive": active_fp,
                "precision": active_tp / (active_tp + active_fp) if active_tp + active_fp else None,
                "labeled_count": len(active_rows),
            },
        },
        "period_start": since,
        "period_end": datetime.utcnow(),
        "llm_evaluation_url": "/api/llm-evaluations/metrics",
        "event_pair": {
            "precision": pair_precision, "recall": pair_recall, "f1": pair_f1,
            "true_positive": pair_tp, "false_positive": pair_fp,
            "false_negative": pair_fn, "labeled_pair_count": len(pair_rows),
        },
        "article_to_signal_latency": {
            "median_hours": median(latency_hours) if latency_hours else None,
            "event_count": len(latency_hours),
            "definition": "Event creation time minus earliest source article publication time",
        },
        "note": "Legacy Stage 1 binary scores exclude four-label Gate B samples and are not hybrid-system recall. Gate B detector and active LLM scores are separate; missing denominators remain null.",
    }


@router.get("/sources")
def get_source_health(
    days: int = 30,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    since = datetime.utcnow() - timedelta(days=min(max(days, 1), 90))
    rows = db.query(models.CrawlRun).filter(models.CrawlRun.started_at >= since).all()
    by_source: dict[str, dict] = {}
    for row in rows:
        item = by_source.setdefault(row.feed_url, {
            "source_id": row.source_id, "feed_url": row.feed_url,
            "daily_entries": {},
            "runs": 0, "entries_fetched": 0, "entries_passed_stage1": 0,
            "entries_saved": 0, "error_count": 0, "last_run_at": row.started_at,
        })
        day = row.started_at.strftime("%Y-%m-%d")
        item["daily_entries"][day] = item["daily_entries"].get(day, 0) + (row.entries_fetched or 0)
        item["runs"] += 1
        item["entries_fetched"] += row.entries_fetched or 0
        item["entries_passed_stage1"] += row.entries_passed_stage1 or 0
        item["entries_saved"] += row.entries_saved or 0
        item["error_count"] += row.error_count or 0
        if row.started_at > item["last_run_at"]:
            item["last_run_at"] = row.started_at
    return sorted(by_source.values(), key=lambda item: item["error_count"], reverse=True)

class PairLabelRequest(BaseModel):
    article_a_id: int = Field(gt=0)
    article_b_id: int = Field(gt=0)
    same_event: bool


@router.get("/event-pairs/candidates")
def pair_candidates(
    limit: int = 20,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    articles = (
        db.query(models.ArticleIdentity)
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
        .order_by(models.ArticleIdentity.published_date.desc())
        .limit(60)
        .all()
    )
    existing = {
        (row.article_a_id, row.article_b_id)
        for row in db.query(models.EventPairLabel.article_a_id, models.EventPairLabel.article_b_id).all()
    }
    candidates = []
    for index, first in enumerate(articles):
        for second in articles[index + 1:]:
            a_id, b_id = sorted((first.id, second.id))
            if (a_id, b_id) in existing:
                continue
            if not first.keywords_matched or not second.keywords_matched:
                continue
            first_diseases = {item.strip().casefold() for item in first.keywords_matched.split(",")}
            second_diseases = {item.strip().casefold() for item in second.keywords_matched.split(",")}
            if not first_diseases.intersection(second_diseases):
                continue
            if first.published_date and second.published_date and abs((first.published_date - second.published_date).days) > 7:
                continue
            candidates.append({
                "article_a_id": a_id, "article_b_id": b_id,
                "title_a": first.title, "title_b": second.title,
                "link_a": first.link, "link_b": second.link,
                "predicted_same_event": first.event_id is not None and first.event_id == second.event_id,
            })
            if len(candidates) >= min(max(limit, 1), 100):
                return candidates
    return candidates


@router.post("/event-pairs")
def label_pair(
    body: PairLabelRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    if body.article_a_id == body.article_b_id:
        raise HTTPException(status_code=422, detail="Choose two distinct articles")
    a_id, b_id = sorted((body.article_a_id, body.article_b_id))
    first = db.get(models.ArticleIdentity, a_id)
    second = db.get(models.ArticleIdentity, b_id)
    if first is None or second is None:
        raise HTTPException(status_code=404, detail="Article not found")
    existing = db.query(models.EventPairLabel).filter(
        models.EventPairLabel.article_a_id == a_id,
        models.EventPairLabel.article_b_id == b_id,
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Pair already labeled")
    row = models.EventPairLabel(
        article_a_id=a_id, article_b_id=b_id,
        same_event=body.same_event,
        predicted_same_event=first.event_id is not None and first.event_id == second.event_id,
        labeled_by=admin.id, labeled_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id}
