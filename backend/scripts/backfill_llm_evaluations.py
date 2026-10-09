"""Idempotent backfill for the unified Stage 2 evaluation tables."""
import argparse
import json
import uuid
from collections import Counter
from datetime import datetime
import sys
from pathlib import Path

# Thêm thư mục backend vào sys.path để import được module app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.modules.auth import models as auth_models  # noqa: F401 - Đăng ký bảng users vào metadata
from app.modules.evaluation import models as evaluation_models
from app.modules.evaluation.writer import identity_for, normalize_url
from app.modules.news import models as news_models

NAMESPACE = uuid.UUID("a6c429d2-5a23-4c91-b75f-2c2bf3e52109")
VALID_LABELS = {"relevant", "noise", "irrelevant", "unsure"}


def ids(source: str, primary_key) -> tuple[str, str]:
    return (
        str(uuid.uuid5(NAMESPACE, f"legacy:chain:{source}:{primary_key}")),
        str(uuid.uuid5(NAMESPACE, f"legacy:run:{source}:{primary_key}")),
    )


def upsert_item(db, *, link, title, summary, published_date, article_id=None, source_domain=None):
    key, method, c_hash = identity_for(link or "", title or "", summary or "", published_date)
    item = db.query(evaluation_models.LlmEvaluationItem).filter_by(identity_key=key).first()
    if item is None:
        item = evaluation_models.LlmEvaluationItem(
            identity_key=key, identity_method=method, content_hash=c_hash,
            canonical_url=normalize_url(link or "") or None, article_id=article_id,
            source_domain=source_domain, published_date=published_date,
            title_snapshot=(title or "Không có tiêu đề")[:500],
            summary_snapshot=summary or "", created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(item)
        db.flush()
    elif article_id and item.article_id is None:
        item.article_id = article_id
    return item


def add_run(db, item, *, source, primary_key, label, title, summary, route, created_at):
    chain_id, inference_id = ids(source, primary_key)
    existing = db.query(evaluation_models.LlmInferenceRun).filter_by(inference_id=inference_id).first()
    if existing:
        return existing, False
    timestamp = created_at or datetime.utcnow()
    normalized_label = label if label in VALID_LABELS else None
    status = "success" if normalized_label else "disabled"
    run = evaluation_models.LlmInferenceRun(
        evaluation_item_id=item.id, inference_chain_id=chain_id, inference_id=inference_id,
        attempt_number=1, run_purpose="production", input_title=(title or "")[:500],
        input_summary=summary or "", input_keywords=[], input_stage1_route=route or "keyword",
        input_signal_type=None, input_checksum=item.content_hash, model_id="legacy-unknown",
        provider="legacy", prompt_version="legacy-unversioned", schema_version="legacy-unknown",
        inference_status=status, llm_label=normalized_label, llm_reason="Backfill dữ liệu cũ",
        requested_at=timestamp, lease_expires_at=timestamp, completed_at=timestamp,
        created_at=timestamp,
    )
    db.add(run)
    db.flush()
    if status == "success":
        item.current_inference_run_id = run.id
    return run, True


def apply_human_label(item, label, reviewer_id=None, reviewed_at=None) -> bool:
    if label not in VALID_LABELS:
        return False
    stored = None if label == "unsure" else label
    if item.human_label is not None and item.human_label != stored:
        item.review_status = "needs_adjudication"
        item.eligible_for_training = False
        return True
    item.human_label = stored
    item.review_status = "needs_adjudication" if label == "unsure" else "reviewed"
    item.eligible_for_training = label != "unsure"
    item.reviewed_by = reviewer_id
    item.reviewed_at = reviewed_at
    return False


def run_backfill(dry_run: bool) -> dict:
    report = Counter()
    labels = Counter()
    with SessionLocal() as db:
        legacy = db.query(evaluation_models.ArticleEvaluation).all()
        for row in legacy:
            article = row.article
            if article is None:
                report["skipped"] += 1
                continue
            item = upsert_item(
                db, link=article.link, title=article.title, summary=article.summary,
                published_date=article.published_date, article_id=article.id,
                source_domain=article.source,
            )
            run, created = add_run(
                db, item, source="article_evaluations", primary_key=row.id,
                label=row.llm_label, title=article.title, summary=article.summary,
                route=article.details.stage1_route if article.details else "keyword",
                created_at=row.verified_at or article.published_date,
            )
            is_conflict = apply_human_label(item, row.human_label, row.verified_by, row.verified_at)
            if row.human_label in VALID_LABELS and not is_conflict:
                item.ground_truth_source_run_id = run.id
            report["conflicts" if is_conflict else ("migrated" if created else "existing")] += 1
            if row.human_label:
                labels[row.human_label] += 1

        samples = db.query(news_models.RssEntrySample).filter(
            news_models.RssEntrySample.llm_label.isnot(None)
        ).all()
        for row in samples:
            if not row.sample_uuid:
                row.sample_uuid = str(uuid.uuid5(NAMESPACE, f"rss-sample:{row.id}"))
            item = upsert_item(
                db, link=row.link, title=row.title, summary=row.summary,
                published_date=row.published_date, article_id=row.article_id,
            )
            run, created = add_run(
                db, item, source="rss_entry_samples", primary_key=row.id,
                label=row.llm_label, title=row.title, summary=row.summary,
                route=row.stage1_route, created_at=row.sampled_at,
            )
            if row.human_relevant is not None:
                label = "relevant" if row.human_relevant else (row.human_signal_label or "irrelevant")
                is_conflict = apply_human_label(item, label, row.labeled_by, row.labeled_at)
                if not is_conflict:
                    item.ground_truth_source_run_id = run.id
                labels[label] += 1
            else:
                is_conflict = False
            report["conflicts" if is_conflict else ("migrated" if created else "existing")] += 1

        report["items"] = db.query(evaluation_models.LlmEvaluationItem).count()
        if dry_run:
            db.rollback()
        else:
            db.commit()
    for key in ("migrated", "existing", "merged", "conflicts", "skipped"):
        report.setdefault(key, 0)
    return {"counts": dict(report), "label_distribution": dict(labels), "dry_run": dry_run}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    report = run_backfill(args.dry_run)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
