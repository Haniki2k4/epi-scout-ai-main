import os

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .llm_client import LlmClient, ProviderError
from .prompt_builder import SYSTEM_PROMPT, build_prompt
from .writer import EvaluationWriter


class InferenceService:
    def __init__(self):
        self.writer = EvaluationWriter()
        self.client = LlmClient()

    def retry(self, db: Session, item_id: int, model_id: str | None = None, prompt_version: str | None = None):
        item = db.get(models.LlmEvaluationItem, item_id)
        if item is None:
            raise HTTPException(404, "Không tìm thấy bài đánh giá")
        source = db.get(models.LlmInferenceRun, item.current_inference_run_id) if item.current_inference_run_id else (
            db.query(models.LlmInferenceRun).filter_by(evaluation_item_id=item.id)
            .order_by(models.LlmInferenceRun.requested_at.desc()).first()
        )
        if source is None:
            raise HTTPException(400, "Bài chưa có input inference để retry")
        selected_model = model_id or os.getenv("LLM_RECHECK_MODEL", "").strip()
        if not selected_model:
            raise HTTPException(400, "Thiếu model_id")
        item_id, run_id = self.writer.start_run(
            canonical_url=item.canonical_url or "", title=source.input_title,
            summary=source.input_summary, source_domain=item.source_domain,
            published_date=item.published_date, keywords=source.input_keywords or [],
            stage1_route=source.input_stage1_route, signal_type=source.input_signal_type,
            model_id=selected_model, provider="openai_compatible", run_purpose="retry",
            prompt_version=prompt_version,
        )
        prompt = build_prompt(
            title=source.input_title, summary=source.input_summary,
            keywords=source.input_keywords or [], route=source.input_stage1_route,
            signal_type=source.input_signal_type,
        )
        try:
            result = self.client.classify(
                base_url=os.getenv("OPENAI_BASE_URL", ""),
                api_key=os.getenv("OPENAI_API_KEY", ""),
                model_id=selected_model, system_prompt=SYSTEM_PROMPT, user_prompt=prompt,
                timeout_seconds=max(int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20")), 1),
            )
            label = str(result.parsed.get("label", "unsure")).lower()
            if label not in {"relevant", "noise", "irrelevant", "unsure"}:
                label = "unsure"
            self.writer.complete(
                run_id, status="success", label=label,
                reason=str(result.parsed.get("reason", "")),
                parsed_response=result.parsed, latency_ms=result.latency_ms,
                actual_model_id=selected_model,
            )
        except ProviderError as exc:
            self.writer.complete(
                run_id, status=exc.code, label=None, reason="",
                error_code=exc.code, error_message=str(exc), actual_model_id=selected_model,
            )
        return run_id

    def promote(self, db: Session, item_id: int, run_id: int):
        item = db.query(models.LlmEvaluationItem).filter_by(id=item_id).with_for_update().first()
        run = db.query(models.LlmInferenceRun).filter_by(id=run_id, evaluation_item_id=item_id).first()
        if item is None or run is None:
            raise HTTPException(404, "Không tìm thấy item hoặc run")
        if run.inference_status != "success":
            raise HTTPException(400, "Chỉ có thể promote run thành công")
        item.current_inference_run_id = run.id
        db.commit()
        db.refresh(item)
        return item
