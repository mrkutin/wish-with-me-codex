import json
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


def require_idempotency_key(request: Request) -> str:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key")
    return key


def _storage_key(identity: str, route: str, key: str) -> str:
    safe_route = route.replace("/", ":")
    return f"idempotency:{identity}:{safe_route}:{key}"


async def get_cached_response(redis: Redis, identity: str, route: str, key: str) -> JSONResponse | None:
    stored = await redis.get(_storage_key(identity, route, key))
    if not stored:
        return None
    payload = json.loads(stored)
    return JSONResponse(status_code=payload["status_code"], content=payload["body"])


async def store_response(redis: Redis, identity: str, route: str, key: str, status_code: int, body: Any) -> None:
    payload = {"status_code": status_code, "body": jsonable_encoder(body)}
    await redis.setex(_storage_key(identity, route, key), IDEMPOTENCY_TTL_SECONDS, json.dumps(payload))
