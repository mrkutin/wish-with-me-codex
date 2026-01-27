"""Drop notifications table.

Revision ID: 006
Revises: 005
Create Date: 2026-01-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop notifications table and related objects."""
    # Drop indexes
    op.drop_index("idx_notifications_unread", table_name="notifications")
    op.drop_index("idx_notifications_user_id", table_name="notifications")

    # Drop table
    op.drop_table("notifications")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS notificationtype")


def downgrade() -> None:
    """Recreate notifications table."""
    # Create notification_type enum
    notification_type = postgresql.ENUM(
        "wishlist_shared",
        "wishlist_accessed",
        "item_marked",
        "item_unmarked",
        "item_resolved",
        "item_resolution_failed",
        name="notificationtype",
    )
    notification_type.create(op.get_bind(), checkfirst=True)

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
                "wishlist_accessed",
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

    # Create indexes
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
