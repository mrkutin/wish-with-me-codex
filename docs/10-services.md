# External Services

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Item Resolver Service

### 1.1 Overview

The Item Resolver is a microservice that extracts product information from marketplace URLs using Playwright for page rendering and DeepSeek LLM for text-based data extraction.

**Location**: `/services/item-resolver/`

**Deployment**: Ubuntu server (176.106.144.182)
- 2 instances (item-resolver-1, item-resolver-2)
- Accessed via internal Docker network
- Each instance has 1 CPU and 2GB memory limit

**Stack**:
- Python 3.12
- FastAPI
- Playwright (Chromium)
- DeepSeek API (text-based extraction, no vision)

### 1.2 Integration Method

**Item resolver watches CouchDB `_changes` feed** for new pending items:

```python
# Item resolver polls CouchDB _changes feed
async def watch_pending_items():
    while True:
        changes = await couchdb.get_changes(
            filter="_selector",
            selector={"type": "item", "status": "pending"}
        )
        for change in changes:
            await process_item(change["doc"])
```

This replaces the previous HTTP call pattern - now item resolver proactively watches for work.

### 1.3 API Endpoints

#### Health Check

```
GET /healthz

Response: 200 OK
{
  "status": "ok"
}
```

#### Resolve URL (still available for manual resolution)

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

### 1.4 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RU_BEARER_TOKEN` | Yes | Authentication token for API access |
| `LLM_MODE` | Yes | `live` for real LLM, `stub` for testing |
| `LLM_BASE_URL` | Yes* | DeepSeek API URL (https://api.deepseek.com) |
| `LLM_API_KEY` | Yes* | API key for DeepSeek |
| `LLM_MODEL` | Yes* | Model name (e.g., `deepseek-chat`) |
| `LLM_MAX_CHARS` | No | Max characters to send to LLM (default: 50000) |
| `COUCHDB_URL` | Yes | CouchDB connection URL |
| `PORT` | No | Server port (default: 8000) |

\* Required when `LLM_MODE=live`

### 1.5 Supported Marketplaces

| Marketplace | Domain | Status |
|-------------|--------|--------|
| Ozon | ozon.ru | Supported |
| Wildberries | wildberries.ru | Supported |
| Yandex Market | market.yandex.ru | Supported |
| AliExpress | aliexpress.ru | Supported |
| Amazon | amazon.com | Supported |
| Generic | * | Best effort |

### 1.6 CouchDB Change Feed Processing

```python
# /services/item-resolver/change_watcher.py

import asyncio
import aiohttp
from config import settings

async def watch_changes():
    """Watch CouchDB _changes feed for pending items."""
    last_seq = "now"

    while True:
        async with aiohttp.ClientSession() as session:
            url = f"{settings.COUCHDB_URL}/wishwithme/_changes"
            params = {
                "feed": "longpoll",
                "since": last_seq,
                "filter": "_selector",
                "include_docs": "true"
            }
            data = {
                "selector": {
                    "type": "item",
                    "status": "pending"
                }
            }

            async with session.post(url, json=data, params=params) as resp:
                changes = await resp.json()
                last_seq = changes["last_seq"]

                for change in changes["results"]:
                    if not change.get("deleted"):
                        await process_item(change["doc"])

async def process_item(item: dict):
    """Process a pending item."""
    item_id = item["_id"]

    # Mark as resolving
    item["status"] = "resolving"
    await update_document(item)

    try:
        # Resolve the URL
        result = await resolve_url(item["source_url"])

        # Update item with resolved data
        item.update({
            "status": "resolved",
            "title": result["title"],
            "description": result.get("description"),
            "price_amount": result.get("price"),
            "price_currency": result.get("currency"),
            "image_base64": result.get("image_base64")
        })
    except Exception as e:
        item["status"] = "failed"
        item["resolution_error"] = {"message": str(e)}

    await update_document(item)
```

### 1.7 Docker Configuration

```dockerfile
# /services/item-resolver/Dockerfile

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "main"]
```

---

## 2. CouchDB Database

### 2.1 Purpose

- Primary data store for all application data
- Native sync protocol for PouchDB clients
- `_changes` feed for item resolver
- JWT authentication support

### 2.2 Configuration

```ini
# /couchdb/local.ini

[chttpd]
port = 5984
bind_address = 0.0.0.0

[chttpd_auth]
authentication_handlers = {chttpd_auth, jwt_authentication_handler}, {chttpd_auth, cookie_authentication_handler}

[jwt_auth]
required_claims = exp, sub
algorithms = HS256

[jwt_keys]
hmac:_default = ${JWT_SECRET_KEY}

[cors]
origins = https://wishwith.me, http://localhost:9000
credentials = true
methods = GET, PUT, POST, DELETE, OPTIONS
headers = accept, authorization, content-type, origin, referer

[couchdb]
single_node = true
max_document_size = 8388608  # 8MB for base64 images
```

### 2.3 Connection in Python

```python
# /services/core-api/app/couchdb.py

import aiohttp
from app.config import settings

class CouchDBClient:
    def __init__(self, base_url: str, database: str):
        self.base_url = base_url
        self.database = database
        self.db_url = f"{base_url}/{database}"

    async def get(self, doc_id: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.db_url}/{doc_id}") as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()

    async def put(self, doc: dict) -> dict:
        async with aiohttp.ClientSession() as session:
            doc_id = doc["_id"]
            async with session.put(
                f"{self.db_url}/{doc_id}",
                json=doc
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def find(self, selector: dict) -> list:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.db_url}/_find",
                json={"selector": selector}
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result["docs"]

couchdb = CouchDBClient(
    settings.COUCHDB_URL,
    settings.COUCHDB_DATABASE
)

def get_couchdb() -> CouchDBClient:
    return couchdb
```

### 2.4 Database Setup Commands

```bash
# Create database
curl -X PUT http://admin:password@localhost:5984/wishwithme

# Create indexes
curl -X POST http://admin:password@localhost:5984/wishwithme/_index \
  -H "Content-Type: application/json" \
  -d '{"index": {"fields": ["type", "access"]}, "name": "type-access-idx"}'

curl -X POST http://admin:password@localhost:5984/wishwithme/_index \
  -H "Content-Type: application/json" \
  -d '{"index": {"fields": ["type", "status"]}, "name": "type-status-idx"}'
```

---

## 3. Service Dependencies

### 3.1 Production Architecture

**Ubuntu Server (docker-compose.ubuntu.yml)**:
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"

  core-api-1:
    build: ./services/core-api
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - COUCHDB_DATABASE=wishwithme
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}

  core-api-2:
    build: ./services/core-api
    # Same config as core-api-1

  item-resolver-1:
    build: ./services/item-resolver
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - RU_BEARER_TOKEN=${RU_BEARER_TOKEN}
      - LLM_MODE=live
      - LLM_BASE_URL=https://api.deepseek.com
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=deepseek-chat
    shm_size: '1gb'
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G

  item-resolver-2:
    build: ./services/item-resolver
    # Same config as item-resolver-1

  frontend:
    build: ./services/frontend

  couchdb:
    image: couchdb:3.3
    environment:
      - COUCHDB_USER=admin
      - COUCHDB_PASSWORD=${COUCHDB_PASSWORD}
    volumes:
      - couchdb_data:/opt/couchdb/data
      - ./couchdb/local.ini:/opt/couchdb/etc/local.d/local.ini

volumes:
  couchdb_data:
```

### 3.2 Local Development (docker-compose.yml)

```yaml
# docker-compose.yml - for local development

version: '3.8'

services:
  core-api:
    build: ./services/core-api
    ports:
      - "8000:8000"
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - COUCHDB_DATABASE=wishwithme
      - JWT_SECRET_KEY=dev-secret-key-min-32-characters
    depends_on:
      - couchdb
      - item-resolver

  item-resolver:
    build: ./services/item-resolver
    ports:
      - "8080:8000"
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - RU_BEARER_TOKEN=dev-token
      - LLM_MODE=stub  # Use stub mode for local dev

  frontend:
    build: ./services/frontend
    ports:
      - "9000:80"
    environment:
      - API_URL=http://localhost:8000
      - COUCHDB_URL=http://localhost:5984
    depends_on:
      - core-api

  couchdb:
    image: couchdb:3.3
    environment:
      - COUCHDB_USER=admin
      - COUCHDB_PASSWORD=password
    volumes:
      - couchdb_data:/opt/couchdb/data
    ports:
      - "5984:5984"

volumes:
  couchdb_data:
```

---

## 4. Health Checks

### 4.1 Core API Health

```python
# /services/core-api/app/routers/health.py

from fastapi import APIRouter
from app.couchdb import couchdb

router = APIRouter(tags=["health"])

@router.get("/healthz")
async def health_check():
    checks = {
        "couchdb": False
    }

    try:
        # Check CouchDB connection
        await couchdb.get("_design/app")
        checks["couchdb"] = True
    except Exception:
        pass

    healthy = all(checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks
    }

@router.get("/live")
async def liveness():
    """Kubernetes liveness probe."""
    return {"status": "ok"}
```

### 4.2 Docker Health Checks

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

  couchdb:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5984/"]
      interval: 10s
      timeout: 5s
      retries: 5

  item-resolver:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 5. Data Flow

### 5.1 Item Resolution Flow

```
User pastes URL in frontend
         |
         v
PouchDB saves item (status: pending)
         |
         v
PouchDB syncs to CouchDB
         |
         v
Item resolver sees change in _changes feed
         |
         v
Item resolver: Playwright fetches page
         |
         v
Item resolver: DeepSeek extracts data (text-based)
         |
         v
Item resolver updates item in CouchDB (status: resolved)
         |
         v
CouchDB syncs to PouchDB
         |
         v
Frontend UI updates automatically
```

### 5.2 Real-Time Updates

All real-time updates are handled by PouchDB live sync:
- No SSE endpoints
- No WebSocket connections
- No Redis pub/sub

PouchDB maintains a persistent connection to CouchDB and automatically syncs changes in both directions.
