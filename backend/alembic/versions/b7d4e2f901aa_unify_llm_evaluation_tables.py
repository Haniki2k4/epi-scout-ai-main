"""Unify Stage 2 LLM evaluation data.

Revision ID: b7d4e2f901aa
Revises: a61d0e4f7b25
"""
from alembic import op
import sqlalchemy as sa

revision = "b7d4e2f901aa"
down_revision = "a61d0e4f7b25"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_evaluation_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("identity_key", sa.String(64), nullable=False),
        sa.Column("identity_method", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("canonical_url", sa.String(767), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("source_domain", sa.String(255), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("title_snapshot", sa.Unicode(500), nullable=False),
        sa.Column("summary_snapshot", sa.UnicodeText(), nullable=False),
        sa.Column("human_label", sa.String(20), nullable=True),
        sa.Column("human_signal_label", sa.String(30), nullable=True),
        sa.Column("human_diseases", sa.JSON(), nullable=True),
        sa.Column("human_location", sa.Unicode(255), nullable=True),
        sa.Column("human_event_date", sa.DateTime(), nullable=True),
        sa.Column("human_case_observations", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("eligible_for_training", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("label_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ground_truth_source_run_id", sa.BigInteger(), nullable=True),
        sa.Column("current_inference_run_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["article_identity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "human_label = 'relevant' OR human_signal_label IS NULL",
            name="ck_llm_eval_signal_requires_relevant",
        ),
        sa.CheckConstraint(
            "human_label <> 'unsure' OR eligible_for_training = 0",
            name="ck_llm_eval_unsure_not_training",
        ),
        sa.UniqueConstraint("identity_key", name="uq_llm_eval_item_identity"),
    )
    op.create_index("ix_llm_eval_item_content_hash", "llm_evaluation_items", ["content_hash"])
    op.create_index("ix_llm_eval_item_article", "llm_evaluation_items", ["article_id"])
    op.create_index("ix_llm_eval_item_review_created", "llm_evaluation_items", ["review_status", "created_at"])
    op.create_index("ix_llm_eval_item_training_label", "llm_evaluation_items", ["eligible_for_training", "human_label"])

    op.create_table(
        "llm_dataset_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("label_schema_version", sa.String(50), nullable=False, server_default="v1"),
        sa.Column("split_strategy", sa.String(50), nullable=False),
        sa.Column("split_seed", sa.Integer(), nullable=True),
        sa.Column("cutoff_dates", sa.JSON(), nullable=True),
        sa.Column("grouping_version", sa.String(50), nullable=True),
        sa.Column("label_distribution", sa.JSON(), nullable=True),
        sa.Column("label_distribution_per_split", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("train_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("notes", sa.UnicodeText(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("version", name="uq_llm_dataset_version"),
    )

    op.create_table(
        "llm_inference_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("evaluation_item_id", sa.BigInteger(), nullable=False),
        sa.Column("inference_chain_id", sa.String(36), nullable=False),
        sa.Column("inference_id", sa.String(36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("run_purpose", sa.String(20), nullable=False, server_default="production"),
        sa.Column("scan_run_id", sa.String(36), nullable=True),
        sa.Column("rss_sample_uuid", sa.String(36), nullable=True),
        sa.Column("is_benchmark_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sampling_version", sa.String(50), nullable=True),
        sa.Column("sampling_probability", sa.Float(), nullable=True),
        sa.Column("selected_for_review_at", sa.DateTime(), nullable=True),
        sa.Column("input_title", sa.Unicode(500), nullable=False),
        sa.Column("input_summary", sa.UnicodeText(), nullable=False),
        sa.Column("input_keywords", sa.JSON(), nullable=True),
        sa.Column("input_stage1_route", sa.String(20), nullable=False),
        sa.Column("input_signal_type", sa.String(50), nullable=True),
        sa.Column("input_checksum", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(150), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("prompt_version", sa.String(50), nullable=False),
        sa.Column("prompt_template_hash", sa.String(64), nullable=True),
        sa.Column("few_shot_dataset_hash", sa.String(64), nullable=True),
        sa.Column("few_shot_dataset_version_id", sa.BigInteger(), nullable=True),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("inference_status", sa.String(30), nullable=False),
        sa.Column("llm_label", sa.String(20), nullable=True),
        sa.Column("llm_reason", sa.Unicode(500), nullable=True),
        sa.Column("parsed_response", sa.JSON(), nullable=True),
        sa.Column("raw_response_text", sa.Text(), nullable=True),
        sa.Column("predicted_diseases", sa.JSON(), nullable=True),
        sa.Column("predicted_location", sa.Unicode(255), nullable=True),
        sa.Column("predicted_event_date", sa.DateTime(), nullable=True),
        sa.Column("predicted_case_observations", sa.JSON(), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Unicode(500), nullable=True),
        sa.Column("fallback_from_run_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_item_id"], ["llm_evaluation_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fallback_from_run_id"], ["llm_inference_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["few_shot_dataset_version_id"], ["llm_dataset_versions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "inference_status <> 'success' OR llm_label IS NOT NULL",
            name="ck_llm_run_success_has_label",
        ),
        sa.UniqueConstraint("inference_id", name="uq_llm_inference_id"),
        sa.UniqueConstraint("inference_chain_id", "attempt_number", name="uq_llm_run_chain_attempt"),
    )
    for name, columns in (
        ("ix_llm_run_item_requested", ["evaluation_item_id", "requested_at"]),
        ("ix_llm_run_status_created", ["inference_status", "created_at"]),
        ("ix_llm_run_model_prompt", ["model_id", "prompt_version"]),
        ("ix_llm_run_benchmark", ["is_benchmark_sample", "sampling_version"]),
        ("ix_llm_run_scan", ["scan_run_id"]),
        ("ix_llm_run_rss_sample", ["rss_sample_uuid"]),
    ):
        op.create_index(name, "llm_inference_runs", columns)

    op.create_table(
        "llm_evaluation_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("evaluation_item_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("reviewed_inference_run_id", sa.BigInteger(), nullable=True),
        sa.Column("previous_ground_truth", sa.JSON(), nullable=True),
        sa.Column("new_ground_truth", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Unicode(500), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_item_id"], ["llm_evaluation_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_inference_run_id"], ["llm_inference_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("evaluation_item_id", "revision_number", name="uq_llm_revision_item_number"),
    )

    op.create_table(
        "llm_dataset_version_items",
        sa.Column("dataset_version_id", sa.BigInteger(), primary_key=True),
        sa.Column("evaluation_item_id", sa.BigInteger(), primary_key=True),
        sa.Column("inference_run_id", sa.BigInteger(), nullable=True),
        sa.Column("model_id_snapshot", sa.String(150), nullable=True),
        sa.Column("prompt_version_snapshot", sa.String(50), nullable=True),
        sa.Column("inference_id_snapshot", sa.String(36), nullable=True),
        sa.Column("stage1_route_snapshot", sa.String(20), nullable=True),
        sa.Column("signal_type_snapshot", sa.String(50), nullable=True),
        sa.Column("split", sa.String(20), nullable=False),
        sa.Column("human_label_snapshot", sa.String(20), nullable=False),
        sa.Column("human_signal_label_snapshot", sa.String(30), nullable=True),
        sa.Column("human_diseases_snapshot", sa.JSON(), nullable=True),
        sa.Column("human_location_snapshot", sa.Unicode(255), nullable=True),
        sa.Column("human_event_date_snapshot", sa.DateTime(), nullable=True),
        sa.Column("human_case_observations_snapshot", sa.JSON(), nullable=True),
        sa.Column("title_snapshot", sa.Unicode(500), nullable=False),
        sa.Column("summary_snapshot", sa.UnicodeText(), nullable=False),
        sa.Column("input_keywords_snapshot", sa.JSON(), nullable=True),
        sa.Column("input_checksum", sa.String(64), nullable=False),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["llm_dataset_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_item_id"], ["llm_evaluation_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["inference_run_id"], ["llm_inference_runs.id"], ondelete="RESTRICT"),
    )

    op.create_foreign_key(
        "fk_eval_item_current_run", "llm_evaluation_items", "llm_inference_runs",
        ["current_inference_run_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_eval_item_ground_truth_run", "llm_evaluation_items", "llm_inference_runs",
        ["ground_truth_source_run_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("rss_entry_samples", sa.Column("sample_uuid", sa.String(36), nullable=True))
    op.create_unique_constraint("uq_rss_entry_sample_uuid", "rss_entry_samples", ["sample_uuid"])


def downgrade():
    op.drop_constraint("uq_rss_entry_sample_uuid", "rss_entry_samples", type_="unique")
    op.drop_column("rss_entry_samples", "sample_uuid")
    op.drop_constraint("fk_eval_item_ground_truth_run", "llm_evaluation_items", type_="foreignkey")
    op.drop_constraint("fk_eval_item_current_run", "llm_evaluation_items", type_="foreignkey")
    op.drop_table("llm_dataset_version_items")
    op.drop_table("llm_evaluation_revisions")
    op.drop_table("llm_inference_runs")
    op.drop_table("llm_dataset_versions")
    op.drop_index("ix_llm_eval_item_training_label", table_name="llm_evaluation_items")
    op.drop_index("ix_llm_eval_item_review_created", table_name="llm_evaluation_items")
    op.drop_index("ix_llm_eval_item_article", table_name="llm_evaluation_items")
    op.drop_index("ix_llm_eval_item_content_hash", table_name="llm_evaluation_items")
    op.drop_table("llm_evaluation_items")
