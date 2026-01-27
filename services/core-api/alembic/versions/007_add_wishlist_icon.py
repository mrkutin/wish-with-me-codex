"""Add icon column to wishlists table

Revision ID: 007
Revises: 006
Create Date: 2026-01-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add icon column to wishlists table."""
    op.add_column(
        "wishlists",
        sa.Column("icon", sa.String(50), nullable=False, server_default="card_giftcard"),
    )


def downgrade() -> None:
    """Remove icon column from wishlists table."""
    op.drop_column("wishlists", "icon")
