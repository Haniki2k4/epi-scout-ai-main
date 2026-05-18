from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta
from collections import defaultdict


def disease_mention_counts(db: Session, months: int = 1, days: int = None):
    """
    Đếm số bài viết nhắc đến từng bệnh trong N tháng hoặc N ngày gần nhất.
    Sử dụng ArticleDetails.keywords_matched để đếm tất cả các bài báo có khớp từ khóa,
    kể cả khi không trích xuất được số ca bệnh cụ thể (DiseaseCase).
    """
    if days is not None:
        start_date = datetime.utcnow() - timedelta(days=days)
    else:
        months = max(1, min(months, 12))
        start_date = datetime.utcnow() - timedelta(days=months * 30)

    # Lấy tất cả keywords_matched của các bài báo trong khoảng thời gian
    articles = (
        db.query(models.ArticleDetails.keywords_matched)
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )

    counts = defaultdict(int)
    for art in articles:
        if art.keywords_matched:
            # Tách các keyword bằng dấu phẩy và chuẩn hóa
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            # Mỗi bài báo chỉ tính 1 lần cho mỗi keyword trong bài đó
            for kw in set(kws):
                counts[kw] += 1

    results = [{"disease_name": k, "article_count": v} for k, v in counts.items() if k]
    results.sort(key=lambda x: x["article_count"], reverse=True)

    return results


def top_mentions(db: Session, months: int = 1):
    """
    Trả về bệnh được nhắc đến nhiều nhất và số lần nhắc trong N tháng gần nhất.
    """
    counts = disease_mention_counts(db, months)
    if counts:
        return counts[0]
    return {"disease_name": None, "article_count": 0}


def get_overview_stats(db: Session):
    # Tổng sự kiện dịch tễ mới trong 7 ngày
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    total_events_7d = db.query(models.NewsEvent).filter(models.NewsEvent.event_date >= seven_days_ago).count()

    # Số lượng keyword (bệnh) có bài báo trong hôm nay
    today_mentions = disease_mention_counts(db, days=1)
    keywords_today = len([m for m in today_mentions if m["article_count"] > 0])

    # Số lượng keyword (bệnh) có bài báo trong 7 ngày
    seven_day_mentions = disease_mention_counts(db, days=7)
    keywords_7d = len([m for m in seven_day_mentions if m["article_count"] > 0])

    # Bệnh được nhắc đến nhiều nhất trong 1 tháng gần nhất
    top = top_mentions(db, months=1)

    return {
        "total_events_7d": total_events_7d,
        "keywords_today": keywords_today,
        "keywords_7d": keywords_7d,
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
    sorted_locations = sorted(location_map.values(), key=lambda x: x["total_mentions"], reverse=True)[:20]
    for loc in sorted_locations:
        loc["diseases"] = sorted(loc["diseases"], key=lambda d: d["mentions"], reverse=True)[:5]
        risk_score = loc["total_mentions"]
        for d in loc["diseases"]:
            if d["disease_name"].lower() in ["h5n1", "bạch hầu", "cúm a/h5n1"]:
                risk_score += 50
        loc["risk_score"] = risk_score

    sorted_locations = sorted(sorted_locations, key=lambda x: x["risk_score"], reverse=True)
    return sorted_locations


def get_stacked_trend_data(db: Session, days: int = 30):
    """
    Trả về dữ liệu cột chồng theo ngày × top N bệnh.
    Shape: [{ date: "2026-03-30", "Tay chân miệng": 5, "Covid-19": 2, ... }]
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

    # Lấy top 7 bệnh trong khoảng thời gian dựa trên ArticleDetails.keywords_matched
    all_mentions = disease_mention_counts(db, days=days)
    top_disease_names = [m["disease_name"] for m in all_mentions[:7]]

    if not top_disease_names:
        return {"dates": [], "diseases": [], "data": []}

    # Lấy số ca mỗi bệnh mỗi ngày (Vẫn lấy từ DiseaseCase vì đây là biểu đồ số ca)
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

    day_map: dict = defaultdict(lambda: {d: 0 for d in top_disease_names})
    for row in raw:
        day_map[row.date_str][row.disease_name] = int(row.total_cases or 0)

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
    Dùng ArticleDetails.keywords_matched để phản ánh đúng số bài báo nhắc đến.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

    all_mentions = disease_mention_counts(db, days=days)
    top_disease_names = [m["disease_name"] for m in all_mentions[:7]]

    if not top_disease_names:
        return {"dates": [], "diseases": [], "data": []}

    articles = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            models.ArticleDetails.keywords_matched
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )

    day_map: dict = defaultdict(lambda: {d: 0 for d in top_disease_names})
    for row in articles:
        if row.keywords_matched:
            kws = [k.strip().lower() for k in row.keywords_matched.split(",") if k.strip()]
            for kw in set(kws):
                if kw in top_disease_names:
                    day_map[row.date_str][kw] += 1

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
    """
    Phát hiện đột biến số lượng bài báo nhắc đến bệnh (Z-Score).
    Dùng ArticleDetails.keywords_matched để đồng bộ với các biểu đồ khác.
    """
    import math
    start_date = datetime.utcnow() - timedelta(days=days + window) # Lấy dư để tính MA cho ngày đầu tiên
    
    articles = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            models.ArticleDetails.keywords_matched
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )
    
    # Đếm mentions theo ngày
    daily_counts = defaultdict(int)
    for art in articles:
        if art.keywords_matched:
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            if not disease_name or disease_name.lower() in kws:
                daily_counts[art.date_str] += 1
                
    target_dates = [(datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days + window)]
    counts = [daily_counts[d] for d in target_dates]
    
    result = []
    # Chỉ trả về dữ liệu của `days` ngày gần nhất
    for i in range(window, len(counts)):
        d = target_dates[i]
        cnt = counts[i]
        
        window_data = counts[i - window:i]
        ma = sum(window_data) / window
        variance = sum((x - ma) ** 2 for x in window_data) / window
        std = math.sqrt(variance)
        
        if std > 0:
            zscore = (cnt - ma) / std
        else:
            zscore = 2.0 + (cnt - ma) if cnt > ma else 0.0
            
        spike_level = 'danger' if zscore >= 3.0 else ('alert' if zscore >= 2.0 else 'normal')
        result.append({
            'date': d, 
            'count': cnt, 
            'ma': round(ma, 2), 
            'zscore': round(zscore, 2), 
            'spike_level': spike_level
        })
    return result


# ===========================================================================
# Prophet Time-Series Forecast
# ===========================================================================

def get_prophet_forecast(db, disease_name=None, horizon_days=7):
    """
    Dự báo xu hướng nhắc đến bài báo bằng Prophet.
    Dùng ArticleDetails.keywords_matched.
    """
    days_history = 90
    start_date = datetime.utcnow() - timedelta(days=days_history + 14)
    
    articles = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            models.ArticleDetails.keywords_matched
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )
    
    daily_counts = defaultdict(int)
    for art in articles:
        if art.keywords_matched:
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            if not disease_name or disease_name.lower() in kws:
                daily_counts[art.date_str] += 1
                
    target_dates = [(datetime.utcnow() - timedelta(days=days_history - 1 - i)).strftime("%Y-%m-%d") for i in range(days_history)]
    historical = [{"ds": d, "y": daily_counts[d]} for d in target_dates]
    
    if len([h for h in historical if h["y"] > 0]) < 5:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "error": "Chưa đủ dữ liệu để dự báo"}
    try:
        import pandas as pd
        from prophet import Prophet
        import logging
        import numpy as np
        logging.getLogger("prophet").setLevel(logging.WARNING)
        
        df = pd.DataFrame(historical)
        df["ds"] = pd.to_datetime(df["ds"])
        
        # Train model chính
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
                "disease": disease_name, "horizon_days": horizon_days, "metrics": {}}
    except Exception as e:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "error": str(e)}

def get_keyword_timeseries(db: Session, days: int = 30):
    """
    Đếm số lượng loại bệnh (keyword) xuất hiện trong mỗi ngày từ ArticleDetails.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    
    articles = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            models.ArticleDetails.keywords_matched
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )
    
    day_keywords = defaultdict(set)
    for art in articles:
        if art.keywords_matched:
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            for kw in kws:
                day_keywords[art.date_str].add(kw)
                
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    return [{"date": d, "keyword_count": len(day_keywords[d])} for d in target_dates]

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
            
        zscore = (cnt - ma) / std if std > 0 else (2.0 + (cnt - ma) if cnt > ma else 0.0)
        spike_level = 'danger' if zscore >= 3.0 else ('alert' if zscore >= 2.0 else 'normal')
        result.append({'date': d, 'count': cnt, 'ma': round(ma, 2), 'zscore': round(zscore, 2), 'spike_level': spike_level})
    return result


def get_keyword_bubble_data(db: Session, days: int = 30, window: int = 14):
    """
    Dữ liệu bubble chart dựa trên số lần nhắc đến từ ArticleDetails.
    """
    import math
    start_date = datetime.utcnow() - timedelta(days=days + window)
    
    articles = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            models.ArticleDetails.keywords_matched
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )
    
    # disease -> date -> count
    data_map = defaultdict(lambda: defaultdict(int))
    all_diseases = set()
    
    for art in articles:
        if art.keywords_matched:
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            for kw in set(kws):
                data_map[kw][art.date_str] += 1
                all_diseases.add(kw)
                
    dates = [(datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d") for i in range(days)]
    full_dates = [(datetime.utcnow() - timedelta(days=days + window - 1 - i)).strftime("%Y-%m-%d") for i in range(days + window)]
    
    result = []
    for disease_name in all_diseases:
        all_counts = [data_map[disease_name][d] for d in full_dates]
        
        for i in range(window, len(all_counts)):
            date = full_dates[i]
            count = all_counts[i]
            if count <= 0: continue
            
            baseline = all_counts[i-window:i]
            ma = sum(baseline) / window
            variance = sum((x - ma) ** 2 for x in baseline) / window
            std = math.sqrt(variance)
            
            zscore = (count - ma) / std if std > 0 else (2.0 + (count - ma) if count > ma else 0.0)
            spike_level = "danger" if zscore >= 3.0 else ("alert" if zscore >= 2.0 else "normal")
            
            prev_count = all_counts[i-1]
            growth_rate = (count - prev_count) / prev_count if prev_count > 0 else (1.0 if count > 0 else 0.0)
            
            result.append({
                "keyword": disease_name,
                "date": date,
                "article_count": count,
                "zscore": round(zscore, 2),
                "spike_level": spike_level,
                "growth_rate": round(growth_rate, 2),
            })
    return result
