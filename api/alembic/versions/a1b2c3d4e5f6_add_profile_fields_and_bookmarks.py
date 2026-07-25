"""add profile fields to users and bookmarks table

Revision ID: a1b2c3d4e5f6
Revises: f3a9c1d5b7e2
Create Date: 2026-07-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a9c1d5b7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('username', sa.String(length=30), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(length=280), nullable=False, server_default=''))
    op.add_column('users', sa.Column('avatar_url', sa.String(length=1000), nullable=True))
    op.add_column(
        'users', sa.Column('profile_visibility', sa.String(length=10), nullable=False, server_default='public')
    )
    op.create_unique_constraint('uq_users_username', 'users', ['username'])
    op.alter_column('users', 'bio', server_default=None)
    op.alter_column('users', 'profile_visibility', server_default=None)

    op.create_table(
        'bookmarks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'analysis_id', name='uq_bookmarks_user_analysis'),
    )
    op.create_index('ix_bookmarks_user_id', 'bookmarks', ['user_id'])
    op.create_index('ix_bookmarks_analysis_id', 'bookmarks', ['analysis_id'])


def downgrade() -> None:
    op.drop_index('ix_bookmarks_analysis_id', table_name='bookmarks')
    op.drop_index('ix_bookmarks_user_id', table_name='bookmarks')
    op.drop_table('bookmarks')

    op.drop_constraint('uq_users_username', 'users', type_='unique')
    op.drop_column('users', 'profile_visibility')
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'username')
