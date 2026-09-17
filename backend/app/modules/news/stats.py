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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
    total_events_7d = db.query(models.NewsEvent).filter(models.NewsEvent.event_date >= seven_days_ago, models.NewsEvent.status != "rejected").count()
    verified_events_7d = db.query(models.NewsEvent).filter(models.NewsEvent.event_date >= seven_days_ago, models.NewsEvent.status == "verified_event").count()

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
        "verified_events_7d": verified_events_7d,
        "keywords_today": keywords_today,
        "keywords_7d": keywords_7d,
        "top_disease": top["disease_name"],
        "top_disease_mentions": top["article_count"],
        "last_updated": datetime.utcnow(),
    }


def get_trend_data(db: Session, days: int = 7):
    """Daily article mentions. Keep `cases` for one API transition period."""
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    rows = (
        db.query(
            func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d").label("date_str"),
            func.count(models.ArticleIdentity.id).label("mentions"),
        )
        .filter(models.ArticleIdentity.published_date >= start_date)
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
        .group_by(func.date_format(models.ArticleIdentity.published_date, "%Y-%m-%d"))
        .all()
    )
    counts = {row.date_str: row.mentions for row in rows}
    return [
        {
            "date": day,
            "cases": counts.get(day, 0),
            "mention_count": counts.get(day, 0),
            "metric_type": "mention_count",
        }
        for day in (
            (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        )
    ]

def get_heatmap_data(db: Session, days: int = 30):
    """Daily article mentions by disease; legacy case rows are not a time series."""
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    rows = (
        db.query(models.ArticleIdentity.published_date, models.ArticleDetails.keywords_matched)
        .join(models.ArticleDetails, models.ArticleDetails.article_id == models.ArticleIdentity.id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
        .all()
    )
    counts = defaultdict(int)
    for published_date, keywords in rows:
        if published_date and keywords:
            for disease in {item.strip() for item in keywords.split(",") if item.strip()}:
                counts[(published_date.strftime("%Y-%m-%d"), disease)] += 1
    return [
        {"date": day, "disease": disease, "count": count}
        for (day, disease), count in sorted(counts.items())
    ]


def get_location_heatmap_data(db: Session, days: int = 30, month: int = None, year: int = None):
    """Article mentions by event location; do not sum source claims across articles."""
    import calendar

    if month and year:
        _, last_day = calendar.monthrange(year, month)
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, last_day, 23, 59, 59)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days - 1)

    rows = (
        db.query(
            models.NewsEvent.location,
            models.NewsEvent.disease_name,
            func.count(func.distinct(models.ArticleIdentity.id)).label("mentions"),
        )
        .join(models.ArticleIdentity, models.ArticleIdentity.event_id == models.NewsEvent.id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .filter(models.ArticleIdentity.published_date <= end_date)
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
        .filter(models.NewsEvent.status.notin_(["rejected", "closed"]))
        .filter(models.NewsEvent.location.isnot(None))
        .filter(models.NewsEvent.location.notin_(["", "Việt Nam", "unknown", "Unknown", "UNKNOWN"]))
        .group_by(models.NewsEvent.location, models.NewsEvent.disease_name)
        .all()
    )
    location_map: dict = {}
    for row in rows:
        item = location_map.setdefault(row.location, {
            "location": row.location, "total_mentions": 0, "total_cases": None, "diseases": [],
        })
        item["total_mentions"] += row.mentions
        item["diseases"].append({
            "disease_name": row.disease_name, "mentions": row.mentions, "cases": None,
        })

    locations = sorted(location_map.values(), key=lambda item: item["total_mentions"], reverse=True)[:20]
    for item in locations:
        item["diseases"] = sorted(item["diseases"], key=lambda disease: disease["mentions"], reverse=True)[:5]
        item["risk_score"] = item["total_mentions"] + sum(
            50 for disease in item["diseases"]
            if disease["disease_name"].lower() in {"h5n1", "bạch hầu", "cúm a/h5n1"}
        )
    return sorted(locations, key=lambda item: item["risk_score"], reverse=True)

def get_stacked_trend_data(db: Session, days: int = 30):
    """Stacked chart uses article mentions, never summed source claims."""
    return get_interest_trends(db, days)

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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
            'count': cnt, 'mention_count': cnt, 'metric_type': 'mention_count',
            'ma': round(ma, 2), 
            'std': round(std, 2),
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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
                "horizon_days": horizon_days, "metric_type": "mention_count", "error": "Chưa đủ dữ liệu để dự báo"}
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

        # Calculate RMSE/MAE using time-based evaluation:
        # Train on first 80%, predict last 20%
        split_idx = max(2, int(len(df) * 0.8))
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        if len(test_df) >= 2:
            eval_model = Prophet(weekly_seasonality=True, yearly_seasonality=False,
                                 daily_seasonality=False, interval_width=0.80)
            eval_model.fit(train_df)
            eval_future = eval_model.make_future_dataframe(periods=len(test_df))
            eval_forecast = eval_model.predict(eval_future)
            eval_preds = eval_forecast[["ds", "yhat"]].tail(len(test_df))
            actuals = test_df["y"].values
            preds = eval_preds["yhat"].values
            mae = float(np.mean(np.abs(actuals - preds)))
            rmse = float(np.sqrt(np.mean((actuals - preds) ** 2)))
        else:
            mae = 0
            rmse = 0

        return {"historical": historical, "forecast": forecast,
                "disease": disease_name, "horizon_days": horizon_days, "metric_type": "mention_count",
                "metrics": {"mae": round(mae, 2), "rmse": round(rmse, 2), "eval_method": "Train 80% / Test 20%"}}
    except Exception as e:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "metric_type": "mention_count", "error": str(e)}

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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
        .filter(models.ArticleIdentity.is_excluded.isnot(True))
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
