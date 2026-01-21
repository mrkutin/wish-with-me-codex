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
3. If tests fail, return to Step 4 (FIX)

#### Step 6: COMPLETE
When all checks pass:
1. Summarize what was implemented
2. List files changed
3. Note any follow-up items or technical debt
4. Update `docs/08-phases.md` checklist if a phase item was completed

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

## Quick Commands

When the user requests:

| User Says | Claude Does |
|-----------|-------------|
| "implement X" | Full workflow: plan → implement → review → fix → verify |
| "review my changes" | Run reviewer agent on recent changes |
| "fix review issues" | Address feedback, then re-review |
| "run tests" | Execute appropriate test suite |
| "check phase progress" | Read `docs/08-phases.md` and report status |

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
