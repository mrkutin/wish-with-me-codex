# CLAUDE.md - Development Workflow Instructions

> This file configures Claude Code's automated development workflow for the Wish With Me application.

---

## Project Context

**Application**: Wish With Me - Offline-first wishlist PWA
**Stack**: Vue 3 + Quasar (frontend), FastAPI + PostgreSQL (backend), RxDB (offline sync)
**Documentation**: See [AGENTS.md](./AGENTS.md) for full specification

### Key Documentation Files
- Architecture: `docs/01-architecture.md`
- Database: `docs/02-database.md`
- API: `docs/03-api.md`
- Frontend: `docs/04-frontend.md`
- Offline Sync: `docs/05-offline-sync.md`
- Testing: `docs/09-testing.md`
- Implementation Phases: `docs/08-phases.md`

---

## Development Workflow

### Mandatory Workflow: Develop → Review → Fix Loop

When implementing ANY code changes, Claude Code MUST follow this iterative workflow:

```
┌─────────────────────────────────────────────────────────────┐
│  1. PLAN        → Read specs, create implementation plan   │
│  2. IMPLEMENT   → Write code using appropriate dev agent   │
│  3. REVIEW      → Use reviewer agent to analyze changes    │
│  4. FIX         → Address review findings                  │
│  5. VERIFY      → Run tests, repeat review if needed       │
│  6. COMPLETE    → All checks pass, summarize changes       │
└─────────────────────────────────────────────────────────────┘
```

### Workflow Steps in Detail

#### Step 1: PLAN
Before writing any code:
1. Read relevant documentation from `docs/` folder
2. Use TodoWrite to create a task breakdown
3. Identify which files will be affected
4. Check `docs/08-phases.md` for current phase requirements

#### Step 2: IMPLEMENT
Use the appropriate development agent based on the task:

| Task Type | Agent | When to Use |
|-----------|-------|-------------|
| Vue/Quasar components | `frontend-dev` | UI components, pages, composables |
| FastAPI endpoints | `backend-dev` | API routes, services, models |
| Database changes | `dba` | Schema migrations, queries |
| API design | `api-designer` | New endpoints, OpenAPI specs |
| Tests | `qa` | Unit tests, integration tests, E2E |
| DevOps | `devops` | Docker, CI/CD, deployment |
| Security | `security` | Auth, vulnerabilities, OWASP |

**Implementation Rules:**
- Follow patterns established in existing code
- Match the style in the relevant docs (e.g., `docs/04-frontend.md` for Vue patterns)
- Write tests alongside implementation when appropriate
- Use TypeScript for frontend, Python type hints for backend

#### Step 3: REVIEW (Mandatory)
After implementing, ALWAYS invoke the `reviewer` agent:

```
Use the reviewer agent to review the changes just made, focusing on:
- Code quality and adherence to project patterns
- Security vulnerabilities (OWASP top 10)
- Performance implications
- Test coverage
- Documentation accuracy
```

The reviewer agent will provide:
- **APPROVED**: Code meets standards, proceed to verify
- **CHANGES REQUESTED**: List of issues to fix

#### Step 4: FIX
If reviewer requests changes:
1. Create TodoWrite items for each issue
2. Address each issue using the appropriate dev agent
3. Mark todos complete as fixed
4. Return to Step 3 (REVIEW) - this loop continues until APPROVED

#### Step 5: VERIFY
Once review is approved:
1. Run relevant tests:
   - Frontend: `npm run test:unit` (in `services/frontend/`)
   - Backend: `pytest` (in `services/core-api/`)
   - E2E: `npm run test:e2e` (if UI changes)
2. Run linting/type checks:
   - Frontend: `npm run lint`
   - Backend: `ruff check .`
3. **CRITICAL**: Test on production servers:
   - SSH to Ubuntu: `ssh ubuntu@176.106.144.182` (for frontend, core-api)
   - SSH to Montreal: `ssh ubuntu@158.69.203.3` (for item-resolver)
   - Check logs: `docker logs wishwithme-core-api-1 --tail=100` and `docker logs wishwithme-core-api-2 --tail=100`
   - Check item-resolver: `docker logs wishwithme-item-resolver-1 --tail=100` and `docker logs wishwithme-item-resolver-2 --tail=100`
   - Verify functionality works as expected
   - **IMPORTANT**: Test everything yourself before saying it's done. Use curl, API calls, and log checks to verify functionality actually works end-to-end.
4. If tests fail, return to Step 4 (FIX)

#### Step 6: COMPLETE
When all checks pass:
1. Summarize what was implemented
2. List files changed
3. Note any follow-up items or technical debt
4. Update `docs/08-phases.md` checklist if a phase item was completed
5. **Deploy**: Push to GitHub `main` branch to trigger automated deployment via GitHub Actions

---

## Review Standards

The reviewer agent MUST check for:

### Code Quality
- [ ] Follows existing project patterns
- [ ] No code duplication
- [ ] Proper error handling
- [ ] Appropriate logging
- [ ] Clear naming conventions

### Security (Backend)
- [ ] No SQL injection vulnerabilities
- [ ] Proper authentication checks
- [ ] Input validation on all endpoints
- [ ] No sensitive data exposure
- [ ] Rate limiting where appropriate

### Security (Frontend)
- [ ] No XSS vulnerabilities
- [ ] Proper sanitization of user input
- [ ] Secure storage of tokens
- [ ] No sensitive data in localStorage

### Performance
- [ ] Efficient database queries (no N+1)
- [ ] Appropriate indexing
- [ ] Lazy loading where beneficial
- [ ] No unnecessary re-renders (Vue)

### Testing
- [ ] Unit tests for new functions
- [ ] Integration tests for API endpoints
- [ ] Component tests for Vue components
- [ ] E2E tests for critical user flows

---

## Agent-Specific Instructions

### frontend-dev Agent
When implementing frontend:
- Follow Vue 3 Composition API patterns from `docs/04-frontend.md`
- Use Quasar components (QBtn, QCard, etc.)
- Implement RxDB queries per `docs/05-offline-sync.md`
- Follow visual design from `docs/11-visual-design.md`
- Support both Russian and English (see `docs/07-i18n.md`)

### backend-dev Agent
When implementing backend:
- Follow FastAPI async patterns
- Use SQLAlchemy async ORM
- Implement schemas per `docs/03-api.md`
- Follow database patterns from `docs/02-database.md`
- Use proper dependency injection

### reviewer Agent
When reviewing:
- Be thorough but constructive
- Prioritize security issues
- Check against project documentation
- Verify test coverage
- Suggest specific fixes, not vague feedback

### qa Agent
When writing tests:
- Follow patterns in `docs/09-testing.md`
- Use Vitest for frontend unit tests
- Use pytest for backend tests
- Use Playwright for E2E tests
- Maintain coverage requirements (90% backend, 80% composables, 70% components)

---

## Testing & Deployment

### Split Server Architecture
**Application is deployed across TWO servers:**

**Ubuntu Server (Main Application):**
- **IP Address**: 176.106.144.182
- **User**: ubuntu
- **Domain**: wishwith.me, api.wishwith.me
- **Services**: nginx (load balancer), frontend, core-api-1, core-api-2, postgres, redis
- **Load Balancing**: nginx uses `ip_hash` for SSE sticky sessions
- **Docker Compose**: `docker-compose.ubuntu.yml`

**Montreal Server (Item Resolver Only):**
- **IP Address**: 158.69.203.3
- **User**: ubuntu
- **Access**: Via IP only (no domain), port 8001
- **Services**: nginx (load balancer), item-resolver-1, item-resolver-2
- **Load Balancing**: nginx uses `least_conn` for distributing requests
- **Docker Compose**: `docker-compose.montreal.yml`

### Testing Location (ALWAYS)
**Test on the appropriate production server:**

**Ubuntu Server (main app):**
- SSH: `ssh ubuntu@176.106.144.182`
- Navigate: `cd /home/ubuntu/wish-with-me-codex`
- Check logs: `docker-compose -f docker-compose.ubuntu.yml logs -f`
- Check service: `docker logs wishwithme-core-api-1 --tail=100` or `docker logs wishwithme-core-api-2 --tail=100`
- Verify status: `docker-compose -f docker-compose.ubuntu.yml ps`
- Test health: `curl -sf https://wishwith.me/health`

**Montreal Server (item-resolver):**
- SSH: `ssh ubuntu@158.69.203.3`
- Navigate: `cd /home/ubuntu/wish-with-me-codex`
- Check logs: `docker-compose -f docker-compose.montreal.yml logs -f`
- Verify status: `docker-compose -f docker-compose.montreal.yml ps`
- Test health: `curl -sf -H "Authorization: Bearer $RU_BEARER_TOKEN" http://158.69.203.3:8001/healthz`

### Deployment Method (ALWAYS AUTOMATIC)
**Deployment happens AUTOMATICALLY on push to main via TWO workflows:**

1. **deploy-ubuntu.yml** - Deploys frontend, core-api to Ubuntu (176.106.144.182)
   - Triggers on: `services/frontend/**`, `services/core-api/**`, `docker-compose.ubuntu.yml`, `nginx/**`
   - Manual: `gh workflow run deploy-ubuntu.yml`

2. **deploy-montreal.yml** - Deploys item-resolver to Montreal (158.69.203.3)
   - Triggers on: `services/item-resolver/**`, `docker-compose.montreal.yml`
   - Manual: `gh workflow run deploy-montreal.yml`

**Split Architecture:**
- `docker-compose.ubuntu.yml` - Main app (frontend, core-api-1, core-api-2, postgres, redis, nginx)
- `docker-compose.montreal.yml` - Item resolver (nginx, item-resolver-1, item-resolver-2)
- Core API connects to item-resolver via: `http://158.69.203.3:8001`
- SSE uses Redis pub/sub for cross-instance communication
- nginx uses `ip_hash` for SSE sticky sessions on Ubuntu
- nginx uses `least_conn` for item-resolver on Montreal
- Services on Ubuntu use shared network: `wishwithme-network`

See `docs/13-deployment.md` for full deployment documentation.

---

## Quick Commands

When the user requests:

| User Says | Claude Does |
|-----------|-------------|
| "implement X" | Full workflow: plan → implement → review → fix → verify |
| "review my changes" | Run reviewer agent on recent changes |
| "fix review issues" | Address feedback, then re-review |
| "run tests" | Execute appropriate test suite |
| "check phase progress" | Read `docs/08-phases.md` and report status |
| "deploy" | Push to GitHub main (triggers split deployment workflows) |
| "check logs ubuntu" | SSH to Ubuntu: `docker-compose -f docker-compose.ubuntu.yml logs -f` |
| "check logs montreal" | SSH to Montreal: `docker-compose -f docker-compose.montreal.yml logs -f` |
| "check status" | SSH to both servers and run `docker-compose ps` |

---

## Error Handling

If the workflow gets stuck:

1. **Review loop > 3 iterations**: Ask user if they want to proceed with known issues
2. **Tests consistently fail**: Create detailed bug report, ask for guidance
3. **Conflicting requirements**: Reference documentation, ask user to clarify
4. **Missing documentation**: Note the gap, proceed with best judgment, flag for review

---

## File Structure Reference

```
services/
├── frontend/           # Vue 3 + Quasar PWA
│   ├── src/
│   │   ├── components/ # Reusable Vue components
│   │   ├── pages/      # Route pages
│   │   ├── composables/# Vue composables
│   │   ├── stores/     # Pinia stores
│   │   └── services/   # RxDB, API clients
│   └── e2e/            # Playwright tests
│
├── core-api/           # FastAPI backend
│   ├── app/
│   │   ├── routers/    # API route handlers
│   │   ├── models.py   # SQLAlchemy models
│   │   └── schemas.py  # Pydantic schemas
│   └── tests/          # pytest tests
│
└── item-resolver/      # URL metadata service
```

---

## Remember

1. **Always review** - No code ships without reviewer agent approval
2. **Always test** - Run tests before marking complete
3. **Always document** - Update phase checklist when items complete
4. **Stay in scope** - Don't over-engineer beyond requirements
5. **Use the docs** - Reference `docs/` folder for all decisions
