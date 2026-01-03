from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.broker import publish_event
from app.db import get_db
from app.deps import get_current_user
from app.idempotency import get_cached_response, require_idempotency_key, store_response
from app.redis_client import get_redis
from app.schemas import AccessRevokeRequest, ItemCreate, ItemUpdate, WishlistCreate, WishlistUpdate
from app.utils import new_uuid, next_sync_seq, normalize_mongo, utcnow
from app.visibility import build_wishlist_view

router = APIRouter(prefix="/api/v1/wishlists", tags=["wishlists"])


def _ensure_owner(user: dict, owner_id: str):
    if str(user.get("_id")) != owner_id and "admin" not in user.get("roles", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")


def _can_view(user: dict, wishlist: dict, owner_id: str) -> bool:
    if str(user.get("_id")) == owner_id or "admin" in user.get("roles", []):
        return True
    access = wishlist.get("access", [])
    return any(str(entry.get("user_id")) == str(user.get("_id")) for entry in access)


async def _find_wishlist_by_id(wishlist_id: str):
    db = get_db()
    cursor = db.users.find({"wishlists.wishlist_id": wishlist_id}, {"wishlists.$": 1})
    user = await cursor.to_list(length=1)
    if not user:
        return None, None
    owner = user[0]
    wishlist = owner.get("wishlists", [None])[0]
    return owner, wishlist


@router.get("")
async def list_wishlists(user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = str(user["_id"])

    owned = await db.users.find_one({"_id": ObjectId(user_id)}, {"wishlists": 1})
    owned_wishlists = owned.get("wishlists", []) if owned else []

    shared_cursor = db.users.find({"wishlists.access.user_id": ObjectId(user_id)}, {"wishlists": 1})
    shared = await shared_cursor.to_list(length=100)

    shared_wishlists = []
    for owner in shared:
        for wishlist in owner.get("wishlists", []):
            access = wishlist.get("access", [])
            if any(str(entry.get("user_id")) == user_id for entry in access):
                shared_wishlists.append(build_wishlist_view(wishlist, owner, user))

    owned_views = [build_wishlist_view(wishlist, user, user) for wishlist in owned_wishlists]
    return {"owned": owned_views, "shared": shared_wishlists}


@router.post("")
async def create_wishlist(request: Request, payload: WishlistCreate, user: dict = Depends(get_current_user)):
    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    wishlist_id = new_uuid()
    wishlist = {
        "wishlist_id": wishlist_id,
        "title": payload.title,
        "description": payload.description,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "last_sync_seq": await next_sync_seq(redis),
        "share": None,
        "access": [],
        "items": [],
    }

    result = await db.users.update_one(
        {"_id": user["_id"]},
        {"$push": {"wishlists": wishlist}, "$set": {"updated_at": now}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create wishlist")
    response = build_wishlist_view(wishlist, user, user)
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.get("/{wishlist_id}")
async def get_wishlist(wishlist_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")

    if not _can_view(user, wishlist, str(owner["_id"])):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return build_wishlist_view(wishlist, owner, user)


@router.patch("/{wishlist_id}")
async def update_wishlist(request: Request, wishlist_id: str, payload: WishlistUpdate, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    updates = {"wishlists.$.updated_at": now, "wishlists.$.version": wishlist.get("version", 1) + 1}
    if payload.title is not None:
        updates["wishlists.$.title"] = payload.title
    if payload.description is not None:
        updates["wishlists.$.description"] = payload.description
    updates["wishlists.$.last_sync_seq"] = await next_sync_seq(redis)

    updates["updated_at"] = now
    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {"$set": updates},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update wishlist")

    refreshed_owner, refreshed_wishlist = await _find_wishlist_by_id(wishlist_id)
    response = build_wishlist_view(refreshed_wishlist, refreshed_owner, user)
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.delete("/{wishlist_id}")
async def delete_wishlist(request: Request, wishlist_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    result = await db.users.update_one(
        {"_id": owner["_id"]},
        {"$pull": {"wishlists": {"wishlist_id": wishlist_id}}, "$set": {"updated_at": now}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to delete wishlist")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/items")
async def add_item(request: Request, wishlist_id: str, payload: ItemCreate, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    item_id = new_uuid()
    item = {
        "item_id": item_id,
        "source_url": payload.source_url,
        "canonical_url": None,
        "title": None,
        "description": None,
        "image_base64": None,
        "image_mime": None,
        "price": None,
        "quantity": payload.quantity or 1,
        "resolution_status": "pending",
        "resolution_error": None,
        "resolution_error_code": None,
        "resolution_confidence": None,
        "resolved_at": None,
        "is_bought": False,
        "bought_by_user_id": None,
        "bought_at": None,
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$push": {"wishlists.$.items": item},
            "$set": {
                "wishlists.$.updated_at": now,
                "wishlists.$.version": wishlist.get("version", 1) + 1,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to add item")

    await publish_event(
        "item.resolve.requested",
        {
            "owner_user_id": str(owner["_id"]),
            "wishlist_id": wishlist_id,
            "item_id": item_id,
            "source_url": payload.source_url,
        },
        request.state.request_id,
    )

    response = normalize_mongo(item)
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.patch("/{wishlist_id}/items/{item_id}")
async def update_item(request: Request, wishlist_id: str, item_id: str, payload: ItemUpdate, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    updates = {"wishlists.$.items.$[item].updated_at": now}
    if payload.title is not None:
        updates["wishlists.$.items.$[item].title"] = payload.title
    if payload.description is not None:
        updates["wishlists.$.items.$[item].description"] = payload.description
    if payload.price is not None:
        updates["wishlists.$.items.$[item].price"] = payload.price
    if payload.quantity is not None:
        updates["wishlists.$.items.$[item].quantity"] = payload.quantity

    updates["wishlists.$.last_sync_seq"] = await next_sync_seq(redis)
    updates["wishlists.$.updated_at"] = now

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$set": {**updates, "updated_at": now},
            "$inc": {"wishlists.$.items.$[item].version": 1, "wishlists.$.version": 1},
        },
        array_filters=[{"item.item_id": item_id}],
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to update item")

    refreshed_owner, refreshed_wishlist = await _find_wishlist_by_id(wishlist_id)
    for item in refreshed_wishlist.get("items", []):
        if item.get("item_id") == item_id:
            response = normalize_mongo(item)
            await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
            return response
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")


@router.delete("/{wishlist_id}/items/{item_id}")
async def delete_item(request: Request, wishlist_id: str, item_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$pull": {"wishlists.$.items": {"item_id": item_id}},
            "$set": {
                "wishlists.$.updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
            "$inc": {"wishlists.$.version": 1},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to delete item")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/items/{item_id}/mark-bought")
async def mark_bought(request: Request, wishlist_id: str, item_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    if not _can_view(user, wishlist, str(owner["_id"])):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$set": {
                "wishlists.$.items.$[item].is_bought": True,
                "wishlists.$.items.$[item].bought_by_user_id": user["_id"],
                "wishlists.$.items.$[item].bought_at": now,
                "wishlists.$.items.$[item].updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "wishlists.$.updated_at": now,
                "updated_at": now,
            },
            "$inc": {"wishlists.$.items.$[item].version": 1, "wishlists.$.version": 1},
        },
        array_filters=[{"item.item_id": item_id}],
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to mark bought")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/items/{item_id}/unmark-bought")
async def unmark_bought(request: Request, wishlist_id: str, item_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    if not _can_view(user, wishlist, str(owner["_id"])):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()

    item = next((it for it in wishlist.get("items", []) if it.get("item_id") == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    is_owner_or_admin = str(owner["_id"]) == str(user["_id"]) or "admin" in user.get("roles", [])
    if not is_owner_or_admin:
        bought_by = item.get("bought_by_user_id")
        if not bought_by or str(bought_by) != str(user["_id"]):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot unmark other user's purchase")

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$set": {
                "wishlists.$.items.$[item].is_bought": False,
                "wishlists.$.items.$[item].bought_by_user_id": None,
                "wishlists.$.items.$[item].bought_at": None,
                "wishlists.$.items.$[item].updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "wishlists.$.updated_at": now,
                "updated_at": now,
            },
            "$inc": {"wishlists.$.items.$[item].version": 1, "wishlists.$.version": 1},
        },
        array_filters=[{"item.item_id": item_id}],
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to unmark bought")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/items/{item_id}/resolve")
async def resolve_item(request: Request, wishlist_id: str, item_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    item = next((item for item in wishlist.get("items", []) if item.get("item_id") == item_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached

    await publish_event(
        "item.resolve.requested",
        {
            "owner_user_id": str(owner["_id"]),
            "wishlist_id": wishlist_id,
            "item_id": item_id,
            "source_url": item.get("source_url"),
        },
        request.state.request_id,
    )
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/share")
async def share_wishlist(request: Request, wishlist_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    share_token = new_uuid()
    share = {
        "share_token": share_token,
        "created_by_user_id": user["_id"],
        "created_at": now,
        "expires_at": None,
        "revoked_at": None,
        "redemptions": 0,
    }

    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$set": {
                "wishlists.$.share": share,
                "wishlists.$.updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
            "$inc": {"wishlists.$.version": 1},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to share wishlist")

    response = normalize_mongo(share)
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/share/revoke")
async def revoke_share(request: Request, wishlist_id: str, user: dict = Depends(get_current_user)):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    if not wishlist.get("share"):
        response = {"ok": True}
        await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
        return response
    now = utcnow()
    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$unset": {"wishlists.$.share": ""},
            "$set": {
                "wishlists.$.updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
            "$inc": {"wishlists.$.version": 1},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to revoke share")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response


@router.post("/{wishlist_id}/access/revoke")
async def revoke_access_for_wishlist(
    request: Request, wishlist_id: str, payload: AccessRevokeRequest, user: dict = Depends(get_current_user)
):
    owner, wishlist = await _find_wishlist_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    _ensure_owner(user, str(owner["_id"]))

    db = get_db()
    redis = get_redis()
    idempotency_key = require_idempotency_key(request)
    cached = await get_cached_response(redis, str(user["_id"]), request.url.path, idempotency_key)
    if cached:
        return cached
    now = utcnow()
    result = await db.users.update_one(
        {"_id": owner["_id"], "wishlists.wishlist_id": wishlist_id},
        {
            "$pull": {"wishlists.$.access": {"user_id": ObjectId(payload.user_id)}},
            "$set": {
                "wishlists.$.updated_at": now,
                "wishlists.$.last_sync_seq": await next_sync_seq(redis),
                "updated_at": now,
            },
            "$inc": {"wishlists.$.version": 1},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to revoke access")
    response = {"ok": True}
    await store_response(redis, str(user["_id"]), request.url.path, idempotency_key, status.HTTP_200_OK, response)
    return response
