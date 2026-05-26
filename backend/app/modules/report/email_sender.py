"""
Email Sender - Gửi báo cáo qua Mailtrap SMTP.
Chỉ cấu hình qua biến môi trường (.env), không dùng DB.
"""
import os
import smtplib
import socket
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

from ...core.logger import get_logger

logger = get_logger("backend.report.email")

SMTP_TIMEOUT_SECONDS = 30


def send_report_email(
    docx_bytes: Optional[bytes] = None,
    excel_bytes: Optional[bytes] = None,
    report_date: Optional[datetime] = None,
    custom_recipients: Optional[list[str]] = None,
    report_data: Optional[dict] = None,
) -> dict:
    smtp_host = os.getenv("MAILTRAP_SMTP_HOST")
    smtp_user = os.getenv("MAILTRAP_SMTP_USER")
    smtp_pass = os.getenv("MAILTRAP_SMTP_PASSWORD")

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.error("Missing SMTP env vars (MAILTRAP_SMTP_HOST/USER/PASSWORD)")
        return {"success": False, "message": "Thiếu cấu hình SMTP trong biến môi trường", "recipient_count": 0}

    smtp_port = int(os.getenv("MAILTRAP_SMTP_PORT", "2525"))
    sender_email = os.getenv("MAILTRAP_SENDER_EMAIL", "no-reply@episcout.ai")

    if not custom_recipients or len([r for r in custom_recipients if r.strip()]) == 0:
        return {"success": False, "message": "Chưa có danh sách email người nhận", "recipient_count": 0}

    recipients = [r.strip() for r in custom_recipients if r.strip()]
    if not recipients:
        return {"success": False, "message": "Danh sách người nhận rỗng", "recipient_count": 0}

    report_date = report_date or datetime.now(timezone.utc)
    date_str = report_date.strftime("%d/%m/%Y %H:%M")
    scope_hours = (report_data or {}).get("scope_hours", 72)
    start_str = (report_data or {}).get("start_date", report_date).strftime("%d/%m/%Y %H:%M")
    subject = f"[Epi Scout AI] Báo cáo Giám sát Dịch bệnh - {report_date.strftime('%d/%m/%Y')}"

    overview = (report_data or {}).get("overview", {})
    top_diseases = (report_data or {}).get("top_diseases", [])

    top_diseases_rows = ""
    for d in top_diseases[:5]:
        name = d.get("disease_name", d.get("keyword", "N/A"))
        count = d.get("article_count", 0)
        top_diseases_rows += f"<tr><td style='padding: 4px 8px; border-bottom: 1px solid #E0E0E0;'>{name}</td><td style='padding: 4px 8px; border-bottom: 1px solid #E0E0E0; text-align: center;'>{count}</td></tr>"

    html_body = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @media only screen and (max-width: 480px) {{
                .card-stack td {{ display: block !important; width: 100% !important; padding: 2px 0 !important; }}
                .body-pad {{ padding: 16px !important; }}
                .h-pad {{ padding: 20px !important; }}
                .badge {{ display: none !important; }}
                .h-title {{ font-size: 18px !important; }}
                .h-sub {{ font-size: 12px !important; }}
                .stat-num {{ font-size: 20px !important; }}
                .stat-lbl {{ font-size: 10px !important; }}
                .disease-table {{ font-size: 12px !important; }}
            }}
            @media only screen and (min-width: 481px) and (max-width: 768px) {{
                .body-pad {{ padding: 20px !important; }}
            }}
    </style>
    </head>
    <body style="margin:0; padding:0; background-color:#F5F5F5; font-family:Arial, sans-serif; font-size:14px; color:#212121;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F5F5F5;">
            <tr><td align="center" style="padding:20px 10px;">
                <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">

                    <!-- Header -->
                    <tr>
                        <td class="h-pad" style="background: linear-gradient(135deg, #1565C0, #1976D2); padding: 28px 32px;">
                            <table width="100%">
                                <tr>
                                    <td>
                                        <h1 class="h-title" style="margin:0; color:#ffffff; font-size:22px; font-weight:700;">Epi Scout AI</h1>
                                        <p class="h-sub" style="margin:4px 0 0; color:rgba(255,255,255,0.85); font-size:13px;">Hệ thống Giám sát Dịch bệnh Dựa vào Sự kiện</p>
                                    </td>
                                    <td class="badge" align="right" style="vertical-align:top;">
                                        <div style="background:rgba(255,255,255,0.15); border-radius:20px; padding:4px 14px; color:#fff; font-size:12px; white-space:nowrap;">Báo cáo tự động</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr><td class="body-pad" style="padding: 24px 32px;">

                        <!-- Greeting -->
                        <p style="margin:0 0 16px; font-size:15px;">Kính gửi Quý cán bộ,</p>
                        <p style="margin:0 0 16px; line-height:1.6;">
                            Hệ thống Epi Scout AI gửi báo cáo giám sát dịch bệnh tổng hợp trong <strong>{scope_hours}h</strong> gần nhất,
                            từ <strong>{start_str}</strong> đến <strong>{date_str}</strong>.
                        </p>

                        <!-- Summary Cards -->
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;">
                            <tr class="card-stack">
                                <td width="33%" style="padding:4px;">
                                    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="background:#E3F2FD; border-radius:8px; padding:10px; text-align:center;">
                                        <div class="stat-num" style="font-size:24px; font-weight:700; color:#1565C0;">{overview.get("total_events_7d", "—")}</div>
                                        <div class="stat-lbl" style="font-size:11px; color:#555;">Sự kiện (7 ngày)</div>
                                    </td></tr></table>
                                </td>
                                <td width="33%" style="padding:4px;">
                                    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="background:#E8F5E9; border-radius:8px; padding:10px; text-align:center;">
                                        <div class="stat-num" style="font-size:24px; font-weight:700; color:#2E7D32;">{overview.get("keywords_7d", "—")}</div>
                                        <div class="stat-lbl" style="font-size:11px; color:#555;">Bệnh được ghi nhận</div>
                                    </td></tr></table>
                                </td>
                                <td width="33%" style="padding:4px;">
                                    <table width="100%" cellpadding="0" cellspacing="0"><tr><td style="background:#FFF3E0; border-radius:8px; padding:10px; text-align:center;">
                                        <div class="stat-num" style="font-size:24px; font-weight:700; color:#E65100;">{overview.get("keywords_today", "—")}</div>
                                        <div class="stat-lbl" style="font-size:11px; color:#555;">Bệnh trong hôm nay</div>
                                    </td></tr></table>
                                </td>
                            </tr>
                        </table>"""

    if top_diseases_rows:
        html_body += f"""
                        <!-- Top Diseases -->
                        <h3 style="color:#1565C0; font-size:15px; margin:20px 0 10px;">Dịch bệnh nổi bật</h3>
                        <table class="disease-table" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E0E0E0; border-radius:6px; font-size:13px;">
                            <tr style="background:#FAFAFA;">
                                <th style="padding:6px 8px; text-align:left; border-bottom:1px solid #E0E0E0; font-weight:600;">Bệnh</th>
                                <th style="padding:6px 8px; text-align:center; border-bottom:1px solid #E0E0E0; font-weight:600;">Bài báo</th>
                            </tr>
                            {top_diseases_rows}
                        </table>"""

    html_body += f"""
                        <!-- Attachments -->
                        <h3 style="color:#1565C0; font-size:15px; margin:20px 0 10px;">File đính kèm</h3>
                        <ul style="margin:0 0 20px; padding-left:20px; font-size:13px;">
                            {"<li><strong>Báo cáo Word (.docx)</strong> — Tóm tắt tình hình dịch bệnh và các sự kiện nổi bật</li>" if docx_bytes else ""}
                            {"<li><strong>Bảng biểu Excel (.xlsx)</strong> — Biểu mẫu ghi nhận dấu hiệu cảnh báo theo Phụ lục I QĐ 2018/QĐ-BYT</li>" if excel_bytes else ""}
                        </ul>

                        <!-- Disclaimer -->
                        <div style="background:#FFF8E1; border-left:4px solid #FFA000; padding:12px 16px; border-radius:4px; font-size:12px; color:#6D4C00; margin:20px 0;">
                            <strong>Lưu ý quan trọng:</strong> Thông tin trong báo cáo được thu thập tự động từ các nguồn truyền thông đại chúng.
                            Cán bộ y tế cần xem xét, xác minh và đánh giá trước khi sử dụng cho mục đích chính thức.
                        </div>

                        <!-- Divider -->
                        <hr style="border:none; border-top:1px solid #E0E0E0; margin:20px 0;">

                        <!-- Footer -->
                        <p style="color:#757575; font-size:11px; line-height:1.5; margin:0;">
                            Email này được gửi tự động từ hệ thống <strong>Epi Scout AI</strong>.<br>
                            Mọi phản hồi xin gửi về bộ phận quản trị hệ thống.
                        </p>
                    </td></tr>
                </table>
            </td></tr>
        </table>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = f"Epi Scout AI <{sender_email}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    if docx_bytes:
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")
        part.set_payload(docx_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="BaoCao_DichBenh_{report_date.strftime("%Y%m%d")}.docx"')
        msg.attach(part)

    if excel_bytes:
        part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        part.set_payload(excel_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="BieuMau_EBS_QD2018_{report_date.strftime("%Y%m%d")}.xlsx"')
        msg.attach(part)

    logger.info("Sending via SMTP | host={} port={} recipients={}", smtp_host, smtp_port, len(recipients))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.set_debuglevel(1)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, recipients, msg.as_string())

        logger.info("Email sent successfully via SMTP | recipients={}", len(recipients))
        return {
            "success": True,
            "message": f"Đã gửi thành công qua SMTP đến {len(recipients)} người nhận",
            "recipient_count": len(recipients),
        }
    except (smtplib.SMTPException, socket.error, OSError) as e:
        logger.error("SMTP send failed | error={}", str(e))
        return {"success": False, "message": f"Lỗi gửi email qua SMTP: {str(e)}", "recipient_count": 0}
