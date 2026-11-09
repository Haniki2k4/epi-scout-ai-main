"""Exports for interactive analytics, independent of the legacy EBS reports."""
import io
import re
from collections import OrderedDict
from threading import Lock
from time import monotonic
from uuid import uuid4
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from textwrap import wrap
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.pagebreak import Break
from pydantic import BaseModel, Field, field_validator

from ..news import stats
from ..news.disease_catalog import canonical_disease


class InteractiveReportRequest(BaseModel):
    diseases: list[str] = Field(min_length=1, max_length=6)
    mode: Literal['zscore', 'forecast']
    days: Literal[30, 60, 90] = 30
    interval_width: Literal[0.8, 0.95] = 0.8
    format: Literal['docx'] = 'docx'
    snapshot_id: str | None = Field(default=None, max_length=36)

    @field_validator('diseases')
    @classmethod
    def validate_diseases(cls, values):
        if any(not value.strip() or len(value) > 200 for value in values):
            raise ValueError('Tên bệnh không được trống hoặc dài quá 200 ký tự')
        return list(dict.fromkeys(canonical_disease(value) for value in values))


NOTE = ('Số liệu là lượt bài báo, không phải số ca bệnh. Mỗi bệnh được tính riêng; '
        'không cộng các chuỗi thành tổng ca. Z-score và khoảng dự báo không chứng minh p < 0,05. '
        'Báo dẫn lại cùng nguồn có thể làm tăng lượt bài. '
        'Dấu — hoặc ô trống là chỉ số không tính được; xem cột trạng thái để biết nguyên nhân.')


# Retain the exact server-generated view for export, including Prophet uncertainty.
# Bounded storage avoids trusting numerical data submitted by the browser.
_snapshots = OrderedDict()
_snapshot_lock = Lock()


def snapshot_settings(request):
    return (tuple(request.diseases), request.mode, request.days, request.interval_width)


def create_interactive_snapshot(db, request):
    report = build_interactive_data(db, request)
    snapshot_id = str(uuid4())
    with _snapshot_lock:
        now = monotonic()
        for key in list(_snapshots):
            if _snapshots[key][0] <= now:
                del _snapshots[key]
        while len(_snapshots) >= 128:
            _snapshots.popitem(last=False)
        _snapshots[snapshot_id] = (now + 1800, snapshot_settings(request), report)
    return {**report, 'snapshot_id': snapshot_id}


def get_interactive_snapshot(request):
    with _snapshot_lock:
        saved = _snapshots.get(request.snapshot_id)
        if saved is None or saved[0] <= monotonic() or saved[1] != snapshot_settings(request):
            return None
        return saved[2]


def build_interactive_data(db, request: InteractiveReportRequest):
    sections = []
    for disease in request.diseases:
        if request.mode == 'zscore':
            data = stats.get_zscore_spikes(db, disease_name=disease, days=request.days, window=14)
            evaluated = sum(row['zscore'] is not None for row in data)
            alerts = sum(row['spike_level'] in {'alert', 'danger'} for row in data)
            summary = (f"{sum(row['count'] for row in data)} bài trong {request.days} ngày; "
                       f"{evaluated} ngày tính được Z-score; {alerts} ngày vượt ngưỡng."
                       if evaluated else f"{sum(row['count'] for row in data)} bài trong {request.days} ngày. "
                       'Chưa đủ đường nền để đánh giá bất thường.')
            tables = [(f'Lượt bài trong {request.days} ngày quan sát — đường nền trượt 14 ngày',
                       ['Ngày', 'Bài/ngày', 'TB 14 ngày', 'Độ lệch chuẩn', 'Z-score', 'Trạng thái'],
                       [[row['date'], row['count'], row['ma'], row['std'], row['zscore'],
                         {'alert': 'Vượt ngưỡng 2σ', 'danger': 'Vượt ngưỡng 3σ',
                          'normal': 'Trong ngưỡng',
                          'insufficient_baseline': ('Không tính Z-score (σ = 0)' if row.get('baseline_status') == 'zero_variance'
                                                    else 'Thiếu lịch sử trước ngày này')}.get(row['spike_level'], row['spike_level'])]
                        for row in data])]
        else:
            data = stats.get_prophet_forecast(db, disease_name=disease, horizon_days=7,
                                             interval_width=request.interval_width)
            metrics = data.get('metrics') or {}
            summary = (f"{sum(row['y'] for row in data.get('historical', []))} bài trong lịch sử quan sát. "
                       f"Prophet · {data.get('history_days', 0)} ngày lịch sử hoàn chỉnh · "
                       f"khoảng dự báo {request.interval_width:.0%}. "
                       f"MAE: {display(metrics.get('mae'))}; RMSE: {display(metrics.get('rmse'))} bài/ngày. "
                       f"{metrics.get('eval_method', '')}. "
                       f"{data.get('error') or 'Chưa có ngưỡng sai số được thẩm định để kết luận độ tin cậy cao.'}")
            tables = [
                ('Dự báo 7 ngày', ['Ngày', 'Bài dự kiến', 'Giới hạn dưới', 'Giới hạn trên'],
                 [[row['ds'], row['yhat'], row['yhat_lower'], row['yhat_upper']] for row in data.get('forecast', [])]),
                ('Dữ liệu lịch sử', ['Ngày', 'Bài thực tế'],
                 [[row['ds'], row['y']] for row in data.get('historical', [])]),
            ]
        remarks = [summary]
        if request.mode == 'zscore':
            for row in reversed(data):
                if row['spike_level'] in {'alert', 'danger'}:
                    remarks.append(f"Ngày {row['date']}: {row['count']} bài; Z-score {row['zscore']}; "
                                   f"trung bình 14 ngày {row['ma']} bài/ngày. Cần đối chiếu nguồn tin.")
            remarks.append('Biến động lượt bài chưa phải bằng chứng ca bệnh tăng hoặc dịch bùng phát.')
        elif data.get('forecast'):
            first, last = data['forecast'][0], data['forecast'][-1]
            remarks.append(f"Giá trị điểm ngày {first['ds']}: {first['yhat']} bài; "
                           f"ngày {last['ds']}: {last['yhat']} bài. "
                           'Chưa kết luận xu hướng có ý nghĩa thống kê.')
        sections.append({'disease': disease, 'summary': summary, 'remarks': remarks,
                         'tables': tables, 'chart_data': data})
    return {
        'title': 'Phân tích đột biến theo bệnh' if request.mode == 'zscore' else 'Dự báo xu hướng báo chí theo bệnh',
        'generated_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(timespec='seconds'),
        'note': NOTE, 'sections': sections, 'mode': request.mode,
        'interval_width': request.interval_width,
    }


def display(value):
    return '—' if value is None else str(value)


def render_interactive_chart(report, sections=None):
    """Render source series with independent colors; missing baselines stay missing."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
    from matplotlib.ticker import MaxNLocator
    figure = Figure(figsize=(10, 4.2), dpi=180, layout='constrained')
    FigureCanvasAgg(figure)
    axis = figure.add_subplot()
    colors = ['#0284c7', '#d97706', '#0d9488', '#9333ea', '#dc2626', '#4f46e5']
    sections = report['sections'] if sections is None else sections
    has_points = False
    for item in sections:
        color = colors[report['sections'].index(item) % len(colors)]
        data = item['chart_data']
        if report['mode'] == 'zscore':
            if not data:
                continue
            dates = [datetime.fromisoformat(row['date']) for row in data]
            axis.plot(dates, [row['count'] for row in data], color=color, label=item['disease'], linewidth=1.8)
            means = [float('nan') if row['ma'] is None else row['ma'] for row in data]
            thresholds = [row['ma'] + 2 * row['std'] if row['ma'] is not None and row['std'] is not None and row['std'] > 0 else float('nan') for row in data]
            axis.plot(dates, means, color=color, alpha=.4, linewidth=1)
            axis.plot(dates, thresholds, color=color, linestyle='--', linewidth=1)
            alerts = [row for row in data if row['spike_level'] in {'alert', 'danger'}]
            axis.scatter([datetime.fromisoformat(row['date']) for row in alerts], [row['count'] for row in alerts], color=color, s=22, zorder=4)
            has_points = True
        else:
            history, future = data.get('historical', []), data.get('forecast', [])
            if history:
                axis.plot([datetime.fromisoformat(row['ds']) for row in history], [row['y'] for row in history], color=color, label=item['disease'], linewidth=1.6)
                has_points = True
            if future:
                dates = [datetime.fromisoformat(row['ds']) for row in future]
                axis.plot(dates, [row['yhat'] for row in future], color=color, linestyle='--', linewidth=1.8, label=None if history else item['disease'])
                axis.fill_between(dates, [row['yhat_lower'] for row in future], [row['yhat_upper'] for row in future], color=color, alpha=.12)
                has_points = True
    if has_points:
        locator = AutoDateLocator(minticks=4, maxticks=8)
        axis.xaxis.set_major_locator(locator)
        axis.xaxis.set_major_formatter(ConciseDateFormatter(locator))
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        axis.set_ylim(bottom=0)
        axis.legend(loc='upper left', fontsize=9, ncol=min(3, len(sections)), frameon=False)
    else:
        axis.text(.5, .5, 'Chưa đủ dữ liệu để vẽ biểu đồ', ha='center', va='center', transform=axis.transAxes)
        axis.set_xticks([])
    axis.set_ylabel('Bài báo / ngày')
    axis.set_title(report['title'], fontsize=12, loc='left', pad=12)
    axis.grid(axis='y', alpha=.2)
    axis.spines[['top', 'right']].set_visible(False)
    output = io.BytesIO()
    figure.savefig(output, format='png', facecolor='white')
    return output.getvalue()


def chart_caption(report):
    return ('Mỗi màu là một bệnh. Nét liền: lượt bài; nét mờ: trung bình 14 ngày; '
            'nét đứt: ngưỡng MA + 2σ; chấm tròn: ngày vượt ngưỡng.' if report['mode'] == 'zscore' else
            f"Mỗi màu là một bệnh. Nét liền: lượt bài thực tế; nét đứt: dự báo; vùng mờ: khoảng dự báo {report['interval_width']:.0%}.")


def add_readable_report(workbook, report):
    """Keep a sequential, printable report alongside the existing data sheets."""
    sheet = workbook.create_sheet('Báo cáo')
    sheet.sheet_view.showGridLines = False
    for column in 'ABCDEF':
        sheet.column_dimensions[column].width = 18
    row = 1

    def paragraph(text, heading=False):
        nonlocal row
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = sheet.cell(row, 1, text)
        cell.data_type = 's'
        cell.font = Font(name='Arial', size=12 if heading else 11, bold=heading)
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        sheet.row_dimensions[row].height = max(26, 17 * len(wrap(text, 90)) + 10)
        row += 1

    def chart(sections=None):
        nonlocal row
        picture = Image(io.BytesIO(render_interactive_chart(report, sections)))
        picture.width, picture.height = 650, 273
        sheet.add_image(picture, f'A{row}')
        for index in range(row, row + 15):
            sheet.row_dimensions[index].height = 15
        row += 15
        paragraph(chart_caption(report))

    paragraph(report['title'], heading=True)
    paragraph('EpiScout AI')
    paragraph(f"Thời điểm tổng hợp (UTC+07:00): {report['generated_at']}")
    paragraph(report['note'])
    paragraph('Biểu đồ so sánh các bệnh đã chọn', heading=True)
    chart()
    for item in report['sections']:
        sheet.row_breaks.append(Break(id=row - 1))
        paragraph(item['disease'], heading=True)
        chart([item])
        paragraph('Nhận xét riêng', heading=True)
        for remark in item['remarks']:
            paragraph(remark)
        for title, headers, rows in item['tables']:
            paragraph(title, heading=True)
            for column, header in enumerate(headers, 1):
                cell = sheet.cell(row, column, header)
                cell.data_type = 's'
                cell.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='0284C7')
                cell.alignment = Alignment(wrap_text=True, vertical='center')
            sheet.row_dimensions[row].height = 32
            row += 1
            for values in rows:
                height = 30
                for column, value in enumerate(values, 1):
                    cell = sheet.cell(row, column, '—' if value is None else value)
                    if isinstance(cell.value, str):
                        cell.data_type = 's'
                    cell.font = Font(name='Arial', size=10)
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
                    height = max(height, 14 * len(wrap(str(cell.value), 17)) + 6)
                    if isinstance(value, float):
                        cell.number_format = '0.00'
                sheet.row_dimensions[row].height = height
                row += 1
            if not rows:
                paragraph('Chưa đủ dữ liệu cho mục này.')
            row += 1
    sheet.print_area = f'A1:F{row - 1}'
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.orientation = 'portrait'
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0


def disease_sheet_name(disease, existing_names):
    # Excel forbids these characters and limits tab names to 31 characters.
    base = re.sub(r'[\\/*?:\[\]]', '-', disease).strip("'")[:31] or 'Bệnh'
    used = {name.casefold() for name in existing_names}
    name, suffix = base, 2
    while name.casefold() in used:
        tail = f' ({suffix})'
        name = base[:31 - len(tail)] + tail
        suffix += 1
    return name


def build_interactive_word(report):
    doc = Document()
    page = doc.sections[0]
    page.page_width, page.page_height = Cm(21), Cm(29.7)
    page.top_margin = page.bottom_margin = Cm(1.8)
    page.left_margin = page.right_margin = Cm(1.8)
    doc.styles['Normal'].font.name = 'Arial'
    doc.styles['Normal'].font.size = Pt(10)
    for name in ['Title', 'Heading 1', 'Heading 2']:
        doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)

    def table(headers, rows):
        result = doc.add_table(rows=1, cols=len(headers))
        result.style = 'Light Shading Accent 1'
        result.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
        for cell, header in zip(result.rows[0].cells, headers):
            cell.text = header
        for values in rows:
            for cell, value in zip(result.add_row().cells, values):
                cell.text = display(value)
        return result

    doc.add_heading(report['title'], 0)
    doc.add_paragraph('EpiScout AI')
    doc.add_paragraph(f"Thời điểm tổng hợp (UTC+07:00): {report['generated_at']}")
    doc.add_heading('Tổng quan', 1)
    doc.add_paragraph(report['note'])
    doc.add_picture(io.BytesIO(render_interactive_chart(report)), width=Cm(17))
    doc.add_paragraph(chart_caption(report))
    table(['Bệnh', 'Nhận xét tổng quan'], [[item['disease'], item['summary']] for item in report['sections']])
    for index, item in enumerate(report['sections']):
        doc.add_page_break()
        if index == 0:
            doc.add_heading('Báo cáo chi tiết từng bệnh', 1)
        doc.add_heading(item['disease'], 2)
        doc.add_picture(io.BytesIO(render_interactive_chart(report, [item])), width=Cm(17))
        doc.add_paragraph(chart_caption(report))
        doc.add_heading('Nhận xét riêng', 2)
        for remark in item['remarks']:
            doc.add_paragraph(remark)
        for title, headers, rows in item['tables']:
            doc.add_heading(title, 2)
            if rows:
                table(headers, rows)
            else:
                doc.add_paragraph('Chưa đủ dữ liệu cho mục này.')
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def build_interactive_excel(report):
    workbook = Workbook()
    overview = workbook.active
    overview.title = 'Tổng quan'
    overview.append([report['title']])
    overview.append(['Thời điểm (UTC+07:00)', report['generated_at']])
    overview.append([report['note']])
    overview.append(['Bệnh', 'Nhận xét'])
    overview_image = Image(io.BytesIO(render_interactive_chart(report)))
    overview_image.width, overview_image.height = 900, 378
    overview.add_image(overview_image, 'H2')
    overview.merge_cells('H22:T22')
    overview['H22'] = chart_caption(report)
    overview['H22'].alignment = Alignment(wrap_text=True, vertical='top')
    overview.row_dimensions[22].height = 48
    for index, item in enumerate(report['sections'], 1):
        overview.cell(index + 4, 1, item['disease'])
        overview.cell(index + 4, 2, item['summary'])
        sheet = workbook.create_sheet(disease_sheet_name(item['disease'], [*workbook.sheetnames, 'Báo cáo']))
        sheet.append([item['disease']])
        sheet.append([item['summary']])
        sheet.merge_cells('A1:F1')
        sheet.merge_cells('A2:F2')
        sheet['A2'].alignment = Alignment(wrap_text=True, vertical='top')
        sheet.row_dimensions[2].height = 65
        for title, headers, rows in item['tables']:
            sheet.append([])
            sheet.append([title])
            sheet.append(headers)
            for row in rows:
                sheet.append(row)
            if not rows:
                sheet.append(['Chưa đủ dữ liệu'])
        chart = Image(io.BytesIO(render_interactive_chart(report, [item])))
        chart.width, chart.height = 900, 378
        sheet.add_image(chart, 'H2')
        sheet.merge_cells('H22:T22')
        sheet['H22'] = chart_caption(report)
        sheet['H22'].alignment = Alignment(wrap_text=True, vertical='top')
        sheet.row_dimensions[22].height = 48
        for offset, remark in enumerate(['Nhận xét riêng', *item['remarks']], 24):
            sheet.merge_cells(start_row=offset, start_column=8, end_row=offset, end_column=20)
            cell = sheet.cell(offset, 8, remark)
            cell.alignment = Alignment(wrap_text=True, vertical='top')
            sheet.row_dimensions[offset].height = 48
    for sheet in workbook:
        sheet.column_dimensions['A'].width = 25
        for column in 'BCDEF':
            sheet.column_dimensions[column].width = 24
        for row in sheet:
            for cell in row:
                # Source strings must stay text, even if they start with '='.
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                cell.font = Font(name='Arial', size=11)
        for cell in sheet[1]:
            cell.font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='0284C7')
    overview.column_dimensions['B'].width = 100
    overview.merge_cells('A3:F3')
    overview['A3'].alignment = Alignment(wrap_text=True, vertical='top')
    overview.row_dimensions[3].height = 48
    for row in overview.iter_rows(min_row=5, max_row=4 + len(report['sections'])):
        row[1].alignment = Alignment(wrap_text=True, vertical='top')
        overview.row_dimensions[row[0].row].height = 65
    add_readable_report(workbook, report)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
