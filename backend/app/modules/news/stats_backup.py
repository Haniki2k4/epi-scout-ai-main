from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta
from collections import defaultdict


def disease_mention_counts(db: Session, months: int = 1, days: int = None):
    """
    Äáº¿m sá»‘ bÃ i viáº¿t nháº¯c Ä‘áº¿n tá»«ng bá»‡nh trong N thÃ¡ng hoáº·c N ngÃ y gáº§n nháº¥t.
    Sá»­ dá»¥ng ArticleDetails.keywords_matched Ä‘á»ƒ Ä‘áº¿m táº¥t cáº£ cÃ¡c bÃ i bÃ¡o cÃ³ khá»›p tá»« khÃ³a,
    ká»ƒ cáº£ khi khÃ´ng trÃ­ch xuáº¥t Ä‘Æ°á»£c sá»‘ ca bá»‡nh cá»¥ thá»ƒ (DiseaseCase).
    """
    if days is not None:
        start_date = datetime.utcnow() - timedelta(days=days)
    else:
        months = max(1, min(months, 12))
        start_date = datetime.utcnow() - timedelta(days=months * 30)

    # Láº¥y táº¥t cáº£ keywords_matched cá»§a cÃ¡c bÃ i bÃ¡o trong khoáº£ng thá»i gian
    articles = (
        db.query(models.ArticleDetails.keywords_matched)
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.ArticleDetails.article_id)
        .filter(models.ArticleIdentity.published_date >= start_date)
        .all()
    )

    counts = defaultdict(int)
    for art in articles:
        if art.keywords_matched:
            # TÃ¡ch cÃ¡c keyword báº±ng dáº¥u pháº©y vÃ  chuáº©n hÃ³a
            kws = [k.strip().lower() for k in art.keywords_matched.split(",") if k.strip()]
            # Má»—i bÃ i bÃ¡o chá»‰ tÃ­nh 1 láº§n cho má»—i keyword trong bÃ i Ä‘Ã³
            for kw in set(kws):
                counts[kw] += 1

    results = [{"disease_name": k, "article_count": v} for k, v in counts.items() if k]
    results.sort(key=lambda x: x["article_count"], reverse=True)

    return results
    """
    Äáº¿m sá»‘ bÃ i viáº¿t nháº¯c Ä‘áº¿n tá»«ng bá»‡nh trong N thÃ¡ng hoáº·c N ngÃ y gáº§n nháº¥t.
    Tráº£ vá» danh sÃ¡ch [{disease_name, article_count}] sáº¯p xáº¿p giáº£m dáº§n.
    Theo ngÃ y Ä‘Äƒng bÃ i (published_date) thay vÃ¬ ngÃ y trong ná»™i dung (report_date).
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
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.DiseaseCase.article_id)
        .filter(
            models.ArticleIdentity.published_date >= start_date,
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
    Tráº£ vá» bá»‡nh Ä‘Æ°á»£c nháº¯c Ä‘áº¿n nhiá»u nháº¥t vÃ  sá»‘ láº§n nháº¯c trong N thÃ¡ng gáº§n nháº¥t.
    """
    counts = disease_mention_counts(db, months)
    if counts:
        return counts[0]
    return {"disease_name": None, "article_count": 0}


def get_overview_stats(db: Session):
    # Tá»•ng sá»± kiá»‡n dá»‹ch tá»… má»›i trong 7 ngÃ y
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    total_events_7d = db.query(models.NewsEvent).filter(models.NewsEvent.event_date >= seven_days_ago).count()

    # Sá»‘ lÆ°á»£ng keyword (bá»‡nh) cÃ³ bÃ i bÃ¡o trong hÃ´m nay (theo ngÃ y Ä‘Äƒng bÃ i)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    keywords_today = (
        db.query(func.count(func.distinct(models.DiseaseCase.disease_name)))
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.DiseaseCase.article_id)
        .filter(
            models.ArticleIdentity.published_date >= today_start,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != ""
        )
        .scalar() or 0
    )

    # Sá»‘ lÆ°á»£ng keyword (bá»‡nh) cÃ³ bÃ i bÃ¡o trong 7 ngÃ y (theo ngÃ y Ä‘Äƒng bÃ i)
    keywords_7d = (
        db.query(func.count(func.distinct(models.DiseaseCase.disease_name)))
        .join(models.ArticleIdentity, models.ArticleIdentity.id == models.DiseaseCase.article_id)
        .filter(
            models.ArticleIdentity.published_date >= seven_days_ago,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != ""
        )
        .scalar() or 0
    )

    # Bá»‡nh Ä‘Æ°á»£c nháº¯c Ä‘áº¿n nhiá»u nháº¥t trong 1 thÃ¡ng gáº§n nháº¥t
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
    Logic chá»‘ng cá»™ng luá»¹ káº¿ vÃ  tÃ¡ch riÃªng ngÃ y:
    - Trong cÃ¹ng 1 ngÃ y cá»§a 1 á»• dá»‹ch: BÃ¡o lÃºc 9h (10 ca), 17h (35 ca) -> Láº¥y má»™t sá»‘ MAX duy nháº¥t 35.
    - So sÃ¡nh vá»›i ngÃ y hÃ´m qua: BÃ¡o (40 ca) -> Láº¥y (40) trá»« Ä‘i (35 hÃ´m qua) -> HÃ´m nay chá»‰ tÄƒng biá»ƒu Ä‘á»“ cá»™t 5 ca má»›i (KhÃ´ng gá»™p ngÃ y).
    """
    # 1. TrÃ­ch xuáº¥t cao nháº¥t tá»«ng ngÃ y cá»§a tá»«ng sá»± kiá»‡n
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

    # 2. Xá»­ lÃ½ logic tÃ¡ch pháº§n "cá»™ng thÃªm" báº±ng Python
    daily_net = defaultdict(int)
    prev_max = defaultdict(int)

    for event_id, date_str, day_max in results:
        net_increase = max(0, day_max - prev_max[event_id])
        daily_net[date_str] += net_increase
        prev_max[event_id] = day_max

    # 3. Format dá»¯ liá»‡u tráº£ vá» cho Chart 7 ngÃ y gáº§n nháº¥t
    start_date = datetime.utcnow() - timedelta(days=days-1) # Äáº£m báº£o máº£ng láº¥y Ä‘á»§ days
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
    Tráº£ vá» top Ä‘á»‹a danh Ä‘Æ°á»£c nháº¯c Ä‘áº¿n nhiá»u nháº¥t cÃ¹ng thá»‘ng kÃª bá»‡nh khi hover.
    Há»— trá»£: rolling N ngÃ y HOáº¶C lá»c theo thÃ¡ng/nÄƒm cá»¥ thá»ƒ.
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

    # Láº¥y tá»•ng sá»‘ bÃ i nháº¯c theo tá»«ng cáº·p (location, disease_name)
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
            models.DiseaseCase.location != "Viá»‡t Nam",
            models.DiseaseCase.location.notin_(["unknown", "Unknown", "UNKNOWN"]),
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(models.DiseaseCase.location, models.DiseaseCase.disease_name)
        .all()
    )

    # Gom nhÃ³m theo location
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

    # TÃ­nh toÃ¡n Risk Score dá»±a trÃªn Time-series (Z-Score Ä‘Æ¡n giáº£n)
    # So sÃ¡nh mentions cá»§a 7 ngÃ y gáº§n nháº¥t vs trung bÃ¬nh cá»§a 30 ngÃ y trÆ°á»›c Ä‘Ã³
    # Giáº£ láº­p: Náº¿u mentions cao báº¥t thÆ°á»ng, risk_score sáº½ cao.
    sorted_locations = sorted(location_map.values(), key=lambda x: x["total_mentions"], reverse=True)[:20]
    for loc in sorted_locations:
        loc["diseases"] = sorted(loc["diseases"], key=lambda d: d["mentions"], reverse=True)[:5]
        # Giáº£ láº­p tÃ­nh Risk Score: Dá»±a trÃªn tá»•ng sá»‘ nháº¯c Ä‘áº¿n cá»™ng vá»›i trá»ng sá»‘ cá»§a cÃ¡c bá»‡nh hiáº¿m (náº¿u cÃ³ H5N1, báº¡ch háº§u -> tÄƒng vá»t)
        risk_score = loc["total_mentions"]
        for d in loc["diseases"]:
            if d["disease_name"].lower() in ["h5n1", "báº¡ch háº§u", "cÃºm a/h5n1"]:
                risk_score += 50 # Cá»™ng Ä‘iá»ƒm rá»§i ro lá»›n cho bá»‡nh hiáº¿m/nguy hiá»ƒm
        loc["risk_score"] = risk_score

    # Sort láº¡i theo risk_score thay vÃ¬ total_mentions
    sorted_locations = sorted(sorted_locations, key=lambda x: x["risk_score"], reverse=True)
    return sorted_locations


def get_stacked_trend_data(db: Session, days: int = 30):
    """
    Tráº£ vá» dá»¯ liá»‡u cá»™t chá»“ng theo ngÃ y Ã— top N bá»‡nh.
    Shape: [{ date: "2026-03-30", "Tay chÃ¢n miá»‡ng": 5, "Covid-19": 2, ... }]
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

    # Láº¥y top 7 bá»‡nh trong khoáº£ng thá»i gian
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

    # Láº¥y sá»‘ ca má»—i bá»‡nh má»—i ngÃ y
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

    # Táº¡o dict ngÃ y â†’ {bá»‡nh: count}
    from collections import defaultdict
    day_map: dict = defaultdict(lambda: {d: 0 for d in top_disease_names})
    for row in raw:
        day_map[row.date_str][row.disease_name] = int(row.total_cases or 0)

    # Build dÃ£y ngÃ y Ä‘áº§y Ä‘á»§
    target_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    result = []
    for d in target_dates:
        entry = {"date": d}
        entry.update(day_map[d])
        result.append(entry)

    return {"dates": target_dates, "diseases": top_disease_names, "data": result}


def get_interest_trends(db: Session, days: int = 30):
    """
    Tráº£ vá» xu hÆ°á»›ng sá»‘ lÆ°á»£ng bÃ i bÃ¡o (sá»± quan tÃ¢m) theo ngÃ y cho top N bá»‡nh.
    DÃ¹ng ArticleDetails.keywords_matched Ä‘á»ƒ pháº£n Ã¡nh Ä‘Ãºng sá»‘ bÃ i bÃ¡o nháº¯c Ä‘áº¿n.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)

    # 1. TÃ¬m Top 7 bá»‡nh dá»±a trÃªn sá»‘ láº§n nháº¯c Ä‘áº¿n trong khoáº£ng thá»i gian
    all_mentions = disease_mention_counts(db, days=days)
    top_disease_names = [m["disease_name"] for m in all_mentions[:7]]

    if not top_disease_names:
        return []

    # 2. Láº¥y dá»¯ liá»‡u theo ngÃ y
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
    """
    Tráº£ vá» xu hÆ°á»›ng sá»‘ lÆ°á»£ng bÃ i bÃ¡o (sá»± quan tÃ¢m) theo ngÃ y cho top N bá»‡nh.
    DÃ¹ng Ä‘á»ƒ thay tháº¿ Wordcloud báº±ng Line Chart.
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
            
        if std > 0:
            zscore = (cnt - ma) / std
        else:
            # Epsilon smoothing / spike heuristic khi variance = 0
            if cnt > ma:
                # Náº¿u cÃ³ ca máº¯c Ä‘á»™t biáº¿n sau 1 thá»i gian dÃ i im láº·ng
                zscore = 2.0 + (cnt - ma) # Äáº£m báº£o zscore tá»‘i thiá»ƒu lÃ  2.0 (má»©c alert)
            else:
                zscore = 0.0
                
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
        import numpy as np
        
        # 1. Train/Test Split Ä‘á»ƒ tÃ­nh Metrics
        test_days = 14
        metrics = {"mae": None, "rmse": None, "eval_method": "not_enough_data"}
        
        if len(df) > test_days * 2:
            train_df = df.iloc[:-test_days]
            test_df = df.iloc[-test_days:]
            
            # Train model riÃªng Ä‘á»ƒ evaluate
            m_eval = Prophet(weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False)
            m_eval.fit(train_df)
            eval_future = m_eval.make_future_dataframe(periods=test_days)
            eval_forecast = m_eval.predict(eval_future)
            
            test_yhat = eval_forecast.iloc[-test_days:]['yhat'].values
            test_y = test_df['y'].values
            
            mae = np.mean(np.abs(test_y - test_yhat))
            rmse = np.sqrt(np.mean((test_y - test_yhat)**2))
            metrics = {
                "mae": round(float(mae), 2),
                "rmse": round(float(rmse), 2),
                "eval_method": f"test_last_{test_days}_days"
            }
            
        # 2. Huáº¥n luyá»‡n model chÃ­nh trÃªn toÃ n bá»™ dá»¯ liá»‡u
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
                "disease": disease_name, "horizon_days": horizon_days, "metrics": metrics}
    except ImportError:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days,
                "error": "Thu vien prophet chua cai. Chay: pip install prophet"}
    except Exception as e:
        return {"historical": historical, "forecast": [], "disease": disease_name,
                "horizon_days": horizon_days, "error": str(e)}

def get_keyword_timeseries(db: Session, days: int = 30):
    """
    Äáº¿m sá»‘ lÆ°á»£ng loáº¡i bá»‡nh (keyword) xuáº¥t hiá»‡n trong má»—i ngÃ y.
    """
    start_date = datetime.utcnow() - timedelta(days=days - 1)
    
    # Gom nhÃ³m theo ngÃ y vÃ  Ä‘áº¿m sá»‘ loáº¡i disease_name khÃ¡c nhau
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

    # Äáº£m báº£o cÃ³ Ä‘á»§ N ngÃ y
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
            
        if std > 0:
            zscore = (cnt - ma) / std
        else:
            if cnt > ma:
                zscore = 2.0 + (cnt - ma)
            else:
                zscore = 0.0
                
        spike_level = 'danger' if zscore >= 3.0 else ('alert' if zscore >= 2.0 else 'normal')
        result.append({'date': d, 'count': cnt, 'ma': round(ma, 2), 'zscore': round(zscore, 2), 'spike_level': spike_level})
        
    return result


def get_keyword_bubble_data(db: Session, days: int = 30, window: int = 14):
    import math

    start_date = datetime.utcnow() - timedelta(days=days - 1)
    raw = (
        db.query(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d").label("date_str"),
            models.DiseaseCase.disease_name,
            func.count(func.distinct(models.DiseaseCase.article_id)).label("article_count"),
        )
        .filter(
            models.DiseaseCase.report_date >= start_date,
            models.DiseaseCase.disease_name.isnot(None),
            models.DiseaseCase.disease_name != "",
        )
        .group_by(
            func.date_format(models.DiseaseCase.report_date, "%Y-%m-%d"),
            models.DiseaseCase.disease_name,
        )
        .all()
    )

    dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    disease_names = sorted({row.disease_name for row in raw})
    counts_by_key = {
        (row.disease_name, row.date_str): int(row.article_count or 0)
        for row in raw
    }

    result = []
    for disease_name in disease_names:
        counts = [counts_by_key.get((disease_name, date), 0) for date in dates]
        for index, date in enumerate(dates):
            count = counts[index]
            if count <= 0:
                continue
            if index < window:
                baseline = counts[:index]
            else:
                baseline = counts[index - window:index]
            ma = sum(baseline) / max(len(baseline), 1) if baseline else 0.0
            variance = sum((item - ma) ** 2 for item in baseline) / max(len(baseline), 1) if baseline else 0.0
            std = math.sqrt(variance)
            if std > 0:
                zscore = (count - ma) / std
            elif count > ma:
                zscore = 2.0 + (count - ma)
            else:
                zscore = 0.0
            spike_level = "danger" if zscore >= 3.0 else ("alert" if zscore >= 2.0 else "normal")
            previous_count = counts[index - 1] if index > 0 else 0
            growth_rate = (count - previous_count) / previous_count if previous_count > 0 else (1.0 if count > 0 else 0.0)
            result.append({
                "keyword": disease_name,
                "date": date,
                "article_count": count,
                "zscore": round(zscore, 2),
                "spike_level": spike_level,
                "growth_rate": round(growth_rate, 2),
            })
    return result
