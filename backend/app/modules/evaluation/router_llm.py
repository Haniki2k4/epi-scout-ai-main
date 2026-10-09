import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ..auth.security import require_admin_role, require_reviewer_role
from . import models, schemas
from .dataset import DatasetService
from .inference_service import InferenceService
from .metrics import MetricsEngine
from .service import LabelingService

router = APIRouter(prefix="/api/llm-evaluations", tags=["LLM Evaluation"])
labeling_service = LabelingService()
inference_service = InferenceService()
metrics_engine = MetricsEngine()
dataset_service = DatasetService()


def _run_dict(run):
    if run is None:
        return None
    return {
        "id": run.id, "inference_id": run.inference_id,
        "status": run.inference_status, "llm_label": run.llm_label,
        "llm_reason": run.llm_reason, "model_id": run.model_id,
        "provider": run.provider, "prompt_version": run.prompt_version,
        "route": run.input_stage1_route, "signal_type": run.input_signal_type,
        "input_keywords": run.input_keywords or [],
        "requested_at": run.requested_at, "latency_ms": run.latency_ms,
        "error_code": run.error_code, "is_benchmark_sample": run.is_benchmark_sample,
    }


def _item_dict(db, item):
    run = db.get(models.LlmInferenceRun, item.current_inference_run_id) if item.current_inference_run_id else (
        db.query(models.LlmInferenceRun).filter_by(evaluation_item_id=item.id)
        .order_by(models.LlmInferenceRun.requested_at.desc()).first()
    )
    return {
        "id": item.id, "canonical_url": item.canonical_url,
        "title_snapshot": item.title_snapshot, "summary_snapshot": item.summary_snapshot,
        "source_domain": item.source_domain, "published_date": item.published_date,
        "human_label": item.human_label, "human_signal_label": item.human_signal_label,
        "human_diseases": item.human_diseases, "human_location": item.human_location,
        "human_event_date": item.human_event_date,
        "human_case_observations": item.human_case_observations,
        "review_status": item.review_status,
        "eligible_for_training": item.eligible_for_training,
        "label_revision": item.label_revision,
        "current_inference_run_id": item.current_inference_run_id,
        "current_run": _run_dict(run),
    }


@router.get("/items")
def list_items(
    review_status: str | None = None, route: str | None = None,
    model_id: str | None = None, prompt_version: str | None = None,
    llm_label: str | None = None, human_label: str | None = None,
    benchmark_only: bool = False, skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db),
    _=Depends(require_reviewer_role),
):
    query = db.query(models.LlmEvaluationItem)
    if any((route, model_id, prompt_version, llm_label, benchmark_only)):
        query = query.join(
            models.LlmInferenceRun,
            models.LlmInferenceRun.id == models.LlmEvaluationItem.current_inference_run_id,
        )
    if review_status == "processed":
        query = query.filter(models.LlmEvaluationItem.review_status != "pending")
    elif review_status:
        query = query.filter(models.LlmEvaluationItem.review_status == review_status)
    if human_label:
        query = query.filter(models.LlmEvaluationItem.human_label == human_label)
    if route:
        query = query.filter(models.LlmInferenceRun.input_stage1_route == route)
    if model_id:
        query = query.filter(models.LlmInferenceRun.model_id == model_id)
    if prompt_version:
        query = query.filter(models.LlmInferenceRun.prompt_version == prompt_version)
    if llm_label:
        query = query.filter(models.LlmInferenceRun.llm_label == llm_label)
    if benchmark_only:
        query = query.filter(models.LlmInferenceRun.is_benchmark_sample.is_(True))
    total = query.count()
    rows = query.order_by(models.LlmEvaluationItem.created_at.desc()).offset(skip).limit(limit).all()
    return {"items": [_item_dict(db, row) for row in rows], "total": total, "skip": skip, "limit": limit}


@router.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db), _=Depends(require_reviewer_role)):
    item = db.get(models.LlmEvaluationItem, item_id)
    if item is None:
        raise HTTPException(404, "Không tìm thấy bài đánh giá")
    result = _item_dict(db, item)
    result["runs"] = [_run_dict(row) for row in db.query(models.LlmInferenceRun).filter_by(
        evaluation_item_id=item.id
    ).order_by(models.LlmInferenceRun.requested_at.desc()).all()]
    result["revisions"] = [{
        "revision_number": row.revision_number,
        "reviewed_inference_run_id": row.reviewed_inference_run_id,
        "previous_ground_truth": row.previous_ground_truth,
        "new_ground_truth": row.new_ground_truth,
        "reason": row.reason, "reviewed_by": row.reviewed_by,
        "created_at": row.created_at,
    } for row in db.query(models.LlmEvaluationRevision).filter_by(
        evaluation_item_id=item.id
    ).order_by(models.LlmEvaluationRevision.revision_number.desc()).all()]
    return result


@router.patch("/items/{item_id}")
def label_item(
    item_id: int, payload: schemas.LabelingPayload, db: Session = Depends(get_db),
    reviewer=Depends(require_reviewer_role),
):
    return _item_dict(db, labeling_service.apply_label(db, item_id, reviewer.id, payload))


@router.post("/items/{item_id}/retry")
def retry_item(
    item_id: int, payload: schemas.RetryPayload, db: Session = Depends(get_db),
    _=Depends(require_reviewer_role),
):
    run_id = inference_service.retry(db, item_id, payload.model_id, payload.prompt_version)
    return _run_dict(db.get(models.LlmInferenceRun, run_id))


@router.post("/items/{item_id}/promote-run/{run_id}")
def promote_run(
    item_id: int, run_id: int, db: Session = Depends(get_db),
    _=Depends(require_reviewer_role),
):
    return _item_dict(db, inference_service.promote(db, item_id, run_id))


@router.get("/metrics")
def metrics(
    model_id: str | None = None, prompt_version: str | None = None,
    benchmark_only: bool = False, db: Session = Depends(get_db),
    _=Depends(require_reviewer_role),
):
    return metrics_engine.calculate(
        db, model_id=model_id, prompt_version=prompt_version,
        benchmark_only=benchmark_only,
    )


@router.get("/dataset/summary")
def dataset_summary(db: Session = Depends(get_db), _=Depends(require_admin_role)):
    rows = db.query(
        models.LlmEvaluationItem.human_label, func.count(models.LlmEvaluationItem.id)
    ).filter(
        models.LlmEvaluationItem.eligible_for_training.is_(True)
    ).group_by(models.LlmEvaluationItem.human_label).all()
    return {"eligible_count": sum(count for _, count in rows), "label_distribution": dict(rows)}


@router.get("/dataset/versions")
def list_versions(db: Session = Depends(get_db), _=Depends(require_admin_role)):
    return db.query(models.LlmDatasetVersion).order_by(models.LlmDatasetVersion.created_at.desc()).all()


@router.get("/dataset/versions/{version_id}")
def get_version(version_id: int, db: Session = Depends(get_db), _=Depends(require_admin_role)):
    row = db.get(models.LlmDatasetVersion, version_id)
    if row is None:
        raise HTTPException(404, "Không tìm thấy dataset version")
    return row


@router.post("/dataset/versions", status_code=201)
def create_version(
    payload: schemas.DatasetCreatePayload, db: Session = Depends(get_db),
    admin=Depends(require_admin_role),
):
    return dataset_service.create_version(
        db, version=payload.version_tag, split_strategy=payload.split_strategy,
        split_seed=payload.split_seed, notes=payload.notes, user_id=admin.id,
    )


@router.post("/dataset/versions/{version_id}/freeze")
def freeze_version(version_id: int, db: Session = Depends(get_db), _=Depends(require_admin_role)):
    return dataset_service.freeze(db, version_id)


@router.get("/dataset/versions/{version_id}/export")
def export_version(
    version_id: int, format: str = Query("jsonl", pattern="^(jsonl|csv|excel)$"),
    db: Session = Depends(get_db), _=Depends(require_admin_role),
):
    rows = dataset_service.export_rows(db, version_id)
    if format == "jsonl":
        body = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")
        return StreamingResponse(io.BytesIO(body), media_type="application/x-ndjson",
                                 headers={"Content-Disposition": f"attachment; filename=dataset-{version_id}.jsonl"})
    if format == "csv":
        import csv
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["split"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})
        return StreamingResponse(io.BytesIO(stream.getvalue().encode("utf-8-sig")), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=dataset-{version_id}.csv"})
    import openpyxl
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    headers = list(rows[0]) if rows else ["split"]
    sheet.append(headers)
    for row in rows:
        sheet.append([json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key) for key in headers])
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename=dataset-{version_id}.xlsx"})
