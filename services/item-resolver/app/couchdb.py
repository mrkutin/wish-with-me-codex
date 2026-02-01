"""CouchDB client for item-resolver operations."""

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

import aiohttp
from aiohttp import BasicAuth

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
    """Async CouchDB client for item-resolver."""

    def __init__(
        self,
        url: str | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.url = (url or os.environ.get("COUCHDB_URL", "http://localhost:5984")).rstrip("/")
        self.database = database or os.environ.get("COUCHDB_DATABASE", "wishwithme")
        self.username = username or os.environ.get("COUCHDB_ADMIN_USER", "admin")
        self.password = password or os.environ.get("COUCHDB_ADMIN_PASSWORD", "")
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

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
        async with self._session_lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=30)
                self._session = aiohttp.ClientSession(auth=self.auth, timeout=timeout)
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

    async def get(self, doc_id: str) -> dict:
        """Get a document by ID."""
        return await self._request("GET", f"{self.db_url}/{doc_id}")

    async def put(self, doc: dict) -> dict:
        """Create or update a document."""
        doc_id = doc.get("_id")
        if not doc_id:
            raise ValueError("Document must have an _id field")
        return await self._request("PUT", f"{self.db_url}/{doc_id}", json=doc)

    async def find(
        self,
        selector: dict,
        fields: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Find documents using Mango query."""
        query: dict[str, Any] = {"selector": selector}
        if fields:
            query["fields"] = fields
        if limit:
            query["limit"] = limit

        result = await self._request("POST", f"{self.db_url}/_find", json=query)
        return result.get("docs", [])

    async def create_index(self, index: dict, name: str, ddoc: str | None = None) -> dict:
        """Create a Mango index.

        Args:
            index: Index definition with 'fields' key
            name: Name of the index
            ddoc: Design document name (optional)
        """
        body: dict[str, Any] = {
            "index": index,
            "name": name,
            "type": "json",
        }
        if ddoc:
            body["ddoc"] = ddoc

        try:
            return await self._request("POST", f"{self.db_url}/_index", json=body)
        except CouchDBError as e:
            # Index may already exist, that's OK
            if "exists" in str(e.message).lower():
                logger.debug(f"Index {name} already exists")
                return {"result": "exists"}
            raise

    async def ensure_indexes(self) -> None:
        """Ensure all required indexes exist for item-resolver operations."""
        indexes = [
            # Index for finding stale leases (items stuck in_progress)
            {
                "name": "item-stale-lease-index",
                "index": {"fields": ["type", "status", "lease_expires_at"]},
            },
            # Index for finding pending items
            {
                "name": "item-pending-index",
                "index": {"fields": ["type", "status"]},
            },
        ]

        for idx in indexes:
            try:
                result = await self.create_index(idx["index"], idx["name"])
                if result.get("result") == "created":
                    logger.info(f"Created index: {idx['name']}")
                else:
                    logger.debug(f"Index {idx['name']} already exists or unchanged")
            except CouchDBError as e:
                logger.warning(f"Failed to create index {idx['name']}: {e}")

    async def changes(
        self,
        since: str = "now",
        feed: str = "continuous",
        filter_selector: dict | None = None,
        include_docs: bool = True,
        heartbeat: int = 30000,
        timeout: int | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream changes from CouchDB _changes feed.

        Args:
            since: Sequence ID to start from ("now" for current, "0" for beginning)
            feed: Feed type ("continuous" for streaming, "longpoll" for single batch)
            filter_selector: Mango selector for filtering changes
            include_docs: Include full document in changes
            heartbeat: Heartbeat interval in milliseconds
            timeout: Request timeout (None for infinite)

        Yields:
            Change objects with seq, id, changes, and optionally doc fields
        """
        session = await self._get_session()

        params: dict[str, Any] = {
            "since": since,
            "feed": feed,
            "include_docs": "true" if include_docs else "false",
            "heartbeat": str(heartbeat),
        }

        # Use _selector filter for Mango queries
        body = None
        if filter_selector:
            params["filter"] = "_selector"
            body = {"selector": filter_selector}

        url = f"{self.db_url}/_changes"

        try:
            async with session.post(
                url,
                params=params,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status >= 400:
                    data = await response.json()
                    error = data.get("error", "unknown")
                    reason = data.get("reason", "Unknown error")
                    raise CouchDBError(reason, response.status, error)

                # Stream continuous feed line by line
                async for line in response.content:
                    line = line.strip()
                    if not line:
                        # Empty line = heartbeat
                        continue

                    try:
                        change = json.loads(line.decode("utf-8"))

                        # Skip the final "last_seq" response
                        if "last_seq" in change and "id" not in change:
                            continue

                        yield change
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning(f"Failed to parse change: {e}")
                        continue

        except aiohttp.ClientError as e:
            logger.error(f"CouchDB changes feed error: {e}")
            raise CouchDBError(str(e), 503, "connection_error")


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
