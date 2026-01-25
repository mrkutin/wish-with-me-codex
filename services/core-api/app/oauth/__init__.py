"""OAuth module for social authentication."""

from app.oauth.providers import oauth_registry, get_oauth_client
from app.oauth.schemas import OAuthProvider, OAuthUserInfo

__all__ = ["oauth_registry", "get_oauth_client", "OAuthProvider", "OAuthUserInfo"]
