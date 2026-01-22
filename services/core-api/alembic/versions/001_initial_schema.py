"""Initial schema for users and authentication.

Revision ID: 001
Revises:
Create Date: 2026-01-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("avatar_base64", sa.Text(), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("public_url_slug", sa.String(50), nullable=True),
        sa.Column(
            "social_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        sa.Column("locale", sa.String(10), nullable=False, server_default="ru"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("public_url_slug"),
        sa.CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="email_format",
        ),
        sa.CheckConstraint(
            "public_url_slug IS NULL OR public_url_slug ~* '^[a-z0-9-]+$'",
            name="slug_format",
        ),
    )

    # Create indexes for users
    op.create_index(
        "idx_users_email",
        "users",
        ["email"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_users_public_url_slug",
        "users",
        ["public_url_slug"],
        postgresql_where=sa.text("deleted_at IS NULL AND public_url_slug IS NOT NULL"),
    )

    # Create social_accounts table
    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "profile_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("provider", "provider_user_id", name="unique_provider_user"),
    )

    # Create indexes for social_accounts
    op.create_index("idx_social_accounts_user_id", "social_accounts", ["user_id"])
    op.create_index(
        "idx_social_accounts_provider_lookup",
        "social_accounts",
        ["provider", "provider_user_id"],
    )

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("token_hash"),
    )

    # Create indexes for refresh_tokens
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index(
        "idx_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
        postgresql_where=sa.text("NOT revoked"),
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("social_accounts")
    op.drop_table("users")
