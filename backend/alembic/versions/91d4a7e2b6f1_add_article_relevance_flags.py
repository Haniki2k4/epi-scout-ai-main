"""add article relevance flags

Revision ID: 91d4a7e2b6f1
Revises: 2dd66cb129c7
Create Date: 2026-05-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "91d4a7e2b6f1"
down_revision: Union[str, None] = "2dd66cb129c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "article_details",
        sa.Column("outbreak_relevance_score", sa.Float(), nullable=True, server_default="0"),
    )
    op.add_column(
        "article_details",
        sa.Column("is_suspected_false_positive", sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("article_details", "is_suspected_false_positive")
    op.drop_column("article_details", "outbreak_relevance_score")
