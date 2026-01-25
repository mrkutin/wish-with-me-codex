"""OAuth authentication router."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import CurrentUser
from app.oauth.providers import get_configured_providers, is_provider_configured
from app.oauth.schemas import (
    ConnectedAccountResponse,
    OAuthAuthorizeResponse,
    OAuthProvider,
)
from app.services.oauth import (
    DuplicateLinkError,
    EmailConflictError,
    OAuthService,
    ProviderNotLinkedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])


@router.get("/providers")
async def get_available_providers() -> dict:
    """Get list of configured OAuth providers."""
    providers = get_configured_providers()
    return {
        "providers": [p.value for p in providers],
    }


@router.get("/{provider}/authorize", response_model=None)
async def oauth_authorize(
    request: Request,
    provider: OAuthProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
    redirect: bool = Query(True, description="Redirect to provider if true, return URL if false"),
):
    """Initiate OAuth login flow.

    If redirect=true (default), redirects to the OAuth provider.
    If redirect=false, returns the authorization URL.
    """
    if not is_provider_configured(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider.value}' is not configured",
        )

    service = OAuthService(db)

    try:
        auth_url, state = await service.get_authorization_url(
            request=request,
            provider=provider,
            action="login",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if redirect:
        return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)

    return OAuthAuthorizeResponse(authorization_url=auth_url, state=state)


@router.get("/{provider}/callback", name="oauth_callback")
async def oauth_callback(
    request: Request,
    provider: OAuthProvider,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> RedirectResponse:
    """Handle OAuth callback from provider.

    Exchanges the authorization code for tokens, authenticates or creates the user,
    and redirects to the frontend with tokens.
    """
    # Handle OAuth errors from provider
    if error:
        logger.warning(f"OAuth error from {provider.value}: {error} - {error_description}")
        error_msg = error_description or error
        return RedirectResponse(
            url=f"{settings.frontend_callback_url}?error={error_msg}",
            status_code=status.HTTP_302_FOUND,
        )

    service = OAuthService(db)

    try:
        # Exchange code for tokens and user info
        user_info, state_data = await service.exchange_code(
            request=request,
            provider=provider,
            code=code,
            state=state,
        )

        action = state_data.get("action", "login")

        if action == "link":
            # This is an account linking flow
            user_id = state_data.get("user_id")
            if not user_id:
                raise ValueError("Invalid state for link action")

            await service.link_account(user_id, user_info)
            await db.commit()

            # Redirect to settings page with success
            return RedirectResponse(
                url=f"{settings.frontend_callback_url}?linked={provider.value}",
                status_code=status.HTTP_302_FOUND,
            )

        # Login/register flow
        auth_response, is_new = await service.authenticate_or_create(
            user_info=user_info,
            device_info=request.headers.get("user-agent"),
        )
        await db.commit()

        # Build redirect URL with tokens
        redirect_url = (
            f"{settings.frontend_callback_url}"
            f"?access_token={auth_response.access_token}"
            f"&refresh_token={auth_response.refresh_token}"
            f"&expires_in={auth_response.expires_in}"
        )
        if is_new:
            redirect_url += "&new_user=true"

        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

    except EmailConflictError as e:
        logger.info(f"OAuth email conflict: {e.email} already registered")
        return RedirectResponse(
            url=f"{settings.frontend_callback_url}?error=email_exists&email={e.email}&provider={e.provider.value}",
            status_code=status.HTTP_302_FOUND,
        )

    except DuplicateLinkError as e:
        return RedirectResponse(
            url=f"{settings.frontend_callback_url}?error=already_linked&provider={e.provider.value}",
            status_code=status.HTTP_302_FOUND,
        )

    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{settings.frontend_callback_url}?error=auth_failed",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        logger.exception(f"Unexpected OAuth error: {e}")
        await db.rollback()
        return RedirectResponse(
            url=f"{settings.frontend_callback_url}?error=server_error",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/{provider}/link/initiate")
async def oauth_link_initiate(
    request: Request,
    provider: OAuthProvider,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Initiate OAuth account linking flow.

    Requires authentication. Returns the authorization URL for the frontend
    to redirect to. This approach is more secure than accepting tokens in URL.
    """
    if not is_provider_configured(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider.value}' is not configured",
        )

    service = OAuthService(db)

    try:
        auth_url, state = await service.get_authorization_url(
            request=request,
            provider=provider,
            action="link",
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {"authorization_url": auth_url, "state": state}


@router.delete("/{provider}/unlink")
async def oauth_unlink(
    provider: OAuthProvider,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Unlink an OAuth provider from the current user's account.

    Will fail if this is the user's only authentication method.
    """
    service = OAuthService(db)

    try:
        await service.unlink_account(current_user.id, provider)
        await db.commit()
        return {"message": f"Successfully unlinked {provider.value}"}

    except ProviderNotLinkedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider.value}' is not linked to your account",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/connected")
async def get_connected_accounts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get list of connected OAuth accounts for the current user."""
    service = OAuthService(db)
    accounts = await service.get_user_social_accounts(current_user.id)

    return {
        "accounts": [
            ConnectedAccountResponse(
                provider=acc.provider,
                email=acc.email,
                connected_at=acc.created_at.isoformat(),
            )
            for acc in accounts
        ],
        "has_password": current_user.password_hash is not None,
    }
