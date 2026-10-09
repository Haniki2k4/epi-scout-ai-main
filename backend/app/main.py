"""
EpiScout AI — FastAPI entry-point.

Refactored:
  - Issue #12: endpoints tách sang router modules
  - Issue #13: duplicate /api/rss-sources removed
  - Issue #14: @app.on_event → lifespan context manager
  - Issue #16: health check endpoint added
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import os

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .core import database
from .core.database import get_db, Base, engine
from .core.logger import get_logger
from .modules.news import crawler, crud, models, schemas
from .modules.auth import router as auth_router, security
from .modules.auth import router_alerts as alerts_router
from .modules.admin import router_users as admin_users_router
from .modules.admin import router_scheduler as admin_scheduler_router
from .modules.report import router as report_router
from .modules.report import router_ai_summary
from .modules.admin import router_llm_status
from .modules.evaluation import router as evaluation_router
from .modules.evaluation import router_llm as llm_evaluation_router
from .modules.news import router_articles, router_resources, router_stats, router_signals, router_quality, router_context_signals
from . import scheduler as app_scheduler

logger = get_logger("backend.main")


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown logic in a single context manager."""
    # --- Startup ---
    with database.SessionLocal() as db:
        crud.seed_default_keywords(db)
        crud.seed_default_rss_sources(db)
        logger.info("Backend startup complete, default keywords and RSS sources seeded")
    crawler.log_llm_preflight_status(force_refresh=True)
    app_scheduler.start_scheduler()
    app_scheduler.trigger_ai_summary()

    yield  # app is running

    # --- Shutdown ---
    app_scheduler.stop_scheduler()


app = FastAPI(
    description="Hệ thống quét và tự động phân tích tin tức dịch tễ.",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_cors_env = os.environ.get("CORS_ORIGINS", "")
_default_origins = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Include routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(alerts_router.router)
app.include_router(admin_users_router.router)
app.include_router(admin_scheduler_router.router)
app.include_router(router_llm_status.router)
app.include_router(report_router.router)
app.include_router(router_ai_summary.router)
app.include_router(evaluation_router.router)
app.include_router(llm_evaluation_router.router)

# New routers (Issue #12 refactor)
app.include_router(router_articles.router)
app.include_router(router_resources.router)
app.include_router(router_stats.router)
app.include_router(router_signals.router)
app.include_router(router_quality.router)
app.include_router(router_context_signals.router)


# ---------------------------------------------------------------------------
# Health check (Issue #16)
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["health"])
def health_check():
    """Basic health check for load balancers and monitoring."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Scan endpoints (kept here — tightly coupled to scheduler)
# ---------------------------------------------------------------------------

@app.post("/api/scan", response_model=schemas.ScanResult)
def scan_news(
    request: schemas.ScanRequest,
    db: Session = Depends(get_db),
    current_user=Depends(security.get_current_active_user),
):
    logger.info(
        "Scan requested | start_date={} end_date={} keywords_count={}",
        request.start_date, request.end_date,
        len(request.keywords_to_scan) if request.keywords_to_scan is not None else "all",
    )
    result = crawler.scan_news(
        db,
        request.start_date,
        request.end_date,
        keywords_to_scan=request.keywords_to_scan,
    )
    logger.info("Scan completed | saved_trusted_count={}", result.saved_trusted_count)
    return result


def _get_scan_status_payload(db: Session) -> dict:
    config = app_scheduler._get_or_create_config(db)
    sched = app_scheduler.get_scheduler()
    latest_run = db.query(models.ScanRun).order_by(models.ScanRun.started_at.desc()).first()
    memory_scanning = bool(getattr(crawler, "is_scanning_flag", False))
    latest_is_running = latest_run is None or latest_run.status == "running"
    is_scanning = memory_scanning and latest_is_running

    # A completed/failed ScanRun is the durable source of truth. Repair a stale
    # process-local flag so the banner cannot remain orange after finalization.
    if memory_scanning and latest_run is not None and latest_run.status != "running":
        crawler.is_scanning_flag = False
        logger.warning(
            "Repaired stale scan flag | latest_scan_run={} status={}",
            latest_run.scan_run_id,
            latest_run.status,
        )

    return {
        "scheduler_running": sched.running,
        "is_scanning": is_scanning,
        "last_run_at": config.last_run_at,
        "last_run_saved_count": config.last_run_saved_count,
        "next_run_at": config.next_run_at,
        "active_scan_run_id": latest_run.scan_run_id if is_scanning and latest_run else None,
        "active_scan_started_at": latest_run.started_at if is_scanning and latest_run else None,
    }


@app.get("/api/scan-status")
def get_scan_status(db: Session = Depends(get_db)):
    """Lấy trạng thái scan hiện tại cho tất cả người dùng (hiển thị banner)."""
    return _get_scan_status_payload(db)


@app.get("/api/page-data", response_model=schemas.PageDataResponse)
def get_page_data(
    skip: int = 0,
    limit: int = 20,
    keyword: str | None = None,
    date: str | None = None,
    include_excluded: bool = False,
    include_label: bool = False,
    events_limit: int = 20,
    db: Session = Depends(get_db),
):
    """Endpoint gộp: articles + events + keywords + scan_status — 1 request thay vì 4-5."""
    logger.info(
        "Page data requested | skip={} limit={} keyword={} events_limit={}",
        skip, limit, keyword, events_limit,
    )

    # 1. Articles
    articles_list = crud.get_articles(
        db, skip=skip, limit=limit, keyword=keyword, date=date, include_excluded=include_excluded,
    )
    total = crud.count_articles(db, keyword=keyword, date=date, include_excluded=include_excluded)

    if include_label:
        from .modules.evaluation.models import ArticleEvaluation
        article_ids = [a.id for a in articles_list]
        if article_ids:
            evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.article_id.in_(article_ids)).all()
            eval_map = {e.article_id: e for e in evals}
            for a in articles_list:
                e = eval_map.get(a.id)
                if e:
                    a.llm_label = e.llm_label
                    a.human_label = e.human_label

    # 2. Events
    events_list = crud.get_events(db, skip=0, limit=events_limit)

    # 3. Keywords (active only)
    keywords_list = crud.get_active_keywords(db)

    # 4. Scan status
    scan_status = _get_scan_status_payload(db)

    logger.info(
        "Page data completed | articles={} events={} keywords={}",
        len(articles_list), len(events_list), len(keywords_list),
    )
    return {
        "articles": {"items": articles_list, "total": total, "skip": skip, "limit": limit},
        "events": events_list,
        "keywords": keywords_list,
        "scan_status": scan_status,
    }
