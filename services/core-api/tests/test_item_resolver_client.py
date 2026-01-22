"""Unit tests for Item Resolver Client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.clients.item_resolver import ItemResolverClient, ItemResolverError


@pytest.fixture
def resolver_client():
    """Create ItemResolverClient instance."""
    return ItemResolverClient()


@pytest.fixture
def mock_resolver_response():
    """Sample successful resolver response."""
    return {
        "title": "Amazing Product",
        "description": "This is a great product",
        "price": 99.99,
        "currency": "USD",
        "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg",
        "source_url": "https://example.com/product",
        "availability": "in_stock",
    }


@pytest.mark.asyncio
async def test_resolve_item_success(resolver_client, mock_resolver_response):
    """Test successful item resolution."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_resolver_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await resolver_client.resolve_item("https://example.com/product")

        assert result["title"] == "Amazing Product"
        assert result["description"] == "This is a great product"
        assert result["price"] == 99.99
        assert result["currency"] == "USD"
        assert result["image_base64"] == "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg"
        assert result["source_url"] == "https://example.com/product"
        assert result["metadata"] == mock_resolver_response

        # Verify correct endpoint was called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0].endswith("/resolver/v1/resolve")
        assert call_args[1]["json"] == {"url": "https://example.com/product"}
        assert "Authorization" in call_args[1]["headers"]


@pytest.mark.asyncio
async def test_resolve_item_minimal_response(resolver_client):
    """Test resolution with minimal response data."""
    minimal_response = {
        "title": "Minimal Product",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = minimal_response
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await resolver_client.resolve_item("https://example.com/product")

        assert result["title"] == "Minimal Product"
        assert result["description"] is None
        assert result["price"] is None
        assert result["currency"] is None
        assert result["image_base64"] is None


@pytest.mark.asyncio
async def test_resolve_item_http_error(resolver_client):
    """Test handling of HTTP errors."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=mock_response
    )

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(ItemResolverError):
            await resolver_client.resolve_item("https://example.com/product")


@pytest.mark.asyncio
async def test_resolve_item_timeout(resolver_client):
    """Test handling of timeout errors."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out", request=MagicMock())
        mock_client_class.return_value = mock_client

        with pytest.raises(ItemResolverError):
            await resolver_client.resolve_item("https://example.com/product")


@pytest.mark.asyncio
async def test_resolve_item_network_error(resolver_client):
    """Test handling of network errors."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value = mock_client

        with pytest.raises(ItemResolverError):
            await resolver_client.resolve_item("https://example.com/product")


@pytest.mark.asyncio
async def test_resolve_item_authentication_header(resolver_client):
    """Test that authentication header is correctly set."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"title": "Test"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        await resolver_client.resolve_item("https://example.com/product")

        # Verify Bearer token is sent
        call_args = mock_client.post.call_args
        headers = call_args[1]["headers"]
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_resolve_item_url_fallback(resolver_client):
    """Test that source_url falls back to input URL if not in response."""
    response_without_url = {
        "title": "Product Without URL",
        "price": 29.99,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_without_url
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        input_url = "https://example.com/product"
        result = await resolver_client.resolve_item(input_url)

        # Should use input URL as fallback
        assert result["source_url"] == input_url


@pytest.mark.asyncio
async def test_resolve_item_timeout_configuration(resolver_client):
    """Test that timeout is properly configured."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"title": "Test"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        await resolver_client.resolve_item("https://example.com/product")

        # Verify timeout was set in AsyncClient initialization
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert "timeout" in call_kwargs
        # Timeout should be 60 seconds (from config)
        assert call_kwargs["timeout"] == 60


@pytest.mark.asyncio
async def test_resolve_item_invalid_json_response(resolver_client):
    """Test handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(ItemResolverError):
            await resolver_client.resolve_item("https://example.com/product")
