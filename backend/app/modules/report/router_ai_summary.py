from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...scheduler import trigger_ai_summary

router = APIRouter(prefix="/api/report", tags=["report-ai-summary"])

REFRESH_LIMIT_SECONDS = 5 * 60
_refresh_by_ip: dict[str, datetime] = {}


@router.get("/daily-summary")
def get_daily_summary(db: Session = Depends(get_db)):
    from .ai_summary import _summary_cache
    now = datetime.utcnow()
    expires_at = _summary_cache.get("expires_at")
    if expires_at and expires_at > now and _summary_cache.get("data"):
        return _summary_cache["data"]
    return {"status": "not_ready", "message": "Chưa có dữ liệu summary, hãy nhấn làm mới để tạo."}


@router.post("/daily-summary/refresh")
def refresh_daily_summary(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.utcnow()
    last_refresh = _refresh_by_ip.get(client_ip)
    if last_refresh and now - last_refresh < timedelta(seconds=REFRESH_LIMIT_SECONDS):
        raise HTTPException(status_code=429, detail="Refresh is rate limited to once every 5 minutes per IP")
    _refresh_by_ip[client_ip] = now

    ok = trigger_ai_summary()
    if not ok:
        raise HTTPException(status_code=429, detail="AI summary đang được tạo, vui lòng đợi.")
    return {"status": "started", "message": "Đang tạo AI summary trong nền..."}
