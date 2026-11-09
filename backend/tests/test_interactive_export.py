import io
import os
from types import SimpleNamespace

os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://root@127.0.0.1:1/unused')

import pytest
from docx import Document
from openpyxl import load_workbook
from pydantic import ValidationError

from backend.app.modules.report import interactive_export as export


def request(**kwargs):
    return export.InteractiveReportRequest(diseases=['Ebola', 'dengue'], mode='zscore', format='docx', **kwargs)


def test_export_rejects_empty_and_more_than_six_diseases():
    for diseases in [[], [''] , [str(i) for i in range(7)]]:
        with pytest.raises(ValidationError):
            export.InteractiveReportRequest(diseases=diseases, mode='zscore', format='docx')
    assert request().diseases == ['ebola', 'sốt xuất huyết']
    with pytest.raises(ValidationError):
        export.InteractiveReportRequest(diseases=['Ebola'], mode='zscore', format='xlsx')


def test_excel_keeps_data_and_adds_sequential_report_with_separate_diseases(monkeypatch):
    calls = []
    def spikes(db, disease_name, days, window):
        calls.append((disease_name, days, window))
        return [{'date': '2026-11-09', 'count': 2 if disease_name == 'ebola' else 3,
                 'ma': None, 'std': None, 'zscore': None, 'spike_level': 'insufficient_baseline'}]
    monkeypatch.setattr(export.stats, 'get_zscore_spikes', spikes)
    report = export.build_interactive_data(None, request(days=60))
    assert calls == [('ebola', 60, 14), ('sốt xuất huyết', 60, 14)]
    assert 'Chưa đủ đường nền' in report['sections'][0]['summary']
    book = load_workbook(io.BytesIO(export.build_interactive_excel(report)))
    assert book.sheetnames == ['Tổng quan', 'ebola', 'sốt xuất huyết', 'Báo cáo']
    assert book['Tổng quan']['A5'].value == 'ebola'
    assert book['Tổng quan']['A6'].value == 'sốt xuất huyết'
    assert book['ebola']['B6'].value == 2 and book['sốt xuất huyết']['B6'].value == 3
    assert book['ebola']['E6'].value is None
    assert all(len(book[name]._images) == 1 for name in ['Tổng quan', 'ebola', 'sốt xuất huyết'])
    readable = book['Báo cáo']
    assert len(readable._images) == 3
    assert sum(row[0].value == 'Nhận xét riêng' for row in readable) == 2
    assert [row[1].value for row in readable if row[0].value == '2026-11-09'] == [2, 3]
    assert all(row[4].value == '—' for row in readable if row[0].value == '2026-11-09')
    assert readable.page_setup.fitToWidth == 1
    assert readable.print_area
    assert book['ebola']['H24'].value == 'Nhận xét riêng'
    assert 'Chưa đủ đường nền' in book['ebola']['H25'].value


def test_forecast_exports_use_selected_interval_and_actual_metrics(monkeypatch):
    calls = []
    def forecast(db, disease_name, horizon_days, interval_width):
        calls.append((disease_name, horizon_days, interval_width))
        return {'history_days': 25, 'metrics': {'mae': 1.2, 'rmse': 2.3, 'eval_method': 'Train/Test'},
                'historical': [{'ds': '2026-11-09', 'y': 2}],
                'forecast': [{'ds': '2026-11-10', 'yhat': 1.5, 'yhat_lower': 0.2, 'yhat_upper': 2.1}]}
    monkeypatch.setattr(export.stats, 'get_prophet_forecast', forecast)
    body = export.InteractiveReportRequest(diseases=['Ebola'], mode='forecast', interval_width=.95, format='docx')
    report = export.build_interactive_data(None, body)
    assert calls == [('ebola', 7, .95)]
    assert 'MAE: 1.2; RMSE: 2.3' in report['sections'][0]['summary']
    book = load_workbook(io.BytesIO(export.build_interactive_excel(report)))
    assert [book['ebola'].cell(6, i).value for i in range(1, 5)] == ['2026-11-10', 1.5, .2, 2.1]
    assert len(book['ebola']._images) == 1
    assert '2026-11-10' in book['ebola']['H26'].value
    assert len(book['Báo cáo']._images) == 2
    assert any('MAE: 1.2; RMSE: 2.3' in str(row[0].value) for row in book['Báo cáo'])
    assert [row[1].value for row in book['Báo cáo'] if row[0].value == '2026-11-10'] == [1.5]


def test_interactive_endpoint_download_and_authentication(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.modules.report.router import router
    from backend.app.core.database import get_db
    from backend.app.modules.auth.security import get_current_active_user
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: None
    monkeypatch.setattr(export.stats, 'get_zscore_spikes', lambda *args, **kwargs: [])
    payload = {'diseases': ['Ebola'], 'mode': 'zscore', 'format': 'docx'}
    with TestClient(app) as client:
        assert client.post('/api/report/interactive-export', json=payload).status_code == 401
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(username='analyst')
        response = client.post('/api/report/interactive-export', json=payload)
        assert response.status_code == 200
        assert '.docx' in response.headers['content-disposition']
        doc = Document(io.BytesIO(response.content))
        assert 'Tổng quan' in [p.text for p in doc.paragraphs]
        assert 'Báo cáo chi tiết từng bệnh' in [p.text for p in doc.paragraphs]
        assert client.post('/api/report/interactive-export', json={**payload, 'format': 'xlsx'}).status_code == 422


@pytest.mark.parametrize(('mode', 'days', 'interval'), [
    ('zscore', 30, .8), ('zscore', 60, .8), ('zscore', 90, .8),
    ('forecast', 30, .8), ('forecast', 30, .95),
])
def test_web_snapshot_word_and_excel_sections_match_even_if_source_changes(monkeypatch, mode, days, interval):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.modules.report.router import router
    from backend.app.core.database import get_db
    from backend.app.modules.auth.security import get_current_active_user
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(username='analyst')
    def spikes(db, disease_name, days, window):
        return [dict(date='2026-11-09', count=5 if disease_name == 'ebola' else 8,
                     ma=1.5, std=.5, zscore=7 if disease_name == 'ebola' else 13,
                     spike_level='danger', baseline_status='available')]
    def forecast(db, disease_name, horizon_days, interval_width):
        return dict(historical=[dict(ds='2026-11-09', y=5 if disease_name == 'ebola' else 8)],
                    forecast=[dict(ds='2026-11-10', yhat=4.25 if disease_name == 'ebola' else 7.5,
                                   yhat_lower=2.1, yhat_upper=9.9)], history_days=25,
                    metrics=dict(mae=1.2, rmse=2.3, eval_method='Train/Test'), interval_width=interval_width)
    monkeypatch.setattr(export.stats, 'get_zscore_spikes', spikes)
    monkeypatch.setattr(export.stats, 'get_prophet_forecast', forecast)
    payload = dict(diseases=['Ebola', 'dengue'], mode=mode, days=days, interval_width=interval)
    with TestClient(app) as client:
        web = client.post('/api/report/interactive-data', json=payload).json()
        def changed_source(*args, **kwargs):
            raise AssertionError('Export must reuse the data already shown on the web')
        monkeypatch.setattr(export.stats, 'get_zscore_spikes', changed_source)
        monkeypatch.setattr(export.stats, 'get_prophet_forecast', changed_source)
        response = client.post('/api/report/interactive-export', json={**payload, 'snapshot_id': web['snapshot_id']})
        assert response.status_code == 200
        doc = Document(io.BytesIO(response.content))
        assert len(doc.inline_shapes) == 3
        paragraphs = [p.text for p in doc.paragraphs]
        for section, row in zip(web['sections'], doc.tables[0].rows[1:]):
            assert [c.text for c in row.cells] == [section['disease'], section['summary']]
            assert all(remark in paragraphs for remark in section['remarks'])
        expected_tables = [table for section in web['sections'] for table in section['tables']]
        for actual, (_, headers, rows) in zip(doc.tables[1:], expected_tables):
            assert [c.text for c in actual.rows[0].cells] == headers
            assert [[c.text for c in row.cells] for row in actual.rows[1:]] == [[export.display(v) for v in row] for row in rows]
        assert len(doc.tables) == 1 + len(expected_tables)
        assert client.post('/api/report/interactive-export', json={**payload, 'days': 90 if days != 90 else 30, 'snapshot_id': web['snapshot_id']}).status_code == 410
        with export._snapshot_lock:
            expires, settings, report = export._snapshots[web['snapshot_id']]
            export._snapshots[web['snapshot_id']] = (0, settings, report)
        assert client.post('/api/report/interactive-export', json={**payload, 'snapshot_id': web['snapshot_id']}).status_code == 410
