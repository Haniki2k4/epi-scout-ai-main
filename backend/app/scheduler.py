"""
Auto Crawler Scheduler - APScheduler integration
Tự động quét bài báo theo chu kỳ cấu hình bởi Admin.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import pytz

from .core.database import SessionLocal
from .modules.news import crawler, models
from .modules.auth import models as auth_models
from .modules.report import email_sender, generator, docx_builder, excel_builder
from .core.logger import get_logger

logger = get_logger("backend.scheduler")

# Múi giờ Việt Nam
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Singleton scheduler
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=VN_TZ)
    return _scheduler


def _get_or_create_config(db) -> models.SchedulerConfig:
    """Lấy hoặc tạo mới bản ghi cấu hình scheduler (singleton id=1)."""
    config = db.query(models.SchedulerConfig).filter(models.SchedulerConfig.id == 1).first()
    if not config:
        config = models.SchedulerConfig(
            id=1,
            is_enabled=True,
            interval_hours=6,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


import asyncio

async def run_scheduled_scan() -> None:
    """
    Job được APScheduler gọi định kỳ.
    Quét từ last_run_at đến now, dùng toàn bộ keyword is_active=True.
    Chạy trong thread riêng để không block event loop (và các request đăng nhập).
    """
    def _do_scan():
        with SessionLocal() as db:
            try:
                config = _get_or_create_config(db)

                if not config.is_enabled:
                    logger.info("Auto-scan skipped | reason=scheduler_disabled")
                    return

                now = datetime.now(VN_TZ)
                # Quét từ lần chạy cuối (hoặc mặc định 6h trước nếu chạy lần đầu)
                start_date = config.last_run_at or (now - timedelta(hours=config.interval_hours))

                logger.info(
                    "Auto-scan started | start_date={} end_date={}",
                    start_date.strftime("%Y-%m-%d %H:%M"),
                    now.strftime("%Y-%m-%d %H:%M"),
                )

                # keywords_to_scan=None → crawler sẽ dùng tất cả keyword is_active=True
                result = crawler.scan_news(
                    db=db,
                    start_date=start_date,
                    end_date=now,
                    keywords_to_scan=None,
                )

                # Cập nhật config sau khi chạy xong
                config.last_run_at = now
                config.last_run_saved_count = result.saved_trusted_count
                config.last_scan_total_checked = result.total_checked
                config.last_scan_noise_count = result.noise_count
                config.last_scan_irrelevant_count = result.irrelevant_count
                config.last_scan_unsure_count = result.unsure_count
                config.last_scan_duration_seconds = round(result.execution_time or 0)
                config.last_scan_started_at = result.started_at
                config.next_run_at = now + timedelta(hours=config.interval_hours)
                db.commit()

                logger.info(
                    "Auto-scan completed | saved={} next_run={}",
                    result.saved_trusted_count,
                    config.next_run_at.strftime("%Y-%m-%d %H:%M"),
                )

            except Exception as e:
                logger.error("Auto-scan failed | error={}", str(e))
                
    await asyncio.to_thread(_do_scan)


async def send_personal_email_job(user_id: int) -> dict | None:
    """
    Job gửi email cho một người dùng cụ thể theo cấu hình của họ.
    Trả về dict kết quả để caller (send-report-now) kiểm tra lỗi.
    """
    with SessionLocal() as db:
        try:
            user = db.query(auth_models.User).filter(auth_models.User.id == user_id).first()
            if not user or not user.is_active or not user.email:
                logger.warning("Personal email skipped | user_id={} reason=missing_email_or_inactive", user_id)
                return None

            logger.info("Personal email job started | user_id={}", user_id)

            # --- 1. Lọc nội dung nếu có bộ lọc cá nhân ---
            # Lưu ý: Cần update generator.get_report_data để hỗ trợ filter_keywords
            # Tạm thời cứ tạo báo cáo mặc định 24h
            scope_hours = 24
            
            # Nếu user có chọn bộ lọc, ta sẽ lấy thông tin bộ lọc đó (Sẽ triển khai sau ở generator)
            alert = None
            if user.report_filter_id:
                alert = db.query(auth_models.UserAlert).filter(auth_models.UserAlert.id == user.report_filter_id).first()
            
            report_data = generator.get_report_data(db, scope_hours=scope_hours, alert=alert)
            docx_bytes = docx_builder.build_word_report(report_data)
            excel_bytes = excel_builder.build_ebs_excel(report_data)

            # 3. Gửi
            result = email_sender.send_report_email(
                docx_bytes=docx_bytes,
                excel_bytes=excel_bytes,
                report_date=report_data["generated_at"],
                custom_recipients=[user.email],
                report_data=report_data,
            )
            
            logger.info("Personal email completed | user_id={} success={}", user_id, result["success"])
            return result

        except Exception as e:
            logger.error("Personal email failed | user_id={} error={}", user_id, str(e))
            return {"success": False, "message": str(e), "recipient_count": 0}
        finally:
            db.close()


def update_user_email_schedule(user_id: int, schedule_type: str, schedule_time: str, schedule_day: int) -> None:
    """Đăng ký hoặc xóa job gửi email cho user"""
    scheduler = get_scheduler()
    job_id = f"email_user_{user_id}"
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    if schedule_type == "none" or not schedule_time:
        return

    try:
        hour, minute = map(int, schedule_time.split(":"))
    except ValueError:
        return
        
    trigger = None
    if schedule_type == "daily":
        trigger = CronTrigger(hour=hour, minute=minute, timezone=VN_TZ)
    elif schedule_type == "weekly" and schedule_day is not None:
        # CronTrigger day_of_week: 0-6 (mon-sun)
        trigger = CronTrigger(day_of_week=schedule_day, hour=hour, minute=minute, timezone=VN_TZ)
    elif schedule_type == "hourly":
        trigger = CronTrigger(minute=minute, timezone=VN_TZ)
        
    if trigger:
        scheduler.add_job(
            send_personal_email_job,
            trigger=trigger,
            id=job_id,
            name=f"Auto Email User {user_id}",
            args=[user_id],
            replace_existing=True,
            misfire_grace_time=300
        )
        logger.info("Scheduled email for user | user_id={} type={} time={}", user_id, schedule_type, schedule_time)


def _reschedule_job(scheduler: AsyncIOScheduler, interval_hours: int, run_now: bool = False) -> None:
    """Xóa job cũ và thêm job mới với chu kỳ mới. Nếu run_now=True, sẽ chạy ngay lập tức một lần."""
    if scheduler.get_job("auto_scan"):
        scheduler.remove_job("auto_scan")

    # Nếu run_now=True, đặt thời điểm chạy kế tiếp là ngay bây giờ
    next_run_time = datetime.now(VN_TZ) if run_now else None

    scheduler.add_job(
        run_scheduled_scan,
        trigger=IntervalTrigger(hours=interval_hours, timezone=VN_TZ),
        id="auto_scan",
        name="Auto Crawler Scan",
        next_run_time=next_run_time,
        replace_existing=True,
        misfire_grace_time=300,  # Bỏ qua nếu trễ > 5 phút
    )
    logger.info("Scheduler job rescheduled | interval_hours={} run_now={}", interval_hours, run_now)


def _is_scan_overdue(config: models.SchedulerConfig) -> bool:
    if not config.last_run_at:
        return True

    last_run = config.last_run_at
    if last_run.tzinfo is None:
        last_run = VN_TZ.localize(last_run)

    diff = datetime.now(VN_TZ) - last_run
    return diff.total_seconds() >= config.interval_hours * 3600


def _schedule_daily_ai_summary(scheduler: AsyncIOScheduler) -> None:
    """Đăng ký job AI summary chạy vào 00:05 mỗi ngày để tự động tổng hợp khi sang ngày mới."""
    if scheduler.get_job("daily_ai_summary"):
        return
    scheduler.add_job(
        trigger_ai_summary,
        trigger=CronTrigger(hour=0, minute=5, timezone=VN_TZ),
        id="daily_ai_summary",
        name="Daily AI Summary",
        replace_existing=True,
        misfire_grace_time=600,
    )
    logger.info("Daily AI summary scheduled at 00:05 VN_TZ")


def start_scheduler() -> None:
    """Khởi động scheduler khi FastAPI startup."""
    run_now = False
    with SessionLocal() as db:
        config = _get_or_create_config(db)
        interval_hours = config.interval_hours
        
        # Nếu chưa từng chạy hoặc lần chạy cuối đã quá lâu so với interval, cho chạy ngay
        if not config.last_run_at:
            run_now = True
        else:
            # Đảm bảo so sánh cùng múi giờ
            last_run = config.last_run_at
            if last_run.tzinfo is None:
                last_run = VN_TZ.localize(last_run)
            
            diff = datetime.now(VN_TZ) - last_run
            if diff.total_seconds() >= interval_hours * 3600:
                run_now = True
                
        # Load all user schedules
        users = db.query(auth_models.User).filter(
            auth_models.User.is_active == True,
            auth_models.User.report_schedule_type != "none"
        ).all()

    scheduler = get_scheduler()
    _reschedule_job(scheduler, interval_hours, run_now=run_now)

    # Đăng ký các job gửi email cá nhân
    for u in users:
        update_user_email_schedule(
            u.id, 
            u.report_schedule_type, 
            u.report_schedule_time, 
            u.report_schedule_day
        )

    # Đăng ký job AI summary chạy vào 00:05 mỗi ngày
    _schedule_daily_ai_summary(scheduler)

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started | interval_hours={} scheduled_emails={}", interval_hours, len(users))


def ensure_scheduler_running() -> bool:
    """
    Reconcile the in-memory scheduler after an external wake-up request.
    HF Spaces can resume a suspended process without executing FastAPI startup again.
    """
    with SessionLocal() as db:
        config = _get_or_create_config(db)
        interval_hours = config.interval_hours
        should_run_now = config.is_enabled and _is_scan_overdue(config)

    scheduler = get_scheduler()
    if not scheduler.running:
        start_scheduler()
        scheduler = get_scheduler()

    if not scheduler.get_job("auto_scan"):
        _reschedule_job(scheduler, interval_hours, run_now=should_run_now)

    if should_run_now and not getattr(crawler, "is_scanning_flag", False):
        scheduler.modify_job("auto_scan", next_run_time=datetime.now(VN_TZ))
        logger.info("Overdue auto-scan queued after wake-up")
        return True

    return False


def stop_scheduler() -> None:
    """Dừng scheduler khi FastAPI shutdown."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


def update_scheduler_interval(new_interval_hours: int) -> None:
    """Cập nhật chu kỳ chạy job, áp dụng ngay lập tức."""
    scheduler = get_scheduler()
    _reschedule_job(scheduler, new_interval_hours)


async def run_ai_summary_job() -> None:
    """
    Job generate AI summary trong background, không phụ thuộc HTTP request.
    """
    def _do_summary():
        with SessionLocal() as db:
            try:
                from .modules.report.ai_summary import (
                    build_daily_summary_context,
                    generate_daily_summary,
                    _summary_cache,
                    SUMMARY_CACHE_TTL_SECONDS,
                )
                logger.info("AI summary job started")
                context_data = build_daily_summary_context(db)
                data = generate_daily_summary(context_data)
                _summary_cache["data"] = data
                _summary_cache["expires_at"] = datetime.utcnow() + timedelta(seconds=SUMMARY_CACHE_TTL_SECONDS)
                logger.info("AI summary job completed")
            except Exception as e:
                logger.error("AI summary job failed | error={}", str(e))
    await asyncio.to_thread(_do_summary)


def trigger_ai_summary() -> bool:
    """
    Kích hoạt AI summary chạy ngay trong background qua APScheduler.
    Trả về True nếu job được tạo mới, False nếu đã có job đang chạy/chờ.
    """
    from apscheduler.triggers.date import DateTrigger
    scheduler = get_scheduler()
    if scheduler.get_job("ai_summary"):
        logger.info("AI summary job skipped | reason=already_exists")
        return False
    scheduler.add_job(
        run_ai_summary_job,
        trigger=DateTrigger(run_date=datetime.now(VN_TZ) + timedelta(seconds=1)),
        id="ai_summary",
        name="AI Daily Summary",
        misfire_grace_time=300,
    )
    logger.info("AI summary job triggered")
    return True
