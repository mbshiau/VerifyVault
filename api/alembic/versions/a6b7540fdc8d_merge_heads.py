"""merge heads

Revision ID: a6b7540fdc8d
Revises: 8386e0b5d2c3, a1b2c3d4e5f6
Create Date: 2026-07-26 11:46:32.240129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6b7540fdc8d'
down_revision: Union[str, None] = ('8386e0b5d2c3', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
