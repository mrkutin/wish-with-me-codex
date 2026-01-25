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
| 6 | i18n & Polish | Week 10 |
| 7 | Deploy | Week 11-12 |

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

- [ ] Google OAuth setup
- [ ] Apple OAuth setup
- [ ] Yandex ID OAuth setup
- [ ] Sber ID OAuth setup
- [ ] OAuth callback handling
- [ ] Account linking (add OAuth to existing account)
- [ ] Social login buttons UI
- [ ] Profile with connected accounts

### Success Criteria

- User can sign up/login with any OAuth provider
- User can link additional providers
- User can disconnect providers (except last one)

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

- [ ] RxDB setup with schemas
- [ ] Wishlist collection + replication
- [ ] Item collection + replication
- [ ] Sync endpoints (pull/push)
- [ ] Conflict resolution (LWW)
- [ ] Service worker with Workbox
- [ ] Live replication (auto-sync)
- [ ] PWA manifest
- [ ] Offline banner UI
- [ ] Sync status indicator
- [ ] App install prompt

### Success Criteria

- App works fully offline
- Changes sync when online
- Conflicts resolved correctly
- PWA installable on mobile

---

## Phase 6: i18n & Polish (Week 10)

**Goal**: Localization and UI polish

### Deliverables

- [ ] Russian translations (complete)
- [ ] English translations (complete)
- [ ] Language auto-detection
- [ ] Language switcher in settings
- [ ] Empty states for all pages
- [ ] Error states for all scenarios
- [ ] Loading skeletons
- [ ] Pull-to-refresh
- [ ] Swipe actions (mobile)
- [ ] Accessibility audit + fixes
- [ ] Color contrast fixes

### Success Criteria

- App fully localized in RU and EN
- All empty/error states have proper UI
- Accessibility passes basic audit

---

## Phase 7: Deploy (Week 11-12)

**Goal**: Production deployment

### Deliverables

- [x] Frontend Dockerfile (Quasar PWA)
- [x] Backend Dockerfile (FastAPI)
- [ ] Kubernetes manifests
- [x] CI/CD pipeline (GitHub Actions)
- [x] Domain + SSL setup (wishwith.me, api.wishwith.me)
- [ ] CDN configuration
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Logging (structured JSON)
- [ ] Error tracking (Sentry)
- [ ] Security audit
- [ ] Load testing
- [ ] Backup strategy

### Success Criteria

- App deployed to production
- CI/CD runs on every push
- Monitoring alerts configured
- Backups running

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
