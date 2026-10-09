"""Add context signal routing, reviews and scan accounting.

Revision ID: c93e42b7d10a
Revises: e7b4c1d2f903
"""
from alembic import op
import sqlalchemy as sa

revision = "c93e42b7d10a"
down_revision = "e7b4c1d2f903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scan_runs",
        sa.Column("scan_run_id", sa.String(36), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("feed_count", sa.Integer(), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_scan_runs_status_completed", "scan_runs", ["status", "completed_at"])

    for name, column in (
        ("stage1_route", sa.String(20)),
        ("context_signal_type", sa.String(50)),
        ("context_matched_phrases", sa.Unicode(1000)),
        ("context_evidence_text", sa.UnicodeText()),
        ("llm_reason", sa.Unicode(500)),
    ):
        op.add_column("article_details", sa.Column(name, column, nullable=True))
    op.add_column("article_details", sa.Column("review_version", sa.Integer(), nullable=False, server_default="0"))

    for name, column in (
        ("scan_run_id", sa.String(36)),
        ("eligible_entries_total", sa.Integer()),
        ("gate_b_candidates_total", sa.Integer()),
        ("gate_b_active_total", sa.Integer()),
        ("gate_b_unexplained_cluster", sa.Integer()),
        ("gate_b_animal_signal", sa.Integer()),
        ("gate_b_environment_signal", sa.Integer()),
        ("gate_b_field_response", sa.Integer()),
    ):
        op.add_column("crawl_runs", sa.Column(name, column, nullable=True))
    op.create_foreign_key("fk_crawl_runs_scan_run", "crawl_runs", "scan_runs", ["scan_run_id"], ["scan_run_id"])

    for name, column in (
        ("stage1_route", sa.String(20)),
        ("gate_b_mode", sa.String(10)),
        ("gate_b_evaluated", sa.Boolean()),
        ("detector_matched", sa.Boolean()),
        ("detector_version", sa.String(30)),
        ("context_signal_type", sa.String(50)),
        ("human_signal_label", sa.String(30)),
        ("llm_reason", sa.Unicode(500)),
    ):
        op.add_column("rss_entry_samples", sa.Column(name, column, nullable=True))

    op.create_table(
        "context_signal_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("article_identity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signal_evidence", sa.UnicodeText(), nullable=True),
        sa.Column("reason", sa.Unicode(500), nullable=False),
        sa.Column("disease_name", sa.Unicode(255), nullable=True),
        sa.Column("disease_source", sa.Unicode(500), nullable=True),
        sa.Column("location", sa.Unicode(255), nullable=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("news_events.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("request_id", name="uq_csr_request"),
    )
    op.create_index("ix_context_signal_reviews_article_current", "context_signal_reviews", ["article_id", "is_superseded"])


def downgrade():
    op.drop_index("ix_context_signal_reviews_article_current", table_name="context_signal_reviews")
    op.drop_table("context_signal_reviews")
    for name in ("llm_reason", "human_signal_label", "context_signal_type", "detector_version", "detector_matched", "gate_b_evaluated", "gate_b_mode", "stage1_route"):
        op.drop_column("rss_entry_samples", name)
    op.drop_constraint("fk_crawl_runs_scan_run", "crawl_runs", type_="foreignkey")
    for name in ("gate_b_field_response", "gate_b_environment_signal", "gate_b_animal_signal", "gate_b_unexplained_cluster", "gate_b_active_total", "gate_b_candidates_total", "eligible_entries_total", "scan_run_id"):
        op.drop_column("crawl_runs", name)
    for name in ("review_version", "llm_reason", "context_evidence_text", "context_matched_phrases", "context_signal_type", "stage1_route"):
        op.drop_column("article_details", name)
    op.drop_index("ix_scan_runs_status_completed", table_name="scan_runs")
    op.drop_table("scan_runs")

