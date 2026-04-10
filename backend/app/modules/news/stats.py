from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta
from collections import defaultdict


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

    # Sum total cases tracked (using NewsEvent to deduplicate)
    total_cases = db.query(func.sum(models.NewsEvent.case_count)).scalar() or 0

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
    Logic chống cộng luỹ kế và tách riêng ngày:
    - Trong cùng 1 ngày của 1 ổ dịch: Báo lúc 9h (10 ca), 17h (35 ca) -> Lấy một số MAX duy nhất 35.
    - So sánh với ngày hôm qua: Báo (40 ca) -> Lấy (40) trừ đi (35 hôm qua) -> Hôm nay chỉ tăng biểu đồ cột 5 ca mới (Không gộp ngày).
    """
    # 1. Trích xuất cao nhất từng ngày của từng sự kiện
    results = (
        db.query(
            models.ArticleIdentity.event_id,
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            func.max(models.DiseaseCase.case_count).label("day_max")
        )
        .join(models.DiseaseCase, models.DiseaseCase.article_id == models.ArticleIdentity.id)
        .filter(models.ArticleIdentity.event_id.isnot(None))
        .group_by(models.ArticleIdentity.event_id, func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"))
        .order_by(models.ArticleIdentity.event_id, func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"))
        .all()
    )

    # 2. Xử lý logic tách phần "cộng thêm" bằng Python
    daily_net = defaultdict(int)
    prev_max = defaultdict(int)

    for event_id, date_str, day_max in results:
        net_increase = max(0, day_max - prev_max[event_id])
        daily_net[date_str] += net_increase
        prev_max[event_id] = day_max

    # 3. Format dữ liệu trả về cho Chart 7 ngày gần nhất
    start_date = datetime.utcnow() - timedelta(days=days-1) # Đảm bảo mảng lấy đủ days
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    data = []
    for d in target_dates:
        data.append({"date": d, "cases": daily_net[d]})

    return data

def get_heatmap_data(db: Session, days: int = 30):
    start_date = datetime.utcnow() - timedelta(days=days-1)
    results = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("count"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"),
            models.DiseaseCase.disease_name
        )
        .all()
    )
    return [{"date": r.date_str, "disease": r.disease_name, "count": r.count} for r in results]

def get_bow_data(db: Session, days: int = 30):
    start_date = datetime.utcnow() - timedelta(days=days-1)
    results = (
        db.query(
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("count"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(models.DiseaseCase.disease_name)
        .order_by(func.count(func.distinct(models.DiseaseCase.article_id)).desc())
        .limit(50)
        .all()
    )
    return [{"word": r.disease_name, "value": r.count} for r in results]


def get_location_heatmap_data(db: Session, days: int = 30, month: int = None, year: int = None):
    """
    Trả về top địa danh được nhắc đến nhiều nhất cùng thống kê bệnh khi hover.
    Hỗ trợ: rolling N ngày HOẶC lọc theo tháng/năm cụ thể.
    """
    import calendar
    from datetime import date as date_type

    if month and year:
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, last_day, 23, 59, 59)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days - 1)

    # Lấy tổng số bài nhắc theo từng cặp (location, disease_name)
    raw = (
        db.query(
            models.DiseaseCase.location,
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("mentions"),
            func.sum(models.DiseaseCase.case_count).label("total_cases"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.report_date <= end_date,
            models.DiseaseCase.location.isnot(None),
            models.DiseaseCase.location != "",
            models.DiseaseCase.location != "Việt Nam",
            models.DiseaseCase.location.notin_(["unknown", "Unknown", "UNKNOWN"]),
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(models.DiseaseCase.location, models.DiseaseCase.disease_name)
        .all()
    )

    # Gom nhóm theo location
    location_map: dict = {}
    for row in raw:
        loc = row.location
        if loc not in location_map:
            location_map[loc] = {"location": loc, "total_mentions": 0, "total_cases": 0, "diseases": []}
        location_map[loc]["total_mentions"] += row.mentions
        location_map[loc]["total_cases"] += (row.total_cases or 0)
        location_map[loc]["diseases"].append({
            "disease_name": row.disease_name,
            "mentions": row.mentions,
            "cases": row.total_cases or 0,
        })

    # Sort theo tổng nhắc, trả về top 20
    sorted_locations = sorted(location_map.values(), key=lambda x: x["total_mentions"], reverse=True)[:20]
    for loc in sorted_locations:
        loc["diseases"] = sorted(loc["diseases"], key=lambda d: d["mentions"], reverse=True)[:5]

    return sorted_locations


def get_stacked_trend_data(db: Session, days: int = 30):
    """
    Trả về dữ liệu cột chồng theo ngày × top N bệnh.
    Shape: [{ date: "2026-03-30", "Tay chân miệng": 5, "Covid-19": 2, ... }]
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

    # Lấy top 7 bệnh trong khoảng thời gian
    top_diseases_q = (
        db.query(
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("cnt"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(models.DiseaseCase.disease_name)
        .order_by(func.count(func.distinct(models.DiseaseCase.article_id)).desc())
        .limit(7)
        .all()
    )
    top_disease_names = [r.disease_name for r in top_diseases_q]

    if not top_disease_names:
        return []

    # Lấy số ca mỗi bệnh mỗi ngày
    raw = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            models.DiseaseCase.disease_name,
            func.sum(models.DiseaseCase.case_count).label("total_cases"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.in_(top_disease_names),
        )
        .group_by(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"),
            models.DiseaseCase.disease_name,
        )
        .all()
    )

    # Tạo dict ngày → {bệnh: count}
    from collections import defaultdict
    day_map: dict = defaultdict(lambda: {d: 0 for d in top_disease_names})
    for row in raw:
        day_map[row.date_str][row.disease_name] = int(row.total_cases or 0)

    # Build dãy ngày đầy đủ
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    result = []
    for d in target_dates:
        entry = {"date": d}
        entry.update(day_map[d])
        result.append(entry)

    return {"dates": target_dates, "diseases": top_disease_names, "data": result}

