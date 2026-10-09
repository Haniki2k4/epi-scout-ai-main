"""
Router: Stats & Events — tách từ app/main.py (Issue #12).
Stats endpoints are public (read-only dashboard data).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...core.database import get_db
from ...core.logger import get_logger
from . import crud, schemas, stats

logger = get_logger("backend.router.stats")
router = APIRouter(prefix="/api", tags=["stats"])


# --- Events ---

@router.get("/events", response_model=List[schemas.NewsEventDTO])
def read_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Read events requested | skip={} limit={}", skip, limit)
    events = crud.get_events(db, skip=skip, limit=limit)
    for ev in events:
        if not ev.severity:
            ev.severity = crud.compute_event_severity(ev)
    logger.info("Read events completed | count={}", len(events))
    return events


@router.get("/events/{event_id}", response_model=schemas.NewsEventDetailDTO)
def read_event_detail(event_id: int, db: Session = Depends(get_db)):
    logger.info("Read event detail requested | event_id={}", event_id)
    event = crud.get_event_by_id(db, event_id)
    if not event:
        logger.warning("Read event detail failed | event_id={} reason=not_found", event_id)
        raise HTTPException(status_code=404, detail="Event not found")

    severity = event.severity or crud.compute_event_severity(event)
    valid_articles = event.valid_articles

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
        "article_count": event.article_count,
        "source_count": event.source_count,
        "sources_preview": event.sources_preview,
        "articles": valid_articles,
    }


# --- Stats (public, read-only dashboard data) ---

@router.get("/stats/overview")
def get_stats_overview(db: Session = Depends(get_db)):
    logger.info("Stats overview requested")
    result = stats.get_overview_stats(db)
    logger.info("Stats overview completed | total_articles={}", result.get("total_articles"))
    return result


@router.get("/stats/trends")
def get_stats_trends(days: int = 7, db: Session = Depends(get_db)):
    logger.info("Stats trends requested | days={}", days)
    result = stats.get_trend_data(db, days)
    logger.info("Stats trends completed | points={}", len(result))
    return result


@router.get("/stats/top-diseases")
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


@router.get("/stats/heatmap")
def get_heatmap(days: int = 30, month: int = None, year: int = None, db: Session = Depends(get_db)):
    logger.info("Location heatmap requested | days={} month={} year={}", days, month, year)
    result = stats.get_location_heatmap_data(db, days=days, month=month, year=year)
    logger.info("Location heatmap completed | locations={}", len(result))
    return result


@router.get("/stats/interest-trends")
def get_interest_trends_api(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Interest trends requested | days={}", days)
    result = stats.get_interest_trends(db, days)
    logger.info("Interest trends completed")
    return result


@router.get("/stats/stacked-trends")
def get_stacked_trends(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Stacked trends requested | days={}", days)
    result = stats.get_stacked_trend_data(db, days)
    logger.info("Stacked trends completed")
    return result


@router.get("/stats/zscore")
def get_zscore(disease: str = None, window: int = 14, days: int = 60, db: Session = Depends(get_db)):
    logger.info("Z-score spikes requested | disease={} window={} days={}", disease, window, days)
    result = stats.get_zscore_spikes(db, disease_name=disease, window=window, days=days)
    logger.info("Z-score spikes completed | items={}", len(result))
    return result


@router.get("/stats/keyword-timeseries")
def get_keyword_timeseries(days: int = 30, db: Session = Depends(get_db)):
    logger.info("Keyword timeseries requested | days={}", days)
    result = stats.get_keyword_timeseries(db, days)
    logger.info("Keyword timeseries completed")
    return result


@router.get("/stats/keyword-zscore")
def get_keyword_zscore(window: int = 14, days: int = 60, db: Session = Depends(get_db)):
    logger.info("Keyword Z-score spikes requested | window={} days={}", window, days)
    result = stats.get_keyword_zscore_spikes(db, window=window, days=days)
    logger.info("Keyword Z-score spikes completed | items={}", len(result))
    return result


@router.get("/stats/keyword-bubble")
def get_keyword_bubble(days: int = 30, window: int = 14, db: Session = Depends(get_db)):
    logger.info("Keyword bubble requested | days={} window={}", days, window)
    result = stats.get_keyword_bubble_data(db, days=days, window=window)
    logger.info("Keyword bubble completed | items={}", len(result))
    return result


@router.get("/stats/forecast")
def get_forecast(disease: str = None, horizon: int = 7, db: Session = Depends(get_db)):
    logger.info("Prophet forecast requested | disease={} horizon={}", disease, horizon)
    result = stats.get_prophet_forecast(db, disease_name=disease, horizon_days=horizon)
    logger.info("Prophet forecast completed")
    return result
