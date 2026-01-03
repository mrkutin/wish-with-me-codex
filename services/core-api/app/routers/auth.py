from datetime import timedelta

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request, status
from jose import JWTError

from app.config import settings
from app.db import get_db
from app.idempotency import get_cached_response, require_idempotency_key, store_response
from app.redis_client import get_redis
from app.schemas import LoginRequest, RegisterRequest, TokenPair
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    require_token_type,
    verify_password,
)
from app.utils import utcnow

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair)
async def register(request: Request, payload: RegisterRequest):
    db = get_db()
    idempotency_key = require_idempotency_key(request)
    redis = get_redis()
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        cached = await get_cached_response(redis, str(existing["_id"]), request.url.path, idempotency_key)
        if cached:
            return cached
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    now = utcnow()
    user_doc = {
        "email": payload.email,
        "full_name": payload.full_name,
        "password_hash": hash_password(payload.password),
        "roles": ["user"],
        "created_at": now,
        "updated_at": now,
        "wishlists": [],
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token, access_expires = create_access_token(user_id, user_doc["roles"])
    refresh_token, jti, refresh_expires = create_refresh_token(user_id)

    ttl = int(timedelta(days=settings.refresh_token_ttl_days).total_seconds())
    await redis.setex(f"refresh:{jti}", ttl, user_id)

    response = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires,
    )
    await store_response(redis, user_id, request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/login", response_model=TokenPair)
async def login(request: Request, payload: LoginRequest):
    db = get_db()
    idempotency_key = require_idempotency_key(request)
    redis = get_redis()
    user = await db.users.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user_id = str(user["_id"])
    cached = await get_cached_response(redis, user_id, request.url.path, idempotency_key)
    if cached:
        return cached
    access_token, access_expires = create_access_token(user_id, user.get("roles", []))
    refresh_token, jti, refresh_expires = create_refresh_token(user_id)

    ttl = int(timedelta(days=settings.refresh_token_ttl_days).total_seconds())
    await redis.setex(f"refresh:{jti}", ttl, user_id)

    response = TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires,
    )
    await store_response(redis, user_id, request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: Request, payload: dict):
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh_token")

    try:
        token_payload = decode_token(refresh_token)
        require_token_type(token_payload, "refresh")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    jti = token_payload.get("jti")
    user_id = token_payload.get("sub")
    if not jti or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, user_id, request.url.path, idempotency_key)
    if cached:
        return cached
    stored = await redis.get(f"refresh:{jti}")
    if stored != user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    await redis.delete(f"refresh:{jti}")

    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token, access_expires = create_access_token(user_id, user.get("roles", []))
    new_refresh_token, new_jti, refresh_expires = create_refresh_token(user_id)

    ttl = int(timedelta(days=settings.refresh_token_ttl_days).total_seconds())
    await redis.setex(f"refresh:{new_jti}", ttl, user_id)

    response = TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires,
    )
    await store_response(redis, user_id, request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/logout")
async def logout(request: Request, payload: dict):
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing refresh_token")

    try:
        token_payload = decode_token(refresh_token)
        require_token_type(token_payload, "refresh")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    jti = token_payload.get("jti")
    user_id = token_payload.get("sub")
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    if user_id:
        cached = await get_cached_response(redis, user_id, request.url.path, idempotency_key)
        if cached:
            return cached
    if jti:
        await redis.delete(f"refresh:{jti}")

    response = {"ok": True}
    if user_id:
        await store_response(redis, user_id, request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response
