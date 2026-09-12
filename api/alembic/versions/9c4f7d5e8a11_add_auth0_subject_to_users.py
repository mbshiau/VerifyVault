"""add Auth0 subject to users

Revision ID: 9c4f7d5e8a11
Revises: a6b7540fdc8d
"""

from alembic import op
import sqlalchemy as sa


revision = "9c4f7d5e8a11"
down_revision = "a6b7540fdc8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth0_sub", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_auth0_sub", "users", ["auth0_sub"])


def downgrade() -> None:
    op.drop_constraint("uq_users_auth0_sub", "users", type_="unique")
    op.drop_column("users", "auth0_sub")
