import hashlib
import json
from collections import Counter
from datetime import datetime
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..news.models import ArticleIdentity
from . import models


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _checksum(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class DatasetService:
    def create_version(
        self, db: Session, *, version: str, split_strategy: str,
        split_seed: int, notes: str | None, user_id: int,
    ) -> models.LlmDatasetVersion:
        if db.query(models.LlmDatasetVersion).filter_by(version=version).first():
            raise HTTPException(409, "Dataset version đã tồn tại")
        items = db.query(models.LlmEvaluationItem).filter(
            models.LlmEvaluationItem.review_status == "reviewed",
            models.LlmEvaluationItem.eligible_for_training.is_(True),
            models.LlmEvaluationItem.human_label.in_(["relevant", "noise", "irrelevant"]),
        ).all()
        version_row = models.LlmDatasetVersion(
            version=version, label_schema_version="v1",
            split_strategy=split_strategy, split_seed=split_seed,
            notes=notes, created_by=user_id, created_at=datetime.utcnow(),
        )
        db.add(version_row)
        db.flush()

        article_ids = [item.article_id for item in items if item.article_id]
        event_by_article = {}
        if article_ids:
            event_by_article = dict(db.query(
                ArticleIdentity.id, ArticleIdentity.event_id
            ).filter(ArticleIdentity.id.in_(article_ids)).all())
        groups: dict[str, list] = {}
        for item in items:
            event_id = event_by_article.get(item.article_id)
            group_key = f"event:{event_id}" if event_id else f"content:{item.content_hash}"
            groups.setdefault(group_key, []).append(item)
        ordered_groups = sorted(
            groups.values(),
            key=lambda group: max((item.published_date or datetime.min) for item in group),
            reverse=True,
        )
        total = len(items)
        targets = {"test": int(total * 0.15), "validation": int(total * 0.10)}
        assigned = {"test": 0, "validation": 0}
        split_by_item: dict[int, str] = {}
        phase = "test"
        for group in ordered_groups:
            if phase == "test" and assigned["test"] >= targets["test"]:
                phase = "validation"
            if phase == "validation" and assigned["validation"] >= targets["validation"]:
                phase = "train"
            for item in group:
                split_by_item[item.id] = phase
            if phase in assigned:
                assigned[phase] += len(group)

        ordered = sorted(items, key=lambda item: item.id)
        distribution = Counter()
        split_distribution: dict[str, Counter] = {
            "train": Counter(), "validation": Counter(), "test": Counter()
        }
        for item in ordered:
            split = split_by_item[item.id]
            run = db.get(models.LlmInferenceRun, item.ground_truth_source_run_id or item.current_inference_run_id)
            title = run.input_title if run else item.title_snapshot
            summary = run.input_summary if run else item.summary_snapshot
            input_checksum = run.input_checksum if run else _checksum({"title": title, "summary": summary})
            content = {
                "label": item.human_label, "signal": item.human_signal_label,
                "diseases": item.human_diseases, "location": item.human_location,
                "event_date": item.human_event_date, "observations": item.human_case_observations,
                "title": title, "summary": summary,
            }
            db.add(models.LlmDatasetVersionItem(
                dataset_version_id=version_row.id, evaluation_item_id=item.id,
                inference_run_id=run.id if run else None,
                model_id_snapshot=run.model_id if run else None,
                prompt_version_snapshot=run.prompt_version if run else None,
                inference_id_snapshot=run.inference_id if run else None,
                stage1_route_snapshot=run.input_stage1_route if run else None,
                signal_type_snapshot=run.input_signal_type if run else None,
                split=split, human_label_snapshot=item.human_label,
                human_signal_label_snapshot=item.human_signal_label,
                human_diseases_snapshot=item.human_diseases,
                human_location_snapshot=item.human_location,
                human_event_date_snapshot=item.human_event_date,
                human_case_observations_snapshot=item.human_case_observations,
                title_snapshot=title, summary_snapshot=summary,
                input_keywords_snapshot=run.input_keywords if run else None,
                input_checksum=input_checksum, content_checksum=_checksum(content),
            ))
            distribution[item.human_label] += 1
            split_distribution[split][item.human_label] += 1

        version_row.sample_count = total
        version_row.train_count = sum(1 for value in split_by_item.values() if value == "train")
        version_row.validation_count = sum(1 for value in split_by_item.values() if value == "validation")
        version_row.test_count = sum(1 for value in split_by_item.values() if value == "test")
        version_row.label_distribution = dict(distribution)
        version_row.label_distribution_per_split = {key: dict(value) for key, value in split_distribution.items()}
        db.commit()
        db.refresh(version_row)
        return version_row

    def freeze(self, db: Session, version_id: int) -> models.LlmDatasetVersion:
        version = db.query(models.LlmDatasetVersion).filter_by(id=version_id).with_for_update().first()
        if version is None:
            raise HTTPException(404, "Không tìm thấy dataset version")
        if version.status == "frozen":
            return version
        if version.status != "draft":
            raise HTTPException(400, "Chỉ draft mới được freeze")
        rows = db.query(models.LlmDatasetVersionItem).filter_by(dataset_version_id=version.id).order_by(
            models.LlmDatasetVersionItem.evaluation_item_id
        ).all()
        manifest = [{"item": r.evaluation_item_id, "split": r.split, "checksum": r.content_checksum} for r in rows]
        version.checksum = _checksum(manifest)
        version.status = "frozen"
        version.frozen_at = datetime.utcnow()
        db.commit()
        db.refresh(version)
        return version

    def export_rows(self, db: Session, version_id: int) -> list[dict]:
        version = db.get(models.LlmDatasetVersion, version_id)
        if version is None:
            raise HTTPException(404, "Không tìm thấy dataset version")
        rows = db.query(models.LlmDatasetVersionItem).filter_by(dataset_version_id=version_id).all()
        return [{
            "split": row.split, "title": row.title_snapshot, "summary": row.summary_snapshot,
            "human_label": row.human_label_snapshot,
            "human_signal_label": row.human_signal_label_snapshot,
            "human_diseases": row.human_diseases_snapshot,
            "human_location": row.human_location_snapshot,
            "human_event_date": row.human_event_date_snapshot.isoformat() if row.human_event_date_snapshot else None,
            "human_case_observations": row.human_case_observations_snapshot,
            "stage1_route": row.stage1_route_snapshot,
            "signal_type": row.signal_type_snapshot,
            "input_checksum": row.input_checksum,
        } for row in rows]
