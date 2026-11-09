"""Disease trends must never treat unresolved labels as unions of all diseases."""
import os
os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://root@127.0.0.1:1/unused')

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.app.modules.news import stats


@pytest.mark.parametrize(('disease', 'expected'), [
    ('virus', 1), ('virus chưa xác định', 1), ('Ebola', 2),
    ('sốt', 1), ('sốt xuất huyết', 3),
    ('H5N1', 1), ('cúm a/h9n2', 2),
])
def test_both_trend_models_count_only_the_requested_identity(monkeypatch, disease, expected):
    day = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    names = [
        {'virus chưa xác định'}, {'ebola'}, {'ebola', 'sốt xuất huyết'},
        {'sốt xuất huyết'}, {'sốt xuất huyết'}, {'sốt chưa rõ nguyên nhân'},
        {'cúm a/h5n1', 'cúm a/h9n2'}, {'cúm a/h9n2'},
    ]
    monkeypatch.setattr(stats, '_disease_rows', lambda *_: [
        SimpleNamespace(date_str=day, diseases=entry) for entry in names
    ])
    spikes = stats.get_zscore_spikes(None, disease_name=disease, days=30)
    forecast = stats.get_prophet_forecast(None, disease_name=disease)
    assert sum(row['count'] for row in spikes) == expected
    assert sum(row['y'] for row in forecast['historical']) == expected
    assert forecast['forecast'] == []  # One observed day cannot support a model.
    assert all(row['zscore'] is None for row in spikes)


def test_baseline_uses_corpus_history_before_first_disease_mention(monkeypatch):
    today = datetime.utcnow().date()
    rows = [SimpleNamespace(date_str=(today - timedelta(days=i)).isoformat(),
                            diseases={'ebola'} if i % 2 else {'sốt xuất huyết'})
            for i in range(44)]
    monkeypatch.setattr(stats, '_disease_rows', lambda *_: rows)
    result = stats.get_zscore_spikes(None, disease_name='Ebola', days=30)
    assert len(result) == 30
    assert all(row['baseline_status'] == 'available' for row in result)
    assert result[0]['ma'] == .5
    assert result[0]['std'] == .5
    assert result[0]['zscore'] == 1
