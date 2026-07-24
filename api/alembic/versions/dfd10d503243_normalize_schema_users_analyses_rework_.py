"""normalize schema: users, analyses rework, claims, sources

Revision ID: dfd10d503243
Revises:
Create Date: 2026-07-24 16:02:46.523656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dfd10d503243'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pre-existing `analyses` rows predate the user/claim/source model and
    # can't satisfy the new NOT NULL columns - dropped and recreated from
    # scratch rather than altered in place (confirmed disposable dev/test
    # data, not production data). IF EXISTS since a fresh database (e.g. a
    # test DB migrated from scratch) never had the old table to begin with.
    op.execute('DROP TABLE IF EXISTS analyses')

    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('profile_picture_url', sa.String(length=1000), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('auth_provider', sa.String(length=20), nullable=False),
    sa.Column('google_sub', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('google_sub')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.create_table('analyses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('source_type', sa.String(length=10), nullable=False),
    sa.Column('original_text', sa.Text(), nullable=False),
    sa.Column('speaker', sa.String(length=200), nullable=True),
    sa.Column('speech_date', sa.Date(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('entities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('entity_details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analyses_user_id'), 'analyses', ['user_id'], unique=False)
    op.create_index('ix_analyses_user_id_created_at', 'analyses', ['user_id', 'created_at'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('jti', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_jti'), 'refresh_tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    op.create_table('claims',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('analysis_id', sa.UUID(), nullable=False),
    sa.Column('extracted_claim', sa.Text(), nullable=False),
    sa.Column('quote', sa.Text(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('related_entities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('time_reference', sa.String(length=50), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('confidence_explanation', sa.Text(), nullable=False),
    sa.Column('materiality', sa.Float(), nullable=False),
    sa.Column('position_in_text', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claims_analysis_id'), 'claims', ['analysis_id'], unique=False)

    op.create_table('sources',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('claim_id', sa.UUID(), nullable=False),
    sa.Column('url', sa.String(length=2000), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('publisher', sa.String(length=200), nullable=True),
    sa.Column('snippet', sa.Text(), nullable=False),
    sa.Column('retrieval_score', sa.Float(), nullable=True),
    sa.Column('relation', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sources_claim_id'), 'sources', ['claim_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sources_claim_id'), table_name='sources')
    op.drop_table('sources')
    op.drop_index(op.f('ix_claims_analysis_id'), table_name='claims')
    op.drop_table('claims')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_jti'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_analyses_user_id_created_at', table_name='analyses')
    op.drop_index(op.f('ix_analyses_user_id'), table_name='analyses')
    op.drop_table('analyses')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.create_table('analyses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('input_text', sa.Text(), nullable=False),
    sa.Column('speaker', sa.String(length=200), nullable=True),
    sa.Column('speech_date', sa.Date(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('claims', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('entities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('entity_details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
