"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.couchdb import close_couchdb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

# Import routers
from app.routers.health import router as health_router
from app.routers.auth_couchdb import router as auth_router
from app.routers.sync_couchdb import router as sync_router
from app.routers.oauth import router as oauth_router
from app.routers.share import router as share_router
from app.routers.shared import router as shared_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    # Startup
    yield
    # Shutdown
    await close_couchdb()


app = FastAPI(
    title=settings.app_name,
    description="Backend API for Wish With Me - Offline-first wishlist PWA with CouchDB",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
    allow_credentials=not settings.cors_allow_all,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


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


# Include routers - All CouchDB-based
app.include_router(health_router)
app.include_router(auth_router)    # /api/v2/auth
app.include_router(sync_router)    # /api/v2/sync
app.include_router(oauth_router)   # /api/v1/oauth (kept for Google/Yandex OAuth)
app.include_router(share_router)   # /api/v1/wishlists/{id}/share
app.include_router(shared_router)  # /api/v1/shared/{token}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Wish With Me API", "version": "2.0.0"}
