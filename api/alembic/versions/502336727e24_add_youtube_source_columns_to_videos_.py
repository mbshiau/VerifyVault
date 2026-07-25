"""add youtube source columns to videos, make storage_path nullable

Revision ID: 502336727e24
Revises: d69309411789
Create Date: 2026-07-25 10:57:08.446258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '502336727e24'
down_revision: Union[str, None] = 'd69309411789'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('videos', 'storage_path', existing_type=sa.String(length=1000), nullable=True)
    op.add_column('videos', sa.Column('source', sa.String(length=20), nullable=False, server_default='upload'))
    op.alter_column('videos', 'source', server_default=None)
    op.add_column('videos', sa.Column('youtube_video_id', sa.String(length=20), nullable=True))
    op.add_column('videos', sa.Column('youtube_url', sa.String(length=2000), nullable=True))


def downgrade() -> None:
    op.drop_column('videos', 'youtube_url')
    op.drop_column('videos', 'youtube_video_id')
    op.drop_column('videos', 'source')
    op.alter_column('videos', 'storage_path', existing_type=sa.String(length=1000), nullable=False)
