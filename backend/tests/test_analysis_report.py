import os
os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://root@127.0.0.1:1/unused')

from datetime import datetime, timedelta
from types import SimpleNamespace
import sys

from backend.app.modules.news import stats
from backend.app.modules.report.analysis import build_analysis_report, validate_summary_prose


def context():
    return {
        'period_start': datetime(2026, 11, 2), 'period_end': datetime(2026, 11, 3),
        'articles': [{'id': i, 'title': f'Bài {i}', 'disease': 'sởi', 'locations': ['Hà Nội'],
                      'observations': [{'reported_value': 10, 'case_type': 'confirmed',
                                        'count_scope': 'cumulative', 'evidence_quote': 'Nguồn ghi nhận 10 ca.', 'verified': False}]}
                     for i in range(7)],
        'forecasts': [{'disease_name': 'sởi', 'forecast': [], 'error': 'Chưa đủ dữ liệu',
                       'metrics': {'mae': None, 'rmse': None}, 'interval_width': .8}],
        'zscore_spikes': [{'zscore': 2.5, 'p_value': .01}],
    }


def test_pagination_and_missing_clinical_values_are_not_fabricated():
    report = build_analysis_report(context())
    assert report['report_metadata']['total_articles'] == 7
    assert report['report_metadata']['clinical_cases_total'] is None
    assert report['report_metadata']['confidence_level'] is None
    assert report['executive_summary']['media_alerts'][0]['p_value'] is None
    page = report['detailed_articles_pagination']
    assert len(page['articles']) == 5 and page['next_skip'] == 5 and page['total_chunks'] == 2
    assert all(article['confirmed_cases'] is None for article in page['articles'])
    assert len(build_analysis_report(context(), skip=5)['detailed_articles_pagination']['articles']) == 2
    assert len(build_analysis_report(context(), include_all_articles=True)['detailed_articles_pagination']['articles']) == 7
    assert report['media_trend_forecast']['metrics']['mae'] is None


def test_model_cannot_add_counts_places_or_confidence_to_a_grounded_report():
    parsed = {'headline': 'Có 999 ca Ebola tại X', 'summaries': [
        {'text': '999 ca ở X', 'evidence_count': 999, 'confidence': 'high'},
        {'text': 'sởi: 7 bài trong kỳ.', 'evidence_count': 999, 'confidence': 'high'},
    ], 'has_alert': False}
    report = validate_summary_prose(parsed, context())
    assert '999' not in report['headline']
    assert report['summaries'] == [{'text': 'sởi: 7 bài trong kỳ.', 'evidence_count': 7, 'confidence': 'unassessed'}]


def test_short_history_does_not_pad_missing_earlier_days(monkeypatch):
    today = datetime.utcnow().date()
    monkeypatch.setattr(stats, '_disease_rows', lambda *_: [
        SimpleNamespace(date_str=(today - timedelta(days=i)).isoformat(), diseases={'sởi'}) for i in range(2)
    ])
    result = stats.get_prophet_forecast(None, 'sởi')
    assert len(result['historical']) == 2
    assert result['forecast'] == [] and result['metrics']['mae'] is None
    assert result['p_value'] is None and result['history_days'] == 1


def test_zero_variance_baseline_has_no_invented_z_score(monkeypatch):
    monkeypatch.setattr(stats, '_disease_rows', lambda *_: [])
    result = stats.get_zscore_spikes(None, days=3)
    assert all(row['zscore'] is None and row['spike_level'] == 'insufficient_baseline' for row in result)


def test_forecast_evaluation_is_chronological_and_excludes_partial_today(monkeypatch):
    import pandas as pd
    today = datetime.utcnow().date()
    monkeypatch.setattr(stats, '_disease_rows', lambda *_: [
        SimpleNamespace(date_str=(today - timedelta(days=i)).isoformat(), diseases={'sởi'}) for i in range(31)
    ])
    fitted = []
    class Prophet:
        def __init__(self, **kwargs):
            assert kwargs['interval_width'] == .95
        def fit(self, df):
            self.df = df.copy()
            fitted.append(df.copy())
        def make_future_dataframe(self, periods):
            return pd.DataFrame({'ds': pd.date_range(self.df.ds.min(), self.df.ds.max() + timedelta(days=periods))})
        def predict(self, future):
            return future.assign(yhat=1., yhat_lower=0., yhat_upper=2.)
    monkeypatch.setitem(sys.modules, 'prophet', SimpleNamespace(Prophet=Prophet))
    result = stats.get_prophet_forecast(None, 'sởi', horizon_days=7, interval_width=.95)
    assert len(result['forecast']) == 7
    assert result['forecast'][0]['ds'] == (today + timedelta(days=1)).isoformat()
    assert fitted[0].ds.max().date() == today - timedelta(days=1)
    assert fitted[1].ds.max() < fitted[0].ds.max()
    assert result['metrics']['mae'] == 0 and result['metrics']['rmse'] == 0
    assert result['metrics']['test_days'] == 6 and result['p_value'] is None


def test_report_context_excludes_hidden_articles_and_counts_more_than_fifty(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.core.database import Base
    from backend.app.modules.auth.models import User
    from backend.app.modules.evaluation.models import ArticleEvaluation
    from backend.app.modules.news import models
    from backend.app.modules.report.ai_summary import build_daily_summary_context
    monkeypatch.setattr(stats, 'get_prophet_forecast', lambda *args, **kwargs: {'forecast': [], 'metrics': {'mae': None, 'rmse': None}})
    monkeypatch.setattr(stats, 'get_zscore_spikes', lambda *args, **kwargs: [])
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        for i in range(62):
            row = models.ArticleIdentity(title=f'Bài {i}', link=f'https://example.org/{i}',
                                         published_date=datetime.utcnow(), is_excluded=(i == 60))
            row.details = models.ArticleDetails(keywords_matched='sởi')
            db.add(row)
            db.flush()
            if i == 61:
                db.add(ArticleEvaluation(article_id=row.id, llm_label='irrelevant'))
        db.commit()
        data = build_daily_summary_context(db)
        report = build_analysis_report(data)
        assert len(data['articles']) == 60
        assert report['report_metadata']['total_articles'] == 60
        assert report['executive_summary']['top_diseases'] == [{'disease': 'sởi', 'article_count': 60}]
    engine.dispose()
