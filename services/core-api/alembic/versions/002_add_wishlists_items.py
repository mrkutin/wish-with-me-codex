"""Add wishlists and items tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-22 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create wishlists table
    op.create_table(
        "wishlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create index on wishlists.user_id for active records
    op.create_index(
        "idx_wishlists_user_id",
        "wishlists",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create items table
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "wishlist_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_base64", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "resolving", "resolved", "failed", name="itemstatus"
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("resolver_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity >= 1", name="check_quantity_positive"),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0", name="check_price_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["wishlist_id"],
            ["wishlists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create unique index on wishlist_id + title for active records (replaces unique constraint)
    op.create_index(
        "uq_wishlist_item_title",
        "items",
        ["wishlist_id", "title"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create indexes on items table for active records
    op.create_index(
        "idx_items_wishlist_id",
        "items",
        ["wishlist_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_index(
        "idx_items_status",
        "items",
        ["status"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index("idx_items_status", table_name="items")
    op.drop_index("idx_items_wishlist_id", table_name="items")
    op.drop_index("uq_wishlist_item_title", table_name="items")
    op.drop_table("items")
    op.drop_index("idx_wishlists_user_id", table_name="wishlists")
    op.drop_table("wishlists")
    # Drop the enum type (created automatically by SQLAlchemy)
    op.execute("DROP TYPE IF EXISTS itemstatus")
