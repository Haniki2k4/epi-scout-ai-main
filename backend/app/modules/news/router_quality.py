"""Ground-truth sampling and crawl health. Metrics include their denominators."""
import json
from datetime import datetime, timedelta
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..auth.security import require_admin_role
from . import models

router = APIRouter(prefix="/api/quality", tags=["quality"])


class SampleLabel(BaseModel):
    human_relevant: bool
    human_disease: str | None = Field(default=None, max_length=255)
    human_location: str | None = Field(default=None, max_length=255)
    human_event_date: datetime | None = None
    human_case_value: int | None = Field(default=None, ge=0)


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
        "id": row.id, "link": row.link, "title": row.title, "summary": row.summary,
        "published_date": row.published_date, "sampled_at": row.sampled_at,
        "passed_stage1": row.passed_stage1, "human_relevant": row.human_relevant,
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
    row.human_relevant = body.human_relevant
    row.human_disease = body.human_disease
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
    tp = sum(row.passed_stage1 and row.human_relevant for row in rows)
    fp = sum(row.passed_stage1 and not row.human_relevant for row in rows)
    fn = sum(not row.passed_stage1 and row.human_relevant for row in rows)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else (0.0 if precision is not None and recall is not None else None)
    # LLM scores are conditional on reaching Stage 2; Stage 1 misses remain in its own recall.
    llm_rows = [row for row in rows if row.llm_label in {"relevant", "irrelevant", "noise", "unsure"}]
    llm_tp = sum(row.llm_label == "relevant" and row.human_relevant for row in llm_rows)
    llm_fp = sum(row.llm_label == "relevant" and not row.human_relevant for row in llm_rows)
    llm_fn = sum(row.llm_label != "relevant" and row.human_relevant for row in llm_rows)
    llm_precision = llm_tp / (llm_tp + llm_fp) if llm_tp + llm_fp else None
    llm_recall = llm_tp / (llm_tp + llm_fn) if llm_tp + llm_fn else None
    llm_f1 = (
        2 * llm_precision * llm_recall / (llm_precision + llm_recall)
        if llm_precision is not None and llm_recall is not None and llm_precision + llm_recall
        else (0.0 if llm_precision is not None and llm_recall is not None else None)
    )

    fields = {name: {"correct": 0, "labeled_count": 0} for name in ("disease", "location", "event_date", "case_value")}
    for row in rows:
        if row.predicted_case_values is None or not row.human_relevant:
            continue
        try:
            predicted_values = json.loads(row.predicted_case_values or "[]")
        except (TypeError, ValueError):
            predicted_values = []
        expected = {
            "disease": row.human_disease,
            "location": row.human_location,
            "event_date": row.human_event_date,
            "case_value": row.human_case_value,
        }
        predicted = {
            "disease": bool(row.human_disease and row.human_disease.casefold() in {
                disease.strip().casefold() for disease in (row.predicted_disease or "").split(",")
            }),
            "location": bool(row.human_location and
                row.human_location.casefold() == (row.predicted_location or "").casefold()),
            "event_date": bool(row.human_event_date and row.predicted_event_date and
                row.human_event_date.date() == row.predicted_event_date.date()),
            "case_value": row.human_case_value in predicted_values,
        }
        for name, human_value in expected.items():
            if human_value is None or (isinstance(human_value, str) and not human_value.strip()):
                continue
            fields[name]["labeled_count"] += 1
            fields[name]["correct"] += int(predicted[name])
    for item in fields.values():
        item["accuracy"] = item["correct"] / item["labeled_count"] if item["labeled_count"] else None

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
            "labeled_sample_count": len(rows),
        },
        "sample_source": "deterministic 10% of eligible RSS entries before Stage 1",
        "period_start": since,
        "period_end": datetime.utcnow(),
        "llm": {
            "precision": llm_precision, "recall": llm_recall, "f1": llm_f1,
            "true_positive": llm_tp, "false_positive": llm_fp, "false_negative": llm_fn,
            "labeled_sample_count": len(llm_rows),
        },
        "event_pair": {
            "precision": pair_precision, "recall": pair_recall, "f1": pair_f1,
            "true_positive": pair_tp, "false_positive": pair_fp,
            "false_negative": pair_fn, "labeled_pair_count": len(pair_rows),
        },
        "field_accuracy": fields,
        "article_to_signal_latency": {
            "median_hours": median(latency_hours) if latency_hours else None,
            "event_count": len(latency_hours),
            "definition": "Event creation time minus earliest source article publication time",
        },
        "note": "Stage 1 uses sampled RSS; LLM and extraction are conditional on prior stages; event-pair scores cover labeled candidates only. Missing denominators remain null.",
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

