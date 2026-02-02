# CLAUDE.md - Wish With Me Development Guide

> Comprehensive project documentation for Claude Code to understand and develop this codebase effectively.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Services](#services)
5. [API Endpoints](#api-endpoints)
6. [Database Schema](#database-schema)
7. [Data Flow & Sync Mechanism](#data-flow--sync-mechanism)
8. [Security Implementation](#security-implementation)
9. [Frontend Components & Pages](#frontend-components--pages)
10. [PWA Configuration](#pwa-configuration)
11. [Infrastructure & Deployment](#infrastructure--deployment)
12. [Environment Variables](#environment-variables)
13. [Development Commands](#development-commands)
14. [Code Conventions](#code-conventions)
15. [Agent Usage Requirements](#agent-usage-requirements)

---

## Project Overview

**Wish With Me** is an offline-first wishlist Progressive Web Application (PWA) that allows users to:
- Create and manage wishlists with items
- Add items via URL (auto-extracts product metadata using LLM)
- Add items manually with optional image upload
- Share wishlists with others via links (view-only or mark permission)
- Mark items as "taken" (surprise mode - hidden from wishlist owner)
- Bookmark shared wishlists for quick access
- Work fully offline with automatic sync when online
- OAuth login via Google and Yandex

**Production URL**: https://wishwith.me
**API URL**: https://api.wishwith.me

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Frontend** | Vue 3 + Quasar Framework + TypeScript | Vue 3, Quasar 2 |
| **State Management** | Pinia (stores) + PouchDB (offline storage) | Pinia 2, PouchDB 8 |
| **Backend API** | FastAPI + Python + async/await | Python 3.12, FastAPI 0.109+ |
| **URL Resolver** | FastAPI + Playwright + DeepSeek LLM | Playwright 1.49 |
| **Database** | CouchDB (with PouchDB sync) | CouchDB 3.3 |
| **Reverse Proxy** | nginx (SSL termination, load balancing) | nginx:alpine |
| **Containerization** | Docker Compose | Docker Compose v2 |
| **CI/CD** | GitHub Actions (auto-deploy on push to main) | - |
| **Authentication** | JWT (HS256) + bcrypt + OAuth 2.0 | - |

---

## Architecture

```
                         Internet
                            │
            ┌───────────────┴───────────────┐
            │                               │
      wishwith.me                    api.wishwith.me
            │                               │
            └───────────────┬───────────────┘
                            │
                      ┌─────┴─────┐
                      │   nginx   │ :80/:443 (SSL termination)
                      └─────┬─────┘
                            │
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
    +-----------+    +-------------+    +-----------+
    | frontend  |    |  upstream   |    | upstream  |
    |  (nginx)  |    |  core-api   |    |item-resolv|
    |   :80     |    +------+------+    +-----+-----+
    +-----------+           |                 |
                     +------+------+    +-----+-----+
                     |             |    |           |
                     v             v    v           v
               +----------+ +----------+ +----------+ +----------+
               |core-api-1| |core-api-2| |resolver-1| |resolver-2|
               |  :8000   | |  :8000   | |  :8000   | |  :8000   |
               +-----+----+ +-----+----+ +-----+----+ +-----+----+
                     |            |            |            |
                     +------+-----+            +------+-----+
                            |                         |
                            v                         v
                      +-----------+            watches _changes
                      |  couchdb  |<-------------------+
                      |   :5984   |
                      +-----+-----+
                            |
                            v
                     [couchdb_data]
                     /home/mrkutin/wishwithme-data/couchdb
```

### Service Overview

| Service | Instances | Port | Load Balancing | Purpose |
|---------|-----------|------|----------------|---------|
| nginx | 1 | 80, 443 | - | Reverse proxy, SSL, routing |
| frontend | 1 | 80 (internal) | - | Vue/Quasar PWA static files |
| core-api | 2 | 8000 (internal) | Least connections | FastAPI backend |
| item-resolver | 2 | 8000 (internal) | Least connections | Playwright + LLM scraper |
| couchdb | 1 | 5984 (internal) | - | Document database |

### Data Flow (Offline-First)

1. User writes data → **PouchDB** (local IndexedDB)
2. UI updates immediately from PouchDB subscriptions
3. When online, PouchDB syncs to **CouchDB** via Core API `/api/v2/sync`
4. **item-resolver** watches CouchDB `_changes` feed for `status: "pending"` items
5. Pending items get resolved (URL → metadata via LLM)
6. Resolved data syncs back to PouchDB → UI updates automatically

---

## Services

### Frontend (`services/frontend/`)

Vue 3 + Quasar PWA with offline-first architecture.

#### Directory Structure

| Directory | Purpose |
|-----------|---------|
| `src/pages/` | Route page components |
| `src/components/` | Reusable UI components |
| `src/components/items/` | Item-specific components (ItemCard, AddItemDialog) |
| `src/stores/` | Pinia state management stores |
| `src/composables/` | Vue composables (useSync, useOAuth) |
| `src/services/pouchdb/` | PouchDB offline storage service |
| `src/boot/` | Quasar boot files (axios, auth, i18n) |
| `src/layouts/` | Page layout wrappers (MainLayout, AuthLayout) |
| `src/router/` | Vue Router configuration |
| `src/types/` | TypeScript type definitions |
| `src/i18n/` | Internationalization (ru, en) |
| `src/css/` | Global styles and CSS variables |
| `src-pwa/` | PWA service worker and manifest |

#### Key Files

| File | Purpose |
|------|---------|
| `quasar.config.js` | Build configuration, plugins, PWA settings |
| `src/boot/axios.ts` | HTTP client with token refresh interceptor |
| `src/boot/auth.ts` | Auth guards and session restoration |
| `src/boot/i18n.ts` | Vue I18n setup (ru, en locales) |
| `src/services/pouchdb/index.ts` | All PouchDB operations and sync logic |
| `src/services/pouchdb/types.ts` | TypeScript document interfaces |
| `src/stores/auth.ts` | Authentication state and JWT management |
| `src/stores/wishlist.ts` | Wishlist CRUD with PouchDB subscriptions |
| `src/stores/item.ts` | Item CRUD with PouchDB subscriptions |

---

### Core API (`services/core-api/`)

FastAPI backend handling auth, sync, sharing, and OAuth.

#### Directory Structure

| Directory | Purpose |
|-----------|---------|
| `app/routers/` | API endpoint handlers |
| `app/schemas/` | Pydantic request/response models |
| `app/services/` | Business logic (auth, oauth) |
| `app/clients/` | External service clients (item_resolver) |
| `app/oauth/` | OAuth provider configuration |
| `app/` | Core modules (main, couchdb, security, config, dependencies) |

#### Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application entry, middleware, exception handlers |
| `app/couchdb.py` | Async CouchDB client with document operations |
| `app/security.py` | JWT creation/validation, bcrypt password hashing |
| `app/config.py` | Pydantic Settings with environment variable loading |
| `app/dependencies.py` | FastAPI auth dependencies (get_current_user) |
| `app/routers/auth_couchdb.py` | Registration, login, refresh, logout endpoints |
| `app/routers/oauth.py` | OAuth flow endpoints (Google, Yandex) |
| `app/routers/sync_couchdb.py` | Push/pull sync endpoints with LWW resolution |
| `app/routers/share.py` | Share link management (create, list, revoke) |
| `app/routers/shared.py` | Shared wishlist access, marking items |
| `app/routers/health.py` | Health check endpoints (/healthz, /live, /ready) |
| `app/services/auth_couchdb.py` | Auth service with token management |
| `app/services/oauth.py` | OAuth service with state signing |

---

### Item Resolver (`services/item-resolver/`)

Extracts product metadata from URLs using Playwright + DeepSeek LLM.

#### Directory Structure

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app with resolve endpoint |
| `app/auth.py` | Bearer token authentication |
| `app/browser_manager.py` | Playwright browser/context management |
| `app/changes_watcher.py` | CouchDB _changes feed listener |
| `app/couchdb.py` | Async CouchDB client |
| `app/scrape.py` | Page capture with anti-bot handling |
| `app/html_optimizer.py` | HTML cleaning for LLM |
| `app/html_parser.py` | Image extraction from HTML |
| `app/llm.py` | DeepSeek/OpenAI LLM client |
| `app/ssrf.py` | SSRF protection and URL validation |
| `app/fetcher.py` | Page/image fetching abstraction |
| `app/errors.py` | Error codes and HTTP exceptions |
| `app/middleware.py` | Request ID middleware |

#### How Item Resolution Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. PLAYWRIGHT CAPTURES PAGE                                    │
│     └─► Navigate to URL with page.goto()                        │
│     └─► Wait for body content to render                         │
│     └─► Dismiss popups (cookie consent, city selector)          │
│     └─► Wait for network quiet (2s no requests)                 │
│     └─► Wait for DOM stability (3 samples at 500ms)             │
│     └─► Capture full HTML with page.content()                   │
├─────────────────────────────────────────────────────────────────┤
│  2. CLEAN HTML FOR LLM                                          │
│     └─► Remove <script>, <style>, <svg>, <noscript>, comments   │
│     └─► Collapse whitespace                                     │
│     └─► Truncate to LLM_MAX_CHARS (default 100000)              │
│     └─► Extract structured hints from JSON-LD/OpenGraph         │
├─────────────────────────────────────────────────────────────────┤
│  3. LLM EXTRACTS METADATA                                       │
│     └─► DeepSeek receives cleaned HTML + structured hints       │
│     └─► Extracts: title, description, price, currency, image    │
│     └─► Returns JSON with confidence score (0.0-1.0)            │
├─────────────────────────────────────────────────────────────────┤
│  4. UPDATE ITEM IN COUCHDB                                      │
│     └─► Set status to "resolved" with extracted data            │
│     └─► Or status "error" with error message                    │
└─────────────────────────────────────────────────────────────────┘
```

#### Multi-Instance Coordination

- Uses CouchDB's `_rev` field for **optimistic locking**
- Each instance has unique `INSTANCE_ID` (defaults to hostname)
- Items are claimed with `lease_expires_at` timestamp
- Expired leases are swept every `SWEEP_INTERVAL_SECONDS` (default: 60s)
- Lease duration: `LEASE_DURATION_SECONDS` (default: 300s / 5 min)

#### Browser Anti-Bot Configuration

```python
# Stealth settings
STEALTH = Stealth(navigator_languages_override=("ru-RU", "ru", "en-US", "en"))

# Chromium launch args
args = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--window-size=1920,1080",
]

# Rotating browser profiles (Chrome on Windows/Mac/Linux)
# Moscow geolocation, ru-RU locale, Europe/Moscow timezone
```

---

## API Endpoints

### Health Endpoints

| Method | Path | Auth | Response | Description |
|--------|------|------|----------|-------------|
| `GET` | `/healthz` | None | `{"status": "healthy", "couchdb": "healthy"}` | Full health check |
| `GET` | `/live` | None | `{"status": "alive"}` | Kubernetes liveness |
| `GET` | `/ready` | None | `{"status": "ready"}` | Kubernetes readiness |
| `GET` | `/` | None | `{"message": "Wish With Me API", "version": "2.0.0"}` | Root |

### Authentication (`/api/v2/auth`)

| Method | Path | Auth | Request | Response | Description |
|--------|------|------|---------|----------|-------------|
| `POST` | `/register` | None | `RegisterRequest` | `AuthResponse` (201) | Register new user |
| `POST` | `/login` | None | `LoginRequest` | `AuthResponse` | Login with email/password |
| `POST` | `/refresh` | None | `RefreshTokenRequest` | `TokenResponse` | Refresh access token |
| `POST` | `/logout` | Bearer | `LogoutRequest` | 204 | Revoke refresh token |
| `GET` | `/me` | Bearer | - | `UserResponse` | Get current user |

**Request Schemas:**

```python
class RegisterRequest:
    email: EmailStr
    password: str  # min=8, max=128
    name: str      # min=1, max=100
    locale: str = "ru"  # ^(ru|en)$

class LoginRequest:
    email: EmailStr
    password: str

class RefreshTokenRequest:
    refresh_token: str

class LogoutRequest:
    refresh_token: str
```

**Response Schemas:**

```python
class AuthResponse:
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class TokenResponse:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
```

### OAuth (`/api/v1/oauth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/providers` | None | List enabled OAuth providers |
| `GET` | `/{provider}/authorize` | None | Start OAuth flow (redirect or URL) |
| `GET` | `/{provider}/callback` | None | Handle OAuth callback |
| `POST` | `/{provider}/link/initiate` | Bearer | Start account linking |
| `DELETE` | `/{provider}/unlink` | Bearer | Unlink OAuth provider |
| `GET` | `/connected` | Bearer | List connected accounts |

**Supported Providers:** `google`, `yandex`

### Sync (`/api/v2/sync`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/pull/{collection}` | Bearer | Pull documents user has access to |
| `POST` | `/push/{collection}` | Bearer | Push documents with LWW conflict resolution |

**Collections:** `wishlists`, `items`, `marks`, `bookmarks`

**Push Authorization Rules:**
- `wishlists`: User must be owner (`owner_id == user_id`)
- `items`: User must have access to parent wishlist
- `marks`: User must be the marker (`marked_by == user_id`)
- `bookmarks`: User must own the bookmark (`user_id == current_user`)

### Share Link Management (`/api/v1/wishlists/{wishlist_id}/share`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List share links (owner only) |
| `POST` | `/` | Bearer | Create share link (owner only) |
| `DELETE` | `/{share_id}` | Bearer | Revoke share link (owner only) |

**Create Share Request:**

```python
class ShareLinkCreate:
    link_type: "view" | "mark" = "mark"
    expires_in_days: int | None  # 1-365 or None for never
```

**Response includes:** `share_url`, `qr_code_base64`, `access_count`

### Shared Wishlist Access (`/api/v1/shared`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/bookmarks` | Bearer | List user's bookmarked wishlists |
| `GET` | `/{token}/preview` | None | Preview shared wishlist (no auth) |
| `POST` | `/{token}/grant-access` | Bearer | Grant access to user |
| `GET` | `/{token}` | Bearer | Access shared wishlist with items |
| `POST` | `/{token}/items/{item_id}/mark` | Bearer | Mark item as taken |
| `DELETE` | `/{token}/items/{item_id}/mark` | Bearer | Unmark item |
| `POST` | `/{token}/bookmark` | Bearer | Create bookmark |
| `DELETE` | `/{token}/bookmark` | Bearer | Delete bookmark |

### Item Resolver (`/resolver/v1`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/resolve` | Bearer | Extract metadata from URL |
| `GET` | `/healthz` | Bearer | Health check |
| `POST` | `/v1/page_source` | Bearer | Fetch page HTML |
| `POST` | `/v1/image_base64` | Bearer | Fetch image as base64 |

**Resolve Response:**

```python
class ResolveOut:
    title: str | None
    description: str | None
    price_amount: float | None
    price_currency: str | None  # ISO: RUB, USD, EUR
    canonical_url: str | None
    confidence: float  # 0.0-1.0
    image_url: str | None
    image_base64: str | None  # data:image/...;base64,...
```

---

## Database Schema

All documents use **type-prefixed IDs**: `{type}:{uuid}`

Every document has an **`access` array** for document-level access control.

### User Document

**ID Format:** `user:{uuid}`

```json
{
  "_id": "user:abc123-uuid",
  "_rev": "1-xyz",
  "type": "user",
  "email": "user@example.com",
  "password_hash": "$2b$12$...",
  "name": "John Doe",
  "avatar_base64": "data:image/png;base64,...",
  "bio": "I love gifts!",
  "public_url_slug": "john-doe",
  "social_links": {
    "instagram": "@johndoe",
    "telegram": "@johndoe",
    "vk": null,
    "twitter": null,
    "facebook": null
  },
  "locale": "en",
  "birthday": "1990-01-15",
  "refresh_tokens": [
    {
      "token_hash": "sha256...",
      "device_info": "Mozilla/5.0...",
      "expires_at": "2024-02-01T00:00:00Z",
      "revoked": false,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "access": ["user:abc123-uuid"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

**Notes:**
- `password_hash` is server-only, never synced to frontend
- `refresh_tokens` stored on user doc, max 10 per user
- OAuth users may not have `password_hash`

### Wishlist Document

**ID Format:** `wishlist:{uuid}`

```json
{
  "_id": "wishlist:def456-uuid",
  "_rev": "3-abc",
  "type": "wishlist",
  "owner_id": "user:abc123-uuid",
  "name": "Birthday Wishlist",
  "description": "Things I want for my birthday",
  "icon": "cake",
  "is_public": false,
  "access": ["user:abc123-uuid", "user:xyz789-uuid"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-02-01T00:00:00Z"
}
```

**Notes:**
- `icon` is a Material Design icon name (default: `card_giftcard`)
- `access` includes owner + all users granted via share links

### Item Document

**ID Format:** `item:{uuid}`

```json
{
  "_id": "item:ghi789-uuid",
  "_rev": "5-def",
  "type": "item",
  "wishlist_id": "wishlist:def456-uuid",
  "owner_id": "user:abc123-uuid",
  "title": "MacBook Pro 14\"",
  "description": "Apple M3 Pro, 18GB RAM",
  "price": 199990,
  "currency": "RUB",
  "quantity": 1,
  "source_url": "https://store.apple.com/...",
  "image_url": "https://cdn.apple.com/...",
  "image_base64": "data:image/jpeg;base64,...",
  "status": "resolved",
  "resolve_confidence": 0.95,
  "resolve_error": null,
  "resolved_at": "2024-01-01T01:00:00Z",
  "resolved_by": "resolver-1",
  "claimed_by": null,
  "claimed_at": null,
  "lease_expires_at": null,
  "skip_resolution": false,
  "access": ["user:abc123-uuid", "user:xyz789-uuid"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T01:00:00Z"
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `pending` | Waiting for resolution |
| `in_progress` | Claimed by resolver instance |
| `resolved` | Successfully extracted data |
| `error` | Resolution failed |

**Notes:**
- `skip_resolution: true` for manually added items
- `access` inherited from parent wishlist

### Mark Document (Surprise Mode)

**ID Format:** `mark:{uuid}`

```json
{
  "_id": "mark:jkl012-uuid",
  "_rev": "1-ghi",
  "type": "mark",
  "item_id": "item:ghi789-uuid",
  "wishlist_id": "wishlist:def456-uuid",
  "owner_id": "user:abc123-uuid",
  "marked_by": "user:xyz789-uuid",
  "quantity": 1,
  "access": ["user:xyz789-uuid"],
  "created_at": "2024-01-15T00:00:00Z",
  "updated_at": "2024-01-15T00:00:00Z"
}
```

**CRITICAL:** Marks **exclude** `owner_id` from `access` array - wishlist owner cannot see who marked items (surprise mode).

### Share Document

**ID Format:** `share:{uuid}`

```json
{
  "_id": "share:mno345-uuid",
  "_rev": "2-jkl",
  "type": "share",
  "wishlist_id": "wishlist:def456-uuid",
  "owner_id": "user:abc123-uuid",
  "token": "abc123XYZ789SecureRandomToken32",
  "link_type": "mark",
  "expires_at": null,
  "access_count": 5,
  "revoked": false,
  "granted_users": ["user:xyz789-uuid", "user:qrs456-uuid"],
  "access": ["user:abc123-uuid"],
  "created_at": "2024-01-10T00:00:00Z",
  "updated_at": "2024-01-15T00:00:00Z"
}
```

**Link Types:**
- `view`: Read-only access
- `mark`: Can mark items as taken

### Bookmark Document

**ID Format:** `bookmark:{uuid}`

```json
{
  "_id": "bookmark:pqr678-uuid",
  "_rev": "1-mno",
  "type": "bookmark",
  "user_id": "user:xyz789-uuid",
  "share_id": "share:mno345-uuid",
  "wishlist_id": "wishlist:def456-uuid",
  "owner_name": "John Doe",
  "owner_avatar_base64": "data:image/png;base64,...",
  "wishlist_name": "Birthday Wishlist",
  "wishlist_icon": "cake",
  "access": ["user:xyz789-uuid"],
  "created_at": "2024-01-15T00:00:00Z",
  "last_accessed_at": "2024-01-20T00:00:00Z"
}
```

**Notes:**
- Caches owner/wishlist info for offline display
- Only visible to the bookmarking user

---

## Data Flow & Sync Mechanism

### Access Control Pattern

Every document has an `access` array. Queries use:

```python
selector = {
    "type": doc_type,
    "access": {"$elemMatch": {"$eq": user_id}}
}
```

**Access Rules:**

| Document | Access Array Contents |
|----------|----------------------|
| `user` | `[self_id]` only |
| `wishlist` | `[owner_id, ...granted_users]` |
| `item` | Inherited from parent wishlist |
| `mark` | All viewers EXCEPT owner (surprise mode) |
| `share` | `[owner_id]` only |
| `bookmark` | `[user_id]` only |

### Sync Flow

```
Frontend                    Core API                    CouchDB
    │                          │                           │
    │─── triggerSync() ───────►│                           │
    │                          │                           │
    │   1. PUSH FIRST          │                           │
    │   ────────────────       │                           │
    │─── POST /push/wishlists ─►│                           │
    │                          │─── validate ownership ───►│
    │                          │─── LWW check ────────────►│
    │◄── conflicts[] ─────────│◄── put/conflict ─────────│
    │                          │                           │
    │─── POST /push/items ────►│ (same for each collection)│
    │─── POST /push/marks ────►│                           │
    │─── POST /push/bookmarks ─►│                           │
    │                          │                           │
    │   2. PULL SECOND         │                           │
    │   ───────────────        │                           │
    │─── GET /pull/wishlists ──►│                           │
    │                          │─── find(access=user) ───►│
    │◄── documents[] ─────────│◄── results ──────────────│
    │                          │                           │
    │   3. RECONCILIATION      │                           │
    │   ─────────────────      │                           │
    │   Delete local docs not  │                           │
    │   in server response     │                           │
    │                          │                           │
```

### LWW (Last-Write-Wins) Conflict Resolution

```python
# Server-side check
if client_updated_at <= server_updated_at:
    # Server wins - return conflict with server document
    conflicts.append(ConflictInfo(
        document_id=doc_id,
        error="Server has newer version",
        server_document=existing,
    ))
else:
    # Client wins - update document
    doc["_rev"] = existing["_rev"]
    await db.put(doc)
```

### Item Resolution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. USER CREATES ITEM (Frontend)                                │
│     └─► PouchDB writes item with status="pending"               │
│     └─► Sync pushes to CouchDB                                  │
├─────────────────────────────────────────────────────────────────┤
│  2. CHANGES WATCHER DETECTS (Item Resolver)                     │
│     └─► CouchDB _changes feed: filter type=item, status=pending │
│     └─► try_claim_item() - optimistic lock via _rev             │
│     └─► Updates status="in_progress", sets lease                │
├─────────────────────────────────────────────────────────────────┤
│  3. RESOLVE URL                                                 │
│     └─► Playwright captures page + screenshot                   │
│     └─► LLM extracts: title, description, price, currency, image│
│     └─► Fetch and encode product image                          │
├─────────────────────────────────────────────────────────────────┤
│  4. UPDATE ITEM                                                 │
│     └─► Success: status="resolved", add extracted fields        │
│     └─► Failure: status="error", add resolve_error              │
│     └─► Clear claim fields                                      │
├─────────────────────────────────────────────────────────────────┤
│  5. SYNC BACK TO CLIENT                                         │
│     └─► Next pull sync fetches updated item                     │
│     └─► UI updates via PouchDB change subscription              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Implementation

### JWT Authentication

| Setting | Value |
|---------|-------|
| Algorithm | HS256 |
| Access Token TTL | 15 minutes |
| Refresh Token TTL | 30 days |
| Secret Key Min Length | 32 characters |

**Token Structure:**
```python
{
    "sub": user_id,
    "exp": expiration_time,
    "iat": issued_at,
    "jti": unique_token_id  # For revocation tracking
}
```

**Refresh Token Handling:**
- Stored as SHA-256 hash in user document
- Token rotation on refresh (old token revoked)
- Max 10 tokens per user
- Device info tracked

### Password Security

- **Hashing:** bcrypt via passlib
- **Min length:** 8 characters
- **Max length:** 128 characters (DoS prevention)
- **Timing attack protection:** Constant-time dummy verify on invalid email

### OAuth Security

| Provider | Scopes |
|----------|--------|
| Google | `openid email profile user.birthday.read` |
| Yandex | `login:email login:info login:avatar login:birthday` |

**State Parameter:**
- HMAC-SHA256 signed
- Contains nonce, action, user_id, timestamp
- 15-minute expiration
- Constant-time comparison

### SSRF Protection (Item Resolver)

```python
# Blocked IP ranges
- Loopback (127.0.0.0/8, ::1)
- Private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
- Link-local (169.254.0.0/16, fe80::/10)
- Multicast, Reserved, Unspecified

# Validation
- HTTP/HTTPS only
- Resolve hostname and check ALL IPs
- Allowlist via SSRF_ALLOWLIST_HOSTS env var
```

### Security Headers

**nginx (Frontend):**
```nginx
Strict-Transport-Security: max-age=63072000
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

**FastAPI (API):**
```python
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains  # prod only
```

### CORS Configuration

```python
cors_origins = [
    "http://localhost:9000",
    "http://localhost:8080",
    "https://wishwith.me",
    "https://www.wishwith.me",
    "https://api.wishwith.me",
]
```

---

## Frontend Components & Pages

### Pages

| Route | Page | Auth | Description |
|-------|------|------|-------------|
| `/` | `IndexPage.vue` | No | Landing page with features |
| `/login` | `LoginPage.vue` | No | Email/password + OAuth login |
| `/register` | `RegisterPage.vue` | No | User registration |
| `/wishlists` | `WishlistsPage.vue` | Yes | My wishlists + shared with me tabs |
| `/wishlists/:id` | `WishlistDetailPage.vue` | Yes | Wishlist items management |
| `/s/:token` | `SharedWishlistPage.vue` | Yes | View shared wishlist, mark items |
| `/shared/wishlist/:id` | `SharedWishlistPage.vue` | Yes | Bookmarked wishlist access |
| `/profile` | `ProfilePage.vue` | Yes | Edit user profile |
| `/settings` | `SettingsPage.vue` | Yes | Language, connected accounts |
| `/auth/callback` | `AuthCallbackPage.vue` | No | OAuth callback handler |

### Key Components

| Component | Purpose | Props/Events |
|-----------|---------|--------------|
| `ItemCard.vue` | Display wishlist item | `@edit`, `@delete`, `@retry` |
| `SharedItemCard.vue` | Shared item with marking | `@mark`, `@unmark`, `:canMark` |
| `AddItemDialog.vue` | Add item (URL or manual) | `@submit`, image upload |
| `ShareDialog.vue` | Manage share links | QR code, copy link |
| `SocialLoginButtons.vue` | OAuth provider buttons | Dynamic from API |
| `SyncStatus.vue` | Sync indicator in toolbar | Click to trigger sync |
| `OfflineBanner.vue` | Offline/online notifications | Auto-dismiss |
| `AppInstallPrompt.vue` | PWA install prompt | 7-day cooldown |

### Stores

| Store | State | Key Actions |
|-------|-------|-------------|
| `auth` | `user`, `accessToken`, `refreshToken` | `login`, `register`, `logout`, `refreshToken` |
| `wishlist` | `wishlists`, `currentWishlist` | `createWishlist`, `updateWishlist`, `deleteWishlist` |
| `item` | `items`, `currentItem` | `createItem`, `updateItem`, `deleteItem`, `retryResolve` |

### Composables

| Composable | Purpose | Returns |
|------------|---------|---------|
| `useSync` | Sync status and triggers | `isOnline`, `isSyncing`, `syncError`, `triggerSync()` |
| `useOAuth` | OAuth management | `providers`, `connectedAccounts`, `initiateOAuthLogin()` |

---

## PWA Configuration

### Manifest (`src-pwa/manifest.json`)

```json
{
  "name": "Wish With Me",
  "short_name": "WishWithMe",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#6366f1",
  "background_color": "#ffffff"
}
```

### Service Worker Caching Strategies

| Resource | Strategy | TTL |
|----------|----------|-----|
| Navigation | NetworkFirst → cached index.html | - |
| API calls | NetworkFirst | 24 hours |
| Sync endpoints | NetworkOnly | Never cached |
| Static assets | CacheFirst | 30 days |
| Images | CacheFirst | 30 days, max 200 |
| Google Fonts | StaleWhileRevalidate | 1 year |

### Excluded from Caching

- `/api/v1/oauth/` (OAuth flows)
- `/api/v2/sync/` (must be fresh)
- `/couchdb/` (direct CouchDB access)

---

## Infrastructure & Deployment

### Docker Services

| Service | Image | Replicas | Resources |
|---------|-------|----------|-----------|
| nginx | `nginx:alpine` | 1 | - |
| couchdb | `couchdb:3.3` | 1 | - |
| core-api | Build: `./services/core-api` | 2 | - |
| frontend | Build: `./services/frontend` | 1 | - |
| item-resolver | Build: `./services/item-resolver` | 2 | 1 CPU, 2GB RAM limit |

### nginx Routing

| Location | Backend | Timeout |
|----------|---------|---------|
| `/` | frontend:80 | default |
| `/api/` | core-api upstream | 60s |
| `/resolver/` | item-resolver upstream | 180s |
| `/couchdb/` | couchdb:5984 | 300s |

### Load Balancing

```nginx
upstream core-api {
    least_conn;
    server core-api-1:8000;
    server core-api-2:8000;
}

upstream item-resolver {
    least_conn;
    server item-resolver-1:8000;
    server item-resolver-2:8000;
}
```

### Health Checks

| Service | Command | Interval |
|---------|---------|----------|
| nginx | `wget http://127.0.0.1/health` | 30s |
| couchdb | `curl http://localhost:5984/_up` | 10s |
| core-api | `wget http://127.0.0.1:8000/live` | 30s |
| frontend | `wget http://127.0.0.1/` | 30s |
| item-resolver | `wget -H "Authorization: Bearer ..." http://127.0.0.1:8000/healthz` | 30s |

### GitHub Actions Deployment

**File:** `.github/workflows/deploy-ubuntu.yml`

**Triggers:** Push to `main` branch (services/, docker-compose.yml, nginx/)

**Jobs:**
1. `detect-changes` - Determine which services changed
2. `deploy` - SSH, git pull, rebuild changed services, health check
3. `rollback` (on failure) - Reset to last known good commit

**Rollback:** Stores `.last-known-good-commit` before deploy

### Server Details

| Setting | Value |
|---------|-------|
| IP | 176.106.144.182 |
| User | mrkutin |
| Path | `/home/mrkutin/wish-with-me-codex` |
| Data | `/home/mrkutin/wishwithme-data/couchdb` |

---

## Environment Variables

### Core API

| Variable | Default | Description |
|----------|---------|-------------|
| `COUCHDB_URL` | `http://localhost:5984` | CouchDB server URL |
| `COUCHDB_DATABASE` | `wishwithme` | Database name |
| `COUCHDB_ADMIN_USER` | `admin` | CouchDB username |
| `COUCHDB_ADMIN_PASSWORD` | - | CouchDB password |
| `JWT_SECRET_KEY` | - | **Required**, min 32 chars |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token TTL |
| `CORS_ORIGINS` | localhost + prod | Allowed CORS origins |
| `CORS_ALLOW_ALL` | `false` | Allow all origins (dev only) |
| `DEBUG` | `false` | Enable debug mode |
| `GOOGLE_CLIENT_ID` | - | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | - | Google OAuth client secret |
| `YANDEX_CLIENT_ID` | - | Yandex OAuth client ID |
| `YANDEX_CLIENT_SECRET` | - | Yandex OAuth client secret |
| `API_BASE_URL` | `https://api.wishwith.me` | API base for OAuth callbacks |
| `FRONTEND_CALLBACK_URL` | `https://wishwith.me/auth/callback` | Frontend OAuth callback |
| `ITEM_RESOLVER_URL` | `http://localhost:8080` | Item resolver service |
| `ITEM_RESOLVER_TOKEN` | - | Bearer token for resolver |
| `ITEM_RESOLVER_TIMEOUT` | `180` | Timeout in seconds |

### Item Resolver

| Variable | Default | Description |
|----------|---------|-------------|
| `RU_BEARER_TOKEN` | - | **Required**, API auth token |
| `RU_FETCHER_MODE` | `playwright` | `playwright` or `stub` |
| `COUCHDB_URL` | `http://localhost:5984` | CouchDB server |
| `COUCHDB_DATABASE` | `wishwithme` | Database name |
| `COUCHDB_WATCHER_ENABLED` | `true` | Enable changes watcher |
| `INSTANCE_ID` | hostname | Unique instance ID |
| `LEASE_DURATION_SECONDS` | `300` | Item processing lease |
| `SWEEP_INTERVAL_SECONDS` | `60` | Stale lease check interval |
| `LLM_MODE` | `live` | `live` or `stub` |
| `LLM_BASE_URL` | - | DeepSeek API URL |
| `LLM_API_KEY` | - | DeepSeek API key |
| `LLM_MODEL` | - | Model name (e.g., `deepseek-chat`) |
| `LLM_TIMEOUT_S` | `60` | LLM request timeout |
| `LLM_MAX_CHARS` | `100000` | Max HTML chars for LLM |
| `BROWSER_CHANNEL` | `chromium` | `chromium` or `chrome` |
| `HEADLESS` | `true` | Run browser headless |
| `MAX_CONCURRENCY` | `2` | Max concurrent requests |
| `STORAGE_STATE_DIR` | `storage_state` | Browser state persistence |
| `SSRF_ALLOWLIST_HOSTS` | - | Comma-separated allowed hosts |

### Frontend (build-time)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_URL` | `http://localhost:8000` | API base URL |

---

## Development Commands

### Frontend (`services/frontend/`)

```bash
npm install          # Install dependencies
npm run dev          # Dev server at localhost:9000
npm run build        # Production build
npm run build:pwa    # PWA production build
npm run lint         # ESLint check
npm run lint:fix     # ESLint fix
npm run test:unit    # Vitest unit tests
npm run typecheck    # TypeScript check
```

### Core API (`services/core-api/`)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
ruff check .         # Linting
ruff format .        # Formatting
pytest               # Run tests
pytest --cov=app     # With coverage
```

### Item Resolver (`services/item-resolver/`)

```bash
pip install -r requirements.txt
playwright install chromium  # or chrome
uvicorn app.main:app --reload --port 8001
pytest               # Run tests
```

### Docker

```bash
docker-compose up -d                    # Start all services
docker-compose up -d --build            # Rebuild and start
docker-compose logs -f                  # View all logs
docker-compose logs -f core-api-1       # Single service logs
docker-compose down                     # Stop services
docker-compose ps                       # Service status
```

### Production Commands

```bash
# SSH to server
ssh mrkutin@176.106.144.182

# Check status
docker-compose -f docker-compose.yml ps

# View logs
docker logs wishwithme-core-api-1 --tail=100
docker logs wishwithme-item-resolver-1 --tail=100

# Health checks
curl -sf https://wishwith.me/healthz
curl -sf https://api.wishwith.me/healthz

# Manual deploy
git pull origin main
docker-compose -f docker-compose.yml up -d --build
```

---

## Code Conventions

### Python (Backend)

- **Style:** Ruff linter, 88 char lines
- **Types:** Full type hints with `typing.Annotated`
- **Async:** All I/O operations are async
- **Naming:** snake_case for files/functions, PascalCase for classes
- **Errors:** Structured `{"error": {"code": "...", "message": "..."}}` format

### TypeScript (Frontend)

- **Style:** ESLint + Prettier, single quotes
- **Components:** Vue 3 Composition API with `<script setup lang="ts">`
- **Stores:** Pinia with composition style
- **Naming:** camelCase for files/functions, PascalCase for components/interfaces

### Document IDs

Always use type-prefixed UUIDs:
```python
user_id = f"user:{uuid4()}"
wishlist_id = f"wishlist:{uuid4()}"
item_id = f"item:{uuid4()}"
```

### API Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `BAD_REQUEST` | 400 | Invalid input |
| `UNAUTHORIZED` | 401 | Invalid/missing credentials |
| `FORBIDDEN` | 403 | Access denied |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Email exists, doc conflict |
| `INVALID_URL` | 422 | Malformed URL |
| `SSRF_BLOCKED` | 403 | Internal network access |
| `TIMEOUT` | 504 | Operation timed out |
| `INTERNAL_ERROR` | 500 | Unexpected error |

---

## Agent Usage Requirements

**IMPORTANT:** Always use the appropriate specialized agent for each task.

### Task-to-Agent Mapping

| Task Type | Agent | When to Use |
|-----------|-------|-------------|
| **Codebase exploration** | `Explore` | Finding files, searching code, understanding structure |
| **Implementation planning** | `Plan` | Designing approach before writing code |
| **Frontend development** | `frontend-dev` | Vue/TypeScript components, Quasar UI, Pinia stores |
| **Backend development** | `backend-dev` | FastAPI endpoints, Python async code, CouchDB operations |
| **Code review** | `reviewer` | Quality, security, performance, maintainability checks |
| **Security analysis** | `security` | Threat modeling, OWASP issues, vulnerability review |
| **Testing** | `qa` | Test strategy, Vitest/pytest automation, coverage |
| **API design** | `api-designer` | REST endpoints, schemas, OpenAPI specs |
| **Database work** | `dba` | CouchDB queries, data modeling, optimization |
| **DevOps/Infrastructure** | `devops` | Docker, CI/CD, nginx, deployment scripts |
| **SRE tasks** | `sre` | Monitoring, health checks, incident runbooks |
| **Performance** | `performance` | Profiling, optimization, load testing |
| **Documentation** | `tech-writer` | API docs, README files, architecture docs |
| **Architecture decisions** | `system-architect` | Distributed systems, microservices, tech decisions |

### Agent Usage Rules

1. **Always explore first:** Before making changes, use `Explore` agent to understand context
2. **Plan before implementing:** For non-trivial features, use `Plan` agent to design approach
3. **Match agent to domain:** Frontend → `frontend-dev`, Backend → `backend-dev`
4. **Review after changes:** Use `reviewer` agent after significant changes
5. **Security-sensitive code:** Always involve `security` agent for auth, validation, data access
6. **Run agents in parallel:** When tasks are independent, launch multiple agents simultaneously

### Workflow: Bug Fix

```
1. INVESTIGATE
   └─► Explore agent: find the bug location
   └─► devops agent: if infrastructure/deployment issue

2. FIX
   └─► frontend-dev / backend-dev: implement the fix

3. UNIT TESTS
   └─► qa agent: run ALL unit tests
   └─► If tests fail → back to step 2

4. VERIFY
   └─► reviewer agent: code quality check
   └─► devops agent: deployment/integration check (if needed)
   └─► If bug not fixed → back to step 2

5. DONE
   └─► Only when fix verified and all tests pass
```

### Workflow: New Feature

```
1. ARCHITECTURE CHECK
   └─► system-architect agent: verify feature fits architecture
   └─► If conflicts exist → DISCUSS with user before proceeding

2. PLAN
   └─► Plan agent: create detailed implementation plan
   └─► Get user approval on the plan

3. IMPLEMENT
   └─► frontend-dev / backend-dev: write the code

4. WRITE TESTS
   └─► qa agent: write new unit tests for the feature

5. RUN TESTS
   └─► qa agent: run ALL unit tests (new + existing)
   └─► If tests fail → back to step 3

6. VERIFY
   └─► reviewer agent: code quality, security, maintainability
   └─► qa agent: functional testing
   └─► If issues found → back to step 3

7. DONE
   └─► Only when all tests pass and verification complete
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start local dev | `docker-compose up -d` |
| View all logs | `docker-compose logs -f` |
| Deploy to prod | Push to `main` branch |
| Check prod logs | `ssh mrkutin@176.106.144.182` then `docker logs ...` |
| Run frontend tests | `cd services/frontend && npm run test:unit` |
| Run backend tests | `cd services/core-api && pytest` |
| Lint frontend | `cd services/frontend && npm run lint` |
| Lint backend | `cd services/core-api && ruff check .` |
| Health check frontend | `curl -sf https://wishwith.me/healthz` |
| Health check API | `curl -sf https://api.wishwith.me/healthz` |

---

## Security Checklist

When making changes, verify:

- [ ] Input validation via Pydantic schemas
- [ ] Access control checks on document operations
- [ ] No SQL/NoSQL injection (use Mango selectors, not string concat)
- [ ] SSRF protection for URL fetching
- [ ] JWT tokens properly validated
- [ ] Sensitive data not logged (passwords, tokens)
- [ ] CORS configured correctly
- [ ] No secrets in code (use environment variables)
- [ ] Rate limiting considered for auth endpoints
- [ ] OAuth state parameter properly validated

---

**NOTE:** Always deploy fixes without asking for confirmation. Commit, push to main, and monitor the deployment via GitHub Actions.
