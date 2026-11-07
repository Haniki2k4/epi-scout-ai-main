import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .writer import EvaluationWriter


class InferenceService:
    def __init__(self):
        self.writer = EvaluationWriter()

    def retry(self, db: Session, item_id: int, model_id: str | None = None, prompt_version: str | None = None):
        # Use the exact classifier and safeguards used by normal crawler runs.
        from ..news import crawler, models as news_models
        from ..news.article_content import fetch_article_content

        item = db.get(models.LlmEvaluationItem, item_id)
        if item is None:
            raise HTTPException(404, "Không tìm thấy bài đánh giá")
        source = db.get(models.LlmInferenceRun, item.current_inference_run_id) if item.current_inference_run_id else (
            db.query(models.LlmInferenceRun).filter_by(evaluation_item_id=item.id)
            .order_by(models.LlmInferenceRun.requested_at.desc()).first()
        )
        if source is None:
            raise HTTPException(400, "Bài chưa có input inference để retry")

        selected_model = model_id or crawler.LLM_RECHECK_MODEL
        if not selected_model:
            raise HTTPException(400, "Thiếu model_id")
        if model_id and model_id != crawler.LLM_RECHECK_MODEL:
            raise HTTPException(422, "Retry dùng model đang cấu hình cho crawler để giữ cùng pipeline.")

        title = source.input_title or item.title_snapshot
        article_url = item.canonical_url
        if not article_url and item.article_id:
            article = db.get(news_models.ArticleIdentity, item.article_id)
            article_url = article.link if article else ""
        article_url = crawler.get_source_url(article_url or "")
        article_content = fetch_article_content(article_url or "")
        summary = article_content.text or source.input_summary or item.summary_snapshot
        is_context = source.input_stage1_route == "context"

        candidate_keywords = [
            value.strip() for value in (source.input_keywords or [])
            if isinstance(value, str) and value.strip()
        ]
        active_keywords = db.query(news_models.Keyword).filter(
            news_models.Keyword.is_active.is_(True)
        ).order_by(news_models.Keyword.id).all()
        detected = crawler.matches_keywords(title, summary, [keyword.text for keyword in active_keywords])
        detected_keywords = [word.strip() for word in (detected or "").split(",") if word.strip()]
        candidate_keywords = list(dict.fromkeys([*candidate_keywords, *detected_keywords]))

        prompt_template_hash, few_shot_dataset_hash = crawler.get_llm_prompt_tracking(is_context)
        _, run_id = self.writer.start_run(
            canonical_url=item.canonical_url or "", title=title, summary=summary,
            source_domain=item.source_domain, published_date=item.published_date,
            keywords=candidate_keywords, stage1_route=source.input_stage1_route,
            signal_type=source.input_signal_type, model_id=selected_model,
            provider="openai_compatible", run_purpose="retry", prompt_version=prompt_version,
            prompt_template_hash=prompt_template_hash,
            few_shot_dataset_hash=few_shot_dataset_hash,
        )

        inference_started_at = time.perf_counter()
        latency_ms = None
        if article_content.status != "full_text":
            label = "unsure"
            reason = f"Chưa đọc được đầy đủ thân bài ({article_content.status}); cần thẩm định."
            metadata = {
                "_inference_status": "success", "_model_id": "content_guard",
                "normalized_title": "", "location": "unknown", "diseases": [],
                "event_start_date": None, "event_end_date": None, "severity": None,
            }
        else:
            label, candidate_keywords, reason, metadata = crawler.llm_recheck_article(
                title, summary, candidate_keywords,
                is_context=is_context, require_evidence=True,
            )
            latency_ms = max(round((time.perf_counter() - inference_started_at) * 1000), 0)

        parsed_response = {
            key: value for key, value in metadata.items()
            if not key.startswith("_")
        }
        parsed_response.update({
            "label": label,
            "reason": reason,
            "matched_keywords": candidate_keywords,
        })
        status = metadata.get("_inference_status", "success")
        actual_model_id = metadata.get("_model_id") or selected_model
        fallback_status = metadata.get("_fallback_from_status")

        if status == "success" and fallback_status:
            self.writer.complete(
                run_id, status=fallback_status, label=None,
                reason="Primary provider failed before fallback",
                error_code=fallback_status, error_message="Fallback provider was used",
                actual_model_id=selected_model,
            )
            run_id = self.writer.start_followup_run(
                run_id, model_id=actual_model_id, provider="openai_compatible",
            )

        self.writer.complete(
            run_id, status=status, label=label, reason=reason,
            parsed_response=parsed_response, latency_ms=latency_ms,
            error_code=None if status == "success" else status,
            error_message=None if status == "success" else reason,
            actual_model_id=actual_model_id,
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
