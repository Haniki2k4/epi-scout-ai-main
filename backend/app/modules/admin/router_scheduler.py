"""
Router quản lý Auto Crawler Scheduler - chỉ Admin mới được thao tác.
"""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from ...core.database import get_db
from ..news import models, crawler
from ..auth.security import require_admin_role
from ...core.logger import get_logger

logger = get_logger("backend.admin.scheduler")

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
SCHEDULER_WAKE_SECRET = os.environ.get("SCHEDULER_WAKE_SECRET")


# --- Schemas ---

class SchedulerStatusResponse(BaseModel):
    is_enabled: bool
    interval_hours: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_run_saved_count: int = 0
    scheduler_running: bool


class SchedulerConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    interval_hours: Optional[int] = Field(default=None, ge=1, le=24)


class ManualScanRequest(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# --- Endpoints ---

@router.post("/wake")
def wake_scheduler(x_scheduler_secret: str = Header(default="")):
    """Wake HF Spaces and queue an overdue scan without waiting for the crawl to finish."""
    if not SCHEDULER_WAKE_SECRET:
        raise HTTPException(status_code=503, detail="Scheduler wake endpoint is not configured")
    if not hmac.compare_digest(x_scheduler_secret, SCHEDULER_WAKE_SECRET):
        raise HTTPException(status_code=401, detail="Invalid scheduler wake secret")

    from ... import scheduler as app_scheduler
    scan_queued = app_scheduler.ensure_scheduler_running()
    return {
        "status": "ok",
        "scheduler_running": app_scheduler.get_scheduler().running,
        "scan_queued": scan_queued,
    }


@router.get("/status", response_model=SchedulerStatusResponse)
def get_scheduler_status(
    db: Session = Depends(get_db),
    _=Depends(require_admin_role)
):
    """Lấy trạng thái hiện tại của scheduler (Admin only)."""
    from ... import scheduler as app_scheduler
    config = app_scheduler._get_or_create_config(db)
    sched = app_scheduler.get_scheduler()
    return SchedulerStatusResponse(
        is_enabled=config.is_enabled,
        interval_hours=config.interval_hours,
        last_run_at=config.last_run_at,
        next_run_at=config.next_run_at,
        last_run_saved_count=config.last_run_saved_count,
        scheduler_running=sched.running,
    )


@router.put("/config", response_model=SchedulerStatusResponse)
def update_scheduler_config(
    body: SchedulerConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin_role)
):
    """Cập nhật cấu hình scheduler (bật/tắt, thay đổi chu kỳ). Admin only."""
    from ... import scheduler as app_scheduler
    config = app_scheduler._get_or_create_config(db)

    if body.is_enabled is not None:
        config.is_enabled = body.is_enabled
        logger.info("Scheduler is_enabled updated | is_enabled={}", body.is_enabled)

    if body.interval_hours is not None:
        config.interval_hours = body.interval_hours
        # Áp dụng chu kỳ mới ngay lập tức
        app_scheduler._reschedule_job(app_scheduler.get_scheduler(), body.interval_hours)
        logger.info("Scheduler interval updated | interval_hours={}", body.interval_hours)

    db.commit()
    db.refresh(config)

    sched = app_scheduler.get_scheduler()
    return SchedulerStatusResponse(
        is_enabled=config.is_enabled,
        interval_hours=config.interval_hours,
        last_run_at=config.last_run_at,
        next_run_at=config.next_run_at,
        last_run_saved_count=config.last_run_saved_count,
        scheduler_running=sched.running,
    )


@router.post("/run-now")
async def trigger_manual_scan(
    body: ManualScanRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin_role)
):
    """
    Kích hoạt quét thủ công ngay lập tức. Admin có thể chỉ định khoảng thời gian.
    Nếu không chỉ định → dùng logic tự động (quét từ last_run_at đến now).
    """
    from datetime import timedelta
    import pytz
    from ... import scheduler as app_scheduler

    VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
    config = app_scheduler._get_or_create_config(db)
    now = datetime.now(VN_TZ)

    start_date = body.start_date or config.last_run_at or (now - timedelta(hours=config.interval_hours))
    end_date = body.end_date or now

    logger.info("Manual scan triggered | start={} end={}", start_date, end_date)

    try:
        import asyncio
        def _do_manual_scan():
            res = crawler.scan_news(
                db=db,
                start_date=start_date,
                end_date=end_date,
                keywords_to_scan=None,  # Dùng toàn bộ keywords is_active=True
            )
            config.last_run_at = now
            config.last_run_saved_count = res.saved_trusted_count
            config.last_scan_total_checked = res.total_checked
            config.last_scan_noise_count = res.noise_count
            config.last_scan_irrelevant_count = res.irrelevant_count
            config.last_scan_unsure_count = res.unsure_count
            config.last_scan_duration_seconds = round(res.execution_time or 0)
            config.last_scan_started_at = res.started_at
            db.commit()
            return res

        result = await asyncio.to_thread(_do_manual_scan)

        logger.info("Manual scan completed | saved={}", result.saved_trusted_count)
        return {
            "status": "success",
            "saved_count": result.saved_trusted_count,
            "scan_start": start_date.isoformat(),
            "scan_end": end_date.isoformat(),
            "execution_time": result.execution_time,
            "disease_counts": result.disease_counts,
        }
    except Exception as e:
        logger.error("Manual scan failed | error={}", str(e))
        raise HTTPException(status_code=500, detail=f"Quét thất bại: {str(e)}")
