import json
import os
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import Session, joinedload

from ...core.logger import get_logger
from ..news import models, stats

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


def build_daily_summary_context(db: Session) -> dict:
    end = datetime.utcnow()
    start = end - timedelta(hours=24)
    articles = (
        db.query(models.ArticleIdentity)
        .options(joinedload(models.ArticleIdentity.cases))
        .join(models.ArticleDetails, models.ArticleIdentity.details)
        .filter(models.ArticleIdentity.published_date >= start)
        .order_by(models.ArticleIdentity.published_date.desc())
        .limit(50)
        .all()
    )
    events = (
        db.query(models.NewsEvent)
        .filter(
            models.NewsEvent.event_date >= start,
            models.NewsEvent.severity.in_(["high", "medium"]),
        )
        .order_by(models.NewsEvent.event_date.desc())
        .limit(10)
        .all()
    )
    zscore_spikes = [item for item in stats.get_zscore_spikes(db, days=30) if item.get("spike_level") in {"alert", "danger"}][:5]
    top_diseases = stats.disease_mention_counts(db, days=30)[:3]
    forecasts = []
    for item in top_diseases:
        forecast = stats.get_prophet_forecast(db, disease_name=item["disease_name"], horizon_days=3)
        if forecast.get("forecast"):
            forecasts.append({
                "disease_name": item["disease_name"],
                "forecast": forecast["forecast"],
            })
    return {
        "period_start": start,
        "period_end": end,
        "articles": [
            {
                "title": article.title,
                "source": article.source,
                "disease": article.keywords_matched,
                "locations": sorted({case.location for case in article.cases if case.location}),
                "published_date": article.published_date.isoformat() if article.published_date else None,
            }
            for article in articles
        ],
        "zscore_spikes": zscore_spikes,
        "forecasts": forecasts,
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
    )
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
                "response_format": {"type": "json_object"},
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
            return parsed
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
                        "response_format": {"type": "json_object"},
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
                    return parsed
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
