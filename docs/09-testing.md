# Testing Strategy

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Overview

| Layer | Framework | Runner |
|-------|-----------|--------|
| Frontend Unit | Vitest | Vitest |
| Frontend Component | Vitest + Vue Test Utils | Vitest |
| Frontend E2E | Playwright | Playwright |
| Backend Unit | pytest | pytest |
| Backend Integration | pytest + httpx | pytest |

---

## 2. Frontend Testing

### 2.1 Setup

```typescript
// /services/frontend/vitest.config.ts

import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { quasar } from '@quasar/vite-plugin';
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [
    vue(),
    quasar({ autoImportComponentCase: 'pascal' }),
    tsconfigPaths()
  ],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,ts}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,vue}'],
      exclude: ['src/**/*.d.ts', 'src/i18n/**']
    }
  }
});
```

### 2.2 Test Setup File

```typescript
// /services/frontend/tests/setup.ts

import { config } from '@vue/test-utils';
import { Quasar } from 'quasar';
import { createI18n } from 'vue-i18n';
import { createTestingPinia } from '@pinia/testing';
import { vi } from 'vitest';
import messages from '@/i18n';

// Mock RxDB
vi.mock('@/services/rxdb', () => ({
  getDatabase: vi.fn(() => Promise.resolve({
    wishlists: {
      find: vi.fn(() => ({ $ : { subscribe: vi.fn() } })),
      insert: vi.fn()
    },
    items: {
      find: vi.fn(() => ({ $ : { subscribe: vi.fn() } })),
      insert: vi.fn()
    }
  }))
}));

// Global plugins
const i18n = createI18n({
  locale: 'en',
  messages,
  legacy: false
});

config.global.plugins = [
  Quasar,
  i18n,
  createTestingPinia({ createSpy: vi.fn })
];

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  }))
});
```

### 2.3 Component Test Example

```typescript
// /services/frontend/src/components/ItemCard.spec.ts

import { describe, it, expect, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import ItemCard from './ItemCard.vue';

describe('ItemCard', () => {
  const mockItem = {
    id: '123',
    title: 'Test Item',
    price: 5990,
    currency: 'RUB',
    image_base64: null,
    status: 'resolved',
    quantity: 1,
    marked_quantity: 0
  };

  it('renders item title', () => {
    const wrapper = mount(ItemCard, {
      props: { item: mockItem, isOwner: true }
    });
    expect(wrapper.text()).toContain('Test Item');
  });

  it('hides marked_quantity from owner', () => {
    const itemWithMarks = { ...mockItem, marked_quantity: 1 };
    const wrapper = mount(ItemCard, {
      props: { item: itemWithMarks, isOwner: true }
    });
    expect(wrapper.text()).not.toContain('Marked');
  });

  it('shows mark button to viewer', () => {
    const wrapper = mount(ItemCard, {
      props: { item: mockItem, isOwner: false }
    });
    expect(wrapper.find('[data-testid="mark-button"]').exists()).toBe(true);
  });

  it('shows resolving state', () => {
    const resolvingItem = { ...mockItem, status: 'resolving' };
    const wrapper = mount(ItemCard, {
      props: { item: resolvingItem, isOwner: true }
    });
    expect(wrapper.find('.q-skeleton').exists()).toBe(true);
  });

  it('shows error state with retry', async () => {
    const failedItem = { ...mockItem, status: 'failed' };
    const wrapper = mount(ItemCard, {
      props: { item: failedItem, isOwner: true }
    });

    const retryButton = wrapper.find('[data-testid="retry-button"]');
    expect(retryButton.exists()).toBe(true);

    await retryButton.trigger('click');
    expect(wrapper.emitted('retry')).toBeTruthy();
  });
});
```

### 2.4 Composable Test Example

```typescript
// /services/frontend/src/composables/useWishlists.spec.ts

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useWishlists } from './useWishlists';

describe('useWishlists', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('loads wishlists reactively', async () => {
    const { wishlists, loading } = useWishlists();

    expect(loading.value).toBe(true);
    // Wait for RxDB subscription
    await vi.waitFor(() => !loading.value);
    expect(Array.isArray(wishlists.value)).toBe(true);
  });

  it('creates wishlist', async () => {
    const { createWishlist } = useWishlists();

    const result = await createWishlist({
      title: 'Birthday List',
      description: 'My birthday wishlist'
    });

    expect(result.title).toBe('Birthday List');
  });
});
```

---

## 3. Backend Testing

### 3.1 Pytest Configuration

```python
# /services/core-api/pytest.ini

[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    slow: marks tests as slow
    integration: marks tests requiring database
```

### 3.2 Conftest

```python
# /services/core-api/tests/conftest.py

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db import Base, get_db
from app.config import settings

# Test database URL
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    settings.POSTGRES_DB,
    f"{settings.POSTGRES_DB}_test"
)

@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_client(client, db_session):
    """Client with authenticated user"""
    # Create test user
    from app.security import hash_password
    from app.models import User

    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        name="Test User"
    )
    db_session.add(user)
    await db_session.commit()

    # Login
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    token = response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    yield client, user
```

### 3.3 API Test Examples

```python
# /services/core-api/tests/test_wishlists.py

import pytest

@pytest.mark.asyncio
async def test_create_wishlist(auth_client):
    client, user = auth_client

    response = await client.post("/api/v1/wishlists", json={
        "title": "Birthday List",
        "description": "Things I want"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Birthday List"
    assert data["owner_id"] == str(user.id)

@pytest.mark.asyncio
async def test_list_wishlists(auth_client):
    client, user = auth_client

    # Create a wishlist first
    await client.post("/api/v1/wishlists", json={"title": "List 1"})
    await client.post("/api/v1/wishlists", json={"title": "List 2"})

    response = await client.get("/api/v1/wishlists")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

@pytest.mark.asyncio
async def test_owner_cannot_see_marks(auth_client):
    client, user = auth_client

    # Create wishlist with item
    wl_response = await client.post("/api/v1/wishlists", json={"title": "Test"})
    wishlist_id = wl_response.json()["id"]

    item_response = await client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={"title": "Gift", "quantity": 1}
    )

    # Get item as owner - should not see marked_quantity
    response = await client.get(f"/api/v1/wishlists/{wishlist_id}/items")
    items = response.json()

    assert "marked_quantity" not in items[0] or items[0].get("marked_quantity") is None
```

### 3.4 Sync Endpoint Tests

```python
# /services/core-api/tests/test_sync.py

import pytest
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_pull_returns_documents(auth_client):
    client, user = auth_client

    # Create some data
    await client.post("/api/v1/wishlists", json={"title": "List 1"})
    await client.post("/api/v1/wishlists", json={"title": "List 2"})

    # Pull with no checkpoint
    response = await client.get("/api/v1/sync/pull/wishlists")

    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 2
    assert "checkpoint" in data

@pytest.mark.asyncio
async def test_pull_with_checkpoint(auth_client):
    client, user = auth_client

    # Create initial data
    await client.post("/api/v1/wishlists", json={"title": "Old"})

    # Get checkpoint
    pull1 = await client.get("/api/v1/sync/pull/wishlists")
    checkpoint = pull1.json()["checkpoint"]

    # Create new data
    await client.post("/api/v1/wishlists", json={"title": "New"})

    # Pull from checkpoint
    response = await client.get("/api/v1/sync/pull/wishlists", params={
        "checkpoint_updated_at": checkpoint["updated_at"],
        "checkpoint_id": checkpoint["id"]
    })

    assert len(response.json()["documents"]) == 1
    assert response.json()["documents"][0]["title"] == "New"

@pytest.mark.asyncio
async def test_push_creates_documents(auth_client):
    client, user = auth_client

    response = await client.post("/api/v1/sync/push/wishlists", json={
        "documents": [
            {
                "id": "client-uuid-1",
                "title": "From Client",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "_deleted": False
            }
        ]
    })

    assert response.status_code == 200
    assert response.json()["conflicts"] == []

    # Verify created
    wishlists = await client.get("/api/v1/wishlists")
    assert any(w["title"] == "From Client" for w in wishlists.json())
```

---

## 4. E2E Testing

### 4.1 Playwright Setup

```typescript
// /services/frontend/playwright.config.ts

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:9000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] }
    }
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:9000',
    reuseExistingServer: !process.env.CI
  }
});
```

### 4.2 E2E Test Example

```typescript
// /services/frontend/e2e/wishlist.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Wishlist', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'testpass123');
    await page.click('[data-testid="login-button"]');
    await expect(page).toHaveURL('/wishlists');
  });

  test('create wishlist', async ({ page }) => {
    await page.click('[data-testid="create-wishlist"]');
    await page.fill('[data-testid="wishlist-title"]', 'Birthday Gifts');
    await page.click('[data-testid="save-wishlist"]');

    await expect(page.locator('text=Birthday Gifts')).toBeVisible();
  });

  test('add item from URL', async ({ page }) => {
    // Navigate to existing wishlist
    await page.click('text=Birthday Gifts');

    // Add item
    await page.click('[data-testid="add-item"]');
    await page.fill('[data-testid="item-url"]', 'https://example.com/product');
    await page.click('[data-testid="resolve-url"]');

    // Wait for resolution
    await expect(page.locator('[data-testid="item-card"]')).toBeVisible({ timeout: 30000 });
  });

  test('share wishlist', async ({ page }) => {
    await page.click('text=Birthday Gifts');
    await page.click('[data-testid="share-button"]');

    await expect(page.locator('[data-testid="share-link"]')).toBeVisible();

    // Copy link
    await page.click('[data-testid="copy-link"]');
    await expect(page.locator('text=Link copied')).toBeVisible();
  });

  test('offline indicator shows when offline', async ({ page, context }) => {
    await context.setOffline(true);

    await expect(page.locator('[data-testid="offline-banner"]')).toBeVisible();
    await expect(page.locator('text=You\'re offline')).toBeVisible();

    await context.setOffline(false);
    await expect(page.locator('[data-testid="offline-banner"]')).not.toBeVisible();
  });
});
```

---

## 5. Test Coverage Requirements

| Area | Minimum Coverage |
|------|-----------------|
| Backend API endpoints | 90% |
| Frontend composables | 80% |
| Frontend components | 70% |
| E2E critical paths | 100% |

### Critical Paths (E2E)

1. User registration and login
2. Create wishlist and add items
3. Share wishlist via link
4. Mark item as viewer
5. Offline mode and sync

---

## 6. CI Integration

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
        working-directory: services/core-api
      - uses: codecov/codecov-action@v4

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
        working-directory: services/frontend
      - run: npm run test:unit -- --coverage
        working-directory: services/frontend
      - run: npx playwright install --with-deps
        working-directory: services/frontend
      - run: npm run test:e2e
        working-directory: services/frontend
```
