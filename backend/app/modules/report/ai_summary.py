import json
import os
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import Session, joinedload

from ...core.logger import get_logger
from ..news import models, stats
from ..news.visibility import public_article_condition
from ..news.disease_catalog import disease_names
from .analysis import build_analysis_report, validate_summary_prose
from collections import Counter

logger = get_logger("backend.report.ai_summary")

SUMMARY_CACHE_TTL_SECONDS = 30 * 60
SUMMARY_MODEL = os.getenv("LLM_SUMMARY_MODEL", os.getenv("LLM_RECHECK_MODEL", "")).strip()
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "openai/gpt-oss-120b:free").strip()
SUMMARY_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
SUMMARY_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
SUMMARY_TIMEOUT_SECONDS = int(os.getenv("LLM_SUMMARY_TIMEOUT_SECONDS", "30"))

_summary_cache: dict[str, object] = {"expires_at": None, "data": None}


def _period_label(start: datetime, end: datetime) -> str:
    return f"từ {start.strftime('%H:%M %d/%m/%Y')} đến {end.strftime('%H:%M %d/%m/%Y')}"


def _empty_summary(start: datetime, end: datetime) -> dict:
    return {
        "period": _period_label(start, end),
        "headline": "Không phát hiện tín hiệu bất thường trong 24h qua",
        "summaries": [],
        "recommendations": [],
        "has_alert": False,
        "message": (
            f"24h qua (từ {start.strftime('%d/%m/%Y 00:00')} "
            f"đến {end.strftime('%d/%m/%Y 23:59')}): "
            "Không phát hiện dấu hiệu cảnh báo nào."
        ),
    }


def build_daily_summary_context(db: Session, scope_hours: int = 24, interval_width: float = 0.8) -> dict:
    end = datetime.utcnow()
    start = end - timedelta(hours=scope_hours)
    articles = (
        db.query(models.ArticleIdentity)
        .options(joinedload(models.ArticleIdentity.cases), joinedload(models.ArticleIdentity.details))
        .join(models.ArticleDetails, models.ArticleIdentity.details)
        .filter(models.ArticleIdentity.published_date >= start, models.ArticleIdentity.published_date <= end,
                public_article_condition())
        .order_by(models.ArticleIdentity.published_date.desc(), models.ArticleIdentity.id.desc())
        .all()
    )
    events = (
        db.query(models.NewsEvent)
        .join(models.ArticleIdentity, models.ArticleIdentity.event_id == models.NewsEvent.id)
        .filter(models.ArticleIdentity.published_date >= start, models.ArticleIdentity.published_date <= end,
                public_article_condition(), models.NewsEvent.status != 'rejected')
        .distinct()
        .order_by(models.NewsEvent.event_date.desc())
        .limit(10)
        .all()
    )
    counts = Counter()
    for article in articles:
        counts.update(disease_names((article.keywords_matched or '').split(',') + [case.disease_name for case in article.cases]))
    top_diseases = [{'disease_name': name} for name, _ in counts.most_common(3)]
    zscore_spikes = []
    forecasts = []
    for item in top_diseases:
        forecast = stats.get_prophet_forecast(db, disease_name=item["disease_name"], horizon_days=7, interval_width=interval_width)
        forecasts.append({**forecast, 'disease_name': item['disease_name']})
        zscore_spikes.extend({**row, 'disease': item['disease_name']} for row in stats.get_zscore_spikes(db, disease_name=item['disease_name'], days=30)
                             if row.get('spike_level') in {'alert', 'danger'} and start.date().isoformat() <= row['date'] <= end.date().isoformat())
    verified_ids = {event.verified_case_source_id for event in events if event.status == 'verified_event' and event.verified_case_source_id}
    return {
        "period_start": start,
        "period_end": end,
        "articles": [
            {
                "id": article.id, "link": article.link,
                "title": article.title,
                "source": article.source,
                "disease": ', '.join(sorted(disease_names((article.keywords_matched or '').split(',') + [case.disease_name for case in article.cases]))),
                "locations": sorted({case.location for case in article.cases if case.location}),
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "observations": [{
                    'id': case.id, 'disease_name': case.disease_name, 'reported_value': case.reported_value,
                    'case_type': case.case_type, 'count_scope': case.count_scope,
                    'location': case.location,
                    'report_period_start': case.report_period_start.isoformat() if case.report_period_start else None,
                    'report_period_end': case.report_period_end.isoformat() if case.report_period_end else None,
                    'evidence_quote': case.evidence_quote[:150], 'verified': case.id in verified_ids,
                } for case in article.cases if case.reported_value is not None and case.reported_value > 0 and case.evidence_quote and case.data_quality is None],
            }
            for article in articles
        ],
        "zscore_spikes": zscore_spikes,
        "forecasts": forecasts,
        "verified_events": [{'event_id': event.id, 'disease': event.disease_name, 'location': event.location,
                             'status': event.status, 'verified_case_source_id': event.verified_case_source_id,
                             'verification_source': event.verification_source}
                            for event in events if event.status == 'verified_event'],
        "events": [
            {
                "title": event.canonical_title,
                "disease": event.disease_name,
                "location": event.location,
                "severity": event.severity,
                "article_count": event.article_count,
            }
            for event in events
        ],
    }


def _fallback_generate_summary(context_data: dict) -> dict:
    return build_analysis_report(context_data)


def _legacy_fallback_generate_summary(context_data: dict) -> dict:
    start = context_data["period_start"]
    end = context_data["period_end"]
    if not context_data["articles"] and not context_data["events"] and not context_data["zscore_spikes"]:
        return _empty_summary(start, end)

    summaries = []
    for event in context_data["events"][:3]:
        evidence_count = int(event.get("article_count") or 0)
        label = "[Cần theo dõi thêm]" if evidence_count <= 1 else ""
        location = event.get("location") or "khu vực chưa rõ"
        summaries.append({
            "text": f"{label} {event.get('disease') or 'dịch tễ'} tại {location} ({evidence_count} nguồn)".strip(),
            "evidence_count": evidence_count,
            "confidence": "high" if evidence_count >= 3 else ("medium" if evidence_count == 2 else "low"),
        })
    if not summaries:
        disease_counts: dict[str, int] = {}
        for article in context_data["articles"]:
            disease = article.get("disease") or "tín hiệu dịch tễ"
            disease_counts[disease] = disease_counts.get(disease, 0) + 1
        for disease, count in sorted(disease_counts.items(), key=lambda item: item[1], reverse=True)[:3]:
            summaries.append({
                "text": f"{disease}: {count} bài báo trong 24h qua",
                "evidence_count": count,
                "confidence": "medium" if count >= 2 else "low",
            })

    total_articles = len(context_data["articles"])
    headline = f"Có {len(summaries)} tín hiệu cần quan tâm trong 24h qua ({total_articles} bài báo)"
    if len(context_data["zscore_spikes"]) > 0:
        headline += ", có dấu hiệu bất thường theo thống kê"

    return {
        "period": _period_label(start, end),
        "headline": headline,
        "summaries": summaries[:3],
        "recommendations": [
            "Xác minh thông tin từ nguồn chính thống trước khi kết luận.",
            "Theo dõi các tín hiệu có ít nguồn trong 24h tới.",
            "Kiểm tra dữ liệu chi tiết trong báo cáo đính kèm.",
        ],
        "has_alert": bool(summaries) or len(context_data["zscore_spikes"]) > 0,
    }


def generate_daily_summary(context_data: dict) -> dict:
    if not SUMMARY_MODEL or not SUMMARY_API_KEY:
        return _fallback_generate_summary(context_data)

    safe_context = {
        key: value
        for key, value in context_data.items()
        if key not in {"period_start", "period_end"}
    }
    system_prompt = (
        "Bạn là trợ lý tóm tắt tin tức dịch tễ học. "
        "Viết NGẮN GỌN, mỗi item tối đa 1 câu. "
        "Chỉ dùng dữ liệu trong context, không thêm số liệu hay địa điểm mới. "
        "Dùng tiếng Việt có dấu. "
        "Trả về JSON với các trường: "
        "headline (string, 1 câu tổng quan), "
        "summaries (list, mỗi item có text + evidence_count + confidence high/medium/low), "
        "recommendations (list, 2-3 khuyến nghị ngắn), "
        "has_alert (bool)."
        " Chỉ chọn nguyên văn text trong allowed_summaries; không viết lại hoặc thêm dữ kiện."
    )
    safe_context['allowed_summaries'] = build_analysis_report(context_data)['summaries']
    context_json = json.dumps(safe_context, ensure_ascii=False)
    max_input_bytes = max(0, int(os.getenv('LLM_MAX_INPUT_BYTES', '0')))
    if max_input_bytes and len((system_prompt + context_json).encode('utf-8')) > max_input_bytes:
        return _fallback_generate_summary(context_data)
    local_options = ({'reasoning_effort': os.getenv('LLM_REASONING_EFFORT')}
                     if os.getenv('LLM_REASONING_EFFORT') else {})
    try:
        response = requests.post(
            f"{SUMMARY_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {SUMMARY_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://epi-scout-ai-main.vercel.app",
                "X-Title": "EpiScout AI",
            },
            json={
                "model": SUMMARY_MODEL,
                "temperature": 0,
                **local_options,
                'max_tokens': 1024,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"<context>{json.dumps(safe_context, ensure_ascii=False)}</context>"},
                ],
            },
            timeout=SUMMARY_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed.setdefault("period", _period_label(context_data["period_start"], context_data["period_end"]))
            parsed.setdefault("headline", "")
            return validate_summary_prose(parsed, context_data)
    except Exception as exc:
        logger.warning("Daily AI summary primary model failed | model={} error={}", SUMMARY_MODEL, str(exc))
        # Fallback to second LLM model if available
        if FALLBACK_MODEL and FALLBACK_MODEL != SUMMARY_MODEL:
            try:
                logger.info("Attempting fallback AI summary | model={}", FALLBACK_MODEL)
                response = requests.post(
                    f"{SUMMARY_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {SUMMARY_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://epi-scout-ai-main.vercel.app",
                        "X-Title": "EpiScout AI",
                    },
                    json={
                        "model": FALLBACK_MODEL,
                        "temperature": 0,
                        **local_options,
                        'max_tokens': 1024,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"<context>{json.dumps(safe_context, ensure_ascii=False)}</context>"},
                        ],
                    },
                    timeout=SUMMARY_TIMEOUT_SECONDS + 20, # More time for potentially larger/slower models
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    parsed.setdefault("period", _period_label(context_data["period_start"], context_data["period_end"]))
                    parsed.setdefault("headline", "")
                    return validate_summary_prose(parsed, context_data)
            except Exception as f_exc:
                logger.warning("Fallback AI summary failed | model={} error={}", FALLBACK_MODEL, str(f_exc))

    return _fallback_generate_summary(context_data)


def get_cached_daily_summary(db: Session, force_refresh: bool = False) -> dict:
    now = datetime.utcnow()
    expires_at = _summary_cache.get("expires_at")
    if not force_refresh and expires_at and expires_at > now and _summary_cache.get("data"):
        return _summary_cache["data"]
    context_data = build_daily_summary_context(db)
    data = generate_daily_summary(context_data)
    _summary_cache["data"] = data
    _summary_cache["expires_at"] = now + timedelta(seconds=SUMMARY_CACHE_TTL_SECONDS)
    return data
