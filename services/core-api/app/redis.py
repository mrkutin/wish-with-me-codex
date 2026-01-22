"""Redis connection and utilities."""

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import settings

# Global Redis client
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


class TokenBlocklist:
    """Manage token blocklist in Redis."""

    PREFIX = "token_blocklist:"

    @classmethod
    async def add(cls, jti: str, expires_in_seconds: int) -> None:
        """Add a token JTI to the blocklist."""
        client = await get_redis()
        await client.setex(f"{cls.PREFIX}{jti}", expires_in_seconds, "1")

    @classmethod
    async def is_blocked(cls, jti: str) -> bool:
        """Check if a token JTI is in the blocklist."""
        client = await get_redis()
        result = await client.get(f"{cls.PREFIX}{jti}")
        return result is not None


class RateLimiter:
    """Simple rate limiting using Redis with atomic operations."""

    PREFIX = "rate_limit:"

    @classmethod
    async def is_rate_limited(
        cls, key: str, max_requests: int, window_seconds: int
    ) -> bool:
        """Check if a key is rate limited using atomic operations."""
        client = await get_redis()
        full_key = f"{cls.PREFIX}{key}"

        # Use atomic INCR - creates key with value 1 if it doesn't exist
        current = await client.incr(full_key)

        # Set expiry only on first request (when count is 1)
        if current == 1:
            await client.expire(full_key, window_seconds)

        return current > max_requests
