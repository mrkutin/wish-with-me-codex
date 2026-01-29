"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status

# Configure logging for the app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# Set specific loggers to INFO level
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app.services.events").setLevel(logging.INFO)
logging.getLogger("app.routers.events").setLevel(logging.INFO)
logging.getLogger("app.routers.items").setLevel(logging.INFO)
logging.getLogger("app.routers.sync").setLevel(logging.INFO)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.couchdb import close_couchdb
from app.redis import close_redis
from app.services.events import event_manager
from app.routers import (
    auth_router,
    health_router,
    users_router,
    wishlists_router,
    items_router,
    oauth_router,
    share_router,
    shared_router,
    sync_router,
    events_router,
)
from app.routers.auth_couchdb import router as auth_couchdb_router
from app.routers.share_couchdb import router as share_couchdb_router
from app.routers.sync_couchdb import router as sync_couchdb_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    yield
    # Shutdown
    await event_manager.stop_subscriber()
    await close_couchdb()
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    description="Backend API for Wish With Me - Offline-first wishlist PWA",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
    allow_credentials=not settings.cors_allow_all,  # credentials not allowed with wildcard
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],  # Allow all headers for browser compatibility
)


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


# Global exception handler for consistent error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    if settings.debug:
        raise exc
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            }
        },
    )


# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(auth_couchdb_router)  # CouchDB-based auth (v2)
app.include_router(share_couchdb_router)  # CouchDB-based sharing (v2)
app.include_router(users_router)
app.include_router(wishlists_router)
app.include_router(items_router)
app.include_router(oauth_router)
app.include_router(share_router)
app.include_router(shared_router)
app.include_router(sync_router)
app.include_router(sync_couchdb_router)  # CouchDB-based sync (v2)
app.include_router(events_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Wish With Me API", "version": "1.0.0"}
