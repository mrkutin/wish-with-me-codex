"""HTTP client for Item Resolver service."""

import asyncio
import json
import logging
import uuid

import httpx
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


async def _curl_request(url: str, token: str, payload: dict, timeout: int) -> bytes:
    """Fallback using curl subprocess for network edge cases."""
    cmd = [
        "curl", "-s",
        "-X", "POST",
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {token}",
        "-d", json.dumps(payload),
        "--max-time", str(timeout),
        url
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {stderr.decode('utf-8', errors='replace')}")

    return stdout


class ItemResolverError(Exception):
    """Exception raised when item resolver service fails."""

    pass


class ItemResolverClient:
    """Client for communicating with the Item Resolver service."""

    def __init__(self):
        self.base_url = settings.item_resolver_url
        self.token = settings.item_resolver_token
        self.read_timeout = settings.item_resolver_timeout
        # Use explicit timeout configuration to avoid pool timeout issues
        # When passing an integer, pool timeout defaults to only 5s which can
        # cause failures when multiple concurrent resolutions are running
        self.timeout = httpx.Timeout(
            connect=10.0,           # Time to establish connection
            read=float(self.read_timeout),  # Time per chunk read (main timeout)
            write=10.0,             # Time to send request
            pool=60.0,              # Time to acquire connection from pool
        )

    async def resolve_item(self, url: str) -> dict[str, Any]:
        """Resolve item metadata from a URL.

        Args:
            url: The product URL to resolve

        Returns:
            Dict containing resolved item data with keys:
            - title: str
            - description: str | None
            - price: float | None
            - currency: str | None
            - image_base64: str | None
            - source_url: str
            - metadata: dict (full resolver response)

        Raises:
            ItemResolverError: If resolution fails
        """
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[{request_id}] Starting resolution for URL: {url}")

        # Configure limits and force HTTP/1.1 for better compatibility
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0,
        )
        # Force HTTP/1.1 and disable connection pooling to avoid potential issues
        async with httpx.AsyncClient(
            timeout=self.timeout,
            limits=limits,
            http2=False,  # Force HTTP/1.1
        ) as client:
            try:
                logger.info(f"[{request_id}] Sending POST to {self.base_url}/resolver/v1/resolve")

                # Use streaming to diagnose where exactly the read stops
                async with client.stream(
                    "POST",
                    f"{self.base_url}/resolver/v1/resolve",
                    json={"url": url},
                    headers={"Authorization": f"Bearer {self.token}"},
                ) as response:
                    logger.info(f"[{request_id}] Received headers: {response.status_code}, content-length: {response.headers.get('content-length', 'chunked')}")
                    response.raise_for_status()

                    # Read response body in chunks to see progress
                    logger.info(f"[{request_id}] Starting to read response body...")
                    chunks = []
                    bytes_read = 0
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        chunks.append(chunk)
                        bytes_read += len(chunk)
                        if bytes_read % 32768 == 0 or len(chunks) == 1:  # Log every 32KB or first chunk
                            logger.info(f"[{request_id}] Read {bytes_read} bytes so far...")

                    body = b"".join(chunks)
                    logger.info(f"[{request_id}] Response body complete: {len(body)} bytes")

                # Parse JSON from the body we already read (can't call response.json() after streaming)
                data = json.loads(body.decode('utf-8'))
                logger.info(f"[{request_id}] Successfully parsed response ({len(str(data))} chars)")

                return {
                    "title": data.get("title", ""),
                    "description": data.get("description"),
                    "price": data.get("price_amount"),  # Resolver returns price_amount
                    "currency": data.get("price_currency"),  # Resolver returns price_currency
                    "image_base64": data.get("image_base64"),
                    "source_url": data.get("canonical_url", url),  # Use canonical_url if available
                    "metadata": data,  # Store full response
                }

            except httpx.HTTPStatusError as e:
                error_detail = f"HTTP {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("detail", error_detail)
                except Exception:
                    pass
                logger.error(f"[{request_id}] HTTP error: {error_detail}")
                raise ItemResolverError(f"Resolution failed: {error_detail}") from e

            except httpx.PoolTimeout as e:
                logger.error(f"[{request_id}] Pool timeout - connection pool exhausted")
                raise ItemResolverError(
                    f"Resolution pool timeout - too many concurrent requests"
                ) from e

            except httpx.ReadTimeout as e:
                logger.warning(f"[{request_id}] Read timeout after {self.read_timeout}s, trying curl fallback...")
                # Try curl fallback - it handles some network edge cases better
                try:
                    curl_body = await _curl_request(
                        f"{self.base_url}/resolver/v1/resolve",
                        self.token,
                        {"url": url},
                        int(self.read_timeout)
                    )
                    logger.info(f"[{request_id}] Curl fallback succeeded: {len(curl_body)} bytes")
                    data = json.loads(curl_body.decode('utf-8'))
                    return {
                        "title": data.get("title", ""),
                        "description": data.get("description"),
                        "price": data.get("price_amount"),
                        "currency": data.get("price_currency"),
                        "image_base64": data.get("image_base64"),
                        "source_url": data.get("canonical_url", url),
                        "metadata": data,
                    }
                except Exception as curl_error:
                    logger.error(f"[{request_id}] Curl fallback also failed: {curl_error}")
                    raise ItemResolverError(
                        f"Resolution read timeout after {self.read_timeout}s (curl fallback also failed)"
                    ) from e

            except httpx.ConnectTimeout as e:
                logger.error(f"[{request_id}] Connect timeout")
                raise ItemResolverError(
                    f"Resolution connect timeout - cannot reach item resolver"
                ) from e

            except httpx.TimeoutException as e:
                logger.error(f"[{request_id}] Timeout: {type(e).__name__}")
                raise ItemResolverError(
                    f"Resolution timeout ({type(e).__name__})"
                ) from e

            except httpx.RequestError as e:
                logger.error(f"[{request_id}] Request error: {str(e)}")
                raise ItemResolverError(f"Resolution request failed: {str(e)}") from e

            except Exception as e:
                logger.exception(f"[{request_id}] Unexpected error: {str(e)}")
                raise ItemResolverError(f"Unexpected error during resolution: {str(e)}") from e
