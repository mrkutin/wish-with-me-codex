"""User service for user management operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.security import DEFAULT_AVATAR_BASE64, hash_password


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> User | None:
        """Get a user by public URL slug."""
        result = await self.db.execute(
            select(User).where(
                User.public_url_slug == slug, User.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=data.email,
            password_hash=hash_password(data.password) if data.password else None,
            name=data.name,
            avatar_base64=data.avatar_base64 or DEFAULT_AVATAR_BASE64,
            bio=data.bio,
            public_url_slug=data.public_url_slug,
            social_links=data.social_links.model_dump() if data.social_links else {},
            locale=data.locale,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, data: UserUpdate) -> User:
        """Update a user's profile."""
        update_data = data.model_dump(exclude_unset=True)

        if "social_links" in update_data and update_data["social_links"]:
            update_data["social_links"] = update_data["social_links"].model_dump()

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def soft_delete(self, user: User) -> None:
        """Soft delete a user."""
        user.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def is_email_taken(self, email: str, exclude_user_id: UUID | None = None) -> bool:
        """Check if an email is already taken."""
        query = select(User).where(User.email == email, User.deleted_at.is_(None))
        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def is_slug_taken(self, slug: str, exclude_user_id: UUID | None = None) -> bool:
        """Check if a public URL slug is already taken."""
        query = select(User).where(
            User.public_url_slug == slug, User.deleted_at.is_(None)
        )
        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
