"""add videos and transcripts tables, claim timestamps

Revision ID: d69309411789
Revises: ddd99e24670b
Create Date: 2026-07-24 23:43:06.233278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd69309411789'
down_revision: Union[str, None] = 'ddd99e24670b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('claims', sa.Column('start_ms', sa.Integer(), nullable=True))
    op.add_column('claims', sa.Column('end_ms', sa.Integer(), nullable=True))

    op.create_table('videos',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('storage_path', sa.String(length=1000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('transcripts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('segments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('transcripts')
    op.drop_table('videos')
    op.drop_column('claims', 'end_ms')
    op.drop_column('claims', 'start_ms')
