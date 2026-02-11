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
| Frontend | Vue 3 + Quasar + TypeScript + Pinia + PouchDB + @vueuse/core |
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
- `src/components/` - UI components (ItemCard, SharedItemCard, AddItemDialog, ShareDialog, SocialLoginButtons, SyncStatus, OfflineBanner, AppInstallPrompt, BackgroundDecorations)
- `src/stores/` - Pinia stores (auth, wishlist, item)
- `src/composables/` - Vue composables (useSync, useOAuth)
- `src/services/pouchdb/` - Offline storage
- `src/boot/` - axios, auth, i18n

### Core API (`services/core-api/`)
- `app/routers/` - auth_couchdb, oauth, sync_couchdb, share, shared, health
- `app/schemas/` - Pydantic models
- `app/services/` - auth_couchdb, oauth
- `app/oauth/` - OAuth provider configuration (providers, schemas)
- `app/clients/` - HTTP clients (item_resolver)
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
- `app/timing.py` - Request profiling (TimingStats, measure_time)

**Resolution Flow:** Playwright captures → clean HTML → LLM extracts (title, price, image) → update CouchDB

**Multi-Instance:** Optimistic locking via `_rev`, lease with `lease_expires_at`, sweep expired every 60s

## API Endpoints

### Core API Root & Health
| Method | Path | Description |
|--------|------|-------------|
| GET | / | Returns `{"message": "Wish With Me API", "version": "2.0.0"}` |
| GET | /healthz | Health check (checks CouchDB via `db_info()`) → `{status, couchdb}` |
| GET | /ready | Readiness probe → `{"status": "ready"}` |
| GET | /live | Liveness probe → `{"status": "alive"}` |

*Note: `/docs` and `/redoc` only available when `DEBUG=true`.*

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

**Response:** `title`, `description`, `price_amount`, `price_currency`, `image_url`, `image_base64`, `canonical_url`, `confidence`

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
 "icon": "card_giftcard", "icon_color": "primary", "is_public": false,
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
 "skip_resolution": false,
 "access": ["..."], "created_at": "...", "updated_at": "..."}
```
*Status values:* `pending` (URL item awaiting resolution), `in_progress` (claimed by resolver instance — server-side only, frontend never sets this), `resolved` (metadata extracted or manual item), `error` (resolution failed). Frontend TypeScript type includes all 4 (`ItemStatus`), but PouchDB type uses 3 (`pending|resolved|error`) since `in_progress` is transient server state.

### Mark (`mark:{uuid}`) - Surprise Mode
```json
{"type": "mark", "item_id": "...", "wishlist_id": "...", "owner_id": "...",
 "marked_by": "user:...", "quantity": 1,
 "access": ["user:all_viewers_except_owner"],
 "created_at": "...", "updated_at": "..."}
```
*Note: `access` includes all wishlist viewers EXCEPT owner (surprise mode).*

**Quantity calculation:** `available_quantity = item.quantity - sum(mark.quantity for all non-deleted marks on item)`. Computed at read time; not stored.

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
 "wishlist_name": "...", "wishlist_icon": "...", "wishlist_icon_color": "...",
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
- Claims: `sub` (user_id string, e.g. `user:uuid`), `exp`, `iat`, `jti` (secrets.token_hex(16))
- Library: `python-jose` for encode/decode

**Refresh tokens:** `secrets.token_urlsafe(32)`, stored as SHA-256 hash in user doc (`hashlib.sha256`)

**Passwords:** bcrypt via `passlib.context.CryptContext(schemes=["bcrypt"])`, 8-128 chars, timing-safe compare (dummy verify on invalid email)

**Default avatar:** SVG blue circle with white silhouette, assigned at registration as `DEFAULT_AVATAR_BASE64`

**OAuth State:** HMAC-SHA256 signed, 15min expiry, format: `nonce:action:user_id:timestamp:callback_b64:signature` (signature = first 32 chars of hex digest). Fallback secret: `JWT_SECRET_KEY` if `OAUTH_STATE_SECRET` not set. Allowed callback schemes: `https`, `wishwithme` (mobile deep link).

**SSRF:** Block loopback/private/link-local IPs, allowlist via `SSRF_ALLOWLIST_HOSTS`

**Headers (dual-layer):**
- **nginx:** HSTS max-age=63072000 (2yr), X-Frame-Options SAMEORIGIN, X-Content-Type-Options nosniff, X-XSS-Protection, Referrer-Policy strict-origin-when-cross-origin
- **core-api middleware:** X-Content-Type-Options nosniff, X-Frame-Options DENY, X-XSS-Protection, HSTS max-age=31536000 (1yr, only when `DEBUG=false`)

**CORS:** Handled entirely by **nginx** (OPTIONS → 204). FastAPI `CORSMiddleware` is NOT enabled (causes duplicate headers). Origins: `https://wishwith.me`.

## Frontend Pages & Components

| Route | Name | Page | Auth | Layout |
|-------|------|------|------|--------|
| / | `home` | IndexPage | No | Main |
| /login | `login` | LoginPage | No | Auth |
| /register | `register` | RegisterPage | No | Auth |
| /auth/callback | `auth-callback` | AuthCallbackPage | No | Auth |
| /wishlists | `wishlists` | WishlistsPage | Yes | Main |
| /wishlists/:id | `wishlist-detail` | WishlistDetailPage | Yes | Main |
| /s/:token | `shared-wishlist` | SharedWishlistPage | Yes | Main |
| /shared/wishlist/:wishlistId | `bookmarked-wishlist` | SharedWishlistPage | Yes | Main |
| /profile | `profile` | ProfilePage | Yes | Main |
| /settings | `settings` | SettingsPage | Yes | Main |
| /:catchAll(.*)* | - | ErrorNotFound | No | - |

**Components:** ItemCard, SharedItemCard, AddItemDialog, ShareDialog, SocialLoginButtons, SyncStatus, OfflineBanner, AppInstallPrompt, BackgroundDecorations

**Stores:** auth (user, tokens), wishlist (CRUD), item (CRUD)

**Quasar plugins:** `Notify`, `Dialog`, `Loading`, `LocalStorage`, `SessionStorage`, `BottomSheet`

**Key npm dependencies:** `qrcode` (QR code generation in ShareDialog via `toDataURL`), `@vueuse/core` (reactivity utilities, `useOnline`)

**Composables:**
- `useSync`: returns `isOnline`, `isInitialized`, `isSyncing`, `syncError`, `pendingCount`, `status: SyncStatus`, `triggerSync`, `initializeSync`, `cleanupSync`, `getDb`. Also exports `initializeSync`/`cleanupSync` as standalone functions for use outside Vue components.
- `useOAuth`: returns `availableProviders`, `connectedAccounts`, `hasPassword`, `canUnlinkAccount`, `isLoading`, `error`, `fetchAvailableProviders`, `fetchConnectedAccounts`, `initiateOAuthLogin`, `initiateOAuthLink`, `unlinkAccount`, `isProviderConnected`, `getProviderDisplayName`, `getProviderIcon`, `getProviderColor`
- `OAuthProvider` type: `'google' | 'apple' | 'yandex' | 'sber'` (apple/sber defined in frontend type but not active server-side). Display names, icons (`mdi-google`, `mdi-apple`, `mdi-alpha-y-box`, `mdi-bank`), brand colors defined for all four.

## PWA

**Workbox mode:** `injectManifest` (custom service worker at `sw.js`)
**Manifest:** `display: standalone`, `orientation: portrait`, `theme_color: #4F46E5`, `background_color: #ffffff`, icons: 128/192/256/384/512px PNG
**Caching:** NetworkFirst (navigation, API), CacheFirst (static, images), NetworkOnly (sync), StaleWhileRevalidate (Google Fonts)

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
| PROXY_IGNORE_CERT_ERRORS | false | |
| SSRF_ALLOWLIST_HOSTS | - | |
| LOG_FORMAT | json | |
| LOG_LEVEL | INFO | |

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

**Item Resolver error codes** (additional, from `app/errors.py`):

| Code | Status |
|------|--------|
| BLOCKED_OR_UNAVAILABLE | 502 |
| UNSUPPORTED_CONTENT | 422 |
| LLM_PARSE_FAILED | 502 |
| UNKNOWN_ERROR | 500 |

Item resolver errors include `trace_id` field (from `RequestIdMiddleware` — propagates/generates `X-Request-Id` header via `contextvars`).

## Pydantic Schemas (Request/Response)

### Auth Schemas (`app/schemas/auth.py`)
| Schema | Fields |
|--------|--------|
| `RegisterRequest` | `email: EmailStr`, `password: str(8-128)`, `name: str(1-100)`, `locale: str(^(ru|en)$, default="ru")` |
| `LoginRequest` | `email: EmailStr`, `password: str` |
| `RefreshTokenRequest` | `refresh_token: str` |
| `LogoutRequest` | `refresh_token: str` |
| `TokenResponse` | `access_token`, `refresh_token`, `token_type="bearer"`, `expires_in: int` |
| `AuthResponse` | `user: UserResponse`, `access_token`, `refresh_token`, `token_type="bearer"`, `expires_in: int` |

### User Schemas (`app/schemas/user.py`)
| Schema | Fields |
|--------|--------|
| `UserResponse` | `id: UUID\|str`, `email`, `name(1-100)`, `bio(max 500)`, `public_url_slug(^[a-z0-9-]+$, max 50)`, `social_links: SocialLinks?`, `locale`, `birthday: date?`, `avatar_base64?`, `created_at`, `updated_at` |
| `UserUpdate` | All fields optional: `name`, `bio`, `public_url_slug`, `social_links`, `avatar_base64`, `locale`, `birthday` |
| `SocialLinks` | `instagram?`, `telegram?`, `vk?`, `twitter?`, `facebook?` (all optional strings) |
| `ConnectedAccount` | `provider: str`, `email?`, `connected_at: datetime` |

### Share Schemas (`app/schemas/share.py`)
| Schema | Fields |
|--------|--------|
| `ShareLinkCreate` | `link_type: ShareLinkType(default=MARK)`, `expires_in_days: int(1-365)\|None` |
| `ShareLinkResponse` | `id: UUID`, `wishlist_id: UUID`, `token`, `link_type`, `expires_at?`, `access_count`, `created_at`, `share_url` |
| `MarkCreate` | `quantity: int(ge=1, default=1)` |
| `MarkResponse` | `item_id: UUID`, `my_mark_quantity`, `total_marked_quantity`, `available_quantity` |
| `GrantAccessResponse` | `wishlist_id: str`, `permissions: list[str]` |

`ShareLinkType` enum: `VIEW = "view"`, `MARK = "mark"`

## User Flows

### Login/Register
1. Form validation (email format, password 8-128 chars, name required)
2. POST `/api/v2/auth/login` or `/register` (with locale from browser)
3. Response: `{user, access_token, refresh_token, expires_in}`
4. `setAuth()` stores tokens in `localStorage` (`refresh_token`, `access_token`, `user_data`)
5. `scheduleTokenRefresh()` sets timer for 2min before JWT expiry
6. `initializeSync()` starts PouchDB → API sync
7. Redirect to `/wishlists` (or to pending share URL if `pending_share_token` in localStorage)

**OAuth variant:** GET `/{provider}/authorize` → redirect to provider → callback → `AuthCallbackPage` processes query params (`access_token`+`refresh_token` or `error`+`error_message`). Errors: `email_exists`, `already_linked`, `auth_failed`, `validation_error`, `server_error`. Success: `setTokensFromOAuth()` → `fetchCurrentUser()` → redirect after 1s delay.

### Create Wishlist
1. Dialog with: name (required), description, icon picker (24 Material icons), color picker (11 Quasar colors)
2. Frontend: `createId('wishlist')` → PouchDB `upsert()` with `access: [userId]`, `owner_id: userId`
3. `triggerSync()` if online (else shows offline notification with `cloud_off` icon)
4. Reactive update via `subscribeToWishlists()` change listener

### Add Item (URL)
1. User pastes URL → validation
2. Creates item doc: `status: 'pending'`, `title: hostname` (temp), `source_url: url`, `skip_resolution: false`
3. `triggerSync()` pushes to CouchDB
4. Item-resolver picks up via `_changes` feed → claims → resolves → writes back
5. Next sync pull updates local PouchDB → UI reactively shows resolved title/price/image
6. UI shows resolving badge while `status` is `pending` or `in_progress`

### Add Item (Manual)
1. Title required; price, currency, quantity, image optional
2. Creates item doc: `status: 'resolved'`, `skip_resolution: true`
3. No item-resolver involvement; syncs normally

### Share Wishlist
1. Owner clicks share → `ShareDialog` → choose link type (`view` or `mark`)
2. POST `/api/v1/wishlists/{id}/share` → generates 32-char token (`secrets.choice(letters+digits)`)
3. Returns share URL: `https://wishwith.me/s/{token}`
4. UI shows copy button + QR code; share doc synced with `access: [owner]`

### Accept Share
1. Visitor navigates to `/s/:token` (route `shared-wishlist`, requires auth)
2. If not authenticated: token saved to `localStorage('pending_share_token')` → redirect to `/login`
3. After login: `AuthCallbackPage` checks for `pending_share_token` → redirects to `/s/:token`
4. `SharedWishlistPage` calls POST `/api/v1/shared/{token}/grant-access`
5. Server: validates token + expiry → adds user to `granted_users` → `update_access_arrays(add)` on wishlist+items → creates/updates bookmark with cached owner info
6. Response: `{wishlist_id, permissions: ['view'] or ['view', 'mark']}`
7. Redirect to `/shared/wishlist/:wishlistId` → sync pulls new data

### Mark Item (Surprise Mode)
1. Viewer clicks mark on shared item → creates `mark` doc
2. Mark `access` = all wishlist viewers EXCEPT owner (computed from wishlist access minus `owner_id`)
3. Quantity selector; unmark = soft delete (`_deleted: true`)
4. Owner never sees marks (pull filter: `owner_id != user_id`)

### OAuth Callback
1. `AuthCallbackPage.vue` processes URL query params on mount
2. Success tokens: `setTokensFromOAuth({access_token, refresh_token})` → `fetchCurrentUser()` → save to PouchDB
3. Account linked: `?linked={provider}` → success message → redirect to `/settings` after 1.5s
4. Error `email_exists`: shows conflict message, login redirect points to `/settings` for account linking
5. Error `already_linked`: shows provider already linked message
6. New user flag: `?new_user=true` → shows account created message

## Frontend Internals

### Boot Order (`quasar.config.js`)
Boots execute in order: `i18n` → `axios` → `auth`. The `auth` boot calls `initializeAuth()` and sets up router navigation guards.

### Axios Configuration (`services/frontend/src/boot/axios.ts`)
- **Base URL:** Dynamic — if accessing via IP/localhost, uses `protocol://hostname:8000`; if via domain, uses `API_URL` env var
- **Timeout:** 30s
- **Request interceptor:** Attaches `Authorization: Bearer {token}` from auth store
- **Response interceptor:** On 401 (non-auth endpoint), retries once after `refreshToken()`; if refresh fails → logout → redirect to `/login`

### Sync System (`services/frontend/src/services/pouchdb/index.ts`)
- **Database:** PouchDB `'wishwithme'` with `auto_compaction: true`
- **Indexes:** 8 Mango indexes on (type), (type, owner_id), (type, wishlist_id), etc.
- **Sync cycle:** `pushToServer()` → `pullFromServer()` → reconcile (delete local docs absent from server)
- **Push:** Reads changes feed ONCE, groups by type, filters by ownership (marks by `marked_by`, bookmarks by `user_id`, users by `_id`), sends per-collection. Handles conflicts: if `server_document` returned, accept it; otherwise track as `failedPushDocIds` to skip reconciliation
- **Pull:** Fetches all 6 collections in parallel (`Promise.all`), upserts each doc, then reconciles: local docs not in server response are soft-deleted UNLESS they weren't in the push batch or are in `failedPushDocIds`
- **Polling interval:** 30s (`setInterval`), also syncs on `window.online` event
- **Debounce:** `triggerSync()` coalesces calls within 1s (`SYNC_DEBOUNCE_MS = 1000`)
- **Fetch timeout:** 30s per request (`SYNC_FETCH_TIMEOUT_MS = 30000`)
- **Token refresh on 401:** `fetchWithTokenRefresh()` retries once after calling `tokenManager.refreshToken()`
- **Cleanup on logout:** `destroyDatabase()` → `db.destroy()` (deletes IndexedDB). Also `clearDatabase()` available (soft-deletes all docs without destroying IndexedDB)
- **Subscription pattern:** `subscribeToChanges(type, callback, filter)` → initial `find()` + live `changes({since: 'now', live: true})` → re-queries on any change of matching type
- **`onSyncComplete(callback)`:** Global listener pattern — components subscribe to sync completion events (e.g., `WishlistsPage` refreshes data after sync). Returns unsubscribe function. Notified via `notifySyncComplete()` after each sync cycle.
- **`SyncStatus` type:** `'idle' | 'syncing' | 'paused' | 'error' | 'offline'` (paused is defined but not currently used)
- **Tombstone recovery:** `find()` catches `TypeError` from evaluating selectors on tombstone docs → runs `compact()` → retries query
- **Startup compact:** Database runs `compact()` on creation (in addition to `auto_compaction: true`)

### Auth Store (`services/frontend/src/stores/auth.ts`)
- **State:** `user`, `accessToken`, `refreshTokenValue`, `isLoading`
- **localStorage keys:** `refresh_token`, `access_token`, `user_data`
- **Init sequence:** `initializeAuth()` → restore from localStorage → if token still valid (>2min to expiry), schedule refresh; else refresh immediately
- **Proactive refresh:** `scheduleTokenRefresh()` → `setTimeout` at `(expiry - now - 2min)` → calls `refreshToken()` → schedules next
- **Token refresh:** POST `/api/v2/auth/refresh` → stores new tokens → schedules next refresh → fetches user if not loaded
- **User in PouchDB:** After `fetchCurrentUser()`, also `upsert()` user doc to PouchDB for offline access
- **Profile update:** `updateUser()` → update PouchDB → update local state immediately → `triggerSync()`

### Wishlist/Item Stores
- **Pattern:** Pinia store → PouchDB subscription on init → reactive `ref<>` arrays
- **Wishlist store:** `subscribeToWishlists(userId, callback)` filters by `owner_id === userId`
- **Item store:** `subscribeToItems(wishlistId, callback)` filters by `wishlist_id`
- **Create:** Generate `createId(type)` → `upsert()` to PouchDB → `triggerSync()` (or offline notification)
- **Item status:** URL items start as `status: 'pending'` (with `source_url`); manual items as `status: 'resolved'`
- **Item access:** Inherited from parent wishlist's `access` array at creation time
- **Price conversion:** PouchDB `ItemDoc` stores `price` as `number|null`; `docToItem()` converts to `String(price)`; `createItem()` converts back via `parseFloat(data.price)`. Frontend `Item` type also has `resolver_metadata: Record<string, any> | null` (not in PouchDB type).
- **Retry resolve:** Sets `status: 'pending'` → `triggerSync()` → server re-processes via changes watcher

### Offline Behavior
- All data in PouchDB (IndexedDB) → reads never hit network
- `useOnline()` from `@vueuse/core` tracks connectivity
- Optimistic creates: write to PouchDB immediately, sync later
- Offline notification: Quasar `Notify.create({icon: 'cloud_off', color: 'info'})`
- Auto-sync on reconnect: `window.addEventListener('online', doSync)`

### Router Guards (`services/frontend/src/boot/auth.ts`)
- `router.beforeEach`: checks `to.meta.requiresAuth`
- Unauthenticated → redirect to `/login?redirect={fullPath}`
- Share token preservation: if redirecting from `/s/:token`, saves token to `localStorage('pending_share_token')`
- Authenticated users on `/login` or `/register` → redirect to `/wishlists`

### Layouts
- **MainLayout:** Header with SyncStatus indicator, OfflineBanner, AppInstallPrompt; wraps all authenticated pages
- **AuthLayout:** Centered card layout for login/register/callback; no navigation bar

### i18n (`services/frontend/src/boot/i18n.ts`)
- **Locales:** `en`, `ru` (default: `ru`, fallback: `ru`)
- **localStorage key:** `wishwithme_locale`
- **Detection:** Saved preference → browser language (`navigator.language`) → default `ru`
- **12 key sections:** `home`, `common`, `auth`, `wishlists`, `items`, `profile`, `errors`, `validation`, `oauth`, `sharing`, `offline`, `pwa`
- **Captured at registration:** Sent as `locale` field in `RegisterRequest`; stored in user doc

### ItemCard States (`services/frontend/src/components/items/ItemCard.vue`)
- **`pending`:** Shows resolving badge (animated), no price/description yet
- **`resolved`:** Shows "auto-filled" badge if has `source_url`, displays extracted metadata
- **`error`:** Shows error badge + retry button; retry sets `status: 'pending'` → `triggerSync()`
- Price displayed as formatted `{amount} {currency}`; image shown if `image_base64` available

## Core API Internals

### Token Rotation (`services/core-api/app/services/auth_couchdb.py`)
- `refresh_tokens` array stored in user doc, each entry: `{token_hash, device_info, expires_at, revoked, created_at}`
- **Hash:** SHA-256 via `hash_token()` (tokens never stored in plaintext)
- **Refresh flow:** Find user by `$elemMatch{token_hash, revoked: false}` → validate expiry → revoke old → create new → append → cleanup
- **Cleanup:** Remove tokens where `revoked=true` AND expired; keep max 10 active per user
- **Timing-safe login:** On invalid email, still runs `verify_password()` against dummy hash to prevent timing attacks
- **Default avatar:** `DEFAULT_AVATAR_BASE64` assigned at registration

### Push Validation (`services/core-api/app/routers/sync_couchdb.py`)
Per-collection authorization:
- **wishlists:** `owner_id == user_id`
- **items:** user in parent wishlist's `access` array
- **marks:** `marked_by == user_id`
- **bookmarks:** `user_id == user_id` (implicit, filtered by user)
- **users:** `_id == user_id`; strips sensitive fields (`password_hash`, `email`, `refresh_tokens`)
- **shares:** `owner_id == user_id`

**Access array computation on new docs:**
- wishlists: `[user_id]`
- items: inherited from wishlist's `access`
- marks: all wishlist `access` members EXCEPT `owner_id`
- users/shares/bookmarks: `[user_id]`

**LWW:** Compare `client_updated_at` vs `server_updated_at` (string comparison). Client wins if newer. Exception: `_deleted` docs always accepted even if older. Server sets `_rev` from existing doc. Conflict response includes `server_document` for client to accept.

**Important push details:**
- Server **overwrites** `updated_at` with server time (`datetime.now(UTC)`) on every successful push (both updates and new docs). Future LWW comparisons use this server-set timestamp.
- If client doc omits `access` field and doc is not deleted, server preserves existing `access` array from server doc.
- New docs sent with `_deleted: true` are silently skipped (nothing to delete).
- **Bookmarks** push has no explicit ownership authorization check in the push handler — access is controlled only via the `access: [user_id]` array set on new bookmarks. Existing bookmarks are not validated for ownership at push time.

### Pull Logic
- Mango selector: `{type: doc_type, access: {$elemMatch: {$eq: user_id}}}`
- **marks:** Additional `owner_id: {$ne: user_id}` (surprise mode)
- **users:** Only own doc `{type: 'user', _id: user_id}`
- **shares:** `{type: 'share', owner_id: user_id, revoked: {$ne: true}}`
- Limit 1000 docs per collection; filter `_deleted`; sort by `updated_at` desc in Python

### OAuth Flow (`services/core-api/app/services/oauth.py`)
- **State:** HMAC-SHA256 signed: `nonce:action:user_id:timestamp:callback_b64:signature` (backward compat with 5-part)
- **Expiry:** 15 minutes (`time.time() - timestamp > 900`)
- **Actions:** `login` (create/authenticate user), `link` (attach provider to existing account)
- **Callback:** Exchange code → get user info from provider → `authenticate_or_create()`

**`authenticate_or_create()` logic (3 paths):**
1. **Social account exists** → login existing user. Update: name always, avatar only if still DEFAULT, birthday only if blank.
2. **Email matches existing user** → **auto-link** (no confirmation). Safe because Google/Yandex verify email. Creates `social_account` doc + logs in.
3. **New user** → Create user + social account. User `_id` is plain `uuid4()` (NOT `user:{uuid}` prefix). Email fallback: `{provider_user_id}@{provider}.oauth`. Locale hardcoded `"en"`.

- **Social account doc:** `_id: social:{provider}:{provider_user_id}`, type `social_account`, stores `profile_data` with raw provider data
- **Avatar download:** HTTPS only, 5MB max, 10s timeout, 3 redirects max, must be `image/*` content-type
- **Duplicate link:** Provider already linked → `DuplicateLinkError` → redirect with `?error=already_linked`
- **Unlink guard:** Cannot unlink if it's the only auth method (no password + no other social account)
- **Account linking:** `/link/initiate` → authorize URL with `action=link, user_id` in state → callback links account

### Grant-Access Flow (`services/core-api/app/routers/shared.py`)
1. Validate share token (non-revoked, non-expired via Mango query)
2. Add user to `share.granted_users[]`, increment `access_count`
3. `db.update_access_arrays(wishlist_id, user_id, action='add')` → cascades to items and marks
4. Create/update bookmark: ONE per wishlist (not per share link), latest share's permissions win
5. Bookmark caches: `owner_name`, `owner_avatar_base64`, `wishlist_name`, `wishlist_icon`, `wishlist_icon_color`

*Note: Bookmark cached data (owner name/avatar, wishlist name/icon) can become stale if the owner updates their profile or wishlist. Cached values are refreshed only when re-following a share link.*

### CouchDB Client (`services/core-api/app/couchdb.py`)
- Basic auth via aiohttp `ClientSession(auth=BasicAuth)`, singleton pattern via `get_couchdb()`
- Methods: `get`, `put`, `delete`, `bulk_docs`, `find` (Mango), `find_one`, `view`, `db_info`
- `generate_id(type)` → `{type}:{uuid4}`
- `update_access_arrays(wishlist_id, user_id, action)`:
  - Updates wishlist `access` array
  - Finds all non-deleted items in wishlist → `bulk_docs` update their `access` arrays
  - Does **NOT** cascade to marks (mark access is computed at push time from wishlist access minus owner)
- `get_user_by_email` → CouchDB view `app/users_by_email` (NOT Mango — uses a design doc view for efficiency)

**Required CouchDB design document** (must be created during setup):
```json
{
  "_id": "_design/app",
  "views": {
    "users_by_email": {
      "map": "function(doc) { if (doc.type === 'user' && doc.email) { emit(doc.email, null); } }"
    }
  }
}
```
This view is queried with `key=email.lower()`, `include_docs=True`. Without it, user login by email will fail.
- `create_user` → generates `user:{uuid}` ID, sets `access: [user_id]`, email lowercased
- `create_mark` → access = `[uid for uid in viewer_access if uid != owner_id]` (surprise mode)
- `create_share` → default `link_type="mark"`, sets `access: [owner_id]`
- Convenience methods: `create_user`, `create_wishlist`, `create_item`, `create_mark`, `create_share`

## Item Resolver Internals

### LLM Clients (`services/item-resolver/app/llm.py`)
- **Vision client** (`OpenAILikeClient`): Sends page screenshot + image candidates list + JSON schema. Uses `image_url` content block. For GPT-4, Claude, etc.
- **Text client** (`DeepSeekTextClient`): Sends cleaned HTML + structured hints + image candidates. Detailed price extraction rules (Russian prices, thousand separators, sale vs old price). For DeepSeek-chat and non-vision models.
- **Auto-detection:** `LLM_CLIENT_TYPE=auto` → if model name contains `deepseek` (without `vl`) → text; if contains `gpt-4`/`claude` → vision; else → text (safer default)
- **Settings:** `temperature=0`, JSON-only output, schema: `{title, description, price_amount, price_currency, canonical_url, confidence, image_url}`
- **JSON extraction:** Try `json.loads()` first, then find `{...}` substring as fallback
- **Stub mode:** `LLM_MODE=stub` returns title from page, null for everything else (testing)

### HTML Optimization (`services/item-resolver/app/html_optimizer.py`)
1. `extract_structured_hints(html)`: Extracts OG tags (`og:title`, `og:description`, `og:image`, `og:price:amount`, `og:price:currency`) and JSON-LD `schema.org/Product` data (`name`, `description`, `offers.price`, `offers.priceCurrency`). Handles `@graph` wrapper.
2. `optimize_html(html)`: Strip `<script>`, `<style>`, `<noscript>`, `<svg>`, HTML comments → collapse whitespace → truncate at `max_chars` (default 100k)
3. `format_html_for_llm()`: Combines URL + title + structured hints section (with PRICE prominently listed) + cleaned HTML

### Image Extraction (`services/item-resolver/app/html_parser.py`)
- `HTMLParser` subclass extracts `<img>` tags with all attributes
- **Filters out:** images <50px (both dimensions), patterns matching `/\bicon\b/`, `/\blogo\b/`, `/\bbadge\b/`, `/\bsprite\b/`, `/\bplaceholder\b/`, `/\bpixel\b/`, `/\btracking\b/`, `/\b1x1\b/`, `/\bavatar\b/`, `/\buser\b/`, `/\bprofile\b/`, `.gif$`
- Resolves relative URLs via `urljoin(base_url, src)`; skips `data:` URIs
- `format_images_for_llm()`: Max 20 candidates, numbered list with src/alt/title/class

### Browser Pool (`services/item-resolver/app/browser_manager.py`)
- **Concurrency:** `asyncio.Semaphore(MAX_CONCURRENCY)` (default 2)
- **Stealth:** `playwright_stealth` with `navigator_languages_override=('ru-RU', 'ru', 'en-US', 'en')`
- **4 rotating UA profiles:** Windows Chrome 121/122, macOS Safari 16.4, Linux Chrome 120. All with Moscow geolocation (55.7558, 37.6173)
- **Anti-detection args:** `--disable-blink-features=AutomationControlled`, `--no-sandbox`, `--disable-web-security`, `--window-size=1920,1080`
- **Proxy:** `PROXY_SERVER/USERNAME/PASSWORD/BYPASS` env vars → Playwright proxy config
- **Storage state:** Per-domain persistence (registrable domain heuristic for eTLD+1), merges legacy per-host files
- **Cookies:** Yandex Market (7 cookies: `_ym_uid`, `_ym_d`, `yandexuid`, `yuidss`, `i`, `yandex_gid`, `_ym_isad`), AliExpress (`aep_usuc_f` with `site=rus&c_tp=RUB`)

### Page Capture Flow (`services/item-resolver/app/scrape.py`)
1. `page.goto(url, wait_until='load', timeout=90s)`
2. Wait for `<body>` to have content (10s timeout)
3. Dismiss popups: 20+ Russian/English button texts ("Понятно", "Принять", "Accept", "OK", "Да", "×", etc.) + CSS close-button selectors
4. Network quiet: No requests for 2s (`wait_for_network_quiet`)
5. DOM stable: 3 consecutive samples with same `(htmlLen, textLen)` at 500ms intervals
6. Settle: 5s sleep for async JS rendering
7. Challenge detection: Check for captcha/bot keywords in title+HTML → if detected, wait up to 120s for challenge to clear (checks title cleanup + product content indicators like prices/cart buttons)
8. Post-challenge: Extra 3s settle + re-stabilize network/DOM

### Changes Watcher State Machine (`services/item-resolver/app/changes_watcher.py`)
```
listen(_changes feed, filter: {type: 'item', status: 'pending'})
  → claim(optimistic lock: update _rev, set status='in_progress', claimed_by=INSTANCE_ID, lease_expires_at=now+300s)
    → ConflictError = another instance claimed it, skip
  → resolve(validate URL → capture page → extract via LLM)
  → update(re-fetch doc _rev, verify still owned by us + not already resolved, write results)
    → ConflictError: retry up to 3 times with re-fetch
  → error(set status='error', resolve_error=message[:200])
```
- **One at a time:** `self._processing` flag prevents concurrent resolution
- **Heartbeat:** 30s on changes feed connection
- **Reconnect:** Exponential backoff 1s → 2s → 4s → ... → 60s max
- **Sweep loop:** Every 60s, finds `{status: 'in_progress', lease_expires_at < now}` → resets to `pending`
- **Safety checks on update:** Verifies `claimed_by == INSTANCE_ID` and `status != 'resolved'` before writing

### Image Processing (`services/item-resolver/app/image_utils.py`)
- **Crop algorithm:** Edge projection (Sobel filter → row/col activity → bounding box) → fallback to largest connected component (flood-fill on non-background pixels) → fallback to `ImageChops.difference` bbox
- **Output:** JPEG quality=75, alpha composited to white background

## Infrastructure Details

### Docker Compose
- **7 services:** nginx, couchdb, core-api-1, core-api-2, frontend, item-resolver-1, item-resolver-2
- **Health checks:** All services have health checks with `condition: service_healthy` dependencies
- **Item resolver:** `shm_size: '1gb'` (for Playwright Chrome), resource limits `1 CPU / 2GB mem`, reservations `0.5 CPU / 1GB`
- **Volumes:** `couchdb_data` bind-mounted to `/home/mrkutin/wishwithme-data/couchdb`; `item_resolver_storage_1/2` named volumes for browser storage state
- **Network:** Single bridge network `wishwithme-network`

### Nginx (`nginx/nginx.conf`)
- **Two HTTPS servers:**
  - `wishwith.me` → frontend (static PWA) + `/api/` proxy to core-api + `/couchdb/` proxy to CouchDB
  - `api.wishwith.me` → core-api (all API) + `/resolver/` proxy to item-resolver + `/couchdb/` proxy
- **Load balancing:** `least_conn` for core-api (2 instances) and item-resolver (2 instances)
- **CouchDB proxy:** `proxy_buffering off` for `_changes` feed streaming, 300s read/send timeout (must exceed changes watcher 30s heartbeat), 50MB body limit
- **CORS preflight:** OPTIONS → 204 with `Access-Control-Allow-Origin: https://wishwith.me`, max-age 86400
- **Static asset caching:** `*.js|css|png|...` → 1yr `immutable`; `sw.js` → `no-cache, no-store, must-revalidate`; `manifest.json` → 1 day
- **SSL:** TLSv1.2+1.3, ECDHE ciphers, HTTP/2, HSTS max-age 63072000 (2yr)
- **Gzip:** Level 6, text/css/json/js/xml/svg
- **Security headers:** X-Frame-Options SAMEORIGIN, X-Content-Type-Options nosniff, X-XSS-Protection, Referrer-Policy strict-origin-when-cross-origin
- **Resolver timeouts:** 180s read/send for `/resolver/` (LLM+scraping)

### CI/CD (`.github/workflows/deploy-ubuntu.yml`)
- **Trigger:** Push to `main` (path-filtered: `services/frontend/**`, `services/core-api/**`, `services/item-resolver/**`, `docker-compose.yml`, `nginx/**`) or manual dispatch
- **Change detection:** `git diff --name-only HEAD^ HEAD` to determine which services changed; manual dispatch deploys all
- **Parallel test jobs:** Frontend (Node 20, `npm ci` + `npm run test:unit`), Core API (Python 3.12, `pytest`), Item Resolver (Python 3.12, `pytest`)
- **Deploy:** SSH to server → save current commit as `.last-known-good-commit` → `git reset --hard origin/main` → selective `docker compose build --no-cache` + `up -d --no-deps --force-recreate` for changed services → 20s wait → health checks (internal container checks)
- **Rollback:** On failure → restore `.last-known-good-commit` → rebuild + restart affected services
- **Frontend rebuild trigger:** Also rebuilds frontend when core-api changes (API contract updates)

### Dockerfiles
- **item-resolver:** `mcr.microsoft.com/playwright/python:v1.49.0-jammy` base (Chrome pre-installed), `playwright install chrome`, runs as root (Playwright requirement)
- **core-api:** Multi-stage (`python:3.12-slim` builder + production), non-root `appuser`, venv-based, built-in HEALTHCHECK
- **frontend:** Multi-stage (`node:20-alpine` builder with `ARG API_URL` → `npm run build:pwa`), production stage `nginx:alpine`, copies built assets to `/usr/share/nginx/html`

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
