"""Apply reversible exclusions from existing labels and a source-text review plan.

No articles, observations, keywords or human labels are deleted or rewritten.
Run without --apply first to produce the report.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.orm import joinedload

from backend.app.core.database import SessionLocal
from backend.app.modules.auth.models import User
from backend.app.modules.evaluation.models import ArticleEvaluation
from backend.app.modules.news import models, event_service
from backend.app.modules.news.article_content import normalized_quote


def values(row):
    return {column.key: getattr(row, column.key) for column in inspect(row).mapper.columns} if row else None


def review_decision(article, evaluation, source, overrides):
    effective = (evaluation.human_label or evaluation.llm_label) if evaluation else None
    if effective in {'noise', 'irrelevant'}:
        return effective, f'Nhãn thẩm định hiện có: {effective}; loại khỏi giám sát công khai.'
    override = overrides.get(str(article.id))
    if override:
        quote = override.get('quote', '')
        if len(quote) < 30 or normalized_quote(quote) not in normalized_quote(source.get('body', '')):
            raise ValueError(f'Review quote does not match body: {article.id}')
        if override['label'] not in {'noise', 'irrelevant'}:
            raise ValueError('Overrides may only exclude; they cannot approve uncertain articles')
        return override['label'], override['reason']
    if effective != 'relevant':
        return 'pending', 'Chờ thẩm định: chưa có kết luận liên quan đủ tin cậy.'
    if source.get('content_status') != 'full_text':
        return 'pending', f"Chờ thẩm định: chưa đọc được đầy đủ thân bài ({source.get('content_status')})."
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--content', required=True)
    parser.add_argument('--overrides', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--backup-dir', default='backups')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    sources = {r['id']: r for r in (json.loads(s) for s in Path(args.content).read_text(encoding='utf-8').splitlines())}
    overrides = json.loads(Path(args.overrides).read_text(encoding='utf-8'))
    with SessionLocal() as db:
        rows = db.query(models.ArticleIdentity).options(
            joinedload(models.ArticleIdentity.details), joinedload(models.ArticleIdentity.cases),
        ).filter(models.ArticleIdentity.is_excluded.isnot(True)).all()
        evaluations = {r.article_id: r for r in db.query(ArticleEvaluation).all()}
        actions, originals = [], []
        for row in rows:
            source = sources.get(row.id)
            if not source:
                raise ValueError(f'Missing source review for article {row.id}; refresh the audit')
            evaluation = evaluations.get(row.id)
            if (source.get('human_label'), source.get('llm_label')) != (
                evaluation.human_label if evaluation else None, evaluation.llm_label if evaluation else None,
            ):
                raise ValueError(f'Review changed since snapshot for article {row.id}')
            decision = review_decision(row, evaluation, source, overrides)
            if decision:
                label, reason = decision
                actions.append(dict(id=row.id, title=row.title, category=label, reason=reason))
                originals.append(dict(article=values(row), details=values(row.details),
                                      evaluation=values(evaluation), cases=[values(c) for c in row.cases]))
        report = dict(before=len(rows), retained=len(rows) - len(actions), excluded=len(actions),
                      categories=dict(Counter(a['category'] for a in actions)), actions=actions, applied=False)
        if args.apply:
            actor = db.query(User).filter(User.role == 'admin', User.is_active.is_(True)).first()
            if not actor:
                raise ValueError('An active admin is required for event review logs')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup = Path(args.backup_dir) / f'relevance-review-before-{stamp}.json'
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(json.dumps(dict(
                database=db.bind.url.database, created_at=stamp, rows=originals,
                events=[values(r) for r in db.query(models.NewsEvent).all()],
            ), ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            by_id = {r.id: r for r in rows}
            for action in actions:
                row = by_id[action['id']]
                event_service.handle_article_exclusion_from_event(db, row, actor.id, action['reason'])
                if row.details:
                    row.details.llm_reason = ('Rà soát nội dung: ' + action['reason'])[:500]
            db.commit()
            report.update(applied=True, backup=str(backup))
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'actions'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
