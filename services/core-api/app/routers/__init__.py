"""API routers - CouchDB-based."""

from app.routers.health import router as health_router
from app.routers.auth_couchdb import router as auth_router
from app.routers.sync_couchdb import router as sync_router
from app.routers.oauth import router as oauth_router

__all__ = [
    "health_router",
    "auth_router",
    "sync_router",
    "oauth_router",
]
