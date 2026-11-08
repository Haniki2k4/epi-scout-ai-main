import os
os.environ.setdefault('DATABASE_URL', 'mysql+pymysql://root@127.0.0.1:1/unused')

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.modules.auth.models import User
from backend.app.modules.evaluation.models import ArticleEvaluation
from backend.app.modules.news import models, crud, stats, crawler
from backend.app.modules.news.article_content import (
    extract_article_content, valid_relevance_evidence, canonical_relevance_evidence, MAX_ARTICLE_CHARS,
)


def test_read_body_not_meta_or_related_or_comment_with_malformed_paragraphs():
    body = 'CDC Cà Mau ghi nhận 2 ca viêm não mô cầu, một người tử vong. '
    paragraph = 'Ngành y tế đang điều tra nguồn lây, cấp thuốc dự phòng cho 22 người tiếp xúc gần. '
    html = f'''<meta name="description" content="Tóm tắt ngắn"><article>
    <div itemprop="articleBody"><div class="detail-content"><p>{body * 3}
    <p>{paragraph * 3}<div class="VCSortableInPreviewMode"><a class="OneNewsTitle">Sốt đất</a><p>99 ca Ebola</div>
    <div class="related-news"><p>Tin khuyến mãi</p></div></div>
    <div class="modal"><p>Bình luận của độc giả</p></div></div></article>'''
    content = extract_article_content(html)
    assert content.status == 'full_text'
    assert body in content.text and paragraph in content.text
    assert not any(s in content.text for s in ['99 ca Ebola', 'Sốt đất', 'khuyến mãi', 'Bình luận', 'Tóm tắt ngắn'])


def test_no_article_body_or_silent_truncation():
    assert extract_article_content('<meta name="description" content="dịch bệnh"><nav><p>Ổ dịch</p></nav>').status == 'body_not_found'
    assert extract_article_content(f'<article><p>{"a" * MAX_ARTICLE_CHARS}</p><p>{"b" * 100}</p></article>').status == 'too_long'


def test_relevant_requires_real_body_quote_not_invented_or_title_only():
    body = 'CDC tỉnh Thanh Hóa báo cáo chùm 15 ca mắc cúm A tại trường mầm non.'
    evidence = dict(signal_type='outbreak', quote=body)
    assert valid_relevance_evidence(evidence, '', body)
    assert not valid_relevance_evidence(evidence, body, 'Bài tư vấn cá nhân về dinh dưỡng.')
    assert not valid_relevance_evidence(dict(evidence, quote='CDC ghi nhận 100 ca Ebola tại Hà Nội.'), '', body)
    assert not valid_relevance_evidence(None, '', body)


def test_citation_can_retain_a_complete_exact_source_paragraph_without_headline():
    paragraph = 'CDC tỉnh Thanh Hóa báo cáo chùm 15 ca mắc cúm A tại trường mầm non.'
    body = paragraph + '\n\nCơ quan y tế đang tiến hành điều tra.'
    value = {'signal_type': 'outbreak', 'quote': 'Tin mới. ' + paragraph + ' Một đoạn khác.'}
    assert canonical_relevance_evidence(value, 'Tin mới', body) == dict(value, quote=paragraph)
    assert canonical_relevance_evidence(dict(value, quote='CDC ghi nhận 100 ca Ebola tại Hà Nội.'), '', body) is None


def test_local_provider_without_fallback_does_not_call_an_empty_model(monkeypatch):
    monkeypatch.setattr(crawler, 'LLM_RECHECK_ENABLED', True)
    monkeypatch.setattr(crawler, 'LLM_RECHECK_MODEL', 'episcout-local')
    monkeypatch.setattr(crawler, 'LLM_FALLBACK_MODEL', '')
    monkeypatch.setattr(crawler, 'get_llm_preflight_status', lambda: {'ok': True})
    monkeypatch.setattr(crawler, '_get_llm_cooldown_status', lambda: (False, ''))
    monkeypatch.setattr(crawler, '_llm_session_is_fallback', False)
    monkeypatch.setattr(crawler, '_llm_circuit_state', 'OPEN')
    calls = []
    def provider(model, *args):
        calls.append(model)
        return {'label': 'irrelevant', 'reason': 'Tin kinh tế'}
    monkeypatch.setattr(crawler, '_call_llm_api', provider)
    label, _, _, _ = crawler.llm_recheck_article('Cơn sốt mua bán', 'Tin kinh tế thị trường', ['sốt'])
    assert label == 'irrelevant' and calls == ['episcout-local']


@pytest.mark.parametrize('evidence,matched,expected', [
    (None, ['cúm A'], 'unsure'),
    ({'signal_type': 'outbreak', 'quote': 'CDC Thanh Hóa ghi nhận 15 ca cúm A tại trường mầm non.'}, ['cúm A'], 'relevant'),
    ({'signal_type': 'outbreak', 'quote': 'CDC Thanh Hóa ghi nhận 15 ca cúm A tại trường mầm non.'}, ['Ebola'], 'unsure'),
])
def test_llm_relevant_without_evidence_is_quarantined(monkeypatch, evidence, matched, expected):
    monkeypatch.setattr(crawler, 'LLM_RECHECK_ENABLED', True)
    monkeypatch.setattr(crawler, 'get_llm_preflight_status', lambda: {'ok': True})
    monkeypatch.setattr(crawler, '_get_llm_cooldown_status', lambda: (False, ''))
    monkeypatch.setattr(crawler, '_llm_session_is_fallback', False)
    monkeypatch.setattr(crawler, '_llm_circuit_state', 'CLOSED')
    monkeypatch.setattr(crawler, '_call_llm_api', lambda *args: {
        'label': 'relevant', 'matched_keywords': matched, 'relevance_evidence': evidence,
        'diseases': [{'disease_name': 'cúm A', 'new_cases': 15}],
    })
    label, keywords, _, meta = crawler.llm_recheck_article(
        '15 ca cúm A', 'CDC Thanh Hóa ghi nhận 15 ca cúm A tại trường mầm non.', ['cúm A'], require_evidence=True,
    )
    assert label == expected
    if expected == 'unsure':
        assert meta['diseases'] == [] and keywords == []


def test_legacy_labels_cannot_leak_into_public_articles_or_stats():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    from datetime import datetime
    with sessionmaker(bind=engine)() as db:
        for i, (llm, human) in enumerate([('noise', None), ('unsure', None), ('relevant', 'irrelevant'), ('unsure', 'relevant')]):
            row = models.ArticleIdentity(title=str(i), link=f'https://example.org/{i}', is_excluded=False, published_date=datetime.utcnow())
            row.details = models.ArticleDetails(keywords_matched='cúm A')
            db.add(row)
            db.flush()
            db.add(ArticleEvaluation(article_id=row.id, llm_label=llm, human_label=human))
        db.commit()
        assert [r.title for r in crud.get_articles(db)] == ['3']
        assert crud.count_articles(db) == 1
        assert len(crud.get_articles(db, include_excluded=True)) == 4
        assert stats.get_disease_breakdown(db, 'virus')['total_articles'] == 1
    engine.dispose()


@pytest.mark.parametrize('status,label', [('body_not_found', 'relevant'), ('full_text', 'noise'), ('full_text', 'unsure'), ('full_text', None)])
def test_manual_article_import_cannot_bypass_content_review(monkeypatch, status, label):
    from fastapi import HTTPException
    from backend.app.modules.news.article_content import ArticleContent
    from backend.app.modules.news.router_articles import save_article
    from backend.app.modules.news.schemas import ArticleCreate
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    monkeypatch.setattr(crawler, 'fetch_article_content', lambda url: ArticleContent('Nội dung bài', status))
    monkeypatch.setattr(crawler, 'matches_keywords', lambda *args: 'cúm A')
    monkeypatch.setattr(crawler, 'llm_recheck_article', lambda *args, **kwargs: (label, [], 'Chưa đủ bằng chứng', {}))
    with sessionmaker(bind=engine)() as db:
        with pytest.raises(HTTPException) as error:
            save_article(ArticleCreate(title='Bài gửi lên', link='https://example.org/test', event_id=99), db, User())
        assert error.value.status_code == 422
        assert db.query(models.ArticleIdentity).count() == 0
    engine.dispose()
