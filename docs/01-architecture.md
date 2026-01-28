# Architecture & Technology Stack

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. System Architecture

### 1.1 C4 Context Diagram

```mermaid
C4Context
    title System Context Diagram - Wish With Me

    Person(user, "User", "Creates wishlists, adds items, shares with friends")
    Person(viewer, "Wishlist Viewer", "Views shared wishlists, marks items to buy")

    System(wwm, "Wish With Me", "PWA wishlist application")

    System_Ext(google, "Google OAuth", "Authentication provider")
    System_Ext(apple, "Apple OAuth", "Authentication provider")
    System_Ext(yandex, "Yandex ID", "Authentication provider")
    System_Ext(sber, "Sber ID", "Authentication provider")
    System_Ext(marketplaces, "Marketplaces", "Ozon, Wildberries, Amazon, etc.")
    System_Ext(llm, "LLM API", "OpenAI-compatible API for item extraction")

    Rel(user, wwm, "Uses", "HTTPS")
    Rel(viewer, wwm, "Uses", "HTTPS")
    Rel(wwm, google, "Authenticates via", "OAuth 2.0")
    Rel(wwm, apple, "Authenticates via", "OAuth 2.0")
    Rel(wwm, yandex, "Authenticates via", "OAuth 2.0")
    Rel(wwm, sber, "Authenticates via", "OAuth 2.0")
    Rel(wwm, marketplaces, "Fetches item data from", "HTTPS")
    Rel(wwm, llm, "Extracts item data via", "HTTPS")
```

### 1.2 C4 Container Diagram

```mermaid
C4Container
    title Container Diagram - Wish With Me

    Person(user, "User")

    Container_Boundary(frontend_boundary, "Frontend") {
        Container(pwa, "Vue Quasar PWA", "Vue 3, Quasar, TypeScript", "Single-page application with offline support")
        Container(sw, "Service Worker", "Workbox", "Caching, background sync, push notifications")
        ContainerDb(idb, "RxDB", "IndexedDB + Reactive", "Offline data with reactive queries and replication")
    }

    Container_Boundary(ubuntu_boundary, "Ubuntu Server (176.106.144.182)") {
        Container(nginx_ubuntu, "Nginx", "Load Balancer", "HTTPS termination, ip_hash for SSE sticky sessions")
        Container(api1, "Core API 1", "Python, FastAPI", "REST API instance 1")
        Container(api2, "Core API 2", "Python, FastAPI", "REST API instance 2")
        ContainerDb(postgres, "PostgreSQL", "PostgreSQL 16", "Primary data store")
        ContainerDb(redis, "Redis", "Redis 7", "Sessions, caching, SSE pub/sub")
    }

    Container_Boundary(montreal_boundary, "Montreal Server (158.69.203.3)") {
        Container(nginx_montreal, "Nginx", "Load Balancer", "least_conn load balancing on port 8001")
        Container(resolver1, "Item Resolver 1", "Python, FastAPI, Playwright", "URL resolver instance 1")
        Container(resolver2, "Item Resolver 2", "Python, FastAPI, Playwright", "URL resolver instance 2")
    }

    Rel(user, pwa, "Uses", "HTTPS")
    Rel(pwa, sw, "Registers")
    Rel(sw, idb, "Reads/Writes")
    Rel(pwa, idb, "Reads/Writes")
    Rel(pwa, nginx_ubuntu, "API calls", "HTTPS/REST")
    Rel(nginx_ubuntu, api1, "Load balanced", "HTTP")
    Rel(nginx_ubuntu, api2, "Load balanced", "HTTP")
    Rel(api1, postgres, "Reads/Writes", "SQL")
    Rel(api2, postgres, "Reads/Writes", "SQL")
    Rel(api1, redis, "Sessions/Cache/Pub-Sub", "Redis Protocol")
    Rel(api2, redis, "Sessions/Cache/Pub-Sub", "Redis Protocol")
    Rel(api1, nginx_montreal, "Resolves URLs", "HTTP")
    Rel(api2, nginx_montreal, "Resolves URLs", "HTTP")
    Rel(nginx_montreal, resolver1, "Load balanced", "HTTP")
    Rel(nginx_montreal, resolver2, "Load balanced", "HTTP")
```

### 1.3 Component Interaction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant PWA as Vue Quasar PWA
    participant IDB as IndexedDB
    participant SW as Service Worker
    participant API as Core API
    participant IR as Item Resolver
    participant DB as PostgreSQL

    Note over U,DB: Add Item from URL Flow

    U->>PWA: Paste marketplace URL
    PWA->>IDB: Save item (status: resolving)
    PWA->>U: Show "Resolving..." state

    alt Online
        PWA->>API: POST /items (url, status: resolving)
        API->>DB: Insert item
        API->>IR: POST /resolver/v1/resolve
        Note over IR: Playwright + LLM extraction (slow)
        IR-->>API: Item data (title, price, image_base64)
        API->>DB: Update item (status: resolved)
        API-->>PWA: Item updated
        PWA->>IDB: Update item
        PWA->>U: Show resolved item
    else Offline
        PWA->>IDB: Queue sync request
        SW->>SW: Background sync when online
        SW->>API: POST /sync
        API->>IR: Resolve pending items
        API-->>SW: Sync response
        SW->>IDB: Update items
    end
```

---

## 2. Technology Stack

### 2.1 Technology Decisions

| Layer | Technology | Version | Rationale |
|-------|------------|---------|-----------|
| **Frontend** | Vue 3 + Quasar | 2.x | Batteries-included PWA framework, excellent mobile UI |
| **Frontend Build** | Quasar CLI (Vite) | 2.x | One-command PWA generation, fast HMR |
| **PWA** | Workbox (Quasar built-in) | 7.x | Integrated service worker, precaching |
| **State Management** | Pinia | 2.x | Official Vue store, TypeScript-first, devtools |
| **Offline Storage** | RxDB | 15.x | Reactive database, real-time queries, built-in replication |
| **Backend** | FastAPI | 0.115.x | Async, automatic OpenAPI, type safety |
| **ORM** | SQLAlchemy 2.0 | 2.x | Async support, mature, PostgreSQL optimized |
| **Database** | PostgreSQL | 16.x | JSONB for flexibility, proven reliability |
| **Cache/Sessions** | Redis | 7.x | Session store, rate limiting, pub/sub for notifications |
| **Auth** | python-jose + passlib + authlib | - | JWT handling, password hashing, OAuth 2.0 clients |
| **Item Resolver** | Playwright + LLM | - | Already implemented |

### 2.2 Database Selection Rationale

**Decision**: RxDB (client) ↔ PostgreSQL (server) + Redis (cache/sessions)

**Architecture Overview**:
```
┌─────────────────────────────────────────────────────────┐
│  Browser                                                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │  RxDB (IndexedDB)                               │    │
│  │  - Reactive queries (auto-updating UI)          │    │
│  │  - Offline-first data storage                   │    │
│  │  - Built-in replication protocol                │    │
│  └───────────────────┬─────────────────────────────┘    │
└──────────────────────┼──────────────────────────────────┘
                       │ HTTP replication
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                      │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PostgreSQL                                     │    │
│  │  - ACID transactions                            │    │
│  │  - Relational integrity                         │    │
│  │  - Complex queries                              │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Why RxDB for client-side storage**:

| Feature | RxDB | Dexie | PouchDB |
|---------|------|-------|---------|
| Reactive Queries | Native Observable | Addon | No |
| TypeScript | First-class | Good | Limited |
| Replication Protocol | Built-in | Manual | Built-in (CouchDB only) |
| Backend Flexibility | Any HTTP | Manual | CouchDB only |
| Multi-tab Support | Built-in | Manual | Manual |
| Schema Validation | JSON Schema | None | None |
| Vue Integration | @vueuse/rxjs | Manual | Manual |

**Why PostgreSQL over MongoDB/CouchDB**:

| Criteria | PostgreSQL | MongoDB | CouchDB |
|----------|------------|---------|---------|
| ACID Compliance | Full | Limited | Limited |
| JSONB Flexibility | Excellent | Native | Native |
| Relational Queries | Native | $lookup | Views |
| Operational Complexity | Low | Medium | Medium |
| Team Familiarity | High | Medium | Low |
| Multi-purpose Use | Excellent | Good | Limited |

**Redis Role**:
- JWT token blocklist (for logout/revocation)
- Session storage for OAuth state
- Rate limiting
- SSE event pub/sub (enables real-time updates across multiple core-api instances)
- In-app notification pub/sub
- Caching (item resolution results)
