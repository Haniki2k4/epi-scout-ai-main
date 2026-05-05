"""
Email Sender - Gửi báo cáo qua Mailtrap API.
Hỗ trợ cả Email Sending (Production) và Email Testing (Sandbox).
"""
import json
import base64
import httpx
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from ..news.models import EmailConfig
from ...core.logger import get_logger

logger = get_logger("backend.report.email")

MAILTRAP_SENDING_URL = "https://send.api.mailtrap.io/api/send"
MAILTRAP_SANDBOX_URL_TEMPLATE = "https://sandbox.api.mailtrap.io/api/send/{inbox_id}"


def _get_email_config(db: Session) -> Optional[EmailConfig]:
    """Lấy cấu hình email (singleton id=1)."""
    return db.query(EmailConfig).filter(EmailConfig.id == 1).first()


def send_report_email(
    db: Session,
    docx_bytes: Optional[bytes] = None,
    excel_bytes: Optional[bytes] = None,
    report_date: Optional[datetime] = None,
    custom_recipients: Optional[list[str]] = None,
) -> dict:
    """
    Gửi báo cáo qua Mailtrap API.
    Tự động chọn endpoint Sending hoặc Sandbox dựa trên cấu hình.
    """
    config = _get_email_config(db)

    if not config or not config.mailtrap_api_token:
        return {"success": False, "message": "Chưa cấu hình Mailtrap API Token", "recipient_count": 0}

    # Quyết định endpoint: Nếu có inbox_id thì dùng Sandbox, ngược lại dùng Sending
    is_sandbox = bool(config.mailtrap_inbox_id)
    if is_sandbox:
        api_url = MAILTRAP_SANDBOX_URL_TEMPLATE.format(inbox_id=config.mailtrap_inbox_id)
        logger.info("Using Mailtrap Sandbox API | inbox_id={}", config.mailtrap_inbox_id)
    else:
        api_url = MAILTRAP_SENDING_URL
        logger.info("Using Mailtrap Sending API (Production)")
        if not config.sender_email:
            return {"success": False, "message": "Chưa cấu hình địa chỉ email gửi cho Production", "recipient_count": 0}

    # Lấy danh sách người nhận
    if custom_recipients:
        recipients = custom_recipients
    else:
        from ..auth.models import User
        users = db.query(User).filter(
            User.is_active == True,
            User.email.isnot(None),
            User.report_schedule_type != "none",
        ).all()
        recipients = [u.email for u in users if u.email]

    recipients = [r.strip() for r in recipients if r.strip()]
    if not recipients:
        return {"success": False, "message": "Chưa có danh sách email người nhận", "recipient_count": 0}

    report_date = report_date or datetime.utcnow()
    date_str = report_date.strftime("%d/%m/%Y %H:%M")
    subject = f"[Epi Scout AI] Báo cáo Giám sát Dịch bệnh - {report_date.strftime('%d/%m/%Y')}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; font-size: 14px; color: #212121;">
        <div style="background-color: #1565C0; color: white; padding: 16px 24px;">
            <h2 style="margin: 0;">Epi Scout AI</h2>
            <p style="margin: 4px 0 0;">Hệ thống Giám sát Dịch bệnh Dựa vào Sự kiện</p>
        </div>
        <div style="padding: 24px;">
            <h3 style="color: #1565C0;">Báo cáo Dịch tễ Tự động</h3>
            <p>Kính gửi Quý cán bộ,</p>
            <p>
                Hệ thống Epi Scout AI gửi đến Quý cán bộ báo cáo giám sát dịch bệnh tổng hợp
                tính đến <strong>{date_str}</strong>.
            </p>
            <p>File đính kèm bao gồm:</p>
            <ul>
                {"<li><strong>Báo cáo Word (.docx)</strong>: Tóm tắt tình hình dịch bệnh và các sự kiện nổi bật</li>" if docx_bytes else ""}
                {"<li><strong>Bảng biểu Excel (.xlsx)</strong>: Biểu mẫu ghi nhận dấu hiệu cảnh báo theo Phụ lục I QĐ 2018/QĐ-BYT</li>" if excel_bytes else ""}
            </ul>
            <p style="color: #C62828;">
                <em>Lưu ý: Thông tin trong báo cáo được thu thập tự động từ các nguồn truyền thông.
                Cán bộ y tế cần xem xét và xác minh trước khi sử dụng chính thức.</em>
            </p>
            <hr style="border-color: #E0E0E0;">
            <p style="color: #757575; font-size: 12px;">
                Email này được gửi tự động từ hệ thống Epi Scout AI.<br>
                Mọi phản hồi xin gửi về bộ phận quản trị hệ thống.
            </p>
        </div>
    </body>
    </html>
    """

    # Xây dựng payload
    payload: dict = {
        "from": {"email": config.sender_email or "no-reply@episcout.ai", "name": "Epi Scout AI"},
        "to": [{"email": r} for r in recipients],
        "subject": subject,
        "html": html_body,
    }

    # Đính kèm file
    attachments = []
    if docx_bytes:
        attachments.append({
            "filename": f"BaoCao_DichBenh_{report_date.strftime('%Y%m%d')}.docx",
            "content": base64.b64encode(docx_bytes).decode(),
            "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "disposition": "attachment",
        })
    if excel_bytes:
        attachments.append({
            "filename": f"BieuMau_EBS_QD2018_{report_date.strftime('%Y%m%d')}.xlsx",
            "content": base64.b64encode(excel_bytes).decode(),
            "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "disposition": "attachment",
        })

    if attachments:
        payload["attachments"] = attachments

    try:
        response = httpx.post(
            api_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {config.mailtrap_api_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        if response.status_code in (200, 201, 202):
            logger.info("Report email sent via Mailtrap | recipients={} status={} sandbox={}", 
                        len(recipients), response.status_code, is_sandbox)
            return {
                "success": True,
                "message": f"Đã gửi thành công (Sandbox={is_sandbox}) đến {len(recipients)} người nhận",
                "recipient_count": len(recipients),
            }
        else:
            error_detail = response.text[:200] if response.text else "Unknown"
            logger.warning("Mailtrap unexpected status | status={} body={}", response.status_code, error_detail)
            return {
                "success": False,
                "message": f"Mailtrap trả về lỗi: HTTP {response.status_code} — {error_detail}",
                "recipient_count": 0,
            }
    except Exception as e:
        logger.error("Email send failed | error={}", str(e))
        return {"success": False, "message": f"Lỗi gửi email: {str(e)}", "recipient_count": 0}
 