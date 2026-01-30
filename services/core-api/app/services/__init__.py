"""Services - CouchDB-based."""

from app.services.auth_couchdb import CouchDBAuthService
from app.services.oauth import OAuthService

__all__ = [
    "CouchDBAuthService",
    "OAuthService",
]
