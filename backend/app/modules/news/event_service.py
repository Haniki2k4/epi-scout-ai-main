import re
import unicodedata
from datetime import datetime, timedelta

from sentence_transformers import SentenceTransformer, util
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...core.logger import get_logger
from . import crud, models

logger = get_logger("backend.news.event_service")
_embedding_model = None


def _embedding() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info("Initializing SentenceTransformer for event matching")
        _embedding_model = SentenceTransformer("BAAI/bge-m3")
    return _embedding_model


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _slug(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", _normalize(value).lower())
    return re.sub(r"[^a-z0-9]+", "-", normalized.encode("ascii", "ignore").decode()).strip("-")


def _primary_keyword(value: str | None) -> str | None:
    first = (value or "").split(",")[0].strip()
    return first or None


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    model = _embedding()
    score = float(util.cos_sim(
        model.encode(left, convert_to_tensor=True),
        model.encode(right, convert_to_tensor=True),
    )[0][0])
    return max(0.0, min(score, 1.0))


def _score(title, summary, event_date, location, case_count, event):
    title_score = _similarity(title, event.canonical_title) * 0.35
    summary_score = _similarity(summary[:200], event.canonical_title) * 0.25
    left, right = _normalize(location), _normalize(event.location)
    location_score = 0.20 if left and left == right else 0.10 if left and right and (left in right or right in left) else 0.10 if not left and not right else 0.05
    days = abs((event_date.date() - event.event_date.date()).days)
    date_score = {0: 0.15, 1: 0.10, 2: 0.05}.get(days, 0.0)
    case_score = 0.02
    if case_count > 0 and (event.case_count or 0) > 0:
        delta = abs(case_count - event.case_count)
        tolerance = max(3, int(max(case_count, event.case_count) * 0.3))
        case_score = 0.05 if delta == 0 else 0.03 if delta <= tolerance else 0.0
    breakdown = {"title": round(title_score, 3), "summary": round(summary_score, 3), "location": round(location_score, 3), "date": round(date_score, 3), "case_count": round(case_score, 3)}
    return round(sum(breakdown.values()), 3), breakdown


def resolve_event_for_article(
    db: Session, title: str, normalized_title: str, summary: str,
    matched_keywords: str, pub_date: datetime, location: str | None,
    cumulative_cases: int, new_cases: int, severity: str | None,
    suspected_cases: int = 0, event_date: datetime | None = None,
    override_disease_name: str | None = None,
) -> tuple[models.NewsEvent | None, float | None, str | None, int]:
    disease = override_disease_name or _primary_keyword(matched_keywords)
    if not disease:
        return None, None, None, 0
    normalized_location = _normalize(location) or None
    compare_title = (normalized_title or title).strip()
    observed_at = event_date or pub_date
    recent = crud.get_recent_events(db, disease_name=disease, location=normalized_location, start_date=observed_at-timedelta(days=3), end_date=observed_at+timedelta(days=3))
    if not recent and normalized_location not in {None, "Việt Nam"}:
        recent = crud.get_recent_events(db, disease_name=disease, location=None, start_date=observed_at-timedelta(days=3), end_date=observed_at+timedelta(days=3))
    best, best_score, breakdown = None, 0.0, {}
    cases = max(cumulative_cases, new_cases, suspected_cases)
    for candidate in recent:
        score, parts = _score(compare_title, summary, observed_at, normalized_location, cases, candidate)
        if score > best_score:
            best, best_score, breakdown = candidate, score, parts
    detail = ", ".join(f"{key}={value}" for key, value in breakdown.items())
    if best is not None and best_score >= 0.75:
        event = crud.update_news_event(db, best, canonical_title=compare_title, severity=severity)
        return event, best_score, f"matched_existing_event: {detail}", 0
    event = crud.create_news_event(
        db, canonical_title=compare_title, disease_name=disease,
        location=normalized_location, event_date=observed_at, case_count=None,
        severity=severity,
        fingerprint=f"{_slug(disease) or 'unknown'}|{_slug(normalized_location) or 'unknown'}|{observed_at:%Y-%m-%d}",
    )
    return event, None, f"new_event_created: {detail}", 0


def _is_valid_verified_case(case: models.DiseaseCase, event_id: int) -> bool:
    article = case.article
    if (
        article is None or article.event_id != event_id or article.is_excluded
        or case.data_quality is not None or case.case_type != "confirmed"
        or case.count_scope != "cumulative" or case.reported_value is None
        or case.report_period_start is None or case.report_period_end is None
        or case.report_period_start > case.report_period_end
        or not case.evidence_quote or not case.location
    ):
        return False
    return case.evidence_quote in f"{article.title or ''} {article.summary or ''}"


def handle_article_exclusion_from_event(
    db: Session, article: models.ArticleIdentity, actor_id: int, reason: str,
) -> None:
    article.is_excluded = True
    event = article.event
    if event is None:
        return
    old_status = event.status
    remaining = [a for a in event.articles if a.id != article.id and not a.is_excluded]
    verified_case = db.get(models.DiseaseCase, event.verified_case_source_id) if event.verified_case_source_id else None
    lost_primary = verified_case is not None and verified_case.article_id == article.id

    if not remaining:
        event.status = "rejected"
        event.rejection_reason = "Không còn bài nguồn hợp lệ sau đánh giá LLM"
        _clear_verification(event)
        log_reason = f"Thu hồi toàn bộ vì bài nguồn cuối cùng bị loại: {reason}"
    elif lost_primary:
        candidates = (
            db.query(models.DiseaseCase)
            .join(models.ArticleIdentity, models.DiseaseCase.article_id == models.ArticleIdentity.id)
            .filter(
                models.ArticleIdentity.event_id == event.id,
                models.ArticleIdentity.id != article.id,
                or_(
                    models.ArticleIdentity.is_excluded.is_(False),
                    models.ArticleIdentity.is_excluded.is_(None),
                ),
            ).all()
        )
        replacement = next((case for case in candidates if _is_valid_verified_case(case, event.id)), None)
        if replacement:
            event.status = "verified_event"
            event.verified_case_source_id = replacement.id
            event.case_count = replacement.reported_value
            event.verification_source = replacement.article.source
            event.rejection_reason = None
            log_reason = f"Chuyển nguồn xác minh sang observation {replacement.id}: {reason}"
        else:
            event.status = "pending_review"
            event.rejection_reason = None
            _clear_verification(event)
            log_reason = f"Hạ về chờ duyệt vì mất nguồn xác minh chính: {reason}"
    else:
        return

    db.add(models.EventReviewLog(
        event_id=event.id, actor_id=actor_id, old_status=old_status,
        new_status=event.status, reason=log_reason[:500],
        verification_source=event.verification_source,
        created_at=datetime.utcnow(),
    ))


def _clear_verification(event: models.NewsEvent) -> None:
    event.case_count = None
    event.verified_by = None
    event.verified_at = None
    event.verification_source = None
    event.verified_case_source_id = None
