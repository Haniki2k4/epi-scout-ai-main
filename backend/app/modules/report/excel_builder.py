"""
Excel Builder - Tạo file Excel theo Phụ lục I Quyết định 2018/QĐ-BYT
về Hướng dẫn Giám sát dựa vào Sự kiện (Event-Based Surveillance - EBS).

Cấu trúc bảng biểu mẫu:
STT | Ngày ghi nhận | Địa điểm (Thôn/Xã/Huyện/Tỉnh) | Mô tả dấu hiệu cảnh báo |
Nguồn tin | Kết quả sàng lọc | Kết quả xác minh | Đánh giá | Biện pháp đáp ứng
"""
import io
from datetime import datetime
from typing import Optional

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter


# --- Style Constants ---
HEADER_BG_COLOR = "1565C0"   # Xanh dương đậm - màu Bộ Y tế
HEADER_FONT_COLOR = "FFFFFF" # Trắng
SUBHEADER_BG_COLOR = "E3F2FD" # Xanh nhạt cho dòng tiêu đề phụ
TABLE_HEADER_BG = "1976D2"   # Xanh tiêu đề bảng
TABLE_ALT_BG = "F5F9FF"      # Nền xen kẽ nhạt


def _thin_border() -> Border:
    thin = Side(style="thin", color="B0BEC5")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _make_cell_style(
    ws,
    row: int,
    col: int,
    value,
    bold: bool = False,
    font_size: int = 10,
    font_color: str = "212121",
    bg_color: Optional[str] = None,
    align_h: str = "left",
    align_v: str = "center",
    wrap: bool = True,
    border: bool = True,
):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(
        name="Times New Roman",
        bold=bold,
        size=font_size,
        color=font_color,
    )
    cell.alignment = Alignment(
        horizontal=align_h,
        vertical=align_v,
        wrap_text=wrap,
    )
    if bg_color:
        cell.fill = PatternFill(
            start_color=bg_color,
            end_color=bg_color,
            fill_type="solid",
        )
    if border:
        cell.border = _thin_border()
    return cell


def build_ebs_excel(report_data: dict) -> bytes:
    """
    Tạo file Excel Phụ lục I QĐ 2018/QĐ-BYT.
    
    Args:
        report_data: Dict trả về từ generator.get_report_data()
    
    Returns:
        bytes của file Excel.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Biểu mẫu EBS"

    # =========================================================
    # PHẦN TIÊU ĐỀ (Rows 1-6)
    # =========================================================
    ws.merge_cells("A1:I1")
    cell_title = ws["A1"]
    cell_title.value = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
    cell_title.font = Font(name="Times New Roman", bold=True, size=13, color="212121")
    cell_title.alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:I2")
    cell_sub = ws["A2"]
    cell_sub.value = "Độc lập - Tự do - Hạnh phúc"
    cell_sub.font = Font(name="Times New Roman", bold=True, size=12, color="212121")
    cell_sub.alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:I3")
    ws["A3"].value = "―――――――"
    ws["A3"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A4:I4")
    title_cell = ws["A4"]
    title_cell.value = "PHỤ LỤC I: BIỂU MẪU GHI NHẬN DẤU HIỆU CẢNH BÁO"
    title_cell.font = Font(name="Times New Roman", bold=True, size=14, color=HEADER_BG_COLOR)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    title_cell.fill = PatternFill(start_color="E3F2FD", end_color="E3F2FD", fill_type="solid")

    ws.merge_cells("A5:I5")
    ws["A5"].value = "(Ban hành kèm theo Quyết định số 2018/QĐ-BYT ngày 28/3/2018 của Bộ trưởng Bộ Y tế)"
    ws["A5"].font = Font(name="Times New Roman", italic=True, size=10, color="616161")
    ws["A5"].alignment = Alignment(horizontal="center", vertical="center")

    # Thông tin đơn vị và ngày báo cáo
    generated_at: datetime = report_data.get("generated_at", datetime.utcnow())
    scope_hours: int = report_data.get("scope_hours", 72)
    start_date: datetime = report_data.get("start_date", generated_at)
    end_date: datetime = report_data.get("end_date", generated_at)

    ws.merge_cells("A6:D6")
    ws["A6"].value = f"Đơn vị: Hệ thống Epi Scout AI"
    ws["A6"].font = Font(name="Times New Roman", bold=True, size=10)
    ws["A6"].alignment = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("E6:I6")
    ws["E6"].value = (
        f"Kỳ báo cáo: {start_date.strftime('%d/%m/%Y %H:%M')} - {end_date.strftime('%d/%m/%Y %H:%M')}"
    )
    ws["E6"].font = Font(name="Times New Roman", size=10)
    ws["E6"].alignment = Alignment(horizontal="right", vertical="center")

    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[4].height = 30
    ws.row_dimensions[5].height = 16
    ws.row_dimensions[6].height = 18

    # =========================================================
    # HEADER BẢNG (Row 7)
    # =========================================================
    COLUMNS = [
        ("STT", 5),
        ("Ngày ghi nhận", 14),
        ("Địa điểm\n(Thôn/Xã/Huyện/Tỉnh)", 25),
        ("Mô tả dấu hiệu cảnh báo\n(Bệnh, triệu chứng, số ca)", 45),
        ("Nguồn tin", 20),
        ("Kết quả sàng lọc", 18),
        ("Kết quả xác minh", 18),
        ("Đánh giá\n(Mức độ rủi ro)", 15),
        ("Biện pháp đáp ứng", 25),
    ]

    header_row = 7
    for col_idx, (header_name, col_width) in enumerate(COLUMNS, start=1):
        _make_cell_style(
            ws=ws,
            row=header_row,
            col=col_idx,
            value=header_name,
            bold=True,
            font_size=10,
            font_color=HEADER_FONT_COLOR,
            bg_color=TABLE_HEADER_BG,
            align_h="center",
            align_v="center",
            wrap=True,
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = col_width

    ws.row_dimensions[header_row].height = 40

    # =========================================================
    # DỮ LIỆU (Rows 8+)
    # =========================================================
    top_events = report_data.get("top_events", [])
    alert_articles = report_data.get("alert_articles", [])
    recent_articles = report_data.get("recent_articles", [])

    # Ưu tiên hiển thị: sự kiện có tọa độ → bài báo có tag cảnh báo → bài báo gần nhất
    rows_data = []

    # 1. Từ NewsEvent
    for event in top_events:
        location_str = event.location or ""
        # Mô tả: canonical_title + số ca
        desc = event.canonical_title
        if event.case_count:
            desc += f" | Số ca: {event.case_count}"

        rows_data.append({
            "date": event.event_date,
            "location": location_str,
            "description": desc,
            "source": ", ".join(event.sources_preview[:3]) if event.sources_preview else "Hệ thống tự động",
            "screening": "Đạt yêu cầu sàng lọc",
            "verification": f"{event.article_count} bài báo xác nhận",
            "assessment": event.severity or "Đang theo dõi",
            "response": "Tiếp tục giám sát",
        })

    # 2. Bài báo có tag cảnh báo (nếu chưa có trong events)
    event_titles = {e.canonical_title for e in top_events}
    for article in alert_articles:
        if article.title and article.title not in event_titles:
            rows_data.append({
                "date": article.published_date,
                "location": "",
                "description": article.title,
                "source": article.source or "Chưa xác định",
                "screening": "Cảnh báo - Cần xác minh",
                "verification": "Chưa xác minh",
                "assessment": "Cảnh báo",
                "response": "Cần điều tra thêm",
            })

    # 3. Bài báo gần nhất (nếu còn ít dữ liệu)
    if len(rows_data) < 3:
        for article in recent_articles:
            if article.title and article.title not in event_titles:
                rows_data.append({
                    "date": article.published_date,
                    "location": "",
                    "description": article.title,
                    "source": article.source or "Chưa xác định",
                    "screening": "Cần xem xét",
                    "verification": "Chưa xác minh",
                    "assessment": "Theo dõi",
                    "response": "Theo dõi thêm",
                })
                if len(rows_data) >= 10:
                    break

    # Đảm bảo có ít nhất 5 dòng trống nếu không có dữ liệu
    if not rows_data:
        rows_data = [{"date": None, "location": "", "description": "", "source": "",
                      "screening": "", "verification": "", "assessment": "", "response": ""}
                     for _ in range(5)]

    for row_idx, row in enumerate(rows_data, start=header_row + 1):
        is_alt = (row_idx % 2 == 0)
        row_bg = TABLE_ALT_BG if is_alt else None
        ws.row_dimensions[row_idx].height = 30

        date_val = row.get("date")
        date_str = date_val.strftime("%d/%m/%Y") if date_val else ""

        values = [
            row_idx - header_row,       # STT
            date_str,
            row.get("location", ""),
            row.get("description", ""),
            row.get("source", ""),
            row.get("screening", ""),
            row.get("verification", ""),
            row.get("assessment", ""),
            row.get("response", ""),
        ]
        for col_idx, val in enumerate(values, start=1):
            _make_cell_style(
                ws=ws,
                row=row_idx,
                col=col_idx,
                value=val,
                bold=False,
                font_size=10,
                bg_color=row_bg,
                align_h="center" if col_idx in (1, 2, 8) else "left",
                align_v="center",
                wrap=True,
            )

    # =========================================================
    # DÒNG CHỮ KÝ (sau bảng dữ liệu)
    # =========================================================
    sig_row = header_row + len(rows_data) + 2
    ws.merge_cells(f"G{sig_row}:I{sig_row}")
    ws[f"G{sig_row}"].value = f"Ngày {generated_at.day} tháng {generated_at.month} năm {generated_at.year}"
    ws[f"G{sig_row}"].font = Font(name="Times New Roman", italic=True, size=10)
    ws[f"G{sig_row}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"G{sig_row+1}:I{sig_row+1}")
    ws[f"G{sig_row+1}"].value = "Người lập biểu"
    ws[f"G{sig_row+1}"].font = Font(name="Times New Roman", bold=True, size=11)
    ws[f"G{sig_row+1}"].alignment = Alignment(horizontal="center")

    ws.merge_cells(f"G{sig_row+5}:I{sig_row+5}")
    ws[f"G{sig_row+5}"].value = "(Ký, ghi rõ họ tên)"
    ws[f"G{sig_row+5}"].font = Font(name="Times New Roman", italic=True, size=10, color="757575")
    ws[f"G{sig_row+5}"].alignment = Alignment(horizontal="center")

    # =========================================================
    # GHI CHÚ CUỐI
    # =========================================================
    note_row = sig_row + 7
    ws.merge_cells(f"A{note_row}:I{note_row}")
    ws[f"A{note_row}"].value = (
        "* Ghi chú: Báo cáo được tạo tự động bởi Hệ thống Epi Scout AI dựa trên dữ liệu thu thập "
        f"trong {scope_hours} giờ (từ {start_date.strftime('%d/%m/%Y %H:%M')} đến {end_date.strftime('%d/%m/%Y %H:%M')}). "
        "Cán bộ y tế cần xác minh và bổ sung thông tin trước khi sử dụng chính thức."
    )
    ws[f"A{note_row}"].font = Font(name="Times New Roman", italic=True, size=9, color="616161")
    ws[f"A{note_row}"].alignment = Alignment(horizontal="left", wrap_text=True)
    ws.row_dimensions[note_row].height = 30

    # In ra bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
