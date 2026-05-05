"""
Report Router - API endpoints cho module báo cáo dịch tễ.
"""
import json
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..news.models import EmailConfig
from ..auth.security import get_current_active_user, require_admin_role
from .generator import get_report_data
from .docx_builder import build_word_report
from .excel_builder import build_ebs_excel
from .email_sender import send_report_email
from ...core.logger import get_logger

logger = get_logger("backend.report.router")

router = APIRouter(prefix="/api/report", tags=["report"])


# --- Schemas ---

class ReportRequest(BaseModel):
    scope_hours: int = 72  # Mặc định 72h = 3 ngày


class SendEmailRequest(BaseModel):
    scope_hours: int = 72
    attach_docx: bool = True
    attach_excel: bool = True
    custom_recipients: Optional[List[str]] = None  # Ghi đè danh sách người nhận


class EmailConfigUpdate(BaseModel):
    mailtrap_api_token: Optional[str] = None
    mailtrap_inbox_id: Optional[str] = None
    sender_email: Optional[str] = None


class EmailConfigResponse(BaseModel):
    sender_email: Optional[str] = None
    has_api_key: bool = False
    has_inbox_id: bool = False


# --- Helpers ---

def _get_or_create_email_config(db: Session) -> EmailConfig:
    config = db.query(EmailConfig).filter(EmailConfig.id == 1).first()
    if not config:
        config = EmailConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# --- Endpoints ---

@router.post("/generate")
def generate_word_report(
    body: ReportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Tạo file báo cáo Word (.docx) từ dữ liệu trong DB."""
    logger.info("Word report requested | scope_hours={} user={}", body.scope_hours, current_user.username)

    try:
        report_data = get_report_data(db, scope_hours=body.scope_hours)
        docx_bytes = build_word_report(report_data)

        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M")
        filename = f"BaoCao_DichBenh_{date_str}.docx"

        logger.info("Word report generated | size_bytes={}", len(docx_bytes))
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error("Word report generation failed | error={}", str(e))
        raise HTTPException(status_code=500, detail=f"Tạo báo cáo thất bại: {str(e)}")


@router.post("/export-excel")
def export_ebs_excel(
    body: ReportRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Xuất file Excel theo Phụ lục I Quyết định 2018/QĐ-BYT
    (Biểu mẫu Ghi nhận Dấu hiệu Cảnh báo EBS).
    """
    logger.info("Excel EBS report requested | scope_hours={} user={}", body.scope_hours, current_user.username)

    try:
        report_data = get_report_data(db, scope_hours=body.scope_hours)
        excel_bytes = build_ebs_excel(report_data)

        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M")
        filename = f"BieuMau_EBS_QD2018_{date_str}.xlsx"

        logger.info("Excel EBS report generated | size_bytes={}", len(excel_bytes))
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error("Excel EBS report generation failed | error={}", str(e))
        raise HTTPException(status_code=500, detail=f"Xuất Excel thất bại: {str(e)}")


@router.post("/send-email")
def send_report_via_email(
    body: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Tạo báo cáo và gửi qua SendGrid API đến danh sách email đã cấu hình."""
    logger.info(
        "Send email report requested | scope_hours={} attach_docx={} attach_excel={} user={}",
        body.scope_hours, body.attach_docx, body.attach_excel, current_user.username,
    )

    try:
        report_data = get_report_data(db, scope_hours=body.scope_hours)
        docx_bytes = build_word_report(report_data) if body.attach_docx else None
        excel_bytes = build_ebs_excel(report_data) if body.attach_excel else None

        result = send_report_email(
            db=db,
            docx_bytes=docx_bytes,
            excel_bytes=excel_bytes,
            report_date=report_data["generated_at"],
            custom_recipients=body.custom_recipients,
        )

        if not result["success"]:
            raise HTTPException(status_code=422, detail=result["message"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Send email report failed | error={}", str(e))
        raise HTTPException(status_code=500, detail=f"Gửi email thất bại: {str(e)}")


@router.get("/email-config", response_model=EmailConfigResponse)
def get_email_config_api(
    db: Session = Depends(get_db),
    _=Depends(require_admin_role),
):
    """Lấy cấu hình email hiện tại (Admin only). API key được ẩn bớt."""
    config = _get_or_create_email_config(db)

    return EmailConfigResponse(
        sender_email=config.sender_email,
        has_api_key=bool(config.mailtrap_api_token),
        has_inbox_id=bool(config.mailtrap_inbox_id),
    )


@router.put("/email-config", response_model=EmailConfigResponse)
def update_email_config_api(
    body: EmailConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin_role),
):
    """Cập nhật cấu hình email (Admin only)."""
    config = _get_or_create_email_config(db)

    if body.mailtrap_api_token is not None:
        config.mailtrap_api_token = body.mailtrap_api_token.strip() or None
    if body.mailtrap_inbox_id is not None:
        config.mailtrap_inbox_id = body.mailtrap_inbox_id.strip() or None
    if body.sender_email is not None:
        config.sender_email = body.sender_email.strip() or None

    db.commit()
    db.refresh(config)
    logger.info("Email config updated by admin")

    return EmailConfigResponse(
        sender_email=config.sender_email,
        has_api_key=bool(config.mailtrap_api_token),
        has_inbox_id=bool(config.mailtrap_inbox_id),
    )
