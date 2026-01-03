import uuid
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from redis.asyncio import Redis


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


async def next_sync_seq(redis: Redis) -> int:
    return await redis.incr("sync:seq")


def normalize_mongo(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [normalize_mongo(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_mongo(val) for key, val in value.items()}
    return value
