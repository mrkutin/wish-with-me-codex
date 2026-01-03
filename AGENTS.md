AGENTS.md — Multi-User Wishlist Platform

Offline-First · Async · Microservices · Agent-Driven

This document is the single authoritative specification for building a scalable, offline-first, multi-user wishlist platform using microservices, asynchronous processing, and agent-driven development (OpenAI Codex, MCP agents, CI agents).

Any implementation MUST follow this document exactly unless an explicit revision is made.

⸻

0) Glossary
	•	Owner – User who owns a wishlist. Wishlists are embedded inside the owner’s user document.
	•	Shared user – A user who redeemed a share link and appears in access[].
	•	Share link / QR – The single invitation mechanism per wishlist, backed by a share token.
	•	Access entry – Grants a user access to a wishlist.
All shared users have identical permissions: view + mark/unmark items as bought.
	•	Resolver – Service that resolves item URLs into structured data asynchronously.
	•	Pending item – Item created with only source_url, awaiting resolution.
	•	Outbox – Client-side queue of offline operations.
	•	Sync cursor – A monotonically increasing server-side integer used for delta sync.
	•	Broker – Message broker used for async inter-service communication (RabbitMQ).

⸻

1) Product Overview

Core Features
	•	Create and manage personal wishlists
	•	Add items via URL (resolved asynchronously)
	•	Share wishlists via a single link or QR code
	•	Shared users can mark items as bought (to prevent duplicates)
	•	Admin can manage any user, wishlist, and item

Killer Feature — Offline-First PWA
	•	Full offline functionality (view, edit, add items, mark bought)
	•	Automatic sync when online
	•	Explicit UI states for:
	•	offline / online
	•	syncing / sync failed
	•	item resolution (pending / resolved / failed)
	•	Push notifications

⸻

2) Architecture Overview

Microservices

1. core-api (FastAPI, async)
	•	Auth (email/password, JWT)
	•	Wishlists, items, sharing, bought state
	•	Sync API
	•	Notification API
	•	MongoDB via Motor (NO ORM)
	•	Redis for idempotency, sync cursor, locks, TTL state
	•	Publishes commands/events to RabbitMQ

2. item-resolver (FastAPI, async)
	•	Renders pages using Playwright (Chromium)
	•	Takes screenshots
	•	Uses LLM to extract item properties
	•	Returns base64 screenshot thumbnail
	•	Safe, compliant, failure-tolerant

3. worker
	•	Consumes RabbitMQ messages
	•	Calls resolver service
	•	Updates MongoDB atomically
	•	Applies retry/backoff rules
	•	Publishes completion/failure events

4. mcp-server
	•	Tool-based interface for third-party agents
	•	Strict auth, auditing, rate limiting
	•	Uses core-api REST only (no DB access, no broker)

⸻

2.1) Load Balancing & Datacenters

DC1 (Primary)
	•	nginx
	•	/api/* → core-api (load balanced)
	•	/mcp/* → mcp-server
	•	/resolver/* → proxy to DC2 resolver balancer (optional convenience)

DC2 (Resolver Datacenter)
	•	resolver-balancer
	•	Balances item-resolver instances
	•	TLS termination and health checks

⸻

3) Technology Stack (Hard Requirements)

Backend
	•	Python, FastAPI (async)
	•	MongoDB (Motor only, NO ORM)
	•	Redis
	•	RabbitMQ
	•	bcrypt
	•	JWT + refresh token rotation

Frontend
	•	Vue 3 + Vite
	•	Vuex
	•	Tailwind CSS
	•	PWA (offline-first)
	•	Push notifications (Web Push / FCM allowed)

Standards
	•	REST only for external APIs
	•	Async via broker for internal workflows
	•	TDD
	•	docker-compose only (no Kubernetes)
	•	Security by default

⸻

4) Data Model (MongoDB Embedded)

Collection: users

{
  "_id": "ObjectId",
  "email": "user@example.com",
  "full_name": "Full Name",
  "password_hash": "...bcrypt...",
  "roles": ["user"],
  "created_at": "...",
  "updated_at": "...",
  "wishlists": [
    {
      "wishlist_id": "uuid",
      "title": "...",
      "description": "...",
      "created_at": "...",
      "updated_at": "...",
      "version": 1,
      "last_sync_seq": 123,

      "share": {
        "share_token": "random",
        "created_by_user_id": "ObjectId",
        "created_at": "...",
        "expires_at": null,
        "redemptions": 0
      },

      "access": [
        { "user_id": "ObjectId", "granted_at": "..." }
      ],

      "items": [
        {
          "item_id": "uuid",
          "source_url": "...",
          "canonical_url": null,
          "title": null,
          "description": null,

          "image_base64": null,
          "image_mime": null,

          "price": null,
          "quantity": 1,

          "resolution_status": "pending | resolved | failed",
          "resolution_error": null,
          "resolution_error_code": null,
          "resolution_confidence": null,
          "resolved_at": null,

          "is_bought": false,
          "bought_by_user_id": null,
          "bought_at": null,

          "version": 1,
          "created_at": "...",
          "updated_at": "..."
        }
      ]
    }
  ]
}

Hard Invariants
	•	Wishlist is the only aggregate root
	•	Items are never fetched independently
	•	Authorization always uses access[], never share tokens
	•	All shared users can mark/unmark bought
	•	Shared user may unmark only if they marked
	•	Owner/admin may always unmark

  4.1) Forbidden Endpoints

Do NOT implement:
	•	GET /api/v1/items
	•	GET /api/v1/items/{id}
	•	GET /api/v1/wishlists/{id}/items

Allowed:
	•	GET /api/v1/wishlists
	•	GET /api/v1/wishlists/{id}

⸻

4.2) Privacy & Response Filtering

Visibility rules
	•	Shared users
	•	NEVER see share.share_token
	•	NEVER see full access[]
	•	Owner
	•	Sees everything
	•	Admin
	•	Sees everything

Mandatory fields in every wishlist response
	•	owner_user_id
	•	owner_full_name

⸻

5) API Conventions

Error Model

{
  "code": "ERROR_CODE",
  "message": "Human readable message",
  "details": {},
  "trace_id": "X-Request-Id"
}

Idempotency
	•	All mutating endpoints require Idempotency-Key
	•	Stored in Redis for 7 days
	•	Scope: (user_id, route, key)
	•	Replay returns original response

⸻

6) Sync Protocol

Cursor semantics
	•	Cursor is a monotonically increasing integer
	•	Source of truth: Redis counter sync:seq
	•	Any wishlist mutation must:
	•	increment sync:seq
	•	set wishlist.last_sync_seq

Endpoint

GET /api/v1/sync?cursor=<int>

Response:

{
  "server_time": "iso8601",
  "next_cursor": 456,
  "changes": {
    "wishlists": [ ... ]
  }
}


⸻

7) Core API Endpoints

Auth
	•	POST /api/v1/auth/register (email, full_name, password)
	•	POST /api/v1/auth/login
	•	POST /api/v1/auth/refresh
	•	POST /api/v1/auth/logout
	•	GET /api/v1/users/me

Wishlists
	•	GET /api/v1/wishlists (owned + shared)
	•	POST /api/v1/wishlists
	•	GET /api/v1/wishlists/{id}
	•	PATCH /api/v1/wishlists/{id}
	•	DELETE /api/v1/wishlists/{id}

Items (mutations only)
	•	POST /api/v1/wishlists/{id}/items
	•	Creates item immediately
	•	Sets resolution_status = "pending"
	•	Publishes item.resolve.requested to RabbitMQ
	•	MUST NOT block on resolver
	•	PATCH /api/v1/wishlists/{id}/items/{item_id}
	•	DELETE /api/v1/wishlists/{id}/items/{item_id}
	•	POST /api/v1/wishlists/{id}/items/{item_id}/mark-bought
	•	POST /api/v1/wishlists/{id}/items/{item_id}/unmark-bought
	•	POST /api/v1/wishlists/{id}/items/{item_id}/resolve (manual retry)

Sharing
	•	POST /api/v1/wishlists/{id}/share
	•	POST /api/v1/wishlists/{id}/share/revoke
		•	Revoking removes the share object; existing access entries are unchanged
	•	POST /api/v1/shares/redeem (idempotent)
	•	POST /api/v1/wishlists/{id}/access/revoke
		•	Revoking removes the access entry

⸻

8) Message Broker — RabbitMQ

Exchange
	•	wishlist.events (topic, durable)

Routing keys
	•	item.resolve.requested
	•	item.resolve.retry
	•	item.resolve.completed
	•	item.resolve.failed

Queues
	•	resolver.jobs
	•	resolver.jobs.dlq

Message Envelope

{
  "message_id": "uuid",
  "type": "item.resolve.requested",
  "occurred_at": "iso8601",
  "trace_id": "X-Request-Id",
  "data": {
    "owner_user_id": "ObjectId",
    "wishlist_id": "uuid",
    "item_id": "uuid",
    "source_url": "https://..."
  }
}

Delivery Guarantees
	•	At-least-once delivery
	•	Consumers MUST be idempotent
	•	ACK only after successful DB update
	•	NACK + requeue for transient failures
	•	DLQ for permanent failures

⸻

9) Worker Service

Responsibilities
	•	Consume broker messages
	•	Call item-resolver via REST
	•	Update embedded item atomically
	•	Increment wishlist version and sync cursor
	•	Publish completion/failure events

Retry Policy
	•	Backoff: 1m → 5m → 15m → 1h → 6h
	•	Max attempts: 5

Idempotency & Concurrency
	•	Track processed message_id in Redis (TTL 7 days)
	•	Mongo compare-and-set on resolution_status

Reconciliation Scan
	•	Periodic (15–30 min)
	•	Finds stale pending items
	•	Publishes retry messages
	•	Secondary mechanism only

⸻

10) Item Resolver Service

Function
	•	Render page with Playwright (Chromium)
	•	Capture screenshot
	•	Extract data via LLM
	•	Return base64 screenshot thumbnail

Compliance & Safety
	•	NO bot-evasion or CAPTCHA bypass
	•	SSRF protection mandatory
	•	Strict timeouts and rate limits

Endpoint

POST /resolver/v1/resolve

LLM Output (Strict JSON)

{
  "title": "string|null",
  "description": "string|null",
  "price_amount": "number|null",
  "price_currency": "string|null",
  "canonical_url": "string|null",
  "confidence": "number"
}

Screenshot Rules
	•	Width ≤ 1280px
	•	JPEG/WebP
	•	Base64 payload ≤ ~300 KB

Caching
	•	Redis key: resolver:cache:{sha256(url)}
	•	TTL: 7 days

Error Codes
	•	INVALID_URL
	•	SSRF_BLOCKED
	•	BLOCKED_OR_UNAVAILABLE
	•	TIMEOUT
	•	UNSUPPORTED_CONTENT
	•	LLM_PARSE_FAILED
	•	UNKNOWN_ERROR

⸻

11) Offline-First PWA

Storage
	•	IndexedDB is source of truth
	•	Vuex derives state from IndexedDB
	•	Outbox stores offline operations

Mandatory UI States
	•	Offline / Online
	•	Syncing / Sync failed
	•	Item resolution:
	•	Pending (“Resolving item details…”)
	•	Resolved (show thumbnail + fields)
	•	Failed (error + Retry/Edit/Delete)

Confidence UI
	•	If confidence < threshold → “Details may be incomplete”

⸻

12) Notifications
	•	Web Push / FCM
	•	Events:
	•	WISHLIST_SHARED
	•	ITEM_BOUGHT
	•	ITEM_UNBOUGHT
	•	ITEM_RESOLUTION_FAILED

⸻

13) Security
	•	bcrypt
	•	JWT refresh rotation
	•	HTTPS in production
	•	Rate limiting
	•	SSRF protection
	•	Secrets via env vars
	•	Auditing for sensitive actions

⸻

14) Observability
	•	JSON logs
	•	X-Request-Id
	•	Health endpoints

⸻

15) Development Workflow
	•	Feature branches + Merge Requests
	•	TDD-first
	•	CI gates:
	•	tests
	•	lint
	•	type checks
	•	build
	•	offline E2E scenarios

⸻

16) Repo Layout

/services
  /core-api
  /item-resolver
  /worker
  /mcp-server
/frontend
  /pwa
/infra
  /nginx
  docker-compose.yml


⸻

17) Definition of Done
	•	Tests pass
	•	Offline-first preserved
	•	Resolver states visible
	•	Atomic bought semantics
	•	Privacy enforced
	•	Broker consumers idempotent

⸻

18) Hard Constraints Summary
	•	REST external APIs
	•	RabbitMQ for async communication
	•	FastAPI async + Motor (no ORM)
	•	Redis required
	•	Offline-first Vue 3 PWA with Tailwind
	•	Async Playwright + LLM resolver
	•	Screenshot-based extraction
	•	Single share link per wishlist
	•	docker-compose only
	•	TDD enforced

⸻

19) Architectural Closure

This document is complete and sufficient to implement the system without additional architectural decisions.

Any deviation MUST be explicitly documented and reviewed.

⸻

END OF DOCUMENT
