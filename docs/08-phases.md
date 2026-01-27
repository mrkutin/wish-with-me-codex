# Implementation Phases

> Part of [Wish With Me Specification](../AGENTS.md)

---

## Overview

| Phase | Focus | Duration |
|-------|-------|----------|
| 1 | Foundation | Week 1-2 |
| 2 | Core Features | Week 3-4 |
| 3 | OAuth | Week 5 |
| 4 | Marking System | Week 6-7 |
| 5 | Offline & PWA | Week 8-9 |
| 6 | Real-Time Updates (SSE) | Week 10 |
| 7 | i18n & Polish | Week 11 |
| 8 | Deploy | Week 12-13 |

---

## Phase 1: Foundation (Week 1-2)

**Goal**: Project scaffolding and basic infrastructure

### Deliverables

- [x] Quasar project setup with TypeScript
- [x] FastAPI project setup with async SQLAlchemy
- [x] PostgreSQL schema + Alembic migrations
- [x] Redis connection for sessions
- [x] Basic auth (email/password)
- [x] User CRUD endpoints
- [x] JWT token flow (access + refresh)
- [x] Docker Compose for local dev

### Success Criteria

- User can register, login, logout
- JWT refresh works correctly
- Migrations run cleanly

---

## Phase 2: Core Features (Week 3-4)

**Goal**: Basic wishlist and item functionality

### Deliverables

- [x] Wishlist CRUD endpoints
- [x] Wishlist UI (list, create, edit, delete)
- [x] Item CRUD endpoints (manual entry)
- [x] Item UI (list, add, edit, delete)
- [x] Item resolver integration
- [x] URL paste → resolve flow
- [x] Item status states (pending, resolving, resolved, failed)
- [x] Basic error handling

### Success Criteria

- User can create wishlists
- User can add items manually
- User can paste URL and see resolved item
- Failed resolutions show error state

---

## Phase 3: OAuth Integration (Week 5)

**Goal**: Social authentication

### Deliverables

- [x] Google OAuth setup (with birthday via People API)
- [x] Yandex ID OAuth setup (with avatar and birthday)
- [x] OAuth callback handling
- [x] Account linking (add OAuth to existing account)
- [x] Account unlinking (disconnect provider)
- [x] Social login buttons UI
- [x] Profile with connected accounts
- [x] Avatar download from OAuth provider

### Success Criteria

- [x] User can sign up/login with Google or Yandex
- [x] User can link additional providers to existing account
- [x] User can disconnect providers (except last one)

---

## Phase 4: Marking System (Week 6-7)

**Goal**: Share and mark functionality (surprise mode)

### Deliverables

- [x] Share link generation
- [x] Share link access (authenticated)
- [x] QR code generation
- [x] Mark/unmark endpoints
- [x] Partial quantity marking
- [x] Surprise mode (hide marks from owner)
- [x] Mark UI for viewers
- [x] Shared wishlist view
- [x] In-app notifications (item resolved, wishlist shared)

### Success Criteria

- Owner can share wishlist via link
- Viewer can mark items (owner can't see who)
- Partial marking works (mark 2 of 5)
- Notifications appear when items resolve

---

## Phase 5: Offline & PWA (Week 8-9)

**Goal**: Full offline-first support

### Deliverables

- [x] RxDB setup with schemas
- [x] Wishlist collection + replication
- [x] Item collection + replication
- [x] Sync endpoints (pull/push)
- [x] Conflict resolution (LWW)
- [x] Service worker with Workbox
- [x] Live replication (auto-sync)
- [x] PWA manifest
- [x] Offline banner UI
- [x] Sync status indicator
- [x] App install prompt

### Success Criteria

- App works fully offline
- Changes sync when online
- Conflicts resolved correctly
- PWA installable on mobile

---

## Phase 6: Real-Time Updates via SSE (Week 10)

**Goal**: Server-to-client real-time notifications for instant UI updates

> Full specification: [docs/14-realtime-sse.md](./14-realtime-sse.md)

### Deliverables

**Backend:**
- [x] EventChannelManager service (`app/services/events.py`)
- [x] SSE endpoint (`/api/v1/events/stream`)
- [x] Event publishing on item resolution
- [x] Event publishing on sync push
- [x] Keepalive ping (30s interval)
- [x] Multi-device support (multiple SSE connections per user)
- [x] Real-time mark sync for shared wishlists
- [x] SSE notifications to owner + markers + bookmarked users

**Frontend:**
- [x] `useRealtimeSync` composable with EventSource
- [x] Automatic reconnection with exponential backoff
- [x] RxDB pull trigger on events
- [x] Integration in App.vue
- [x] Offline-aware SSE (close connection when offline to prevent error spam)
- [x] Custom DOM events for shared wishlist mark updates
- [x] Optimized mark updates (only re-render affected item, not entire list)

**Infrastructure:**
- [x] Nginx SSE configuration (disable buffering)
- [x] Montreal server verification

### Event Types

| Event | Trigger | Action |
|-------|---------|--------|
| `items:updated` | Item created/modified | Pull items |
| `items:resolved` | Resolution complete | Pull items |
| `wishlists:updated` | Wishlist modified | Pull wishlists |
| `marks:updated` | Mark added/removed | Pull marks, refresh shared wishlist view |
| `sync:ping` | Keepalive (30s) | None |

### Success Criteria

- [x] Item added by URL resolves and updates UI without refresh
- [x] Cross-device edits appear within seconds
- [x] Connection auto-reconnects after network drop
- [x] App works normally if SSE unavailable (graceful degradation)
- [x] Multiple devices with same account receive SSE events simultaneously
- [x] Shared wishlist viewers see mark changes in real-time

---

## Phase 7: i18n & Polish (Week 11)

**Goal**: Localization and UI polish

### Deliverables

- [x] Russian translations (complete)
- [x] English translations (complete)
- [x] Language auto-detection
- [x] Language switcher in settings
- [x] Empty states for all pages
- [x] Error states for all scenarios
- [x] Loading skeletons
- [x] Pull-to-refresh
- [x] Swipe actions (mobile)
- [x] Accessibility audit + fixes
- [x] Color contrast fixes (verified WCAG AA compliant)

### Success Criteria

- [x] App fully localized in RU and EN
- [x] All empty/error states have proper UI
- [x] Accessibility passes basic audit

---

## Phase 8: Deploy & Production Hardening (Week 12-13)

**Goal**: Production deployment and operational readiness

### Deliverables

- [x] Frontend Dockerfile (Quasar PWA)
- [x] Backend Dockerfile (FastAPI)
- [x] CI/CD pipeline (GitHub Actions with smart change detection, health checks, auto-rollback)
- [x] Domain + SSL setup (wishwith.me, api.wishwith.me)
- [x] Backup strategy (documented in docs/13-deployment.md)
- N/A Kubernetes manifests (using docker-compose for single-server deployment)

### Deferred to Post-Launch

- [ ] CDN configuration
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Logging (upgrade to structured JSON)
- [ ] Error tracking (Sentry)
- [ ] Security audit (formal penetration testing)
- [ ] Load testing

### Success Criteria

- [x] App deployed to production
- [x] CI/CD runs on every push
- [x] Health checks in place (GitHub Actions failure notifications)
- [x] Backup strategy documented

---

## Post-Launch Roadmap

### V1.1 (Week 13-14)
- [ ] First-time onboarding flow
- [ ] Wishlist templates
- [ ] Search functionality
- [ ] Sort/filter options

### V1.2 (Week 15-16)
- [ ] Push notifications (web push)
- [ ] Email notifications
- [ ] Public profiles
- [ ] Wishlist discovery

### V2.0 (Future)
- [ ] Mobile apps (Capacitor)
- [ ] Collaborative wishlists
- [ ] Price tracking
- [ ] AI recommendations
