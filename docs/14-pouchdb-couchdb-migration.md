# Migration Plan: RxDB+PostgreSQL → PouchDB+CouchDB

> Implementation plan for migrating Wish With Me to a "sync and forget" architecture.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Vue + Quasar PWA)                                │
│  PouchDB ←──live sync──► CouchDB (JWT auth)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  CouchDB 3.x (single DB: wishwithme)                        │
│  Documents: user, wishlist, item, mark, share               │
│  Access control via access[] arrays + selector replication  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI - minimal)                                │
│  - Auth (register/login → JWT)                              │
│  - Sharing (create/revoke → update access arrays)           │
│  - Item Resolver (watches _changes, resolves URLs)          │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: CouchDB Infrastructure

### 1.1 Install & Configure CouchDB

**Tasks:**
- [ ] Install CouchDB 3.x on Ubuntu server (176.106.144.182)
- [ ] Configure single-node setup (sufficient for <100K docs)
- [ ] Enable CORS for frontend domain (wishwith.me)
- [ ] Configure JWT authentication
- [ ] Set up admin credentials
- [ ] Create `wishwithme` database

**CouchDB Configuration (`local.ini`):**
```ini
[chttpd]
port = 5984
bind_address = 0.0.0.0

[chttpd_auth]
authentication_handlers = {chttpd_auth, jwt_authentication_handler}, {chttpd_auth, cookie_authentication_handler}, {chttpd_auth, default_authentication_handler}

[jwt_auth]
required_claims = exp, sub
algorithms = HS256

[cors]
origins = https://wishwith.me, http://localhost:9000
credentials = true
methods = GET, PUT, POST, DELETE, OPTIONS
headers = accept, authorization, content-type, origin, referer

[couchdb]
single_node = true
```

**JWT Secret Setup:**
```bash
# Set JWT secret (same as backend will use)
curl -X PUT http://admin:password@localhost:5984/_node/_local/_config/jwt_keys/hmac:_default \
  -d '"your-256-bit-secret"'
```

### 1.2 Design Documents

**Create indexes and validation:**

```javascript
// _design/app
{
  "_id": "_design/app",

  // Mango indexes for selector replication
  "views": {
    "by_type": {
      "map": "function(doc) { if(doc.type) emit(doc.type, null); }"
    },
    "pending_items": {
      "map": "function(doc) { if(doc.type === 'item' && doc.status === 'pending') emit(doc._id, null); }"
    }
  },

  // Validation function
  "validate_doc_update": "function(newDoc, oldDoc, userCtx) { ... }"
}
```

**Mango Index for access-based queries:**
```javascript
// POST /wishwithme/_index
{
  "index": {
    "fields": ["access"]
  },
  "name": "access-index",
  "type": "json"
}
```

### 1.3 Docker Setup

**Add to `docker-compose.ubuntu.yml`:**
```yaml
couchdb:
  image: couchdb:3.3
  container_name: wishwithme-couchdb
  restart: unless-stopped
  ports:
    - "5984:5984"
  environment:
    - COUCHDB_USER=${COUCHDB_ADMIN_USER}
    - COUCHDB_PASSWORD=${COUCHDB_ADMIN_PASSWORD}
  volumes:
    - couchdb_data:/opt/couchdb/data
    - ./couchdb/local.ini:/opt/couchdb/etc/local.d/local.ini
  networks:
    - wishwithme-network

volumes:
  couchdb_data:
```

---

## Phase 2: Document Schema Design

### 2.1 Document Types

**User Document:**
```javascript
{
  "_id": "user:<uuid>",
  "type": "user",
  "email": "user@example.com",
  "password_hash": "...",  // bcrypt
  "name": "John Doe",
  "avatar_base64": "...",
  "bio": "...",
  "public_url_slug": "john-doe",
  "locale": "en",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "access": ["user:<uuid>"]  // only self
}
```

**Wishlist Document:**
```javascript
{
  "_id": "wishlist:<uuid>",
  "type": "wishlist",
  "owner_id": "user:<uuid>",
  "name": "Birthday Wishlist",
  "description": "Things I want for my birthday",
  "icon": "🎂",
  "is_public": false,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "access": ["user:<uuid>"]  // owner + shared users
}
```

**Item Document:**
```javascript
{
  "_id": "item:<uuid>",
  "type": "item",
  "wishlist_id": "wishlist:<uuid>",
  "owner_id": "user:<uuid>",  // denormalized for filtering
  "title": "PlayStation 5",
  "description": "Digital Edition",
  "price": "499.99",
  "currency": "USD",
  "quantity": 1,
  "source_url": "https://amazon.com/...",
  "image_url": "https://...",
  "image_base64": null,
  "status": "resolved",  // pending | resolving | resolved | failed
  "resolution_error": null,
  "sort_order": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "access": ["user:<uuid>"]  // same as wishlist
}
```

**Mark Document:**
```javascript
{
  "_id": "mark:<uuid>",
  "type": "mark",
  "item_id": "item:<uuid>",
  "wishlist_id": "wishlist:<uuid>",  // denormalized
  "owner_id": "user:<uuid>",  // wishlist owner (to exclude from access)
  "marked_by": "user:<uuid>",  // who created this mark
  "quantity": 1,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "access": ["user:<viewer1>", "user:<viewer2>"]  // all viewers EXCEPT owner
}
```

**Share Document:**
```javascript
{
  "_id": "share:<uuid>",
  "type": "share",
  "wishlist_id": "wishlist:<uuid>",
  "owner_id": "user:<uuid>",
  "token": "abc123def456...",  // 32 char token
  "link_type": "mark",  // view | mark
  "expires_at": null,
  "access_count": 0,
  "revoked": false,
  "revoked_at": null,
  "granted_users": [],  // users who have accessed this share
  "created_at": "2024-01-01T00:00:00Z",
  "access": ["user:<uuid>"]  // only owner sees share docs
}
```

---

## Phase 3: Backend Changes

### 3.1 Remove PostgreSQL Dependencies

**Files to delete:**
- `services/core-api/app/models.py` (SQLAlchemy models)
- `services/core-api/app/database.py` (DB connection)
- `services/core-api/alembic/` (migrations)

**Dependencies to remove from `requirements.txt`:**
```
sqlalchemy
asyncpg
alembic
```

**Dependencies to add:**
```
couchdb
pycouchdb
pyjwt
```

### 3.2 New Backend Structure

```
services/core-api/app/
├── main.py
├── config.py
├── couchdb.py          # CouchDB client
├── auth/
│   ├── router.py       # /auth/register, /auth/login, /auth/refresh
│   ├── jwt.py          # JWT generation (CouchDB-compatible)
│   └── schemas.py
├── share/
│   ├── router.py       # /share (create, revoke, access)
│   └── schemas.py
└── health/
    └── router.py       # /health
```

### 3.3 Auth Endpoints

**POST /auth/register**
```python
@router.post("/register")
async def register(data: RegisterRequest):
    # Check if email exists
    # Create user doc in CouchDB
    # Generate JWT with sub=user_id
    # Return JWT
```

**POST /auth/login**
```python
@router.post("/login")
async def login(data: LoginRequest):
    # Find user by email
    # Verify password
    # Generate JWT with sub=user_id, exp=...
    # Return JWT
```

**JWT Payload (CouchDB-compatible):**
```json
{
  "sub": "user:uuid-123",
  "exp": 1234567890,
  "iat": 1234567800,
  "_couchdb.roles": []
}
```

### 3.4 Share Endpoints

**POST /share**
```python
@router.post("/share")
async def create_share(data: CreateShareRequest, user: User = Depends(get_current_user)):
    # Verify user owns wishlist
    # Create share doc
    # Update access[] on wishlist + all items
    # Return share token and URL
```

**POST /share/{token}/access**
```python
@router.post("/share/{token}/access")
async def access_share(token: str, user: User = Depends(get_current_user)):
    # Find share by token
    # Verify not expired/revoked
    # Add user to wishlist + items access[]
    # Add user to share.granted_users
    # Increment access_count
    # Return wishlist info
```

**DELETE /share/{token}**
```python
@router.delete("/share/{token}")
async def revoke_share(token: str, user: User = Depends(get_current_user)):
    # Verify user owns the share
    # Set revoked=true, revoked_at=now
    # Remove granted_users from wishlist + items access[]
    # Schedule cleanup after 30 days
```

### 3.5 Item Resolver Changes

**Watch CouchDB `_changes` feed:**
```python
# services/item-resolver/app/watcher.py

async def watch_pending_items():
    async for change in couchdb.changes_feed(
        filter="_selector",
        selector={"type": "item", "status": "pending"}
    ):
        item_id = change["id"]
        await resolve_item(item_id)

async def resolve_item(item_id: str):
    # Fetch item from CouchDB
    # Extract metadata via Playwright + LLM
    # Update item doc with status="resolved" + metadata
    # CouchDB → PouchDB sync handles the rest
```

---

## Phase 4: Frontend Changes

### 4.1 Remove RxDB

**Files to delete:**
```
services/frontend/src/services/rxdb/
├── database.ts
├── schemas.ts
├── replication.ts
└── index.ts
```

**Dependencies to remove:**
```
rxdb
rxdb-premium
dexie
```

**Dependencies to add:**
```
pouchdb-browser
pouchdb-find
@types/pouchdb-browser
@types/pouchdb-find
```

### 4.2 New PouchDB Service

**`services/frontend/src/services/pouchdb/database.ts`:**
```typescript
import PouchDB from 'pouchdb-browser';
import PouchDBFind from 'pouchdb-find';

PouchDB.plugin(PouchDBFind);

let localDB: PouchDB.Database | null = null;
let syncHandler: PouchDB.Replication.Sync<{}> | null = null;

export async function initDatabase(userId: string, jwt: string): Promise<PouchDB.Database> {
  // Create local database
  localDB = new PouchDB('wishwithme_local');

  // Create index on access field
  await localDB.createIndex({
    index: { fields: ['access', 'type'] }
  });

  // Setup live sync with selector
  const remoteDB = new PouchDB('https://api.wishwith.me/couchdb/wishwithme', {
    fetch: (url, opts) => {
      opts.headers.set('Authorization', `Bearer ${jwt}`);
      return fetch(url, opts);
    }
  });

  syncHandler = localDB.sync(remoteDB, {
    live: true,
    retry: true,
    selector: {
      access: { $elemMatch: userId }
    }
  });

  syncHandler.on('change', (info) => console.log('Sync change:', info));
  syncHandler.on('error', (err) => console.error('Sync error:', err));

  return localDB;
}

export function getDatabase(): PouchDB.Database {
  if (!localDB) throw new Error('Database not initialized');
  return localDB;
}

export async function destroyDatabase(): Promise<void> {
  if (syncHandler) {
    syncHandler.cancel();
    syncHandler = null;
  }
  if (localDB) {
    await localDB.destroy();
    localDB = null;
  }
}
```

### 4.3 Document Helpers

**`services/frontend/src/services/pouchdb/documents.ts`:**
```typescript
import { getDatabase } from './database';
import { v4 as uuidv4 } from 'uuid';

// Wishlist operations
export async function createWishlist(userId: string, data: Partial<Wishlist>): Promise<Wishlist> {
  const db = getDatabase();
  const now = new Date().toISOString();

  const doc: Wishlist = {
    _id: `wishlist:${uuidv4()}`,
    type: 'wishlist',
    owner_id: userId,
    name: data.name || 'New Wishlist',
    description: data.description || '',
    icon: data.icon || '🎁',
    is_public: false,
    created_at: now,
    updated_at: now,
    access: [userId]
  };

  await db.put(doc);
  return doc;
}

export async function getWishlists(userId: string): Promise<Wishlist[]> {
  const db = getDatabase();
  const result = await db.find({
    selector: {
      type: 'wishlist',
      access: { $elemMatch: userId }
    }
  });
  return result.docs as Wishlist[];
}

// Item operations
export async function createItem(userId: string, wishlistId: string, data: Partial<Item>): Promise<Item> {
  const db = getDatabase();
  const now = new Date().toISOString();

  // Get wishlist to copy access array
  const wishlist = await db.get(wishlistId) as Wishlist;

  const doc: Item = {
    _id: `item:${uuidv4()}`,
    type: 'item',
    wishlist_id: wishlistId,
    owner_id: userId,
    title: data.title || '',
    description: data.description || null,
    price: data.price || null,
    currency: data.currency || null,
    quantity: data.quantity || 1,
    source_url: data.source_url || null,
    image_url: null,
    image_base64: null,
    status: data.source_url ? 'pending' : 'resolved',
    resolution_error: null,
    sort_order: data.sort_order || 0,
    created_at: now,
    updated_at: now,
    access: wishlist.access  // inherit from wishlist
  };

  await db.put(doc);
  return doc;
}

// Mark operations (for viewers)
export async function createMark(
  viewerId: string,
  item: Item,
  wishlist: Wishlist,
  quantity: number
): Promise<Mark> {
  const db = getDatabase();
  const now = new Date().toISOString();

  // Access includes all viewers EXCEPT owner
  const viewerAccess = wishlist.access.filter(id => id !== wishlist.owner_id);

  const doc: Mark = {
    _id: `mark:${uuidv4()}`,
    type: 'mark',
    item_id: item._id,
    wishlist_id: wishlist._id,
    owner_id: wishlist.owner_id,
    marked_by: viewerId,
    quantity,
    created_at: now,
    updated_at: now,
    access: viewerAccess
  };

  await db.put(doc);
  return doc;
}
```

### 4.4 Reactive Composables

**`services/frontend/src/composables/useWishlists.ts`:**
```typescript
import { ref, onMounted, onUnmounted } from 'vue';
import { getDatabase } from '@/services/pouchdb/database';
import type { Wishlist } from '@/types';

export function useWishlists(userId: string) {
  const wishlists = ref<Wishlist[]>([]);
  const loading = ref(true);
  const error = ref<Error | null>(null);

  let changesHandler: PouchDB.Core.Changes<{}> | null = null;

  async function fetchWishlists() {
    const db = getDatabase();
    const result = await db.find({
      selector: {
        type: 'wishlist',
        access: { $elemMatch: userId }
      }
    });
    wishlists.value = result.docs as Wishlist[];
  }

  onMounted(async () => {
    try {
      await fetchWishlists();

      // Watch for changes
      const db = getDatabase();
      changesHandler = db.changes({
        since: 'now',
        live: true,
        include_docs: true,
        selector: { type: 'wishlist' }
      }).on('change', () => {
        fetchWishlists();
      });
    } catch (err) {
      error.value = err as Error;
    } finally {
      loading.value = false;
    }
  });

  onUnmounted(() => {
    if (changesHandler) {
      changesHandler.cancel();
    }
  });

  return { wishlists, loading, error, refetch: fetchWishlists };
}
```

### 4.5 Remove SSE / Realtime Sync

**Files to delete:**
```
services/frontend/src/composables/useRealtimeSync.ts
```

**Remove from components:**
- Remove all SSE connection logic
- Remove `useRealtimeSync` usage
- PouchDB live sync replaces this entirely

---

## Phase 5: Data Migration

### 5.1 Migration Script

**`scripts/migrate-to-couchdb.py`:**
```python
"""
Migrate data from PostgreSQL to CouchDB.
Run once before cutover.
"""

import asyncio
import asyncpg
import couchdb
from uuid import uuid4

async def migrate():
    # Connect to PostgreSQL
    pg = await asyncpg.connect(PG_CONNECTION_STRING)

    # Connect to CouchDB
    couch = couchdb.Server(COUCHDB_URL)
    db = couch['wishwithme']

    # Migrate users
    users = await pg.fetch("SELECT * FROM users WHERE deleted_at IS NULL")
    for user in users:
        doc = {
            "_id": f"user:{user['id']}",
            "type": "user",
            "email": user['email'],
            "password_hash": user['password_hash'],
            "name": user['name'],
            "avatar_base64": user['avatar_base64'],
            "locale": user['locale'],
            "created_at": user['created_at'].isoformat(),
            "updated_at": user['updated_at'].isoformat(),
            "access": [f"user:{user['id']}"]
        }
        db.save(doc)

    # Migrate wishlists
    wishlists = await pg.fetch("SELECT * FROM wishlists WHERE deleted_at IS NULL")
    for wl in wishlists:
        doc = {
            "_id": f"wishlist:{wl['id']}",
            "type": "wishlist",
            "owner_id": f"user:{wl['owner_id']}",
            "name": wl['title'],
            "description": wl['description'],
            "icon": "🎁",
            "created_at": wl['created_at'].isoformat(),
            "updated_at": wl['updated_at'].isoformat(),
            "access": [f"user:{wl['owner_id']}"]
        }
        db.save(doc)

    # Migrate items
    items = await pg.fetch("SELECT * FROM items WHERE deleted_at IS NULL")
    for item in items:
        # Get wishlist to copy access
        wl_doc = db.get(f"wishlist:{item['wishlist_id']}")

        doc = {
            "_id": f"item:{item['id']}",
            "type": "item",
            "wishlist_id": f"wishlist:{item['wishlist_id']}",
            "owner_id": wl_doc['owner_id'],
            "title": item['title'],
            "description": item['description'],
            "price": str(item['price_amount']) if item['price_amount'] else None,
            "currency": item['price_currency'],
            "quantity": item['quantity'],
            "source_url": item['source_url'],
            "image_url": item['image_url'],
            "image_base64": item['image_base64'],
            "status": item['status'],
            "created_at": item['created_at'].isoformat(),
            "updated_at": item['updated_at'].isoformat(),
            "access": wl_doc['access']
        }
        db.save(doc)

    # Migrate marks
    marks = await pg.fetch("SELECT * FROM marks")
    for mark in marks:
        item_doc = db.get(f"item:{mark['item_id']}")
        wl_doc = db.get(item_doc['wishlist_id'])

        # Access excludes owner
        access = [uid for uid in wl_doc['access'] if uid != wl_doc['owner_id']]

        doc = {
            "_id": f"mark:{mark['id']}",
            "type": "mark",
            "item_id": f"item:{mark['item_id']}",
            "wishlist_id": wl_doc['_id'],
            "owner_id": wl_doc['owner_id'],
            "marked_by": f"user:{mark['user_id']}",
            "quantity": mark['quantity'],
            "created_at": mark['created_at'].isoformat(),
            "updated_at": mark['updated_at'].isoformat(),
            "access": access
        }
        db.save(doc)

    # Migrate share links
    shares = await pg.fetch("SELECT * FROM share_links WHERE revoked = false")
    for share in shares:
        wl_doc = db.get(f"wishlist:{share['wishlist_id']}")

        doc = {
            "_id": f"share:{share['id']}",
            "type": "share",
            "wishlist_id": f"wishlist:{share['wishlist_id']}",
            "owner_id": wl_doc['owner_id'],
            "token": share['token'],
            "link_type": share['link_type'],
            "expires_at": share['expires_at'].isoformat() if share['expires_at'] else None,
            "access_count": share['access_count'],
            "revoked": False,
            "granted_users": [],
            "created_at": share['created_at'].isoformat(),
            "access": [wl_doc['owner_id']]
        }
        db.save(doc)

    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
```

---

## Phase 6: Testing

### 6.1 Test Scenarios

| Scenario | Test |
|----------|------|
| User registration | Create user, verify JWT works with CouchDB |
| Wishlist CRUD | Create/read/update/delete via PouchDB |
| Item with URL | Create item, verify resolver updates it |
| Offline mode | Disconnect, make changes, reconnect, verify sync |
| Share wishlist | Create share, access as viewer, verify sync |
| Mark item | Viewer marks, verify owner doesn't see |
| Revoke share | Revoke, verify viewer loses access |
| Conflict resolution | Two users edit same doc, verify resolution |

### 6.2 Test Commands

```bash
# Backend tests
cd services/core-api
pytest tests/ -v

# Frontend tests
cd services/frontend
npm run test:unit

# E2E tests
npm run test:e2e

# Manual CouchDB verification
curl -X GET http://admin:pass@localhost:5984/wishwithme/_all_docs
```

---

## Phase 7: Deployment

### 7.1 Deployment Order

1. **Deploy CouchDB** (new service)
2. **Deploy updated backend** (with CouchDB support)
3. **Run migration script** (PostgreSQL → CouchDB)
4. **Deploy updated frontend** (PouchDB)
5. **Verify everything works**
6. **Remove PostgreSQL** (after 1 week verification period)

### 7.2 Rollback Plan

If issues arise:
1. Frontend: Revert to RxDB build
2. Backend: Revert to PostgreSQL endpoints
3. PostgreSQL data preserved for 1 week

### 7.3 Updated docker-compose.ubuntu.yml

```yaml
version: '3.8'

services:
  nginx:
    # ... existing config ...

  frontend:
    # ... existing config ...

  core-api-1:
    build: ./services/core-api
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - COUCHDB_DATABASE=wishwithme
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - couchdb
    networks:
      - wishwithme-network

  core-api-2:
    # Same as core-api-1

  item-resolver-1:
    build: ./services/item-resolver
    environment:
      - COUCHDB_URL=http://couchdb:5984
      - COUCHDB_DATABASE=wishwithme
    depends_on:
      - couchdb
    networks:
      - wishwithme-network

  item-resolver-2:
    # Same as item-resolver-1

  couchdb:
    image: couchdb:3.3
    restart: unless-stopped
    environment:
      - COUCHDB_USER=${COUCHDB_ADMIN_USER}
      - COUCHDB_PASSWORD=${COUCHDB_ADMIN_PASSWORD}
    volumes:
      - couchdb_data:/opt/couchdb/data
      - ./couchdb/local.ini:/opt/couchdb/etc/local.d/local.ini
    networks:
      - wishwithme-network
    ports:
      - "5984:5984"

  # REMOVED: postgres, redis

volumes:
  couchdb_data:

networks:
  wishwithme-network:
    driver: bridge
```

---

## Summary: What Changes

| Component | Before | After |
|-----------|--------|-------|
| **Frontend DB** | RxDB (IndexedDB) | PouchDB (IndexedDB) |
| **Backend DB** | PostgreSQL | CouchDB |
| **Sync** | Custom HTTP endpoints | Native CouchDB replication |
| **Real-time** | SSE + Redis pub/sub | PouchDB live sync |
| **Auth** | JWT + sessions | CouchDB JWT |
| **Item resolver** | Writes to PostgreSQL | Watches CouchDB _changes |

| Removed | Reason |
|---------|--------|
| PostgreSQL | Replaced by CouchDB |
| Redis | No SSE, no sessions needed |
| RxDB | Replaced by PouchDB |
| SSE endpoints | Native sync replaces |
| Custom sync code | Native replication |

---

## Timeline Estimate

| Phase | Duration |
|-------|----------|
| Phase 1: CouchDB Infrastructure | 2-3 days |
| Phase 2: Document Schema | 1 day |
| Phase 3: Backend Changes | 3-4 days |
| Phase 4: Frontend Changes | 4-5 days |
| Phase 5: Data Migration | 1 day |
| Phase 6: Testing | 2-3 days |
| Phase 7: Deployment | 1 day |
| **Total** | **~2-3 weeks** |

---

## Next Steps

1. Review this plan
2. Set up CouchDB on dev environment
3. Start with Phase 1 (infrastructure)
4. Proceed phase by phase
