"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    """Test root endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient):
    """Test readiness endpoint."""
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient):
    """Test liveness endpoint."""
    response = await client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
