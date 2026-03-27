from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta


def disease_mention_counts(db: Session, months: int = 1):
    """
    Đếm số bài viết nhắc đến từng bệnh trong N tháng gần nhất.
    Trả về danh sách [{disease_name, article_count}] sắp xếp giảm dần.
    """
    months = max(1, min(months, 12))
    start_date = datetime.utcnow() - timedelta(days=months * 30)

    results = (
        db.query(
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("article_count"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(models.DiseaseCase.disease_name)
        .order_by(func.count(func.distinct(models.DiseaseCase.article_id)).desc())
        .all()
    )

    return [{"disease_name": r.disease_name, "article_count": r.article_count} for r in results]


def top_mentions(db: Session, months: int = 1):
    """
    Trả về bệnh được nhắc đến nhiều nhất và số lần nhắc trong N tháng gần nhất.
    """
    counts = disease_mention_counts(db, months)
    if counts:
        return counts[0]
    return {"disease_name": None, "article_count": 0}


def get_overview_stats(db: Session):
    total_articles = db.query(models.ArticleIdentity).count()

    # Sum total cases tracked
    total_cases = db.query(func.sum(models.DiseaseCase.case_count)).scalar() or 0

    # Count alerts (articles with 'Cảnh báo' tag)
    alert_count = (
        db.query(models.ArticleIdentity)
        .join(models.ArticleDetails)
        .filter(models.ArticleDetails.tags.like("%Cảnh báo%"))
        .count()
    )

    # Bệnh được nhắc đến nhiều nhất trong 1 tháng gần nhất
    top = top_mentions(db, months=1)

    return {
        "total_articles": total_articles,
        "total_cases": total_cases,
        "alert_count": alert_count,
        "top_disease": top["disease_name"],
        "top_disease_mentions": top["article_count"],
        "last_updated": datetime.utcnow(),
    }


def get_trend_data(db: Session, days: int = 7):
    """
    Get case counts by day for the last N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    results = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date"),
            func.sum(models.DiseaseCase.case_count).label("cases"),
        )
        .filter(models.DiseaseCase.report_date >= start_date)
        .group_by(func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"))
        .all()
    )

    # Format for chart
    data = []
    for r in results:
        data.append({"date": r.date, "cases": r.cases})

    return data
