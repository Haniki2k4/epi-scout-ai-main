import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError

from ...core.database import SessionLocal
from . import models
from .prompt_builder import (
    PROMPT_VERSION, SCHEMA_VERSION, calculate_prompt_template_hash,
    compute_canonical_input_checksum,
)

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def content_hash(title: str, summary: str, published_date=None) -> str:
    value = f"{title.strip()}\n{summary.strip()}\n{published_date.isoformat() if published_date else ''}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identity_for(url: str, title: str, summary: str, published_date=None) -> tuple[str, str, str]:
    normalized = normalize_url(url)
    c_hash = content_hash(title, summary, published_date)
    if normalized:
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest(), "canonical_url", c_hash
    return c_hash, "content_fallback", c_hash


class EvaluationWriter:
    def start_run(
        self, *, canonical_url: str, title: str, summary: str, source_domain: str | None,
        published_date, keywords: list[str], stage1_route: str, signal_type: str | None,
        model_id: str, provider: str, scan_run_id: str | None = None,
        rss_sample_uuid: str | None = None, run_purpose: str = "production",
        inference_chain_id: str | None = None, attempt_number: int = 1,
        few_shot_dataset_hash: str | None = None, few_shot_dataset_version_id: int | None = None,
        prompt_version: str | None = None, article_id: int | None = None,
        prompt_template_hash: str | None = None,
    ) -> tuple[int, int]:
        now = datetime.utcnow()
        prompt_hash = prompt_template_hash or calculate_prompt_template_hash(stage1_route)
        checksum = compute_canonical_input_checksum(
            title=title, summary=summary, keywords=keywords, stage1_route=stage1_route,
            signal_type=signal_type, prompt_template_hash=prompt_hash,
            few_shot_dataset_hash=few_shot_dataset_hash, schema_version=SCHEMA_VERSION,
        )
        identity_key, identity_method, c_hash = identity_for(canonical_url, title, summary, published_date)
        chain_id = inference_chain_id or str(uuid.uuid4())
        providers = 2 if os.getenv("LLM_FALLBACK_MODEL", "").strip() else 1
        timeout = max(int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20")), 1)
        retries = max(int(os.getenv("LLM_MAX_RETRIES", "2")), 1)
        lease = now + timedelta(seconds=timeout * retries * providers + 120)

        with SessionLocal() as db:
            normalized_url = normalize_url(canonical_url) or None
            item = None
            if normalized_url:
                item = db.query(models.LlmEvaluationItem).filter(
                    models.LlmEvaluationItem.canonical_url == normalized_url
                ).with_for_update().first()
            if item is None and article_id is not None:
                item = db.query(models.LlmEvaluationItem).filter(
                    models.LlmEvaluationItem.article_id == article_id
                ).with_for_update().first()
            if item is None:
                item = db.query(models.LlmEvaluationItem).filter(
                    models.LlmEvaluationItem.identity_key == identity_key
                ).with_for_update().first()
            if item is None:
                item = db.query(models.LlmEvaluationItem).filter(
                    models.LlmEvaluationItem.content_hash == c_hash
                ).with_for_update().first()
            if item is None:
                item = models.LlmEvaluationItem(
                    identity_key=identity_key, identity_method=identity_method,
                    content_hash=c_hash, canonical_url=normalized_url,
                    article_id=article_id, source_domain=source_domain, published_date=published_date,
                    title_snapshot=title[:500], summary_snapshot=summary,
                    created_at=now, updated_at=now,
                )
                db.add(item)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    item = db.query(models.LlmEvaluationItem).filter(
                        models.LlmEvaluationItem.identity_key == identity_key
                    ).one()
            elif normalized_url and item.canonical_url != normalized_url:
                old_host = urlsplit(item.canonical_url or "").netloc.lower()
                new_host = urlsplit(normalized_url).netloc.lower()
                if old_host == "news.google.com" and new_host and new_host != "news.google.com":
                    collision = db.query(models.LlmEvaluationItem).filter(
                        models.LlmEvaluationItem.canonical_url == normalized_url,
                        models.LlmEvaluationItem.id != item.id,
                    ).with_for_update().first()
                    if collision is None:
                        logger.info("Upgrading Google News evaluation item %s to %s", item.id, normalized_url)
                        item.canonical_url = normalized_url
                        item.identity_key = identity_key
                        item.identity_method = "canonical_url"
                        item.source_domain = source_domain
            if article_id is not None and item.article_id is None:
                item.article_id = article_id
            run = models.LlmInferenceRun(
                evaluation_item_id=item.id, inference_chain_id=chain_id,
                inference_id=str(uuid.uuid4()), attempt_number=attempt_number,
                run_purpose=run_purpose, scan_run_id=scan_run_id,
                rss_sample_uuid=rss_sample_uuid, input_title=title[:500],
                input_summary=summary, input_keywords=keywords,
                input_stage1_route=stage1_route, input_signal_type=signal_type,
                input_checksum=checksum, model_id=model_id or "disabled",
                provider=provider, prompt_version=prompt_version or PROMPT_VERSION,
                prompt_template_hash=prompt_hash,
                few_shot_dataset_hash=few_shot_dataset_hash,
                few_shot_dataset_version_id=few_shot_dataset_version_id,
                schema_version=SCHEMA_VERSION, inference_status="pending",
                requested_at=now, lease_expires_at=lease, created_at=now,
            )
            db.add(run)
            db.flush()
            self._tag_benchmark(run, item.identity_key)
            db.commit()
            return item.id, run.id

    @staticmethod
    def _tag_benchmark(run, identity_key: str) -> None:
        version = os.getenv("LLM_SAMPLING_VERSION", "v1").strip()
        rate = min(max(int(os.getenv("LLM_BENCHMARK_SAMPLE_RATE", "15")), 0), 100)
        seed = f"{identity_key}:{run.model_id}:{run.prompt_version}:{version}"
        if int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 100 < rate:
            run.is_benchmark_sample = True
            run.sampling_version = version
            run.sampling_probability = rate / 100 if rate else None
            run.selected_for_review_at = datetime.utcnow()

    def complete(
        self, run_id: int, *, status: str, label: str | None, reason: str,
        parsed_response: dict | None = None, latency_ms: int | None = None,
        error_code: str | None = None, error_message: str | None = None,
        actual_model_id: str | None = None,
    ) -> None:
        now = datetime.utcnow()
        with SessionLocal() as db:
            run = db.query(models.LlmInferenceRun).filter_by(id=run_id).with_for_update().one()
            if run.inference_status != "pending":
                return
            run.inference_status = status
            run.llm_label = label if status == "success" else None
            run.llm_reason = (reason or "")[:500]
            run.parsed_response = parsed_response
            run.predicted_diseases = (parsed_response or {}).get("diseases")
            run.predicted_location = (parsed_response or {}).get("location")
            event_date = (parsed_response or {}).get("event_date") or (parsed_response or {}).get("event_start_date")
            if isinstance(event_date, str) and event_date.strip():
                try:
                    run.predicted_event_date = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                except ValueError:
                    run.predicted_event_date = None
            run.predicted_case_observations = (parsed_response or {}).get("case_observations") or (parsed_response or {}).get("diseases")
            run.completed_at = now
            run.latency_ms = latency_ms
            run.error_code = error_code
            run.error_message = (error_message or "")[:500] or None
            if actual_model_id:
                run.model_id = actual_model_id
            if status == "success" and run.run_purpose in {"production", "retry"}:
                item = db.query(models.LlmEvaluationItem).filter_by(id=run.evaluation_item_id).with_for_update().one()
                current = db.get(models.LlmInferenceRun, item.current_inference_run_id) if item.current_inference_run_id else None
                if current is None or run.requested_at >= current.requested_at:
                    item.current_inference_run_id = run.id
            db.commit()

    def start_followup_run(
        self, source_run_id: int, *, model_id: str, provider: str,
    ) -> int:
        now = datetime.utcnow()
        providers = 2 if os.getenv("LLM_FALLBACK_MODEL", "").strip() else 1
        timeout = max(int(os.getenv("LLM_RECHECK_TIMEOUT_SECONDS", "20")), 1)
        retries = max(int(os.getenv("LLM_MAX_RETRIES", "2")), 1)
        lease = now + timedelta(seconds=timeout * retries * providers + 120)
        with SessionLocal() as db:
            source = db.query(models.LlmInferenceRun).filter_by(id=source_run_id).with_for_update().one()
            item = db.get(models.LlmEvaluationItem, source.evaluation_item_id)
            run = models.LlmInferenceRun(
                evaluation_item_id=source.evaluation_item_id,
                inference_chain_id=source.inference_chain_id,
                inference_id=str(uuid.uuid4()),
                attempt_number=source.attempt_number + 1,
                run_purpose=source.run_purpose,
                scan_run_id=source.scan_run_id,
                rss_sample_uuid=source.rss_sample_uuid,
                input_title=source.input_title,
                input_summary=source.input_summary,
                input_keywords=source.input_keywords,
                input_stage1_route=source.input_stage1_route,
                input_signal_type=source.input_signal_type,
                input_checksum=source.input_checksum,
                model_id=model_id,
                provider=provider,
                prompt_version=source.prompt_version,
                prompt_template_hash=source.prompt_template_hash,
                few_shot_dataset_hash=source.few_shot_dataset_hash,
                few_shot_dataset_version_id=source.few_shot_dataset_version_id,
                schema_version=source.schema_version,
                inference_status="pending",
                requested_at=now,
                lease_expires_at=lease,
                fallback_from_run_id=source.id,
                created_at=now,
            )
            db.add(run)
            db.flush()
            self._tag_benchmark(run, item.identity_key)
            db.commit()
            return run.id

    def attach_article(self, item_id: int, article_id: int) -> None:
        with SessionLocal() as db:
            item = db.get(models.LlmEvaluationItem, item_id)
            if item and item.article_id is None:
                item.article_id = article_id
                db.commit()


def sweep_abandoned_runs(db) -> int:
    now = datetime.utcnow()
    rows = db.query(models.LlmInferenceRun).filter(
        models.LlmInferenceRun.inference_status == "pending",
        models.LlmInferenceRun.lease_expires_at <= now,
    ).all()
    for row in rows:
        row.inference_status = "abandoned"
        row.error_code = "process_interrupted"
        row.error_message = "Inference lease expired before completion"
        row.completed_at = now
    if rows:
        db.commit()
    return len(rows)
