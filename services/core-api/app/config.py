"""Application configuration settings."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Wish With Me API"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wishwithme"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT - No default in production, must be explicitly set
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Validate JWT secret key meets minimum security requirements."""
        # Allow empty default only in development
        if not v:
            # Will be checked at runtime
            return v
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v

    # CORS - Allow common local addresses and production server
    cors_origins: list[str] = [
        "http://localhost:9000",
        "http://localhost:8080",
        "http://127.0.0.1:9000",
        "http://127.0.0.1:8080",
        "http://158.69.203.3:9000",  # Montreal production server
        "https://wishwith.me",
        "https://www.wishwith.me",
    ]
    # Allow all origins in development (set via env var CORS_ALLOW_ALL=true)
    cors_allow_all: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True

    # Item Resolver Service
    item_resolver_url: str = "http://localhost:8080"
    item_resolver_token: str = "dev-token"
    item_resolver_timeout: int = 60  # seconds (as per spec)

    # OAuth (optional - configured in Phase 3)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    apple_client_id: str | None = None
    apple_client_secret: str | None = None
    yandex_client_id: str | None = None
    yandex_client_secret: str | None = None
    sber_client_id: str | None = None
    sber_client_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
