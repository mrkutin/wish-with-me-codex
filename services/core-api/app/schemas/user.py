"""User-related Pydantic schemas."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SocialLinks(BaseModel):
    """Social media links for user profile."""

    instagram: str | None = None
    telegram: str | None = None
    vk: str | None = None
    twitter: str | None = None
    facebook: str | None = None


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    name: Annotated[str, Field(min_length=1, max_length=100)]
    bio: Annotated[str | None, Field(max_length=500)] = None
    public_url_slug: Annotated[
        str | None, Field(pattern=r"^[a-z0-9-]+$", max_length=50)
    ] = None
    social_links: SocialLinks | None = None
    locale: Annotated[str, Field(pattern=r"^(ru|en)$")] = "ru"
    birthday: date | None = None


class UserCreate(UserBase):
    """Schema for user registration."""

    password: Annotated[str | None, Field(min_length=8, max_length=128)] = None
    avatar_base64: str | None = None


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    bio: Annotated[str | None, Field(max_length=500)] = None
    public_url_slug: Annotated[
        str | None, Field(pattern=r"^[a-z0-9-]+$", max_length=50)
    ] = None
    social_links: SocialLinks | None = None
    avatar_base64: str | None = None
    locale: Annotated[str | None, Field(pattern=r"^(ru|en)$")] = None
    birthday: date | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    avatar_base64: str
    created_at: datetime
    updated_at: datetime


class UserPublicProfile(BaseModel):
    """Public profile visible to other users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    avatar_base64: str
    bio: str | None = None
    social_links: SocialLinks | None = None


class ConnectedAccount(BaseModel):
    """Connected OAuth account info."""

    provider: str
    email: str | None
    connected_at: datetime


class ConnectedAccountsResponse(BaseModel):
    """Response for connected accounts listing."""

    accounts: list[ConnectedAccount]
