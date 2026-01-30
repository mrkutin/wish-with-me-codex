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
| 5 | Offline & PWA (PouchDB/CouchDB) | Week 8-9 |
| 6 | i18n & Polish | Week 10 |
| 7 | Deploy | Week 11-12 |

---

## Phase 1: Foundation (Week 1-2)

**Goal**: Project scaffolding and basic infrastructure

### Deliverables

- [x] Quasar project setup with TypeScript (Webpack)
- [x] FastAPI project setup
- [x] CouchDB setup with document schemas
- [x] Basic auth (email/password)
- [x] User CRUD endpoints
- [x] JWT token flow (access + refresh)
- [x] CouchDB JWT authentication
- [x] Docker Compose for local dev

### Success Criteria

- User can register, login, logout
- JWT refresh works correctly
- CouchDB accepts JWT tokens

---

## Phase 2: Core Features (Week 3-4)

**Goal**: Basic wishlist and item functionality

### Deliverables

- [x] Wishlist CRUD endpoints
- [x] Wishlist UI (list, create, edit, delete)
- [x] Item CRUD endpoints (manual entry)
- [x] Item UI (list, add, edit, delete)
- [x] Item resolver integration (CouchDB change feed)
- [x] URL paste -> resolve flow
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
- [x] Auto-link existing users by email

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
- [x] Mark/unmark via CouchDB documents
- [x] Partial quantity marking
- [x] Surprise mode (hide marks from owner via access arrays)
- [x] Mark UI for viewers
- [x] Shared wishlist view
- [x] In-app notifications (item resolved, wishlist shared)

### Success Criteria

- Owner can share wishlist via link
- Viewer can mark items (owner can't see who)
- Partial marking works (mark 2 of 5)
- Notifications appear when items resolve

---

## Phase 5: Offline & PWA with PouchDB/CouchDB (Week 8-9)

**Goal**: Full offline-first support with native sync

### Deliverables

- [x] PouchDB setup with document types
- [x] CouchDB database with indexes
- [x] PouchDB live sync to CouchDB
- [x] Filtered replication (user access arrays)
- [x] Conflict resolution (CouchDB revisions)
- [x] Service worker with Workbox
- [x] PWA manifest
- [x] Offline banner UI
- [x] Sync status indicator
- [x] App install prompt

### Architecture Notes

**Previous (RxDB + PostgreSQL + SSE)**:
- RxDB for client-side storage
- PostgreSQL for server-side storage
- Custom sync endpoints (pull/push)
- SSE for real-time updates
- Redis for pub/sub

**Current (PouchDB + CouchDB)**:
- PouchDB for client-side storage
- CouchDB for server-side storage
- Native sync protocol (no custom endpoints)
- Live sync for real-time updates (replaces SSE)
- No Redis needed

### Success Criteria

- App works fully offline
- Changes sync automatically when online
- Conflicts resolved via CouchDB revisions
- PWA installable on mobile

---

## Phase 6: i18n & Polish (Week 10)

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

## Phase 7: Deploy & Production Hardening (Week 11-12)

**Goal**: Production deployment and operational readiness

### Deliverables

- [x] Frontend Dockerfile (Quasar PWA with Webpack)
- [x] Backend Dockerfile (FastAPI)
- [x] CouchDB Dockerfile with config
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
