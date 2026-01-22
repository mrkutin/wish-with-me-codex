"""HTTP client for Item Resolver service."""

import httpx
from typing import Any

from app.config import settings


class ItemResolverError(Exception):
    """Exception raised when item resolver service fails."""

    pass


class ItemResolverClient:
    """Client for communicating with the Item Resolver service."""

    def __init__(self):
        self.base_url = settings.item_resolver_url
        self.token = settings.item_resolver_token
        self.timeout = settings.item_resolver_timeout

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
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/resolver/v1/resolve",
                    json={"url": url},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "title": data.get("title", ""),
                    "description": data.get("description"),
                    "price": data.get("price"),
                    "currency": data.get("currency"),
                    "image_base64": data.get("image_base64"),
                    "source_url": data.get("source_url", url),
                    "metadata": data,  # Store full response
                }

            except httpx.HTTPStatusError as e:
                error_detail = f"HTTP {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("detail", error_detail)
                except Exception:
                    pass
                raise ItemResolverError(f"Resolution failed: {error_detail}") from e

            except httpx.TimeoutException as e:
                raise ItemResolverError(
                    f"Resolution timeout after {self.timeout}s"
                ) from e

            except httpx.RequestError as e:
                raise ItemResolverError(f"Resolution request failed: {str(e)}") from e

            except Exception as e:
                raise ItemResolverError(f"Unexpected error during resolution: {str(e)}") from e
