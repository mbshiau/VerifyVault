"""generalize videos youtube columns to external_video_id and source_url

Revision ID: e74fe243bd4f
Revises: 502336727e24
Create Date: 2026-07-25 11:26:32.358685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e74fe243bd4f'
down_revision: Union[str, None] = '502336727e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'videos', 'youtube_video_id', new_column_name='external_video_id',
        existing_type=sa.String(length=20), type_=sa.String(length=40),
    )
    op.alter_column('videos', 'youtube_url', new_column_name='source_url', existing_type=sa.String(length=2000))


def downgrade() -> None:
    op.alter_column('videos', 'source_url', new_column_name='youtube_url', existing_type=sa.String(length=2000))
    op.alter_column(
        'videos', 'external_video_id', new_column_name='youtube_video_id',
        existing_type=sa.String(length=40), type_=sa.String(length=20),
    )
