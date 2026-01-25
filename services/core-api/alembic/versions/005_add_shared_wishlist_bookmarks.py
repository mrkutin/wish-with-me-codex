"""Add shared wishlist bookmarks table.

Revision ID: 005
Revises: 004
Create Date: 2024-01-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shared_wishlist_bookmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wishlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wishlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("share_token", sa.String(32), nullable=False),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "wishlist_id", name="uq_bookmark_user_wishlist"),
    )

    # Index for fetching user's bookmarks
    op.create_index(
        "ix_shared_wishlist_bookmarks_user_id",
        "shared_wishlist_bookmarks",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_shared_wishlist_bookmarks_user_id")
    op.drop_table("shared_wishlist_bookmarks")
