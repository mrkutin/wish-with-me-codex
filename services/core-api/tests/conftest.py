"""Pytest fixtures for testing."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

# Set environment variables for tests BEFORE importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-must-be-at-least-32-characters-long"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "30"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Clear the settings cache to pick up test env vars
from app.config import get_settings
get_settings.cache_clear()

from app.config import settings
from app.couchdb import DocumentNotFoundError
from app.security import hash_password, hash_token, get_refresh_token_expiry


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class MockCouchDBClient:
    """Mock CouchDB client for testing."""

    def __init__(self):
        self._documents: dict[str, dict] = {}
        self._email_index: dict[str, str] = {}  # email -> doc_id

    def reset(self):
        """Reset all stored documents."""
        self._documents.clear()
        self._email_index.clear()

    async def get(self, doc_id: str) -> dict:
        """Get a document by ID."""
        if doc_id not in self._documents:
            raise DocumentNotFoundError(doc_id)
        return self._documents[doc_id].copy()

    async def put(self, doc: dict) -> dict:
        """Create or update a document."""
        doc_id = doc.get("_id")
        if not doc_id:
            raise ValueError("Document must have an _id field")

        # Update revision
        current_rev = doc.get("_rev")
        if current_rev:
            new_rev_num = int(current_rev.split("-")[0]) + 1
        else:
            new_rev_num = 1
        new_rev = f"{new_rev_num}-{uuid4().hex[:32]}"

        doc["_rev"] = new_rev
        self._documents[doc_id] = doc.copy()

        # Update email index for users
        if doc.get("type") == "user" and "email" in doc:
            self._email_index[doc["email"].lower()] = doc_id

        return {"ok": True, "id": doc_id, "rev": new_rev}

    async def delete(self, doc_id: str, rev: str) -> dict:
        """Delete a document."""
        if doc_id not in self._documents:
            raise DocumentNotFoundError(doc_id)
        del self._documents[doc_id]
        return {"ok": True, "id": doc_id, "rev": rev}

    async def find(
        self,
        selector: dict,
        fields: list[str] | None = None,
        sort: list[dict] | None = None,
        limit: int | None = None,
        skip: int | None = None,
    ) -> list[dict]:
        """Find documents using Mango query."""
        results = []
        for doc in self._documents.values():
            if self._matches_selector(doc, selector):
                results.append(doc.copy())

        if limit:
            results = results[:limit]

        return results

    async def find_one(
        self,
        selector: dict,
        fields: list[str] | None = None,
    ) -> dict | None:
        """Find a single document."""
        docs = await self.find(selector, fields=fields, limit=1)
        return docs[0] if docs else None

    async def view(
        self,
        design_doc: str,
        view_name: str,
        key: Any | None = None,
        keys: list | None = None,
        startkey: Any | None = None,
        endkey: Any | None = None,
        include_docs: bool = False,
        reduce: bool = False,
        group: bool = False,
        limit: int | None = None,
    ) -> dict:
        """Query a view."""
        # Simulate users_by_email view
        if design_doc == "app" and view_name == "users_by_email":
            if key and key.lower() in self._email_index:
                doc_id = self._email_index[key.lower()]
                doc = self._documents.get(doc_id)
                if doc and include_docs:
                    return {"rows": [{"id": doc_id, "key": key.lower(), "doc": doc.copy()}]}
            return {"rows": []}

        return {"rows": []}

    async def bulk_docs(self, docs: list[dict]) -> list[dict]:
        """Bulk create/update documents."""
        results = []
        for doc in docs:
            result = await self.put(doc)
            results.append(result)
        return results

    async def close(self) -> None:
        """Close the client session."""
        pass

    @staticmethod
    def generate_id(doc_type: str) -> str:
        """Generate a document ID with type prefix."""
        return f"{doc_type}:{uuid4()}"

    async def create_user(
        self,
        email: str,
        password_hash: str,
        name: str,
        **kwargs,
    ) -> dict:
        """Create a new user document."""
        user_id = self.generate_id("user")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "_id": user_id,
            "type": "user",
            "email": email.lower(),
            "password_hash": password_hash,
            "name": name,
            "avatar_base64": kwargs.get("avatar_base64"),
            "bio": kwargs.get("bio"),
            "public_url_slug": kwargs.get("public_url_slug"),
            "locale": kwargs.get("locale", "en"),
            "created_at": now,
            "updated_at": now,
            "access": [user_id],
            **{k: v for k, v in kwargs.items() if k not in ["avatar_base64", "bio", "public_url_slug", "locale"]},
        }

        await self.put(doc)
        return doc

    async def get_user_by_email(self, email: str) -> dict | None:
        """Find a user by email."""
        result = await self.view(
            "app",
            "users_by_email",
            key=email.lower(),
            include_docs=True,
            limit=1,
        )
        rows = result.get("rows", [])
        return rows[0]["doc"] if rows else None

    def _matches_selector(self, doc: dict, selector: dict) -> bool:
        """Check if a document matches a Mango selector."""
        for key, value in selector.items():
            if key == "$and":
                if not all(self._matches_selector(doc, sub) for sub in value):
                    return False
            elif key == "$or":
                if not any(self._matches_selector(doc, sub) for sub in value):
                    return False
            elif key == "$elemMatch":
                # Used within array field
                return False  # Will be handled by parent
            elif isinstance(value, dict):
                if "$elemMatch" in value:
                    # Array contains element matching criteria
                    doc_value = doc.get(key, [])
                    if not isinstance(doc_value, list):
                        return False
                    match_criteria = value["$elemMatch"]
                    found = False
                    for item in doc_value:
                        if isinstance(item, dict):
                            if all(item.get(k) == v for k, v in match_criteria.items()):
                                found = True
                                break
                    if not found:
                        return False
                elif "$eq" in value:
                    if doc.get(key) != value["$eq"]:
                        return False
                elif "$ne" in value:
                    if doc.get(key) == value["$ne"]:
                        return False
                elif "$gt" in value:
                    if not (doc.get(key) and doc.get(key) > value["$gt"]):
                        return False
                elif "$gte" in value:
                    if not (doc.get(key) and doc.get(key) >= value["$gte"]):
                        return False
                elif "$lt" in value:
                    if not (doc.get(key) and doc.get(key) < value["$lt"]):
                        return False
                elif "$lte" in value:
                    if not (doc.get(key) and doc.get(key) <= value["$lte"]):
                        return False
                else:
                    # Nested object comparison
                    if not self._matches_selector(doc.get(key, {}), value):
                        return False
            else:
                if doc.get(key) != value:
                    return False
        return True


@pytest.fixture
def mock_couchdb() -> MockCouchDBClient:
    """Create a fresh mock CouchDB client for each test."""
    return MockCouchDBClient()


@pytest_asyncio.fixture
async def client(mock_couchdb: MockCouchDBClient) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with mocked CouchDB."""
    # Import here to avoid circular imports
    from app.main import app
    from app import couchdb

    # Patch the global CouchDB client
    original_get_couchdb = couchdb.get_couchdb

    def mock_get_couchdb():
        return mock_couchdb

    couchdb.get_couchdb = mock_get_couchdb
    couchdb._client = mock_couchdb

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Restore original
    couchdb.get_couchdb = original_get_couchdb
    couchdb._client = None


@pytest.fixture
def user_data() -> dict[str, Any]:
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "securePassword123",
        "name": "Test User",
        "locale": "en",
    }


@pytest.fixture
def another_user_data() -> dict[str, Any]:
    """Another sample user registration data."""
    return {
        "email": "another@example.com",
        "password": "anotherPassword456",
        "name": "Another User",
        "locale": "ru",
    }


@pytest_asyncio.fixture
async def registered_user(
    mock_couchdb: MockCouchDBClient,
    user_data: dict[str, Any],
) -> dict[str, Any]:
    """Create a registered user in the mock database."""
    user = await mock_couchdb.create_user(
        email=user_data["email"],
        password_hash=hash_password(user_data["password"]),
        name=user_data["name"],
        locale=user_data["locale"],
    )
    return {**user_data, "user_id": user["_id"], "user_doc": user}


@pytest_asyncio.fixture
async def user_with_refresh_token(
    mock_couchdb: MockCouchDBClient,
    registered_user: dict[str, Any],
) -> dict[str, Any]:
    """Create a user with an active refresh token."""
    import secrets

    user_doc = registered_user["user_doc"]
    refresh_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    user_doc["refresh_tokens"] = [{
        "token_hash": hash_token(refresh_token),
        "device_info": "Test Device",
        "expires_at": get_refresh_token_expiry().isoformat(),
        "revoked": False,
        "created_at": now.isoformat(),
    }]

    await mock_couchdb.put(user_doc)

    return {
        **registered_user,
        "refresh_token": refresh_token,
        "user_doc": user_doc,
    }


@pytest_asyncio.fixture
async def user_with_expired_refresh_token(
    mock_couchdb: MockCouchDBClient,
    registered_user: dict[str, Any],
) -> dict[str, Any]:
    """Create a user with an expired refresh token."""
    import secrets

    user_doc = registered_user["user_doc"]
    refresh_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expired = now - timedelta(days=1)

    user_doc["refresh_tokens"] = [{
        "token_hash": hash_token(refresh_token),
        "device_info": "Test Device",
        "expires_at": expired.isoformat(),
        "revoked": False,
        "created_at": (expired - timedelta(days=30)).isoformat(),
    }]

    await mock_couchdb.put(user_doc)

    return {
        **registered_user,
        "refresh_token": refresh_token,
        "user_doc": user_doc,
    }


@pytest_asyncio.fixture
async def user_with_revoked_refresh_token(
    mock_couchdb: MockCouchDBClient,
    registered_user: dict[str, Any],
) -> dict[str, Any]:
    """Create a user with a revoked refresh token."""
    import secrets

    user_doc = registered_user["user_doc"]
    refresh_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    user_doc["refresh_tokens"] = [{
        "token_hash": hash_token(refresh_token),
        "device_info": "Test Device",
        "expires_at": get_refresh_token_expiry().isoformat(),
        "revoked": True,
        "created_at": now.isoformat(),
    }]

    await mock_couchdb.put(user_doc)

    return {
        **registered_user,
        "refresh_token": refresh_token,
        "user_doc": user_doc,
    }


@pytest.fixture
def access_token(registered_user: dict[str, Any]) -> str:
    """Generate a valid access token for the registered user."""
    from app.security import create_access_token
    return create_access_token(registered_user["user_id"])


@pytest.fixture
def expired_access_token(registered_user: dict[str, Any]) -> str:
    """Generate an expired access token for the registered user."""
    from app.security import create_access_token
    return create_access_token(
        registered_user["user_id"],
        expires_delta=timedelta(seconds=-1),  # Already expired
    )
