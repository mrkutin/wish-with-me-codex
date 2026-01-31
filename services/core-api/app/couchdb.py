"""CouchDB client for async operations."""

import logging
from typing import Any
from uuid import uuid4

import aiohttp
from aiohttp import BasicAuth

from app.config import settings

logger = logging.getLogger(__name__)


class CouchDBError(Exception):
    """Base CouchDB error."""

    def __init__(self, message: str, status_code: int = 500, error: str = "unknown"):
        self.message = message
        self.status_code = status_code
        self.error = error
        super().__init__(message)


class DocumentNotFoundError(CouchDBError):
    """Document not found error."""

    def __init__(self, doc_id: str):
        super().__init__(
            message=f"Document not found: {doc_id}",
            status_code=404,
            error="not_found",
        )


class ConflictError(CouchDBError):
    """Document conflict error."""

    def __init__(self, doc_id: str):
        super().__init__(
            message=f"Document conflict: {doc_id}",
            status_code=409,
            error="conflict",
        )


class CouchDBClient:
    """Async CouchDB client."""

    def __init__(
        self,
        url: str | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.url = (url or settings.couchdb_url).rstrip("/")
        self.database = database or settings.couchdb_database
        self.username = username or settings.couchdb_admin_user
        self.password = password or settings.couchdb_admin_password
        self._session: aiohttp.ClientSession | None = None

    @property
    def db_url(self) -> str:
        """Get the database URL."""
        return f"{self.url}/{self.database}"

    @property
    def auth(self) -> BasicAuth | None:
        """Get basic auth if credentials are provided."""
        if self.username and self.password:
            return BasicAuth(self.username, self.password)
        return None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(auth=self.auth)
        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an HTTP request to CouchDB."""
        session = await self._get_session()
        try:
            async with session.request(
                method,
                url,
                json=json,
                params=params,
                headers={"Content-Type": "application/json"},
            ) as response:
                data = await response.json()
                if response.status >= 400:
                    error = data.get("error", "unknown")
                    reason = data.get("reason", "Unknown error")
                    if response.status == 404:
                        raise DocumentNotFoundError(url)
                    if response.status == 409:
                        raise ConflictError(url)
                    raise CouchDBError(reason, response.status, error)
                return data
        except aiohttp.ClientError as e:
            logger.error(f"CouchDB request error: {e}")
            raise CouchDBError(str(e), 503, "connection_error")

    # Database operations

    async def db_info(self) -> dict:
        """Get database information."""
        return await self._request("GET", self.db_url)

    # Document operations

    async def get(self, doc_id: str) -> dict:
        """Get a document by ID."""
        return await self._request("GET", f"{self.db_url}/{doc_id}")

    async def put(self, doc: dict) -> dict:
        """Create or update a document."""
        doc_id = doc.get("_id")
        if not doc_id:
            raise ValueError("Document must have an _id field")
        return await self._request("PUT", f"{self.db_url}/{doc_id}", json=doc)

    async def delete(self, doc_id: str, rev: str) -> dict:
        """Delete a document."""
        return await self._request(
            "DELETE",
            f"{self.db_url}/{doc_id}",
            params={"rev": rev},
        )

    async def bulk_docs(self, docs: list[dict]) -> list[dict]:
        """Bulk create/update documents."""
        return await self._request(
            "POST",
            f"{self.db_url}/_bulk_docs",
            json={"docs": docs},
        )

    async def find(
        self,
        selector: dict,
        fields: list[str] | None = None,
        sort: list[dict] | None = None,
        limit: int | None = None,
        skip: int | None = None,
    ) -> list[dict]:
        """Find documents using Mango query."""
        query: dict[str, Any] = {"selector": selector}
        if fields:
            query["fields"] = fields
        if sort:
            query["sort"] = sort
        if limit:
            query["limit"] = limit
        if skip:
            query["skip"] = skip

        result = await self._request("POST", f"{self.db_url}/_find", json=query)
        return result.get("docs", [])

    async def find_one(
        self,
        selector: dict,
        fields: list[str] | None = None,
    ) -> dict | None:
        """Find a single document."""
        docs = await self.find(selector, fields=fields, limit=1)
        return docs[0] if docs else None

    # View operations

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
        params: dict[str, Any] = {}
        if key is not None:
            params["key"] = f'"{key}"' if isinstance(key, str) else key
        if startkey is not None:
            params["startkey"] = f'"{startkey}"' if isinstance(startkey, str) else startkey
        if endkey is not None:
            params["endkey"] = f'"{endkey}"' if isinstance(endkey, str) else endkey
        if include_docs:
            params["include_docs"] = "true"
        if reduce:
            params["reduce"] = "true"
        if group:
            params["group"] = "true"
        if limit:
            params["limit"] = limit

        url = f"{self.db_url}/_design/{design_doc}/_view/{view_name}"

        if keys:
            return await self._request("POST", url, json={"keys": keys}, params=params)
        return await self._request("GET", url, params=params)

    # Helper methods for document types

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
        from datetime import datetime, timezone

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
            "access": [user_id],  # User can access their own document
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

    async def create_wishlist(
        self,
        owner_id: str,
        name: str,
        **kwargs,
    ) -> dict:
        """Create a new wishlist document."""
        from datetime import datetime, timezone

        wishlist_id = self.generate_id("wishlist")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "_id": wishlist_id,
            "type": "wishlist",
            "owner_id": owner_id,
            "name": name,
            "description": kwargs.get("description"),
            "icon": kwargs.get("icon", "🎁"),
            "is_public": kwargs.get("is_public", False),
            "created_at": now,
            "updated_at": now,
            "access": [owner_id],  # Owner has access
        }

        await self.put(doc)
        return doc

    async def create_item(
        self,
        wishlist_id: str,
        owner_id: str,
        access: list[str],
        **kwargs,
    ) -> dict:
        """Create a new item document."""
        from datetime import datetime, timezone

        item_id = self.generate_id("item")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "_id": item_id,
            "type": "item",
            "wishlist_id": wishlist_id,
            "owner_id": owner_id,
            "title": kwargs.get("title", ""),
            "description": kwargs.get("description"),
            "price": kwargs.get("price"),
            "currency": kwargs.get("currency"),
            "quantity": kwargs.get("quantity", 1),
            "source_url": kwargs.get("source_url"),
            "image_url": kwargs.get("image_url"),
            "image_base64": kwargs.get("image_base64"),
            "status": "pending" if kwargs.get("source_url") else "resolved",
            "created_at": now,
            "updated_at": now,
            "access": access,  # Inherit from wishlist
        }

        await self.put(doc)
        return doc

    async def create_mark(
        self,
        item_id: str,
        wishlist_id: str,
        owner_id: str,
        marked_by: str,
        quantity: int,
        viewer_access: list[str],
    ) -> dict:
        """Create a new mark document (viewer's intent to purchase)."""
        from datetime import datetime, timezone

        mark_id = self.generate_id("mark")
        now = datetime.now(timezone.utc).isoformat()

        # Access includes all viewers EXCEPT owner (surprise mode)
        access = [uid for uid in viewer_access if uid != owner_id]

        doc = {
            "_id": mark_id,
            "type": "mark",
            "item_id": item_id,
            "wishlist_id": wishlist_id,
            "owner_id": owner_id,
            "marked_by": marked_by,
            "quantity": quantity,
            "created_at": now,
            "updated_at": now,
            "access": access,
        }

        await self.put(doc)
        return doc

    async def create_share(
        self,
        wishlist_id: str,
        owner_id: str,
        token: str,
        link_type: str = "mark",
        expires_at: str | None = None,
    ) -> dict:
        """Create a new share document."""
        from datetime import datetime, timezone

        share_id = self.generate_id("share")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "_id": share_id,
            "type": "share",
            "wishlist_id": wishlist_id,
            "owner_id": owner_id,
            "token": token,
            "link_type": link_type,
            "expires_at": expires_at,
            "access_count": 0,
            "revoked": False,
            "granted_users": [],
            "created_at": now,
            "access": [owner_id],  # Only owner sees share docs
        }

        await self.put(doc)
        return doc

    async def update_access_arrays(
        self,
        wishlist_id: str,
        user_id: str,
        action: str = "add",
    ) -> None:
        """Add or remove a user from access arrays on wishlist and items."""
        # Get wishlist
        wishlist = await self.get(wishlist_id)

        # Update wishlist access
        access = wishlist.get("access", [])
        if action == "add" and user_id not in access:
            access.append(user_id)
        elif action == "remove" and user_id in access:
            access.remove(user_id)

        wishlist["access"] = access
        await self.put(wishlist)

        # Update all items in this wishlist (including deleted ones for consistency)
        all_items = await self.find(
            {"type": "item", "wishlist_id": wishlist_id},
        )
        # Filter out deleted items - they shouldn't have access updated
        items = [i for i in all_items if not i.get("_deleted")]

        if items:
            for item in items:
                item_access = item.get("access", [])
                if action == "add" and user_id not in item_access:
                    item_access.append(user_id)
                elif action == "remove" and user_id in item_access:
                    item_access.remove(user_id)
                item["access"] = item_access

            await self.bulk_docs(items)


# Global client instance
_client: CouchDBClient | None = None


def get_couchdb() -> CouchDBClient:
    """Get the global CouchDB client instance."""
    global _client
    if _client is None:
        _client = CouchDBClient()
    return _client


async def close_couchdb() -> None:
    """Close the global CouchDB client."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
