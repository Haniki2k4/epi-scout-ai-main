"""
Router Custom Alerts - Cho phép mỗi user tạo bộ lọc bài báo riêng theo nhu cầu cá nhân.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import json

from ...core.database import get_db
from ..auth import models as auth_models
from ..news import models as news_models, schemas as news_schemas
from ..auth.security import get_current_active_user
from ...core.logger import get_logger

logger = get_logger("backend.auth.alerts")

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# --- Schemas ---

class AlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    keywords: List[str] = Field(..., min_items=1, description="Danh sách từ khóa lọc")
    location_filter: Optional[str] = Field(default=None, max_length=255)


class AlertUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    keywords: Optional[List[str]] = Field(default=None, min_items=1)
    location_filter: Optional[str] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    id: int
    user_id: int
    name: str
    keywords: List[str]
    location_filter: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertFeedResponse(BaseModel):
    alert_id: int
    alert_name: str
    total: int
    items: List[news_schemas.ArticleDTO]


# --- Helpers ---

def _parse_keywords(keywords_json: str) -> List[str]:
    """Parse JSON string thành list keywords."""
    try:
        result = json.loads(keywords_json)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _alert_to_response(alert: auth_models.UserAlert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        user_id=alert.user_id,
        name=alert.name,
        keywords=_parse_keywords(alert.keywords),
        location_filter=alert.location_filter,
        is_active=alert.is_active,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


# --- Endpoints ---

@router.get("", response_model=List[AlertResponse])
def get_user_alerts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Lấy danh sách tất cả bộ lọc cảnh báo của user hiện tại."""
    alerts = (
        db.query(auth_models.UserAlert)
        .filter(auth_models.UserAlert.user_id == current_user.id)
        .order_by(auth_models.UserAlert.created_at.desc())
        .all()
    )
    return [_alert_to_response(a) for a in alerts]


@router.post("", response_model=AlertResponse, status_code=201)
def create_user_alert(
    body: AlertCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Tạo bộ lọc cảnh báo cá nhân mới."""
    alert = auth_models.UserAlert(
        user_id=current_user.id,
        name=body.name,
        keywords=json.dumps(body.keywords, ensure_ascii=False),
        location_filter=body.location_filter,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    logger.info("Alert created | user_id={} name={}", current_user.id, body.name)
    return _alert_to_response(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
def update_user_alert(
    alert_id: int,
    body: AlertUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Cập nhật bộ lọc cảnh báo."""
    alert = (
        db.query(auth_models.UserAlert)
        .filter(
            auth_models.UserAlert.id == alert_id,
            auth_models.UserAlert.user_id == current_user.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ lọc cảnh báo")

    if body.name is not None:
        alert.name = body.name
    if body.keywords is not None:
        alert.keywords = json.dumps(body.keywords, ensure_ascii=False)
    if body.location_filter is not None:
        alert.location_filter = body.location_filter
    if body.is_active is not None:
        alert.is_active = body.is_active

    db.commit()
    db.refresh(alert)
    return _alert_to_response(alert)


@router.delete("/{alert_id}")
def delete_user_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Xóa bộ lọc cảnh báo."""
    alert = (
        db.query(auth_models.UserAlert)
        .filter(
            auth_models.UserAlert.id == alert_id,
            auth_models.UserAlert.user_id == current_user.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ lọc cảnh báo")

    db.delete(alert)
    db.commit()
    logger.info("Alert deleted | user_id={} alert_id={}", current_user.id, alert_id)
    return {"status": "success", "id": alert_id}


@router.get("/active", response_model=List[news_schemas.ArticleDTO])
def get_active_outbreak_alerts(
    include_filtered: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = (
        db.query(news_models.ArticleIdentity)
        .options(joinedload(news_models.ArticleIdentity.cases))
        .join(news_models.ArticleDetails, news_models.ArticleIdentity.details)
    )
    if include_filtered:
        query = query.filter(news_models.ArticleDetails.is_suspected_false_positive == True)
    else:
        query = query.filter(
            news_models.ArticleDetails.outbreak_relevance_score >= 3,
            news_models.ArticleDetails.is_suspected_false_positive == False,
        )
    return (
        query.order_by(
            news_models.ArticleDetails.outbreak_relevance_score.desc(),
            news_models.ArticleIdentity.published_date.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/important-signals", response_model=List[news_schemas.ArticleDTO])
def get_important_signals(
    hours: int = 24,
    min_score: int = 2,
    db: Session = Depends(get_db),
):
    """Lấy các tín hiệu cảnh báo quan trọng (score >= 2) trong N giờ qua."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = (
        db.query(news_models.ArticleIdentity)
        .options(joinedload(news_models.ArticleIdentity.cases))
        .join(news_models.ArticleDetails, news_models.ArticleIdentity.details)
        .filter(
            news_models.ArticleIdentity.published_date >= since,
            news_models.ArticleDetails.outbreak_relevance_score >= min_score,
            news_models.ArticleDetails.is_suspected_false_positive == False,
        )
        .order_by(news_models.ArticleDetails.outbreak_relevance_score.desc())
    )
    return query.all()


@router.get("/{alert_id}/feed", response_model=AlertFeedResponse)
def get_alert_feed(
    alert_id: int,
    skip: int = 0,
    limit: int = 20,
    include_label: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Lấy feed bài báo phù hợp với bộ lọc cảnh báo.
    Lọc từ DB theo keywords + location_filter của alert đó.
    """
    from ...modules.evaluation.models import ArticleEvaluation

    alert = (
        db.query(auth_models.UserAlert)
        .filter(
            auth_models.UserAlert.id == alert_id,
            auth_models.UserAlert.user_id == current_user.id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ lọc cảnh báo")

    keywords = _parse_keywords(alert.keywords)
    if not keywords:
        return AlertFeedResponse(
            alert_id=alert_id,
            alert_name=alert.name,
            total=0,
            items=[],
        )

    # Xây dựng điều kiện tìm kiếm: keywords_matched chứa ít nhất 1 keyword,
    # kết hợp với DiseaseCase.disease_name để tránh match ngữ cảnh rộng
    # (VD: bài về Ebola không hiện trong bộ lọc "virus" nếu không có DiseaseCase khớp)
    from sqlalchemy import exists, and_, select

    keyword_conditions = []
    for kw in keywords:
        kw_match = news_models.ArticleDetails.keywords_matched.ilike(f"%{kw}%")
        has_matching_case = exists(
            select(news_models.DiseaseCase.id).where(
                and_(
                    news_models.DiseaseCase.article_id == news_models.ArticleIdentity.id,
                    news_models.DiseaseCase.disease_name.ilike(f"%{kw}%"),
                )
            )
        )
        has_any_case = exists(
            select(news_models.DiseaseCase.id).where(
                news_models.DiseaseCase.article_id == news_models.ArticleIdentity.id
            )
        )
        keyword_conditions.append(and_(kw_match, or_(has_matching_case, ~has_any_case)))

    query = (
        db.query(news_models.ArticleIdentity)
        .options(joinedload(news_models.ArticleIdentity.cases))
        .join(news_models.ArticleDetails, news_models.ArticleIdentity.details)
        .filter(or_(*keyword_conditions))
    )

    # Lọc thêm theo location nếu có (dùng DiseaseCase.location thay vì keywords_matched)
    if alert.location_filter:
        location_match = exists(
            select(news_models.DiseaseCase.id).where(
                and_(
                    news_models.DiseaseCase.article_id == news_models.ArticleIdentity.id,
                    news_models.DiseaseCase.location.ilike(f"%{alert.location_filter}%"),
                )
            )
        )
        query = query.filter(location_match)

    total = query.count()
    articles = (
        query.order_by(news_models.ArticleIdentity.published_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Gắn nhãn evaluation nếu được yêu cầu
    if include_label and articles:
        article_ids = [a.id for a in articles]
        evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
        eval_map = {e.article_id: e for e in evals}
        for a in articles:
            e = eval_map.get(a.id)
            if e:
                a.llm_label = e.llm_label
                a.human_label = e.human_label

    return AlertFeedResponse(
        alert_id=alert_id,
        alert_name=alert.name,
        total=total,
        items=articles,
    )
