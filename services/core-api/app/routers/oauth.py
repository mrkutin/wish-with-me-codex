"""OAuth authentication router - CouchDB-based."""

import logging
import traceback
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.config import settings
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


def _build_error_redirect(error_code: str, message: str | None = None) -> RedirectResponse:
    """Build redirect URL with error information."""
    url = f"{settings.frontend_callback_url}?error={error_code}"
    if message:
        url += f"&error_message={quote(message[:200])}"  # Limit message length
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

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
    redirect: bool = Query(True, description="Redirect to provider if true, return URL if false"),
    callback_url: str | None = Query(None, description="Custom callback URL for mobile apps (e.g. wishwithme://auth/callback)"),
):
    """Initiate OAuth login flow."""
    if not is_provider_configured(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider.value}' is not configured",
        )

    service = OAuthService()

    try:
        auth_url, state = await service.get_authorization_url(
            request=request,
            provider=provider,
            action="login",
            callback_url=callback_url,
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
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> RedirectResponse:
    """Handle OAuth callback from provider."""
    # Try to extract callback URL from state early for error redirects
    service = OAuthService()
    base_callback = settings.frontend_callback_url
    state_peek = service._verify_state(state)
    if state_peek and state_peek.get("callback_url"):
        base_callback = state_peek["callback_url"]

    if error:
        logger.warning(f"OAuth error from {provider.value}: {error} - {error_description}")
        error_msg = error_description or error
        return RedirectResponse(
            url=f"{base_callback}?error={error_msg}",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        user_info, state_data = await service.exchange_code(
            request=request,
            provider=provider,
            code=code,
            state=state,
        )

        action = state_data.get("action", "login")
        # Use custom callback URL from state if provided, otherwise default
        cb = state_data.get("callback_url") or settings.frontend_callback_url

        if action == "link":
            user_id = state_data.get("user_id")
            if not user_id:
                raise ValueError("Invalid state for link action")

            await service.link_account(user_id, user_info)

            return RedirectResponse(
                url=f"{cb}?linked={provider.value}",
                status_code=status.HTTP_302_FOUND,
            )

        auth_response, is_new = await service.authenticate_or_create(
            user_info=user_info,
            device_info=request.headers.get("user-agent"),
        )

        redirect_url = (
            f"{cb}"
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
            url=f"{base_callback}?error=email_exists&email={e.email}&provider={e.provider.value}",
            status_code=status.HTTP_302_FOUND,
        )

    except DuplicateLinkError as e:
        return RedirectResponse(
            url=f"{base_callback}?error=already_linked&provider={e.provider.value}",
            status_code=status.HTTP_302_FOUND,
        )

    except ValidationError as e:
        error_details = str(e)
        logger.error(f"OAuth validation error: {error_details}")
        logger.error(f"Validation error details: {e.errors()}")
        return RedirectResponse(
            url=f"{base_callback}?error=validation_error&error_message={quote('Invalid data from OAuth provider')}",
            status_code=status.HTTP_302_FOUND,
        )

    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"{base_callback}?error=auth_failed&error_message={quote(str(e)[:200])}",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        # Log full traceback for debugging
        error_msg = str(e)
        error_type = type(e).__name__
        tb = traceback.format_exc()
        logger.error(f"Unexpected OAuth error ({error_type}): {error_msg}")
        logger.error(f"Full traceback:\n{tb}")
        return RedirectResponse(
            url=f"{base_callback}?error=server_error&error_message={quote(f'{error_type}: {error_msg}'[:200])}",
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/{provider}/link/initiate")
async def oauth_link_initiate(
    request: Request,
    provider: OAuthProvider,
    current_user: CurrentUser,
) -> dict:
    """Initiate OAuth account linking flow."""
    if not is_provider_configured(provider):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider.value}' is not configured",
        )

    service = OAuthService()

    try:
        auth_url, state = await service.get_authorization_url(
            request=request,
            provider=provider,
            action="link",
            user_id=current_user["_id"],
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
) -> dict:
    """Unlink an OAuth provider from the current user's account."""
    service = OAuthService()

    try:
        await service.unlink_account(current_user["_id"], provider)
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
) -> dict:
    """Get list of connected OAuth accounts for the current user."""
    service = OAuthService()
    accounts = await service.get_user_social_accounts(current_user["_id"])

    return {
        "accounts": [
            ConnectedAccountResponse(
                provider=acc["provider"],
                email=acc.get("email"),
                connected_at=acc.get("created_at", ""),
            )
            for acc in accounts
        ],
        "has_password": current_user.get("password_hash") is not None,
    }
