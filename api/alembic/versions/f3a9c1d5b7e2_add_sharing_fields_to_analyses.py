"""add sharing fields to analyses

Revision ID: f3a9c1d5b7e2
Revises: e74fe243bd4f
Create Date: 2026-07-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a9c1d5b7e2'
down_revision: Union[str, None] = 'e74fe243bd4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('visibility', sa.String(length=10), nullable=False, server_default='private'))
    op.add_column('analyses', sa.Column('share_token', sa.String(length=48), nullable=True))
    op.add_column('analyses', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('analyses', sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_unique_constraint('uq_analyses_share_token', 'analyses', ['share_token'])
    op.alter_column('analyses', 'visibility', server_default=None)
    op.alter_column('analyses', 'view_count', server_default=None)


def downgrade() -> None:
    op.drop_constraint('uq_analyses_share_token', 'analyses', type_='unique')
    op.drop_column('analyses', 'view_count')
    op.drop_column('analyses', 'published_at')
    op.drop_column('analyses', 'share_token')
    op.drop_column('analyses', 'visibility')
