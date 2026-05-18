from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from .ai_summary import get_cached_daily_summary


router = APIRouter(prefix="/api/report", tags=["report-ai-summary"])

REFRESH_LIMIT_SECONDS = 5 * 60
_refresh_by_ip: dict[str, datetime] = {}


@router.get("/daily-summary")
def get_daily_summary(db: Session = Depends(get_db)):
    return get_cached_daily_summary(db)


@router.post("/daily-summary/refresh")
def refresh_daily_summary(request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    last_refresh = _refresh_by_ip.get(client_ip)
    if last_refresh and now - last_refresh < timedelta(seconds=REFRESH_LIMIT_SECONDS):
        raise HTTPException(status_code=429, detail="Refresh is rate limited to once every 5 minutes per IP")
    _refresh_by_ip[client_ip] = now
    return get_cached_daily_summary(db, force_refresh=True)
