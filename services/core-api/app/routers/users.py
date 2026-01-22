"""User management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import CurrentUser
from app.models.user import SocialAccount
from app.schemas.user import (
    ConnectedAccount,
    ConnectedAccountsResponse,
    UserPublicProfile,
    UserResponse,
    UserUpdate,
)
from app.services.user import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser) -> UserResponse:
    """Get current user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    data: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update current user's profile."""
    user_service = UserService(db)

    # Check if slug is taken by another user
    if data.public_url_slug:
        if await user_service.is_slug_taken(data.public_url_slug, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This URL slug is already taken",
            )

    updated_user = await user_service.update(current_user, data)
    return UserResponse.model_validate(updated_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete current user's account."""
    user_service = UserService(db)
    await user_service.soft_delete(current_user)


@router.get(
    "/{user_id}/public",
    response_model=UserPublicProfile,
    responses={
        404: {"description": "User not found"},
    },
)
async def get_user_public_profile(
    user_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPublicProfile:
    """Get public profile of any user."""
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserPublicProfile.model_validate(user)


@router.get("/me/connected-accounts", response_model=ConnectedAccountsResponse)
async def get_connected_accounts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectedAccountsResponse:
    """Get connected OAuth accounts for current user."""
    result = await db.execute(
        select(SocialAccount).where(SocialAccount.user_id == current_user.id)
    )
    accounts = result.scalars().all()

    connected_accounts = [
        ConnectedAccount(
            provider=account.provider,
            email=account.email,
            connected_at=account.created_at,
        )
        for account in accounts
    ]

    return ConnectedAccountsResponse(accounts=connected_accounts)
