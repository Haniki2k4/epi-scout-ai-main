from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..news import event_service
from . import models
from .schemas import LabelingPayload


def _snapshot(item: models.LlmEvaluationItem) -> dict:
    return {
        "human_label": item.human_label,
        "human_signal_label": item.human_signal_label,
        "human_diseases": item.human_diseases,
        "human_location": item.human_location,
        "human_event_date": item.human_event_date.isoformat() if item.human_event_date else None,
        "human_case_observations": item.human_case_observations,
        "review_status": item.review_status,
        "eligible_for_training": item.eligible_for_training,
        "ground_truth_source_run_id": item.ground_truth_source_run_id,
    }


class LabelingService:
    def apply_label(
        self, db: Session, item_id: int, user_id: int, payload: LabelingPayload,
    ) -> models.LlmEvaluationItem:
        item = db.query(models.LlmEvaluationItem).filter_by(id=item_id).with_for_update().first()
        if item is None:
            raise HTTPException(404, "Không tìm thấy bài đánh giá")
        if item.label_revision != payload.expected_revision:
            raise HTTPException(409, {
                "code": "STALE_REVISION",
                "message": "Dữ liệu đã được người khác cập nhật",
                "current_revision": item.label_revision,
            })

        source_run = None
        if payload.reviewed_inference_run_id is not None:
            source_run = db.query(models.LlmInferenceRun).filter_by(
                id=payload.reviewed_inference_run_id, evaluation_item_id=item.id
            ).first()
            if source_run is None:
                raise HTTPException(422, "Inference run không thuộc bài đánh giá")
        elif item.current_inference_run_id:
            source_run = db.get(models.LlmInferenceRun, item.current_inference_run_id)

        if (
            payload.human_label == "relevant" and source_run is not None
            and source_run.input_stage1_route == "context"
            and payload.human_signal_label is None
        ):
            raise HTTPException(422, "Bài Cửa B relevant phải chọn confirmed_event hoặc early_signal")

        previous = _snapshot(item) if item.label_revision else None
        is_unsure = payload.human_label == "unsure"
        item.label_revision += 1
        item.human_label = None if is_unsure else payload.human_label
        item.human_signal_label = payload.human_signal_label if payload.human_label == "relevant" else None
        item.human_diseases = payload.human_diseases
        item.human_location = payload.human_location
        item.human_event_date = payload.human_event_date
        item.human_case_observations = payload.human_case_observations
        item.review_status = "needs_adjudication" if is_unsure else "reviewed"
        item.eligible_for_training = False if is_unsure else payload.eligible_for_training
        item.reviewed_by = user_id
        item.reviewed_at = datetime.utcnow()
        item.ground_truth_source_run_id = source_run.id if source_run else None

        revision = models.LlmEvaluationRevision(
            evaluation_item_id=item.id, revision_number=item.label_revision,
            reviewed_inference_run_id=source_run.id if source_run else None,
            previous_ground_truth=previous, new_ground_truth=_snapshot(item),
            reason=payload.reason, reviewed_by=user_id,
        )
        db.add(revision)

        article = item.article_id
        if article:
            from ..news.models import ArticleIdentity
            article_row = db.get(ArticleIdentity, article)
            if article_row:
                if payload.human_label == "relevant":
                    article_row.is_excluded = False
                else:
                    event_service.handle_article_exclusion_from_event(
                        db, article_row, user_id, payload.reason
                    )
        db.commit()
        db.refresh(item)
        return item
