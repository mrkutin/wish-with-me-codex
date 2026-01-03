from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.deps import get_current_user
from app.redis_client import get_redis
from app.utils import utcnow
from app.visibility import build_wishlist_view

router = APIRouter(prefix="/api/v1", tags=["sync"])


@router.get("/sync")
async def sync(cursor: int = 0, user: dict = Depends(get_current_user)):
    if cursor < 0:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    db = get_db()
    redis = get_redis()
    user_id = str(user["_id"])

    user_doc = await db.users.find_one({"_id": ObjectId(user_id)}, {"wishlists": 1})
    changes = []
    for wl in user_doc.get("wishlists", []) if user_doc else []:
        if wl.get("last_sync_seq", 0) > cursor:
            changes.append(build_wishlist_view(wl, user, user))

    shared_cursor = db.users.find({"wishlists.access.user_id": ObjectId(user_id)}, {"wishlists": 1})
    owners = await shared_cursor.to_list(length=200)
    for owner in owners:
        for wl in owner.get("wishlists", []):
            access = wl.get("access", [])
            if not any(str(entry.get("user_id")) == user_id for entry in access):
                continue
            if wl.get("last_sync_seq", 0) > cursor:
                changes.append(build_wishlist_view(wl, owner, user))

    latest = await redis.get("sync:seq")
    latest_cursor = int(latest) if latest else cursor

    return {
        "server_time": utcnow().isoformat(),
        "next_cursor": latest_cursor,
        "changes": {"wishlists": changes},
    }
