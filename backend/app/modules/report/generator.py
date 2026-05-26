"""
Report Generator - Truy vấn dữ liệu từ DB để tạo nội dung báo cáo.
"""
import json
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta

from ..news import models, stats
from ..auth.models import UserAlert


def get_report_data(
    db: Session,
    scope_hours: int = 72,
    alert: UserAlert = None,
) -> dict:
    """
    Lấy dữ liệu thô từ DB để render báo cáo.
    
    Args:
        db: Database session
        scope_hours: Khoảng thời gian báo cáo (giờ). Mặc định 72h = 3 ngày.
    
    Returns:
        dict chứa toàn bộ dữ liệu cần thiết để render báo cáo.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(hours=scope_hours)

    # --- Lọc theo Alert (nếu có) ---
    keyword_filters = []
    location_filter = None
    if alert:
        try:
            keywords = json.loads(alert.keywords)
            if isinstance(keywords, list):
                keyword_filters = [k.lower() for k in keywords if k.strip()]
        except:
            pass
        if alert.location_filter and alert.location_filter.strip():
            location_filter = alert.location_filter.strip().lower()

    # --- Thống kê tổng quan ---
    # Tạm thời overview giữ nguyên (toàn bộ hệ thống) hoặc nếu có alert thì báo cáo overview cho toàn hệ thống
    overview = stats.get_overview_stats(db)

    # --- Top sự kiện nổi bật trong khoảng thời gian ---
    events_query = db.query(models.NewsEvent).filter(models.NewsEvent.event_date >= start_date)
    if location_filter:
        events_query = events_query.filter(models.NewsEvent.location.ilike(f"%{location_filter}%"))
    if keyword_filters:
        or_conditions = [models.NewsEvent.disease_name.ilike(f"%{k}%") for k in keyword_filters]
        events_query = events_query.filter(or_(*or_conditions))

    top_events = events_query.order_by(models.NewsEvent.case_count.desc()).limit(10).all()

    # --- Top dịch bệnh theo số bài báo ---
    scope_days = max(1, scope_hours // 24)
    top_diseases = stats.disease_mention_counts(db, days=scope_days)

    # --- Bài báo có tag cảnh báo ---
    alert_query = db.query(models.ArticleIdentity).join(models.ArticleDetails).filter(
        models.ArticleDetails.tags.like("%Cảnh báo%"),
        models.ArticleIdentity.published_date >= start_date,
    )
    if keyword_filters:
        or_conditions = [
            models.ArticleDetails.keywords_matched.ilike(f"%{k}%") for k in keyword_filters
        ]
        alert_query = alert_query.filter(or_(*or_conditions))

    alert_articles = alert_query.order_by(models.ArticleIdentity.published_date.desc()).limit(5).all()

    # --- Bài báo mới nhất ---
    recent_query = db.query(models.ArticleIdentity).filter(models.ArticleIdentity.published_date >= start_date)
    if keyword_filters:
        # Lọc bằng cách join bảng Details nếu cần tìm theo keyword (do keywords_matched nằm ở Details)
        recent_query = recent_query.join(models.ArticleDetails)
        or_conditions = [
            models.ArticleDetails.keywords_matched.ilike(f"%{k}%") for k in keyword_filters
        ]
        recent_query = recent_query.filter(or_(*or_conditions))

    recent_articles = recent_query.order_by(models.ArticleIdentity.published_date.desc()).limit(20).all()

    return {
        "generated_at": end_date,
        "scope_hours": scope_hours,
        "start_date": start_date,
        "end_date": end_date,
        "overview": overview,
        "top_events": top_events,
        "top_diseases": top_diseases,
        "alert_articles": alert_articles,
        "recent_articles": recent_articles,
    }
