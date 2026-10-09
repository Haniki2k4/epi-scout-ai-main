from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer,
    JSON, String, Text, Unicode, UnicodeText, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from ...core.database import Base


class ArticleEvaluation(Base):
    __tablename__ = "article_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("article_identity.id"), unique=True, index=True)
    llm_label = Column(String(50), nullable=True)
    human_label = Column(String(50), nullable=True)
    keyword_is_correct = Column(Boolean, nullable=True)
    corrected_keyword = Column(Unicode(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    article = relationship("ArticleIdentity", backref="evaluation")


class LlmEvaluationItem(Base):
    __tablename__ = "llm_evaluation_items"
    __table_args__ = (
        CheckConstraint(
            "human_label = 'relevant' OR human_signal_label IS NULL",
            name="ck_llm_eval_signal_requires_relevant",
        ),
        CheckConstraint(
            "human_label <> 'unsure' OR eligible_for_training = 0",
            name="ck_llm_eval_unsure_not_training",
        ),
        Index("ix_eval_item_review_created", "review_status", "created_at"),
        Index("ix_eval_item_training_label", "eligible_for_training", "human_label"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    identity_key = Column(String(64), nullable=False, unique=True)
    identity_method = Column(String(20), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    canonical_url = Column(String(767), nullable=True)
    article_id = Column(Integer, ForeignKey("article_identity.id", ondelete="SET NULL"), nullable=True, index=True)
    source_domain = Column(String(255), nullable=True)
    published_date = Column(DateTime, nullable=True)
    title_snapshot = Column(Unicode(500), nullable=False)
    summary_snapshot = Column(UnicodeText, nullable=False)

    human_label = Column(String(20), nullable=True)
    human_signal_label = Column(String(30), nullable=True)
    human_diseases = Column(JSON, nullable=True)
    human_location = Column(Unicode(255), nullable=True)
    human_event_date = Column(DateTime, nullable=True)
    human_case_observations = Column(JSON, nullable=True)
    review_status = Column(String(30), nullable=False, default="pending")
    eligible_for_training = Column(Boolean, nullable=False, default=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    label_revision = Column(Integer, nullable=False, default=0)

    ground_truth_source_run_id = Column(
        BigInteger,
        ForeignKey("llm_inference_runs.id", ondelete="SET NULL", use_alter=True, name="fk_eval_item_ground_truth_run"),
        nullable=True,
    )
    current_inference_run_id = Column(
        BigInteger,
        ForeignKey("llm_inference_runs.id", ondelete="SET NULL", use_alter=True, name="fk_eval_item_current_run"),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmDatasetVersion(Base):
    __tablename__ = "llm_dataset_versions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False, unique=True)
    label_schema_version = Column(String(50), nullable=False, default="v1")
    split_strategy = Column(String(50), nullable=False)
    split_seed = Column(Integer, nullable=True)
    cutoff_dates = Column(JSON, nullable=True)
    grouping_version = Column(String(50), nullable=True)
    label_distribution = Column(JSON, nullable=True)
    label_distribution_per_split = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="draft")
    sample_count = Column(Integer, nullable=False, default=0)
    train_count = Column(Integer, nullable=False, default=0)
    validation_count = Column(Integer, nullable=False, default=0)
    test_count = Column(Integer, nullable=False, default=0)
    checksum = Column(String(64), nullable=True)
    notes = Column(UnicodeText, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    frozen_at = Column(DateTime, nullable=True)


class LlmInferenceRun(Base):
    __tablename__ = "llm_inference_runs"
    __table_args__ = (
        CheckConstraint(
            "inference_status <> 'success' OR llm_label IS NOT NULL",
            name="ck_llm_run_success_has_label",
        ),
        UniqueConstraint("inference_chain_id", "attempt_number", name="uq_llm_run_chain_attempt"),
        Index("ix_llm_run_item_requested", "evaluation_item_id", "requested_at"),
        Index("ix_llm_run_status_created", "inference_status", "created_at"),
        Index("ix_llm_run_model_prompt", "model_id", "prompt_version"),
        Index("ix_llm_run_benchmark", "is_benchmark_sample", "sampling_version"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_item_id = Column(BigInteger, ForeignKey("llm_evaluation_items.id", ondelete="CASCADE"), nullable=False)
    inference_chain_id = Column(String(36), nullable=False)
    inference_id = Column(String(36), nullable=False, unique=True)
    attempt_number = Column(Integer, nullable=False)
    run_purpose = Column(String(20), nullable=False, default="production")
    scan_run_id = Column(String(36), nullable=True, index=True)
    rss_sample_uuid = Column(String(36), nullable=True, index=True)

    is_benchmark_sample = Column(Boolean, nullable=False, default=False)
    sampling_version = Column(String(50), nullable=True)
    sampling_probability = Column(Float, nullable=True)
    selected_for_review_at = Column(DateTime, nullable=True)

    input_title = Column(Unicode(500), nullable=False)
    input_summary = Column(UnicodeText, nullable=False)
    input_keywords = Column(JSON, nullable=True)
    input_stage1_route = Column(String(20), nullable=False)
    input_signal_type = Column(String(50), nullable=True)
    input_checksum = Column(String(64), nullable=False)

    model_id = Column(String(150), nullable=False)
    provider = Column(String(50), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    prompt_template_hash = Column(String(64), nullable=True)
    few_shot_dataset_hash = Column(String(64), nullable=True)
    few_shot_dataset_version_id = Column(
        BigInteger, ForeignKey("llm_dataset_versions.id", ondelete="RESTRICT"), nullable=True
    )
    schema_version = Column(String(50), nullable=False)

    inference_status = Column(String(30), nullable=False)
    llm_label = Column(String(20), nullable=True)
    llm_reason = Column(Unicode(500), nullable=True)
    parsed_response = Column(JSON, nullable=True)
    raw_response_text = Column(Text, nullable=True)
    predicted_diseases = Column(JSON, nullable=True)
    predicted_location = Column(Unicode(255), nullable=True)
    predicted_event_date = Column(DateTime, nullable=True)
    predicted_case_observations = Column(JSON, nullable=True)

    requested_at = Column(DateTime, nullable=False)
    lease_expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Unicode(500), nullable=True)
    fallback_from_run_id = Column(
        BigInteger, ForeignKey("llm_inference_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LlmEvaluationRevision(Base):
    __tablename__ = "llm_evaluation_revisions"
    __table_args__ = (
        UniqueConstraint("evaluation_item_id", "revision_number", name="uq_llm_revision_item_number"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_item_id = Column(BigInteger, ForeignKey("llm_evaluation_items.id", ondelete="CASCADE"), nullable=False)
    revision_number = Column(Integer, nullable=False)
    reviewed_inference_run_id = Column(
        BigInteger, ForeignKey("llm_inference_runs.id", ondelete="RESTRICT"), nullable=True
    )
    previous_ground_truth = Column(JSON, nullable=True)
    new_ground_truth = Column(JSON, nullable=False)
    reason = Column(Unicode(500), nullable=False)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LlmDatasetVersionItem(Base):
    __tablename__ = "llm_dataset_version_items"

    dataset_version_id = Column(
        BigInteger, ForeignKey("llm_dataset_versions.id", ondelete="CASCADE"), primary_key=True
    )
    evaluation_item_id = Column(
        BigInteger, ForeignKey("llm_evaluation_items.id", ondelete="RESTRICT"), primary_key=True
    )
    inference_run_id = Column(
        BigInteger, ForeignKey("llm_inference_runs.id", ondelete="RESTRICT"), nullable=True
    )
    model_id_snapshot = Column(String(150), nullable=True)
    prompt_version_snapshot = Column(String(50), nullable=True)
    inference_id_snapshot = Column(String(36), nullable=True)
    stage1_route_snapshot = Column(String(20), nullable=True)
    signal_type_snapshot = Column(String(50), nullable=True)
    split = Column(String(20), nullable=False)

    human_label_snapshot = Column(String(20), nullable=False)
    human_signal_label_snapshot = Column(String(30), nullable=True)
    human_diseases_snapshot = Column(JSON, nullable=True)
    human_location_snapshot = Column(Unicode(255), nullable=True)
    human_event_date_snapshot = Column(DateTime, nullable=True)
    human_case_observations_snapshot = Column(JSON, nullable=True)
    title_snapshot = Column(Unicode(500), nullable=False)
    summary_snapshot = Column(UnicodeText, nullable=False)
    input_keywords_snapshot = Column(JSON, nullable=True)
    input_checksum = Column(String(64), nullable=False)
    content_checksum = Column(String(64), nullable=False)
