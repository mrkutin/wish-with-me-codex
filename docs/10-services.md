# External Services

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Item Resolver Service

### 1.1 Overview

The Item Resolver is a microservice that extracts product information from marketplace URLs using Playwright for page rendering and LLM for data extraction.

**Location**: `/services/item-resolver/`

**Deployment**: Montreal server (158.69.203.3)
- 2 instances load balanced by nginx using `least_conn`
- Exposed on port 8001
- Each instance has 1 CPU and 2GB memory limit

**Stack**:
- Python 3.12
- FastAPI
- Playwright (Chromium)
- OpenAI-compatible LLM API

### 1.2 API Endpoints

#### Health Check

```
GET /healthz

Response: 200 OK
{
  "status": "ok"
}
```

#### Resolve URL

```
POST /resolver/v1/resolve
Authorization: Bearer {RU_BEARER_TOKEN}
Content-Type: application/json

Request:
{
  "url": "https://www.ozon.ru/product/123456"
}

Response:
{
  "title": "Product Name",
  "description": "Product description...",
  "price": 5990,
  "currency": "RUB",
  "image_base64": "data:image/jpeg;base64,...",
  "source_url": "https://www.ozon.ru/product/123456"
}
```

#### Get Page Source

```
POST /v1/page_source
Authorization: Bearer {RU_BEARER_TOKEN}
Content-Type: application/json

Request:
{
  "url": "https://example.com/page"
}

Response:
{
  "html": "<!DOCTYPE html>..."
}
```

#### Get Image as Base64

```
POST /v1/image_base64
Authorization: Bearer {RU_BEARER_TOKEN}
Content-Type: application/json

Request:
{
  "url": "https://example.com/image.jpg"
}

Response:
{
  "base64": "data:image/jpeg;base64,..."
}
```

### 1.3 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RU_BEARER_TOKEN` | Yes | Authentication token for API access |
| `LLM_MODE` | Yes | `live` for real LLM, `stub` for testing |
| `LLM_BASE_URL` | Yes* | OpenAI-compatible API URL |
| `LLM_API_KEY` | Yes* | API key for LLM service |
| `LLM_MODEL` | Yes* | Model name (e.g., `gpt-4o-mini`) |
| `PORT` | No | Server port (default: 8080) |

\* Required when `LLM_MODE=live`

### 1.4 Supported Marketplaces

| Marketplace | Domain | Status |
|-------------|--------|--------|
| Ozon | ozon.ru | Supported |
| Wildberries | wildberries.ru | Supported |
| Yandex Market | market.yandex.ru | Supported |
| AliExpress | aliexpress.ru | Supported |
| Amazon | amazon.com | Supported |
| Generic | * | Best effort |

### 1.5 Response Handling

| Scenario | Core API Action |
|----------|-----------------|
| Success | Update item with resolved data |
| Timeout | Mark item as `failed`, allow retry |
| Parse error | Mark item as `failed`, allow retry |
| Invalid URL | Mark item as `failed` immediately |
| Service unavailable | Queue for retry |

### 1.6 Integration with Core API

```python
# /services/core-api/app/services/item_resolver.py

import httpx
from app.config import settings

async def resolve_item_url(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.ITEM_RESOLVER_URL}/resolver/v1/resolve",
            headers={"Authorization": f"Bearer {settings.ITEM_RESOLVER_TOKEN}"},
            json={"url": url},
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()
```

### 1.7 Docker Configuration

```dockerfile
# /services/item-resolver/Dockerfile

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 2. Redis Cache

### 2.1 Purpose

- JWT token blocklist (for logout/revocation)
- Rate limiting counters
- Session storage
- SSE event pub/sub (enables real-time updates across multiple core-api instances)
- Temporary data cache

### 2.2 Key Patterns

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `blocklist:{token_jti}` | Revoked access tokens | 15 min |
| `rate:{ip}:{endpoint}` | Rate limit counters | 1 min |
| `session:{session_id}` | User sessions | 30 days |
| `resolve:{url_hash}` | Cached item resolutions | 24 hours |
| `sse:events:{user_id}` | SSE event pub/sub channel | N/A (pub/sub) |

### 2.3 Configuration

```python
# /services/core-api/app/redis_client.py

import redis.asyncio as redis
from app.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

async def add_to_blocklist(jti: str, ttl_seconds: int = 900):
    await redis_client.setex(f"blocklist:{jti}", ttl_seconds, "1")

async def is_blocklisted(jti: str) -> bool:
    return await redis_client.exists(f"blocklist:{jti}") > 0
```

---

## 3. PostgreSQL Database

### 3.1 Connection Configuration

```python
# /services/core-api/app/db.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 3.2 Migrations (Alembic)

```python
# /services/core-api/alembic/env.py

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.db import Base
from app.config import settings

# Import all models to register with Base
from app.models import *

target_metadata = Base.metadata

def run_migrations_online():
    connectable = create_async_engine(settings.DATABASE_URL)

    async def do_run_migrations(connection):
        await connection.run_sync(do_run_migrations_sync)

    def do_run_migrations_sync(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

    import asyncio
    asyncio.run(do_run_migrations(connectable))
```

**Commands**:
```bash
# Create migration
alembic revision --autogenerate -m "Add notifications table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 4. Service Dependencies

### 4.1 Production Architecture (Split Servers)

**Ubuntu Server (docker-compose.ubuntu.yml)**:
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    # Uses ip_hash for SSE sticky sessions

  core-api-1:
    build: ./services/core-api
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/wishwithme
      - REDIS_URL=redis://redis:6379/0
      - ITEM_RESOLVER_URL=http://158.69.203.3:8001  # Montreal server

  core-api-2:
    build: ./services/core-api
    # Same config as core-api-1

  frontend:
    build: ./services/frontend

  postgres:
    image: postgres:16-alpine

  redis:
    image: redis:7-alpine
```

**Montreal Server (docker-compose.montreal.yml)**:
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "8001:8001"
    # Uses least_conn for load balancing

  item-resolver-1:
    build: ./services/item-resolver
    environment:
      - RU_BEARER_TOKEN=${RU_BEARER_TOKEN}
      - LLM_MODE=live
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=gpt-4o-mini
    shm_size: '1gb'
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G

  item-resolver-2:
    build: ./services/item-resolver
    # Same config as item-resolver-1
```

### 4.2 Local Development (docker-compose.yml)

```yaml
# docker-compose.yml - for local development (all services on one machine)

version: '3.8'

services:
  core-api:
    build: ./services/core-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/wishwithme
      - REDIS_URL=redis://redis:6379/0
      - ITEM_RESOLVER_URL=http://item-resolver:8080
    depends_on:
      - postgres
      - redis
      - item-resolver

  item-resolver:
    build: ./services/item-resolver
    ports:
      - "8080:8080"
    environment:
      - RU_BEARER_TOKEN=${ITEM_RESOLVER_TOKEN}
      - LLM_MODE=live
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=gpt-4o-mini

  frontend:
    build: ./services/frontend
    ports:
      - "9000:80"
    depends_on:
      - core-api

  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=wishwithme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 5. Health Checks

### 5.1 Core API Health

```python
# /services/core-api/app/routers/health.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_db
from app.redis_client import redis_client

router = APIRouter(tags=["health"])

@router.get("/healthz")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {
        "database": False,
        "redis": False
    }

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    healthy = all(checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks
    }
```

### 5.2 Docker Health Checks

```yaml
# In docker-compose.yml

services:
  core-api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d wishwithme"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```
