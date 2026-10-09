"""Store multiple ground-truth diseases for RSS quality samples.

Revision ID: a61d0e4f7b25
Revises: c93e42b7d10a
"""
from alembic import op
import sqlalchemy as sa

revision = "a61d0e4f7b25"
down_revision = "c93e42b7d10a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rss_entry_samples", sa.Column("human_diseases", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("rss_entry_samples", "human_diseases")

