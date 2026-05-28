"""add_keyword_evaluation

Revision ID: f1a2b3c4d5e6
Revises: fdf6c488eb9d
Create Date: 2026-05-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '91d4a7e2b6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('article_evaluations', sa.Column('keyword_is_correct', sa.Boolean(), nullable=True))
    op.add_column('article_evaluations', sa.Column('corrected_keyword', sa.Unicode(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('article_evaluations', 'corrected_keyword')
    op.drop_column('article_evaluations', 'keyword_is_correct')
