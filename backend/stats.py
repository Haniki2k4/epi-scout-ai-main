from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models
from datetime import datetime, timedelta

def get_overview_stats(db: Session):
    total_articles = db.query(models.ArticleIdentity).count()
    
    # Sum total cases tracked
    total_cases = db.query(func.sum(models.DiseaseCase.case_count)).scalar() or 0
    
    # Count alerts (articles with 'Cảnh báo' tag)
    # Since tags are in Details, we join.
    alert_count = db.query(models.ArticleIdentity).join(models.ArticleDetails).filter(models.ArticleDetails.tags.like("%Cảnh báo%")).count()
    
    return {
        "total_articles": total_articles,
        "total_cases": total_cases,
        "alert_count": alert_count,
        "last_updated": datetime.utcnow()
    }

def get_trend_data(db: Session, days: int = 7):
    """
    Get case counts by day for the last N days.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    results = db.query(
        func.format(models.DiseaseCase.report_date, 'yyyy-MM-dd').label('date'),
        func.sum(models.DiseaseCase.case_count).label('cases')
    ).filter(models.DiseaseCase.report_date >= start_date)\
     .group_by(func.format(models.DiseaseCase.report_date, 'yyyy-MM-dd'))\
     .all()
     
    # Format for chart
    data = []
    for r in results:
        data.append({"date": r.date, "cases": r.cases})
        
    return data
