from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta
from collections import defaultdict


def disease_mention_counts(db: Session, months: int = 1, days: int = None):
    """
    Đếm số bài viết nhắc đến từng bệnh trong N tháng hoặc N ngày gần nhất.
    Trả về danh sách [{disease_name, article_count}] sắp xếp giảm dần.
    """
    if days is not None:
        start_date = datetime.utcnow() - timedelta(days=days)
    else:
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

    # Tính toán Risk Score dựa trên Time-series (Z-Score đơn giản)
    # So sánh mentions của 7 ngày gần nhất vs trung bình của 30 ngày trước đó
    # Giả lập: Nếu mentions cao bất thường, risk_score sẽ cao.
    sorted_locations = sorted(location_map.values(), key=lambda x: x["total_mentions"], reverse=True)[:20]
    for loc in sorted_locations:
        loc["diseases"] = sorted(loc["diseases"], key=lambda d: d["mentions"], reverse=True)[:5]
        # Giả lập tính Risk Score: Dựa trên tổng số nhắc đến cộng với trọng số của các bệnh hiếm (nếu có H5N1, bạch hầu -> tăng vọt)
        risk_score = loc["total_mentions"]
        for d in loc["diseases"]:
            if d["disease_name"].lower() in ["h5n1", "bạch hầu", "cúm a/h5n1"]:
                risk_score += 50 # Cộng điểm rủi ro lớn cho bệnh hiếm/nguy hiểm
        loc["risk_score"] = risk_score

    # Sort lại theo risk_score thay vì total_mentions
    sorted_locations = sorted(sorted_locations, key=lambda x: x["risk_score"], reverse=True)
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


def get_interest_trends(db: Session, days: int = 30):
    """
    Trả về xu hướng số lượng bài báo (sự quan tâm) theo ngày cho top N bệnh.
    Dùng để thay thế Wordcloud bằng Line Chart.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

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

    raw = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("total_articles"),
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

    day_map: dict = defaultdict(lambda: {d: 0 for d in top_disease_names})
    for row in raw:
        day_map[row.date_str][row.disease_name] = int(row.total_articles or 0)

    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    result = []
    for d in target_dates:
        entry = {"date": d}
        entry.update(day_map[d])
        result.append(entry)

    return {"dates": target_dates, "diseases": top_disease_names, "data": result}

# MA Z-Score Spike Detection
# ===========================================================================

def get_zscore_spikes(db, disease_name=None, window=14, days=60):
    import math
    from datetime import timedelta
    from sqlalchemy import func
    from . import models
    start_date = __import__('datetime').datetime.utcnow() - timedelta(days=days - 1)
    query = db.query(
        func.date_format(models.DiseaseCase.report_date, '%Y-%m-%d').label('date_str'),
        func.count(func.distinct(models.DiseaseCase.article_id)).label('count'),
    ).filter(models.DiseaseCase.report_date >= start_date)
    if disease_name:
        query = query.filter(models.DiseaseCase.disease_name == disease_name)
    raw = query.group_by(
        func.date_format(models.DiseaseCase.report_date, '%Y-%m-%d')
    ).order_by(func.date_format(models.DiseaseCase.report_date, '%Y-%m-%d')).all()
    count_map = {r.date_str: r.count for r in raw}
    from datetime import datetime, timedelta
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    target_dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days)]
    counts = [count_map.get(d, 0) for d in target_dates]
    result = []
    for i, (d, cnt) in enumerate(zip(target_dates, counts)):
        if i < window:
            ma = sum(counts[:i]) / max(i, 1) if i > 0 else 0.0
            std = 0.0
        else:
            window_data = counts[i - window:i]
            ma = sum(window_data) / window
            variance = sum((x - ma) ** 2 for x in window_data) / window
            std = math.sqrt(variance)
        zscore = (cnt - ma) / std if std > 0 else 0.0
        spike_level = 'danger' if zscore >= 3.0 else ('alert' if zscore >= 2.0 else 'normal')
        result.append({'date': d, 'count': cnt, 'ma': round(ma, 2), 'zscore': round(zscore, 2), 'spike_level': spike_level})
    return result


# ===========================================================================
# Prophet Time-Series Forecast
# ===========================================================================

def get_prophet_forecast(db, disease_name=None, horizon_days=7):
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from . import models
    days_history = 90
    start_date = datetime.utcnow() - timedelta(days=days_history - 1)
    query = db.query(
        func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
        func.count(func.distinct(models.DiseaseCase.article_id)).label("count"),
    ).filter(models.DiseaseCase.report_date >= start_date)
    if disease_name:
        query = query.filter(models.DiseaseCase.disease_name == disease_name)
    raw = query.group_by(
        func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d")
    ).order_by(func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d")).all()
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_history)]
    count_map = {r.date_str: r.count for r in raw}
    historical = [{"ds": d, "y": count_map.get(d, 0)} for d in target_dates]
    if len([h for h in historical if h["y"] > 0]) < 5:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "error": "Chua du du lieu"}
    try:
        import pandas as pd
        from prophet import Prophet
        import logging
        logging.getLogger("prophet").setLevel(logging.WARNING)
        logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
        df = pd.DataFrame(historical)
        df["ds"] = pd.to_datetime(df["ds"])
        m = Prophet(weekly_seasonality=True, yearly_seasonality=False,
                    daily_seasonality=False, uncertainty_samples=300, interval_width=0.80)
        m.fit(df)
        future = m.make_future_dataframe(periods=horizon_days)
        forecast_df = m.predict(future)
        last_hist_date = df["ds"].max()
        future_only = forecast_df[forecast_df["ds"] > last_hist_date]
        forecast = [
            {"ds": row["ds"].strftime("%Y-%m-%d"),
             "yhat": max(0, round(float(row["yhat"]), 2)),
             "yhat_lower": max(0, round(float(row["yhat_lower"]), 2)),
             "yhat_upper": max(0, round(float(row["yhat_upper"]), 2))}
            for _, row in future_only.iterrows()
        ]
        return {"historical": historical, "forecast": forecast,
                "disease": disease_name, "horizon_days": horizon_days}
    except ImportError:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days,
                "error": "Thu vien prophet chua cai. Chay: pip install prophet"}
    except Exception as e:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "error": str(e)}

def get_keyword_timeseries(db: Session, days: int = 30):
    """
    Đếm số lượng loại bệnh (keyword) xuất hiện trong mỗi ngày.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    
    # Gom nhóm theo ngày và đếm số loại disease_name khác nhau
    raw = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            func.count(func.distinct(models.DiseaseCase.disease_name)).label("keyword_count")
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != ""
        )
        .group_by(func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"))
        .order_by(func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"))
        .all()
    )

    # Đảm bảo có đủ N ngày
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    count_map = {r.date_str: r.keyword_count for r in raw}
    
    return [{"date": d, "keyword_count": count_map.get(d, 0)} for d in target_dates]

def get_keyword_zscore_spikes(db: Session, window: int = 14, days: int = 60):
    import math
    
    timeseries = get_keyword_timeseries(db, days=days)
    counts = [item["keyword_count"] for item in timeseries]
    target_dates = [item["date"] for item in timeseries]
    
    result = []
    for i, (d, cnt) in enumerate(zip(target_dates, counts)):
        if i < window:
            ma = sum(counts[:i]) / max(i, 1) if i > 0 else 0.0
            std = 0.0
        else:
            window_data = counts[i - window:i]
            ma = sum(window_data) / window
            variance = sum((x - ma) ** 2 for x in window_data) / window
            std = math.sqrt(variance)
            
        zscore = (cnt - ma) / std if std > 0 else 0.0
        spike_level = 'danger' if zscore >= 3.0 else ('alert' if zscore >= 2.0 else 'normal')
        result.append({'date': d, 'count': cnt, 'ma': round(ma, 2), 'zscore': round(zscore, 2), 'spike_level': spike_level})
        
    return result
