"""Authentication-related Pydantic schemas."""

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Schema for login request."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    locale: Annotated[str, Field(pattern=r"^(ru|en)$")] = "ru"


class TokenResponse(BaseModel):
    """Schema for token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class AuthResponse(BaseModel):
    """Schema for authentication response (login/register)."""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    """Schema for logout request."""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str
    new_password: Annotated[str, Field(min_length=8, max_length=128)]


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
