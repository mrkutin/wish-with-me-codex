"""API routers."""

from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.health import router as health_router
from app.routers.wishlists import router as wishlists_router
from app.routers.items import router as items_router
from app.routers.oauth import router as oauth_router
from app.routers.share import router as share_router
from app.routers.shared import router as shared_router
from app.routers.sync import router as sync_router
from app.routers.events import router as events_router

__all__ = [
    "auth_router",
    "users_router",
    "health_router",
    "wishlists_router",
    "items_router",
    "oauth_router",
    "share_router",
    "shared_router",
    "sync_router",
    "events_router",
]
