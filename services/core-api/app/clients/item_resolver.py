"""HTTP client for Item Resolver service."""

import logging
import uuid

import httpx
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                logger.debug(f"[{request_id}] Sending POST to {self.base_url}/resolver/v1/resolve")
                response = await client.post(
                    f"{self.base_url}/resolver/v1/resolve",
                    json={"url": url},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                logger.debug(f"[{request_id}] Received response: {response.status_code}")
                response.raise_for_status()
                data = response.json()
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
                logger.error(f"[{request_id}] Read timeout after {self.read_timeout}s")
                raise ItemResolverError(
                    f"Resolution read timeout after {self.read_timeout}s"
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
