"""Add rss_sources table

Revision ID: a1b2c3d4e5f6
Revises: 4cbedb9455af
Create Date: 2026-04-02 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4cbedb9455af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rss_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(767), nullable=False),
        sa.Column('label', sa.Unicode(255), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rss_sources_id', 'rss_sources', ['id'])
    op.execute('CREATE UNIQUE INDEX ix_rss_sources_url ON rss_sources (url(200))')


def downgrade() -> None:
    op.drop_index('ix_rss_sources_url', table_name='rss_sources')
    op.drop_index('ix_rss_sources_id', table_name='rss_sources')
    op.drop_table('rss_sources')
