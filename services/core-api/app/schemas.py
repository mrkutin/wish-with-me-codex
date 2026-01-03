from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_at: datetime
    refresh_expires_at: datetime


class UserOut(BaseModel):
    id: str = Field(alias="_id")
    email: EmailStr
    full_name: str
    roles: list[str]
    created_at: datetime
    updated_at: datetime


class WishlistCreate(BaseModel):
    title: str
    description: str | None = None


class WishlistUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class ItemCreate(BaseModel):
    source_url: str
    quantity: int | None = 1


class ItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    price: Any | None = None
    quantity: int | None = None


class ShareResponse(BaseModel):
    share_token: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    redemptions: int


class RedeemRequest(BaseModel):
    share_token: str


class AccessRevokeRequest(BaseModel):
    user_id: str


class SyncResponse(BaseModel):
    cursor: int
    wishlists: list[dict]


class ErrorResponse(BaseModel):
    detail: str
