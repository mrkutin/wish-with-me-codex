import os

import pytest
import redis
from httpx import Client
from pymongo import MongoClient


@pytest.fixture(autouse=True)
def cleanup_state():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017/wish")
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

    mongo_client = MongoClient(mongo_uri)
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    mongo_client.get_default_database().users.delete_many({})
    redis_client.flushdb()
    yield
    mongo_client.get_default_database().users.delete_many({})
    redis_client.flushdb()


@pytest.fixture
def client():
    with Client(base_url="http://localhost:8000") as client:
        yield client


def _register(client: Client, email: str, full_name: str, password: str):
    resp = client.post(
        "/api/v1/auth/register",
        headers={"Idempotency-Key": "register-" + email},
        json={"email": email, "full_name": full_name, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()


def _login(client: Client, email: str, password: str):
    resp = client.post(
        "/api/v1/auth/login",
        headers={"Idempotency-Key": "login-" + email},
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_idempotency_replay_register(client: Client):
    payload = {"email": "idem@example.com", "full_name": "Idem", "password": "pass123"}
    headers = {"Idempotency-Key": "fixed-key"}

    first = client.post("/api/v1/auth/register", headers=headers, json=payload)
    second = client.post("/api/v1/auth/register", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_privacy_and_owner_fields_for_shared_users(client: Client):
    owner_tokens = _register(client, "owner@example.com", "Owner User", "pass123")
    owner_auth = _auth_header(owner_tokens["access_token"])

    create_resp = client.post(
        "/api/v1/wishlists",
        headers={**owner_auth, "Idempotency-Key": "wl-create"},
        json={"title": "List", "description": "Desc"},
    )
    assert create_resp.status_code == 200
    wishlist_id = create_resp.json()["wishlist_id"]

    share_resp = client.post(
        f"/api/v1/wishlists/{wishlist_id}/share",
        headers={**owner_auth, "Idempotency-Key": "share-create"},
    )
    assert share_resp.status_code == 200
    share_token = share_resp.json()["share_token"]

    shared_tokens = _register(client, "shared@example.com", "Shared User", "pass123")
    shared_auth = _auth_header(shared_tokens["access_token"])

    redeem = client.post(
        "/api/v1/shares/redeem",
        headers={**shared_auth, "Idempotency-Key": "share-redeem"},
        json={"share_token": share_token},
    )
    assert redeem.status_code == 200

    shared_view = client.get(f"/api/v1/wishlists/{wishlist_id}", headers=shared_auth)
    assert shared_view.status_code == 200
    body = shared_view.json()
    assert "owner_user_id" in body
    assert "owner_full_name" in body
    assert "access" not in body
    if isinstance(body.get("share"), dict):
        assert "share_token" not in body["share"]

    owner_view = client.get(f"/api/v1/wishlists/{wishlist_id}", headers=owner_auth)
    assert owner_view.status_code == 200
    owner_body = owner_view.json()
    assert "access" in owner_body
    assert owner_body.get("share", {}).get("share_token") == share_token


def test_unmark_rules_for_shared_users(client: Client):
    owner_tokens = _register(client, "owner2@example.com", "Owner Two", "pass123")
    owner_auth = _auth_header(owner_tokens["access_token"])

    create_resp = client.post(
        "/api/v1/wishlists",
        headers={**owner_auth, "Idempotency-Key": "wl-create-2"},
        json={"title": "List", "description": "Desc"},
    )
    wishlist_id = create_resp.json()["wishlist_id"]

    share_resp = client.post(
        f"/api/v1/wishlists/{wishlist_id}/share",
        headers={**owner_auth, "Idempotency-Key": "share-create-2"},
    )
    share_token = share_resp.json()["share_token"]

    shared_a = _register(client, "shareda@example.com", "Shared A", "pass123")
    shared_b = _register(client, "sharedb@example.com", "Shared B", "pass123")
    auth_a = _auth_header(shared_a["access_token"])
    auth_b = _auth_header(shared_b["access_token"])

    redeem_a = client.post(
        "/api/v1/shares/redeem",
        headers={**auth_a, "Idempotency-Key": "redeem-a"},
        json={"share_token": share_token},
    )
    redeem_b = client.post(
        "/api/v1/shares/redeem",
        headers={**auth_b, "Idempotency-Key": "redeem-b"},
        json={"share_token": share_token},
    )
    assert redeem_a.status_code == 200
    assert redeem_b.status_code == 200

    add_item = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        headers={**owner_auth, "Idempotency-Key": "item-add"},
        json={"source_url": "https://example.com/item", "quantity": 1},
    )
    item_id = add_item.json()["item_id"]

    mark = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}/mark-bought",
        headers={**auth_a, "Idempotency-Key": "mark-a"},
    )
    assert mark.status_code == 200

    unmark_by_b = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}/unmark-bought",
        headers={**auth_b, "Idempotency-Key": "unmark-b"},
    )
    assert unmark_by_b.status_code == 403

    unmark_by_owner = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items/{item_id}/unmark-bought",
        headers={**owner_auth, "Idempotency-Key": "unmark-owner"},
    )
    assert unmark_by_owner.status_code == 200


def test_sync_response_shape(client: Client):
    tokens = _register(client, "sync@example.com", "Sync User", "pass123")
    auth = _auth_header(tokens["access_token"])

    sync_resp = client.get("/api/v1/sync?cursor=0", headers=auth)
    assert sync_resp.status_code == 200
    body = sync_resp.json()
    assert "server_time" in body
    assert "next_cursor" in body
    assert "changes" in body
    assert "wishlists" in body["changes"]


def test_error_model_for_missing_idempotency_key(client: Client):
    tokens = _register(client, "err@example.com", "Err User", "pass123")
    auth = _auth_header(tokens["access_token"])

    resp = client.post(
        "/api/v1/wishlists",
        headers=auth,
        json={"title": "List", "description": "Desc"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body.get("code") == "BAD_REQUEST"
    assert body.get("message") == "Missing Idempotency-Key"
    assert "trace_id" in body


def test_owner_cannot_redeem_own_share(client: Client):
    owner_tokens = _register(client, "owner-redeem@example.com", "Owner Redeem", "pass123")
    owner_auth = _auth_header(owner_tokens["access_token"])

    create_resp = client.post(
        "/api/v1/wishlists",
        headers={**owner_auth, "Idempotency-Key": "wl-create-owner-redeem"},
        json={"title": "List", "description": "Desc"},
    )
    wishlist_id = create_resp.json()["wishlist_id"]

    share_resp = client.post(
        f"/api/v1/wishlists/{wishlist_id}/share",
        headers={**owner_auth, "Idempotency-Key": "share-create-owner-redeem"},
    )
    share_token = share_resp.json()["share_token"]

    redeem = client.post(
        "/api/v1/shares/redeem",
        headers={**owner_auth, "Idempotency-Key": "share-redeem-owner"},
        json={"share_token": share_token},
    )
    assert redeem.status_code == 400


def test_revoke_share_blocks_future_redeems(client: Client):
    owner_tokens = _register(client, "owner-revoke@example.com", "Owner Revoke", "pass123")
    owner_auth = _auth_header(owner_tokens["access_token"])

    create_resp = client.post(
        "/api/v1/wishlists",
        headers={**owner_auth, "Idempotency-Key": "wl-create-revoke"},
        json={"title": "List", "description": "Desc"},
    )
    wishlist_id = create_resp.json()["wishlist_id"]

    share_resp = client.post(
        f"/api/v1/wishlists/{wishlist_id}/share",
        headers={**owner_auth, "Idempotency-Key": "share-create-revoke"},
    )
    share_token = share_resp.json()["share_token"]

    revoke = client.post(
        f"/api/v1/wishlists/{wishlist_id}/share/revoke",
        headers={**owner_auth, "Idempotency-Key": "share-revoke"},
    )
    assert revoke.status_code == 200

    shared_tokens = _register(client, "shared-revoke@example.com", "Shared Revoke", "pass123")
    shared_auth = _auth_header(shared_tokens["access_token"])

    redeem = client.post(
        "/api/v1/shares/redeem",
        headers={**shared_auth, "Idempotency-Key": "share-redeem-revoked"},
        json={"share_token": share_token},
    )
    assert redeem.status_code == 404
