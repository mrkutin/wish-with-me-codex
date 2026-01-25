"""Add sharing, marks, and notifications tables for Phase 4

Revision ID: 004
Revises: 003
Create Date: 2026-01-25 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create share_link_type enum
    share_link_type = postgresql.ENUM("view", "mark", name="sharelinktype")
    share_link_type.create(op.get_bind(), checkfirst=True)

    # Create notification_type enum
    notification_type = postgresql.ENUM(
        "wishlist_shared",
        "item_marked",
        "item_unmarked",
        "item_resolved",
        "item_resolution_failed",
        name="notificationtype",
    )
    notification_type.create(op.get_bind(), checkfirst=True)

    # Add marked_quantity column to items table
    op.add_column(
        "items",
        sa.Column("marked_quantity", sa.Integer(), nullable=False, server_default="0"),
    )

    # Create share_links table
    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "wishlist_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column(
            "link_type",
            postgresql.ENUM("view", "mark", name="sharelinktype", create_type=False),
            nullable=False,
            server_default="mark",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["wishlist_id"],
            ["wishlists.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )

    # Create indexes on share_links
    op.create_index(
        "idx_share_links_token",
        "share_links",
        ["token"],
        unique=False,
        postgresql_where=sa.text("NOT revoked"),
    )
    op.create_index(
        "idx_share_links_wishlist_id",
        "share_links",
        ["wishlist_id"],
        unique=False,
    )

    # Create marks table
    op.create_table(
        "marks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
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
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "user_id", name="uq_mark_item_user"),
        sa.CheckConstraint("quantity > 0", name="check_mark_quantity_positive"),
    )

    # Create indexes on marks
    op.create_index(
        "idx_marks_item_id",
        "marks",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "idx_marks_user_id",
        "marks",
        ["user_id"],
        unique=False,
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "type",
            postgresql.ENUM(
                "wishlist_shared",
                "item_marked",
                "item_unmarked",
                "item_resolved",
                "item_resolution_failed",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on notifications
    op.create_index(
        "idx_notifications_user_id",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_notifications_unread",
        "notifications",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("NOT read"),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop notifications table and indexes
    op.drop_index("idx_notifications_unread", table_name="notifications")
    op.drop_index("idx_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    # Drop marks table and indexes
    op.drop_index("idx_marks_user_id", table_name="marks")
    op.drop_index("idx_marks_item_id", table_name="marks")
    op.drop_table("marks")

    # Drop share_links table and indexes
    op.drop_index("idx_share_links_wishlist_id", table_name="share_links")
    op.drop_index("idx_share_links_token", table_name="share_links")
    op.drop_table("share_links")

    # Remove marked_quantity column from items
    op.drop_column("items", "marked_quantity")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS sharelinktype")
