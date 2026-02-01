# CLAUDE.md - Wish With Me Development Guide

> Comprehensive project documentation for Claude Code to understand and develop this codebase effectively.

---

## Project Overview

**Wish With Me** is an offline-first wishlist Progressive Web Application (PWA) that allows users to:
- Create and manage wishlists with items
- Add items via URL (auto-extracts product metadata using LLM)
- Share wishlists with others via links
- Mark items as "taken" (surprise mode - hidden from owner)
- Work fully offline with automatic sync when online

**Production URL**: https://wishwith.me
**API URL**: https://api.wishwith.me

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vue 3 + Quasar Framework + TypeScript + Webpack |
| **State** | Pinia (stores) + PouchDB (offline storage) |
| **Backend API** | FastAPI + Python 3.12 + async/await |
| **URL Resolver** | FastAPI + Playwright + DeepSeek LLM |
| **Database** | CouchDB 3.3 (with PouchDB sync) |
| **Proxy** | nginx (SSL, load balancing) |
| **Deployment** | Docker Compose on Ubuntu server |
| **CI/CD** | GitHub Actions (auto-deploy on push to main) |

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
                      │   nginx   │ :80/:443
                      └─────┬─────┘
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    ┌──────────┐    ┌─────────────┐    ┌──────────┐
    │ frontend │    │  core-api   │    │ couchdb  │
    │  :80     │    │ (2 instances│    │  :5984   │
    └──────────┘    │  :8000)     │    └────┬─────┘
                    └──────┬──────┘         │
                           │                │
                    ┌──────┴──────┐         │
                    │item-resolver│◄────────┘
                    │ (2 instances│  watches _changes
                    │  :8000)     │
                    └─────────────┘
```

### Data Flow (Offline-First)

1. User writes data → **PouchDB** (local IndexedDB)
2. UI updates immediately from PouchDB
3. When online, PouchDB syncs to **CouchDB** via API
4. **item-resolver** watches CouchDB `_changes` feed
5. Pending items get resolved (URL → metadata via LLM)
6. Resolved data syncs back to PouchDB → UI updates

---

## Services

### Frontend (`services/frontend/`)

Vue 3 + Quasar PWA with offline-first architecture.

| Directory | Purpose |
|-----------|---------|
| `src/pages/` | Route pages (WishlistsPage, WishlistDetailPage, etc.) |
| `src/components/` | Reusable UI components (ItemCard, ShareDialog, etc.) |
| `src/composables/` | Vue composables (useSync, useOAuth) |
| `src/stores/` | Pinia stores (auth, wishlist, item) |
| `src/services/pouchdb/` | PouchDB wrapper for offline storage |
| `src/i18n/` | Translations (Russian, English) |
| `src-pwa/` | Service worker and PWA manifest |

**Key Files:**
- `quasar.config.js` - Build configuration
- `src/boot/axios.ts` - HTTP client with token refresh
- `src/boot/auth.ts` - Auth guards and session restoration
- `src/services/pouchdb/index.ts` - All database operations

### Core API (`services/core-api/`)

FastAPI backend handling auth, sync, and sharing.

| Directory | Purpose |
|-----------|---------|
| `app/routers/` | API endpoints |
| `app/schemas/` | Pydantic request/response models |
| `app/services/` | Business logic |
| `app/` | Core modules (couchdb.py, security.py, config.py) |

**Key Files:**
- `app/main.py` - FastAPI application entry
- `app/couchdb.py` - Async CouchDB client
- `app/security.py` - JWT and password utilities
- `app/config.py` - Pydantic settings

### Item Resolver (`services/item-resolver/`)

Extracts product metadata from URLs using Playwright + LLM.

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app with factory pattern |
| `app/changes_watcher.py` | Watches CouchDB for pending items |
| `app/scrape.py` | Playwright page capture |
| `app/llm.py` | DeepSeek integration for extraction |
| `app/ssrf.py` | SSRF protection |

---

## API Endpoints

### Authentication (`/api/v2/auth`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/register` | Register with email/password |
| POST | `/login` | Login, get tokens |
| POST | `/refresh` | Refresh access token |
| POST | `/logout` | Revoke refresh token |
| GET | `/me` | Get current user |

### OAuth (`/api/v1/oauth`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/providers` | List enabled OAuth providers |
| GET | `/{provider}/authorize` | Start OAuth flow |
| GET | `/{provider}/callback` | Handle OAuth callback |

### Sync (`/api/v2/sync`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/pull/{collection}` | Pull documents (wishlists/items/marks/bookmarks) |
| POST | `/push/{collection}` | Push documents with LWW conflict resolution |

### Sharing (`/api/v1/wishlists/{id}/share`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | List share links |
| POST | `/` | Create share link |
| DELETE | `/{share_id}` | Revoke share link |

### Shared Access (`/api/v1/shared`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/{token}/preview` | Preview (no auth required) |
| POST | `/{token}/grant-access` | Grant access to user |
| POST | `/{token}/items/{item_id}/mark` | Mark item as taken |
| DELETE | `/{token}/items/{item_id}/mark` | Unmark item |

### Item Resolver (`/resolver/v1`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/resolve` | Extract metadata from URL |
| GET | `/healthz` | Health check (requires bearer token) |

---

## Database Schema (CouchDB)

All documents use type-prefixed IDs: `{type}:{uuid}`

### User
```json
{
  "_id": "user:abc123",
  "type": "user",
  "email": "user@example.com",
  "password_hash": "bcrypt...",
  "name": "User Name",
  "locale": "ru",
  "access": ["user:abc123"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Wishlist
```json
{
  "_id": "wishlist:def456",
  "type": "wishlist",
  "owner_id": "user:abc123",
  "name": "Birthday Wishlist",
  "description": "My birthday wishes",
  "icon": "gift",
  "access": ["user:abc123", "user:xyz789"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Item
```json
{
  "_id": "item:ghi789",
  "type": "item",
  "wishlist_id": "wishlist:def456",
  "owner_id": "user:abc123",
  "title": "Product Name",
  "description": "Description",
  "price": 1500.00,
  "currency": "RUB",
  "source_url": "https://...",
  "image_base64": "data:image/...",
  "status": "resolved",
  "access": ["user:abc123", "user:xyz789"],
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Mark (Surprise Mode)
```json
{
  "_id": "mark:jkl012",
  "type": "mark",
  "item_id": "item:ghi789",
  "wishlist_id": "wishlist:def456",
  "owner_id": "user:abc123",
  "marked_by": "user:xyz789",
  "quantity": 1,
  "access": ["user:xyz789"],
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Note**: Marks exclude `owner_id` from `access` array so wishlist owner cannot see who marked items (surprise mode).

### Share
```json
{
  "_id": "share:mno345",
  "type": "share",
  "wishlist_id": "wishlist:def456",
  "owner_id": "user:abc123",
  "token": "random32charstring",
  "link_type": "mark",
  "expires_at": null,
  "granted_users": ["user:xyz789"],
  "access": ["user:abc123"]
}
```

---

## Key Patterns

### Access Control
Every document has an `access` array containing user IDs who can read it:
```python
# Query for user's wishlists
selector = {"type": "wishlist", "access": {"$elemMatch": {"$eq": user_id}}}
```

### Offline-First Sync
```typescript
// Frontend writes to PouchDB first
await pouchdb.put(doc);
// Then triggers sync when online
if (navigator.onLine) {
  await triggerSync();
}
```

### LWW Conflict Resolution
Server uses Last-Write-Wins based on `updated_at`:
```python
if client_updated_at > server_updated_at:
    # Client wins - accept update
else:
    # Server wins - return conflict
```

### Soft Deletes
Documents use `_deleted: true` marker:
```python
doc["_deleted"] = True
doc["updated_at"] = now()
await db.put(doc)
```

---

## Development Commands

### Frontend (`services/frontend/`)
```bash
npm install          # Install dependencies
npm run dev          # Dev server at localhost:9000
npm run build        # Production build
npm run lint         # ESLint
npm run test:unit    # Vitest unit tests
npm run typecheck    # TypeScript check
```

### Backend (`services/core-api/`)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
ruff check .         # Linting
pytest               # Run tests
```

### Item Resolver (`services/item-resolver/`)
```bash
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8001
pytest               # Run tests
```

### Docker (local)
```bash
docker-compose up -d                    # Start all services
docker-compose logs -f                  # View logs
docker-compose down                     # Stop services
```

---

## Deployment

### Server Details
- **IP**: 176.106.144.182
- **User**: mrkutin
- **Path**: `/home/mrkutin/wish-with-me-codex`
- **Compose File**: `docker-compose.ubuntu.yml`
- **Credentials**: See `.credentials.local` file (gitignored)

### SSH Access
```bash
# Read credentials from .credentials.local and SSH to server
# Password is stored in SSH_PASSWORD variable
sshpass -p "$(grep SSH_PASSWORD .credentials.local | cut -d= -f2)" ssh mrkutin@176.106.144.182
```

### Auto-Deploy (GitHub Actions)
Push to `main` branch triggers `.github/workflows/deploy-ubuntu.yml`:
1. Detects changed services
2. SSH to server, git pull
3. Rebuilds changed containers
4. Health check
5. Rollback on failure

**NOTE**: Always deploy fixes without asking for confirmation. Commit, push to main, and monitor the deployment.

### Manual Deploy
```bash
ssh mrkutin@176.106.144.182
cd /home/mrkutin/wish-with-me-codex
git pull origin main
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

### Check Logs
```bash
# All services
docker-compose -f docker-compose.ubuntu.yml logs -f

# Specific service
docker logs wishwithme-core-api-1 --tail=100
docker logs wishwithme-item-resolver-1 --tail=100
```

### Health Checks
```bash
curl -sf https://wishwith.me/healthz
curl -sf https://api.wishwith.me/healthz
```

---

## Environment Variables

### Core API
```bash
COUCHDB_URL=http://couchdb:5984
COUCHDB_DATABASE=wishwithme
COUCHDB_ADMIN_USER=admin
COUCHDB_ADMIN_PASSWORD=secret
JWT_SECRET_KEY=your-32-char-secret
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
YANDEX_CLIENT_ID=...
YANDEX_CLIENT_SECRET=...
```

### Item Resolver
```bash
COUCHDB_URL=http://couchdb:5984
COUCHDB_DATABASE=wishwithme
COUCHDB_WATCHER_ENABLED=true
RU_BEARER_TOKEN=service-token
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
```

### Frontend (build-time)
```bash
API_URL=https://api.wishwith.me
```

---

## Code Conventions

### Python (Backend)
- **Style**: Ruff linter, 88 char lines
- **Types**: Full type hints with `typing.Annotated`
- **Async**: All I/O operations are async
- **Naming**: snake_case for files/functions, PascalCase for classes
- **Errors**: Structured errors with codes (e.g., `SSRF_BLOCKED`, `TIMEOUT`)

### TypeScript (Frontend)
- **Style**: ESLint + Prettier, single quotes
- **Components**: Vue 3 Composition API with `<script setup lang="ts">`
- **Stores**: Pinia with composition style
- **Naming**: camelCase for files/functions, PascalCase for components/interfaces

### Document IDs
Always use type-prefixed UUIDs:
```python
user_id = f"user:{uuid4()}"
wishlist_id = f"wishlist:{uuid4()}"
item_id = f"item:{uuid4()}"
```

### API Responses
Standard error format:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

---

## Security Checklist

When making changes, verify:

- [ ] Input validation via Pydantic schemas
- [ ] Access control checks on document operations
- [ ] No SQL/NoSQL injection (use parameterized queries)
- [ ] SSRF protection for URL fetching
- [ ] JWT tokens properly validated
- [ ] Sensitive data not logged
- [ ] CORS configured correctly
- [ ] No secrets in code (use environment variables)

---

## Testing on Production

**Always test changes on the production server:**

```bash
# SSH to server
ssh mrkutin@176.106.144.182

# Check service status
docker-compose -f docker-compose.ubuntu.yml ps

# Check logs for errors
docker logs wishwithme-core-api-1 --tail=100
docker logs wishwithme-item-resolver-1 --tail=100

# Test health endpoints
curl -sf https://wishwith.me/healthz
curl -sf https://api.wishwith.me/healthz

# Test specific functionality with curl
curl -X POST https://api.wishwith.me/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"password"}'
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

---

## Agent Usage Requirements

**IMPORTANT**: Always use the appropriate specialized agent for each task. This ensures higher quality work and proper domain expertise.

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

1. **Always explore first**: Before making changes, use `Explore` agent to understand the codebase context
2. **Plan before implementing**: For non-trivial features, use `Plan` agent to design the approach
3. **Match agent to domain**:
   - Frontend changes → `frontend-dev`
   - Backend changes → `backend-dev`
   - Both → use both agents in parallel
4. **Review after changes**: Use `reviewer` agent after implementing significant changes
5. **Security-sensitive code**: Always involve `security` agent for auth, input validation, or data access changes
6. **Run agents in parallel**: When tasks are independent, launch multiple agents simultaneously

---

## Workflow: Bug Fix

**All bug fixes MUST follow this workflow:**

```
┌─────────────────────────────────────────────────────────────────┐
│  1. INVESTIGATE                                                 │
│     └─► Explore agent: find the bug location                    │
│     └─► devops agent: if infrastructure/deployment issue        │
├─────────────────────────────────────────────────────────────────┤
│  2. FIX                                                         │
│     └─► frontend-dev / backend-dev: implement the fix           │
├─────────────────────────────────────────────────────────────────┤
│  3. UNIT TESTS                                                  │
│     └─► qa agent: run ALL unit tests                            │
│     └─► If tests fail → back to step 2                          │
├─────────────────────────────────────────────────────────────────┤
│  4. VERIFY                                                      │
│     └─► reviewer agent: code quality check                      │
│     └─► devops agent: deployment/integration check (if needed)  │
│     └─► If bug not fixed → back to step 2                       │
├─────────────────────────────────────────────────────────────────┤
│  5. DONE                                                        │
│     └─► Only when fix verified and all tests pass               │
└─────────────────────────────────────────────────────────────────┘
```

**Bug Fix Rules:**
- Never skip unit tests before verification
- Loop between FIX → TEST → VERIFY until the bug is confirmed fixed
- For infrastructure bugs, `devops` leads investigation; for code bugs, `Explore` + dev agents lead

---

## Workflow: New Feature

**All new features MUST follow this workflow:**

```
┌─────────────────────────────────────────────────────────────────┐
│  1. ARCHITECTURE CHECK                                          │
│     └─► system-architect agent: verify feature fits architecture│
│     └─► If conflicts exist → DISCUSS with user before proceeding│
│     └─► Agree on approach before moving forward                 │
├─────────────────────────────────────────────────────────────────┤
│  2. PLAN                                                        │
│     └─► Plan agent: create detailed implementation plan         │
│     └─► Get user approval on the plan                           │
├─────────────────────────────────────────────────────────────────┤
│  3. IMPLEMENT                                                   │
│     └─► frontend-dev / backend-dev: write the code              │
├─────────────────────────────────────────────────────────────────┤
│  4. WRITE TESTS                                                 │
│     └─► qa agent: write new unit tests for the feature          │
├─────────────────────────────────────────────────────────────────┤
│  5. RUN TESTS                                                   │
│     └─► qa agent: run ALL unit tests (new + existing)           │
│     └─► If tests fail → back to step 3                          │
├─────────────────────────────────────────────────────────────────┤
│  6. VERIFY                                                      │
│     └─► reviewer agent: code quality, security, maintainability │
│     └─► qa agent: functional testing                            │
│     └─► devops agent: deployment check (if needed)              │
│     └─► If issues found → back to step 3                        │
├─────────────────────────────────────────────────────────────────┤
│  7. DONE                                                        │
│     └─► Only when all tests pass and verification complete      │
└─────────────────────────────────────────────────────────────────┘
```

**New Feature Rules:**
- NEVER skip architecture check - features must fit the existing design
- If architecture conflict: STOP and discuss with user before proceeding
- All new features MUST have unit tests before verification
- Loop between IMPLEMENT → TEST → VERIFY until fully working
- Only mark complete when all agents confirm success

---

## Workflow Examples

### Bug Fix Example
```
User: "The sync is failing after adding items"

Step 1 - INVESTIGATE:
  → Explore agent: search for sync-related code, find the issue

Step 2 - FIX:
  → backend-dev agent: fix the sync logic

Step 3 - UNIT TESTS:
  → qa agent: run `pytest` for backend
  → If fails: back to backend-dev

Step 4 - VERIFY:
  → reviewer agent: check the fix quality
  → devops agent: verify sync works in docker environment
  → If still broken: back to backend-dev

Step 5 - DONE
```

### New Feature Example
```
User: "Add wishlist categories"

Step 1 - ARCHITECTURE CHECK:
  → system-architect agent: check if categories fit current data model
  → If conflicts: discuss with user (e.g., "Categories would require
    schema changes. Should we add category_id to wishlists or create
    a separate categories collection?")

Step 2 - PLAN:
  → Plan agent: design implementation (DB schema, API endpoints, UI)
  → Get user approval

Step 3 - IMPLEMENT:
  → backend-dev agent: add category model, API endpoints
  → frontend-dev agent: add category UI components

Step 4 - WRITE TESTS:
  → qa agent: write tests for category CRUD operations

Step 5 - RUN TESTS:
  → qa agent: run all tests
  → If fails: back to dev agents

Step 6 - VERIFY:
  → reviewer agent: code review
  → qa agent: functional testing
  → If issues: back to dev agents

Step 7 - DONE
```

---

### Agent Invocation

Agents are invoked using the Task tool with `subagent_type` parameter:
- Single agent: Provide detailed context in the prompt
- Multiple agents: Launch in parallel when tasks are independent
- Sequential agents: Wait for one to complete before starting dependent work
