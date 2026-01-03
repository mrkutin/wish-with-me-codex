from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.db import get_db
from app.deps import get_current_user
from app.idempotency import get_cached_response, require_idempotency_key, store_response
from app.redis_client import get_redis
from app.schemas import RedeemRequest
from app.utils import next_sync_seq, utcnow

router = APIRouter(prefix="/api/v1/shares", tags=["shares"])


@router.post("/redeem")
async def redeem_share(request: Request, payload: RedeemRequest, user: dict = Depends(get_current_user)):
    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()

    owner = await db.users.find_one({"wishlists.share.share_token": payload.share_token})
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    wishlist = next(
        (wl for wl in owner.get("wishlists", []) if wl.get("share", {}).get("share_token") == payload.share_token),
        None,
    )
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")

    if str(owner["_id"]) == str(user.get("_id")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot redeem own share")

    share = wishlist.get("share") or {}
    if share.get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share revoked")
    if share.get("expires_at") and share.get("expires_at") < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share expired")

    if any(str(entry.get("user_id")) == str(user.get("_id")) for entry in wishlist.get("access", [])):
        response = {"ok": True}
        await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
        return response

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist.get("wishlist_id")},
        {
            "$push": {"wishlists.$.access": {"user_id": user["_id"], "granted_at": now}},
            "$inc": {"wishlists.$.share.redemptions": 1, "wishlists.$.version": 1},
            "$set": {
                "wishlists.$.updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to redeem share")

    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response
