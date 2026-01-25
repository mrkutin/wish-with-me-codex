"""Add birthday column to users table

Revision ID: 003
Revises: 002
Create Date: 2026-01-25 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add birthday column to users table."""
    op.add_column("users", sa.Column("birthday", sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove birthday column from users table."""
    op.drop_column("users", "birthday")
