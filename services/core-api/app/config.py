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

    # CouchDB (primary database)
    couchdb_url: str = "http://localhost:5984"
    couchdb_database: str = "wishwithme"
    couchdb_admin_user: str = "admin"
    couchdb_admin_password: str = ""

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Validate JWT secret key meets minimum security requirements."""
        if not v:
            return v
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v

    # CORS
    cors_origins: list[str] = [
        "http://localhost:9000",
        "http://localhost:8080",
        "http://127.0.0.1:9000",
        "http://127.0.0.1:8080",
        "http://176.106.144.182:9000",
        "https://wishwith.me",
        "https://www.wishwith.me",
        "https://api.wishwith.me",
    ]
    cors_allow_all: bool = False

    # Item Resolver Service
    item_resolver_url: str = "http://localhost:8080"
    item_resolver_token: str = "dev-token"
    item_resolver_timeout: int = 180

    # OAuth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    yandex_client_id: str | None = None
    yandex_client_secret: str | None = None

    # OAuth URLs
    api_base_url: str = "https://api.wishwith.me"
    frontend_callback_url: str = "https://wishwith.me/auth/callback"
    oauth_state_secret: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
