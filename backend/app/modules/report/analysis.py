"""Reports rendered from source facts; model prose cannot change numeric facts."""
from collections import Counter
from math import ceil

from ..news.disease_catalog import disease_names


def build_analysis_report(context: dict, skip: int = 0, include_all_articles: bool = False) -> dict:
    articles = context.get('articles', [])
    counts = Counter()
    for article in articles:
        counts.update(disease_names((article.get('disease') or '').split(',')))
    top = [{'disease': name, 'article_count': count} for name, count in counts.most_common(5)]
    findings = [f"{item['disease']}: {item['article_count']} bài trong kỳ." for item in top]
    headline = f"Hệ thống ghi nhận {len(articles)} bài hợp lệ trong kỳ."
    forecasts = []
    for forecast in context.get('forecasts', []):
        points = forecast.get('forecast', [])
        metrics = forecast.get('metrics') or {}
        forecasts.append({
            'disease_name': forecast.get('disease_name'), 'model_name': 'Meta Prophet',
            'metric_type': 'mention_count', 'interval_width': forecast.get('interval_width'),
            'interval_type': 'prediction_interval', 'metrics': metrics,
            'forecast_summary': (
                f"Giá trị điểm ngày {points[0]['ds']}: {points[0]['yhat']} bài; "
                f"ngày {points[-1]['ds']}: {points[-1]['yhat']} bài."
                if points else forecast.get('error', 'Chưa đủ thông tin dự báo.')
            ),
            'future_projections': [{'date': row['ds'], 'expected_articles': row['yhat'],
                                    'lower_bound': row['yhat_lower'], 'upper_bound': row['yhat_upper']} for row in points],
            'analyst_interpretation': 'Lượt bài cần đối chiếu với thông tin y tế; chưa kết luận xu hướng có ý nghĩa thống kê.',
            'p_value': None, 'significance_test': 'not_performed',
            'limitations': forecast.get('limitations', []),
        })
    spikes = [{**row, 'p_value': None, 'significance_test': 'not_performed',
               'interpretation': 'Vượt ngưỡng theo dõi lượt bài; chưa phải bằng chứng dịch bùng phát.'}
              for row in context.get('zscore_spikes', [])]
    details = []
    selected_articles = articles[skip:] if include_all_articles else articles[skip:skip + 5]
    for index, article in enumerate(selected_articles, skip + 1):
        observations = article.get('observations', [])
        # Source claims stay separate. Missing or legacy case_count is never 0.
        verified = [row for row in observations if row.get('verified') and row.get('case_type') == 'confirmed']
        details.append({
            'index': index, 'id': article.get('id'), 'title': article['title'],
            'source': article.get('source'), 'link': article.get('link'),
            'published_date': article.get('published_date'), 'disease': article.get('disease'),
            'location': ', '.join(article.get('locations', [])) or 'Chưa xác định',
            'confirmed_cases': verified[0]['reported_value'] if len(verified) == 1 else None,
            'suspected_cases': None,
            'evidence_quote': (observations[0].get('evidence_quote') or '')[:150] if observations else None,
            'observations': observations,
        })
    period = f"từ {context['period_start'].isoformat()} đến {context['period_end'].isoformat()} UTC"
    return {
        'report_metadata': {
            'generated_at': context['period_end'].isoformat() + 'Z', 'period': period,
            'total_articles': len(articles), 'confidence_level': None,
            'p_value': None, 'significance_test': 'not_performed',
            'clinical_cases_total': None,
        },
        'executive_summary': {'headline': headline, 'key_findings': findings,
                              'top_diseases': top, 'epidemiological_alerts': context.get('verified_events', []),
                              'media_alerts': spikes},
        'media_trend_forecast': forecasts[0] if forecasts else None,
        'media_trend_forecasts': forecasts,
        'detailed_articles_pagination': {'chunk_size': 5, 'total_chunks': ceil(len(articles) / 5),
                                        'skip': skip, 'next_skip': skip + 5 if not include_all_articles and skip + 5 < len(articles) else None,
                                        'articles': details},
        # Existing summary card contract is preserved.
        'period': period, 'headline': headline,
        'summaries': [{'text': text, 'evidence_count': item['article_count'], 'confidence': 'unassessed'}
                      for text, item in zip(findings, top)],
        'recommendations': ['Đối chiếu từng số ca với trích dẫn và nguồn y tế.',
                            'Kiểm tra các bài dẫn lại cùng nguồn trước khi đánh giá mức độ quan tâm.'],
        'has_alert': bool(spikes or context.get('verified_events')),
        'message': None if articles else 'Chưa có bài hợp lệ trong kỳ; chưa đủ thông tin đánh giá tình hình dịch bệnh.',
    }


def validate_summary_prose(parsed: dict, context: dict) -> dict:
    """Only accept model selections of existing fact sentences, never new prose."""
    report = build_analysis_report(context)
    allowed = {item['text']: item for item in report['summaries']}
    selected = []
    for item in parsed.get('summaries', []) if isinstance(parsed.get('summaries'), list) else []:
        if isinstance(item, dict) and item.get('text') in allowed and allowed[item['text']] not in selected:
            selected.append(allowed[item['text']])
    if selected:
        report['summaries'] = selected
    return report
