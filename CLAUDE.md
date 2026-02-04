# CLAUDE.md - Wish With Me Development Guide

## Project Overview

**Wish With Me** - Offline-first wishlist PWA with:
- Wishlists & items management
- URL item addition (auto-extracts metadata via LLM)
- Share links (view-only or mark permission)
- Surprise mode (marks hidden from owner)
- Offline-first with PouchDB → CouchDB sync
- OAuth (Google, Yandex)

**URLs:** https://wishwith.me | https://api.wishwith.me

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Vue 3 + Quasar + TypeScript + Pinia + PouchDB |
| Backend | FastAPI + Python 3.12 + async/await |
| URL Resolver | FastAPI + Playwright + DeepSeek LLM |
| Database | CouchDB 3.3 (with PouchDB sync) |
| Proxy | nginx (SSL, load balancing) |
| Deploy | Docker Compose, GitHub Actions |
| Auth | JWT (HS256) + bcrypt + OAuth 2.0 |

## Architecture

```
Internet → nginx :443 → ┬→ frontend :80 (Vue PWA)
                        ├→ core-api x2 :8000 (FastAPI)
                        ├→ item-resolver x2 :8000 (Playwright+LLM)
                        └→ couchdb :5984
```

**Data Flow:** User writes → PouchDB (local) → sync to CouchDB → item-resolver watches `_changes` for `status: "pending"` → resolves URL → syncs back

## Services Structure

### Frontend (`services/frontend/`)
- `src/pages/` - Route pages
- `src/components/` - UI components (ItemCard, AddItemDialog, ShareDialog, SocialLoginButtons, SyncStatus, OfflineBanner, AppInstallPrompt, BackgroundDecorations)
- `src/stores/` - Pinia stores (auth, wishlist, item)
- `src/composables/` - Vue composables (useSync, useOAuth)
- `src/services/pouchdb/` - Offline storage
- `src/boot/` - axios, auth, i18n

### Core API (`services/core-api/`)
- `app/routers/` - auth_couchdb, oauth, sync_couchdb, share, shared, health
- `app/schemas/` - Pydantic models
- `app/services/` - auth_couchdb, oauth
- `app/` - main, couchdb, security, config, dependencies

### Item Resolver (`services/item-resolver/`)
- `app/main.py` - FastAPI + resolve endpoint
- `app/browser_manager.py` - Playwright browser pool
- `app/changes_watcher.py` - CouchDB `_changes` listener
- `app/scrape.py` - Page capture with anti-bot
- `app/html_optimizer.py` - HTML cleaning for LLM
- `app/html_parser.py` - HTML parsing utilities
- `app/llm.py` - DeepSeek extraction
- `app/ssrf.py` - SSRF protection
- `app/couchdb.py` - CouchDB client
- `app/fetcher.py` - URL fetching abstraction
- `app/image_utils.py` - Image processing
- `app/auth.py` - Bearer token auth
- `app/errors.py` - Error definitions
- `app/middleware.py` - Request middleware
- `app/logging_config.py` - Logging setup

**Resolution Flow:** Playwright captures → clean HTML → LLM extracts (title, price, image) → update CouchDB

**Multi-Instance:** Optimistic locking via `_rev`, lease with `lease_expires_at`, sweep expired every 60s

## API Endpoints

### Auth (`/api/v2/auth`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /register | - | Register (email, password, name, locale) |
| POST | /login | - | Login → AuthResponse |
| POST | /refresh | - | Refresh tokens → TokenResponse |
| POST | /logout | Bearer | Revoke refresh token (body: `{refresh_token}`) |
| GET | /me | Bearer | Current user |

### OAuth (`/api/v1/oauth`)
| Method | Path | Description |
|--------|------|-------------|
| GET | /providers | List providers |
| GET | /{provider}/authorize | Start OAuth |
| GET | /{provider}/callback | OAuth callback |
| POST | /{provider}/link/initiate | Link account |
| DELETE | /{provider}/unlink | Unlink |
| GET | /connected | List connected |

**Providers:** `google`, `yandex`

### Sync (`/api/v2/sync`)
| Method | Path | Description |
|--------|------|-------------|
| GET | /pull/{collection} | Pull docs user has access to |
| POST | /push/{collection} | Push with LWW conflict resolution |

**Collections:** `wishlists`, `items`, `marks`, `bookmarks`, `users`, `shares`

**Push Rules:** wishlists (owner only), items (wishlist access), marks (marker only), bookmarks (owner only), shares (owner only)

### Share (`/api/v1/wishlists/{wishlist_id}/share`)
| Method | Path | Description |
|--------|------|-------------|
| POST | / | Create (link_type: view|mark, expires_in_days) |
| DELETE | /{share_id} | Revoke |

*Note: List share links via sync (`/api/v2/sync/pull/shares`).*

### Shared (`/api/v1/shared`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /{token}/grant-access | Bearer | Grant access to shared wishlist |

*Note: Most shared wishlist operations (view, mark, bookmark) are handled via PouchDB sync.*

### Item Resolver
| Method | Path | Description |
|--------|------|-------------|
| GET | /healthz | Health check |
| POST | /resolver/v1/resolve | Extract metadata from URL |
| POST | /v1/page_source | Fetch page HTML |
| POST | /v1/image_base64 | Fetch image as base64 |

**Response:** `title`, `description`, `price_amount`, `price_currency`, `image_url`, `image_base64`, `confidence`

## Database Schema

All docs use **type-prefixed IDs** (`{type}:{uuid}`) and **`access` array** for ACL.

### User (`user:{uuid}`)
```json
{"type": "user", "email": "...", "password_hash": "...", "name": "...",
 "avatar_base64": "...", "bio": "...", "public_url_slug": "...", "birthday": "...",
 "locale": "ru|en", "refresh_tokens": [...],
 "access": ["user:{uuid}"], "created_at": "...", "updated_at": "..."}
```

### Wishlist (`wishlist:{uuid}`)
```json
{"type": "wishlist", "owner_id": "user:...", "name": "...", "description": "...",
 "icon": "card_giftcard", "is_public": false,
 "access": ["user:owner", "user:granted..."], "created_at": "...", "updated_at": "..."}
```

### Item (`item:{uuid}`)
```json
{"type": "item", "wishlist_id": "...", "owner_id": "...", "title": "...",
 "description": "...", "price": 100, "currency": "RUB", "quantity": 1,
 "source_url": "...", "image_url": "...", "image_base64": "...",
 "status": "pending|in_progress|resolved|error",
 "resolve_confidence": 0.95, "resolve_error": "...", "resolved_at": "...", "resolved_by": "...",
 "claimed_by": "...", "claimed_at": "...", "lease_expires_at": "...",
 "access": ["..."], "created_at": "...", "updated_at": "..."}
```

### Mark (`mark:{uuid}`) - Surprise Mode
```json
{"type": "mark", "item_id": "...", "wishlist_id": "...", "owner_id": "...",
 "marked_by": "user:...", "quantity": 1,
 "access": ["user:all_viewers_except_owner"],
 "created_at": "...", "updated_at": "..."}
```
*Note: `access` includes all wishlist viewers EXCEPT owner (surprise mode).*

### Share (`share:{uuid}`)
```json
{"type": "share", "wishlist_id": "...", "owner_id": "...", "token": "...",
 "link_type": "view|mark", "expires_at": null, "granted_users": [...],
 "access_count": 0, "revoked": false,
 "access": ["user:owner"], "created_at": "..."}
```

### Bookmark (`bookmark:{uuid}`)
```json
{"type": "bookmark", "user_id": "...", "share_id": "...", "wishlist_id": "...",
 "owner_name": "...", "owner_avatar_base64": "...",
 "wishlist_name": "...", "wishlist_icon": "...",
 "access": ["user:{uuid}"], "created_at": "...", "last_accessed_at": "..."}
```

## Access Control

```python
selector = {"type": doc_type, "access": {"$elemMatch": {"$eq": user_id}}}
```

| Doc | Access |
|-----|--------|
| user | `[self]` |
| wishlist | `[owner, ...granted]` |
| item | inherited from wishlist |
| mark | all viewers EXCEPT owner |
| share | `[owner]` |
| bookmark | `[user]` |

## Sync & Conflict Resolution

1. **Push first** (all collections) → server validates ownership, LWW check
2. **Pull second** → server returns docs where `access` includes user
3. **Reconcile** → delete local docs not in server response

**LWW:** `client_updated_at > server_updated_at` → client wins, else server wins

## Security

**JWT:** HS256, access=15min, refresh=30days, secret min 32 chars
**Passwords:** bcrypt, 8-128 chars, timing-safe compare
**OAuth State:** HMAC-SHA256 signed, 15min expiry
**SSRF:** Block loopback/private/link-local IPs, allowlist via `SSRF_ALLOWLIST_HOSTS`

**Headers:** HSTS, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

**CORS:** localhost:9000, localhost:8080, wishwith.me, api.wishwith.me

## Frontend Pages & Components

| Route | Page | Auth |
|-------|------|------|
| / | IndexPage | No |
| /login, /register | Auth pages | No |
| /wishlists | WishlistsPage | Yes |
| /wishlists/:id | WishlistDetailPage | Yes |
| /s/:token | SharedWishlistPage | Yes |
| /shared/wishlist/:wishlistId | SharedWishlistPage | Yes |
| /profile, /settings | Profile pages | Yes |
| /auth/callback | OAuth callback | No |

**Components:** ItemCard, SharedItemCard, AddItemDialog, ShareDialog, SocialLoginButtons, SyncStatus, OfflineBanner, AppInstallPrompt, BackgroundDecorations

**Stores:** auth (user, tokens), wishlist (CRUD), item (CRUD)

**Composables:** useSync (isOnline, isSyncing, triggerSync), useOAuth (providers, connectedAccounts)

## PWA

**Caching:** NetworkFirst (navigation, API), CacheFirst (static, images), NetworkOnly (sync, oauth)

## Infrastructure

| Service | Replicas | Notes |
|---------|----------|-------|
| nginx | 1 | SSL, routing |
| frontend | 1 | Static PWA |
| core-api | 2 | least_conn LB |
| item-resolver | 2 | least_conn LB, 1CPU/2GB |
| couchdb | 1 | Data at /home/mrkutin/wishwithme-data/couchdb |

**Server:** 176.106.144.182, user: mrkutin, path: /home/mrkutin/wish-with-me-codex

**Deploy:** Push to `main` → GitHub Actions tests → deploy → rollback on failure

## Environment Variables

### Core API
| Var | Default | Required |
|-----|---------|----------|
| COUCHDB_URL | http://localhost:5984 | |
| COUCHDB_DATABASE | wishwithme | |
| COUCHDB_ADMIN_USER/PASSWORD | admin/- | Yes |
| JWT_SECRET_KEY | - | Yes (32+ chars) |
| ACCESS_TOKEN_EXPIRE_MINUTES | 15 | |
| REFRESH_TOKEN_EXPIRE_DAYS | 30 | |
| GOOGLE_CLIENT_ID/SECRET | - | |
| YANDEX_CLIENT_ID/SECRET | - | |
| OAUTH_STATE_SECRET | - | For OAuth state HMAC |
| API_BASE_URL | https://api.wishwith.me | |
| FRONTEND_CALLBACK_URL | https://wishwith.me/auth/callback | |
| ITEM_RESOLVER_URL | http://localhost:8080 | |
| ITEM_RESOLVER_TOKEN | dev-token | |
| ITEM_RESOLVER_TIMEOUT | 180 | |
| CORS_ORIGINS | (see config.py) | |
| CORS_ALLOW_ALL | false | |
| DEBUG | false | |
| ENVIRONMENT | development | |

### Item Resolver
| Var | Default | Required |
|-----|---------|----------|
| RU_BEARER_TOKEN | - | Yes |
| RU_FETCHER_MODE | playwright | |
| COUCHDB_URL/DATABASE | localhost/wishwithme | |
| COUCHDB_ADMIN_USER/PASSWORD | admin/- | |
| COUCHDB_WATCHER_ENABLED | true | |
| INSTANCE_ID | HOSTNAME or socket.gethostname() | |
| LEASE_DURATION_SECONDS | 300 | |
| SWEEP_INTERVAL_SECONDS | 60 | |
| LLM_MODE/BASE_URL/API_KEY/MODEL | live/-/-/- | |
| LLM_MAX_CHARS | 100000 | |
| LLM_TIMEOUT_S | 60 | |
| LLM_CLIENT_TYPE | auto (vision/text) | |
| BROWSER_CHANNEL | chromium | |
| HEADLESS | true | |
| MAX_CONCURRENCY | 2 | |
| STORAGE_STATE_DIR | storage_state | |
| PAGE_TIMEOUT_MS | 90000 | |
| PAGE_WAIT_UNTIL | load | |
| RANDOM_UA | false | |
| PROXY_SERVER/USERNAME/PASSWORD/BYPASS | - | |
| SSRF_ALLOWLIST_HOSTS | - | |

### Frontend (build-time)
| Var | Default |
|-----|---------|
| API_URL | http://localhost:8000 |

## Testing

**All tests must pass before deployment.**

| Service | Framework | Location | Count |
|---------|-----------|----------|-------|
| Frontend | Vitest | src/**/__tests__/ | 290 |
| Core API | pytest | tests/ | 154 |
| Item Resolver | pytest | tests/ | 305 |

```bash
# Frontend
npm run test:unit

# Core API
pytest tests/ -v

# Item Resolver
pytest tests/ -v
```

## Development Commands

```bash
# Frontend
npm install && npm run dev  # localhost:9000
npm run lint && npm run test:unit

# Core API
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
ruff check . && pytest

# Item Resolver
pip install -r requirements.txt && playwright install chromium
uvicorn app.main:app --reload --port 8001
pytest

# Docker
docker-compose up -d --build
docker-compose logs -f
docker-compose down
```

## Code Conventions

**Python:** Ruff, 88 chars, full type hints, async I/O, snake_case
**TypeScript:** ESLint+Prettier, single quotes, `<script setup lang="ts">`, camelCase

**Doc IDs:** `{type}:{uuid}` (user:xxx, wishlist:xxx, item:xxx, mark:xxx, share:xxx, bookmark:xxx)

**API Errors:**
```json
{"error": {"code": "ERROR_CODE", "message": "...", "details": {}}}
```

| Code | Status |
|------|--------|
| BAD_REQUEST | 400 |
| UNAUTHORIZED | 401 |
| FORBIDDEN | 403 |
| NOT_FOUND | 404 |
| CONFLICT | 409 |
| INVALID_URL | 422 |
| SSRF_BLOCKED | 403 |
| TIMEOUT | 504 |
| INTERNAL_ERROR | 500 |

## Agent Usage

| Task | Agent |
|------|-------|
| Codebase exploration | Explore |
| Planning | Plan |
| Frontend | frontend-dev |
| Backend | backend-dev |
| Code review | reviewer |
| Security | security |
| Testing | qa |
| API design | api-designer |
| Database | dba |
| DevOps | devops |
| SRE | sre |
| Performance | performance |
| Docs | tech-writer |
| Architecture | system-architect |

**Bug Fix:** Explore → Fix → Run ALL tests → Review → Done
**New Feature:** Architecture check → Plan → Implement → Write tests → Run ALL tests → Review → Done

## Quick Reference

| Task | Command |
|------|---------|
| Start dev | `docker-compose up -d` |
| Logs | `docker-compose logs -f` |
| Deploy | Push to `main` |
| Frontend tests | `cd services/frontend && npm run test:unit` |
| Backend tests | `cd services/core-api && pytest` |
| Health | `curl https://wishwith.me/healthz` |

## Security Checklist

- [ ] Input validation (Pydantic)
- [ ] Access control on docs
- [ ] No injection (use Mango selectors)
- [ ] SSRF protection
- [ ] JWT validated
- [ ] No secrets logged
- [ ] CORS correct
- [ ] OAuth state validated

**Deploy fixes without asking.** Commit, push to main, monitor GitHub Actions.
