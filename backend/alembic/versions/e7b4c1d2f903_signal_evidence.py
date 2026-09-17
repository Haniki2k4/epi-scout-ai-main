"""Preserve legacy counts and add evidence-based signal review.

Revision ID: e7b4c1d2f903
Revises: 77f5cfd3440d
"""
from alembic import op
import sqlalchemy as sa


revision = "e7b4c1d2f903"
down_revision = "77f5cfd3440d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("disease_cases", sa.Column("reported_value", sa.Integer(), nullable=True))
    op.add_column("disease_cases", sa.Column("case_type", sa.String(30), nullable=True))
    op.add_column("disease_cases", sa.Column("count_scope", sa.String(20), nullable=True))
    op.add_column("disease_cases", sa.Column("report_period_start", sa.DateTime(), nullable=True))
    op.add_column("disease_cases", sa.Column("report_period_end", sa.DateTime(), nullable=True))
    op.add_column("disease_cases", sa.Column("evidence_quote", sa.Unicode(400), nullable=True))
    op.add_column("disease_cases", sa.Column("time_allocation", sa.String(20), nullable=True))
    op.add_column("disease_cases", sa.Column("location_allocation", sa.String(20), nullable=True))
    op.add_column("disease_cases", sa.Column("data_quality", sa.String(20), nullable=True))
    op.execute("UPDATE disease_cases SET data_quality = 'legacy_unverified' WHERE reported_value IS NULL")
    op.alter_column("disease_cases", "case_count", existing_type=sa.Integer(), nullable=True)

    op.add_column("news_events", sa.Column("analyst_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("news_events", sa.Column("analyst_reviewed_by", sa.Integer(), nullable=True))
    op.add_column("news_events", sa.Column("verified_at", sa.DateTime(), nullable=True))
    op.add_column("news_events", sa.Column("verified_by", sa.Integer(), nullable=True))
    op.add_column("news_events", sa.Column("rejection_reason", sa.Unicode(500), nullable=True))
    op.add_column("news_events", sa.Column("verification_notes", sa.UnicodeText(), nullable=True))
    op.add_column("news_events", sa.Column("verification_source", sa.Unicode(500), nullable=True))
    op.add_column("news_events", sa.Column("verified_case_source_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_events_case_source", "news_events", "disease_cases", ["verified_case_source_id"], ["id"])
    op.create_foreign_key("fk_events_reviewed_by", "news_events", "users", ["analyst_reviewed_by"], ["id"])
    op.create_foreign_key("fk_events_verified_by", "news_events", "users", ["verified_by"], ["id"])
    op.execute("UPDATE news_events SET status = 'pending_review' WHERE status = 'active' OR status IS NULL")
    # Existing event totals were inferred from overlapping articles.
    op.execute("UPDATE news_events SET case_count = NULL")
    op.alter_column("news_events", "case_count", existing_type=sa.Integer(), nullable=True)

    op.create_table(
        "event_review_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("news_events.id"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("old_status", sa.String(50), nullable=True),
        sa.Column("new_status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Unicode(500), nullable=True),
        sa.Column("notes", sa.UnicodeText(), nullable=True),
        sa.Column("verification_source", sa.Unicode(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_event_review_log_event_id", "event_review_log", ["event_id"])


    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("rss_sources.id"), nullable=True),
        sa.Column("feed_url", sa.String(767), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("entries_fetched", sa.Integer(), nullable=True),
        sa.Column("entries_passed_stage1", sa.Integer(), nullable=True),
        sa.Column("entries_saved", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("error_sample", sa.Unicode(500), nullable=True),
    )
    op.create_index("ix_crawl_runs_source_started", "crawl_runs", ["source_id", "started_at"])
    op.create_table(
        "rss_entry_samples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("rss_sources.id"), nullable=True),
        sa.Column("link", sa.String(767), nullable=False),
        sa.Column("title", sa.Unicode(500), nullable=False),
        sa.Column("summary", sa.UnicodeText(), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("sampled_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("passed_stage1", sa.Boolean(), nullable=False),
        sa.Column("llm_label", sa.String(20), nullable=True),
        sa.Column("predicted_disease", sa.Unicode(500), nullable=True),
        sa.Column("predicted_location", sa.Unicode(255), nullable=True),
        sa.Column("predicted_event_date", sa.DateTime(), nullable=True),
        sa.Column("predicted_case_values", sa.UnicodeText(), nullable=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("article_identity.id", ondelete="SET NULL"), nullable=True),
        sa.Column("human_relevant", sa.Boolean(), nullable=True),
        sa.Column("labeled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("labeled_at", sa.DateTime(), nullable=True),
        sa.Column("human_disease", sa.Unicode(255), nullable=True),
        sa.Column("human_location", sa.Unicode(255), nullable=True),
        sa.Column("human_event_date", sa.DateTime(), nullable=True),
        sa.Column("human_case_value", sa.Integer(), nullable=True),
    )
    op.create_index("ix_rss_samples_expires", "rss_entry_samples", ["expires_at"])

    op.create_table(
        "event_pair_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_a_id", sa.Integer(), sa.ForeignKey("article_identity.id"), nullable=False),
        sa.Column("article_b_id", sa.Integer(), sa.ForeignKey("article_identity.id"), nullable=False),
        sa.Column("same_event", sa.Boolean(), nullable=False),
        sa.Column("predicted_same_event", sa.Boolean(), nullable=False),
        sa.Column("labeled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("labeled_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("article_a_id", "article_b_id", name="uq_event_pair_articles"),
    )

def downgrade():
    raise RuntimeError("This migration preserves legacy data and cannot be safely downgraded automatically")
