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
import tsconfigPaths from 'vite-tsconfig-paths';

export default defineConfig({
  plugins: [
    vue(),
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

// Mock PouchDB
vi.mock('@/services/pouchdb', () => ({
  getDatabase: vi.fn(() => ({
    find: vi.fn(() => Promise.resolve({ docs: [] })),
    put: vi.fn(() => Promise.resolve({ ok: true })),
    get: vi.fn(() => Promise.resolve({})),
    changes: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      cancel: vi.fn()
    }))
  })),
  initDatabase: vi.fn(() => Promise.resolve()),
  destroyDatabase: vi.fn(() => Promise.resolve())
}));

// Mock PouchDB sync
vi.mock('@/services/pouchdb/sync', () => ({
  startSync: vi.fn(),
  stopSync: vi.fn(),
  getSyncStatus: vi.fn(() => ({
    isActive: false,
    isPaused: false,
    lastSync: null,
    error: null
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
    _id: 'item:123',
    type: 'item',
    title: 'Test Item',
    price_amount: 5990,
    price_currency: 'RUB',
    image_base64: null,
    status: 'resolved',
    quantity: 1,
    marked_quantity: 0,
    access: ['user:owner']
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
    // Wait for PouchDB query
    await vi.waitFor(() => !loading.value);
    expect(Array.isArray(wishlists.value)).toBe(true);
  });

  it('creates wishlist', async () => {
    const { create } = useWishlists();

    const result = await create({
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
    integration: marks tests requiring CouchDB
```

### 3.2 Conftest

```python
# /services/core-api/tests/conftest.py

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.config import settings

# Mock CouchDB client
@pytest.fixture
def mock_couchdb():
    """Create a mock CouchDB client."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value={})
    mock.put = AsyncMock(return_value={'ok': True})
    mock.find = AsyncMock(return_value={'docs': []})
    return mock

@pytest_asyncio.fixture
async def client(mock_couchdb):
    """Create test client with mocked CouchDB."""
    from app.couchdb import get_couchdb

    app.dependency_overrides[get_couchdb] = lambda: mock_couchdb

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_client(client, mock_couchdb):
    """Client with authenticated user."""
    from app.security import hash_password, create_access_token

    # Mock user in CouchDB
    test_user = {
        "_id": "user:test-user-id",
        "type": "user",
        "email": "test@example.com",
        "password_hash": hash_password("testpass123"),
        "name": "Test User",
        "access": ["user:test-user-id"]
    }

    mock_couchdb.get.return_value = test_user
    mock_couchdb.find.return_value = {"docs": [test_user]}

    # Create token
    token = create_access_token("user:test-user-id")
    client.headers["Authorization"] = f"Bearer {token}"

    yield client, test_user
```

### 3.3 API Test Examples

```python
# /services/core-api/tests/test_auth.py

import pytest

@pytest.mark.asyncio
async def test_login_success(client, mock_couchdb):
    from app.security import hash_password

    # Setup mock user
    mock_couchdb.find.return_value = {
        "docs": [{
            "_id": "user:123",
            "email": "test@example.com",
            "password_hash": hash_password("testpass123"),
            "name": "Test"
        }]
    }

    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpass123"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login_invalid_password(client, mock_couchdb):
    from app.security import hash_password

    mock_couchdb.find.return_value = {
        "docs": [{
            "_id": "user:123",
            "email": "test@example.com",
            "password_hash": hash_password("correct-password"),
            "name": "Test"
        }]
    }

    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrong-password"
    })

    assert response.status_code == 401
```

### 3.4 Share Endpoint Tests

```python
# /services/core-api/tests/test_share.py

import pytest

@pytest.mark.asyncio
async def test_create_share_link(auth_client, mock_couchdb):
    client, user = auth_client

    # Mock wishlist owned by user
    mock_couchdb.get.return_value = {
        "_id": "wishlist:123",
        "type": "wishlist",
        "owner_id": user["_id"],
        "title": "Test Wishlist",
        "access": [user["_id"]]
    }

    response = await client.post("/api/v1/wishlists/wishlist:123/share", json={
        "link_type": "mark"
    })

    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["link_type"] == "mark"

@pytest.mark.asyncio
async def test_access_share_link(auth_client, mock_couchdb):
    client, user = auth_client

    # Mock share document
    mock_couchdb.find.return_value = {
        "docs": [{
            "_id": "share:abc123",
            "token": "share-token-123",
            "wishlist_id": "wishlist:456",
            "owner_id": "user:other",
            "link_type": "mark",
            "revoked": False
        }]
    }

    # Mock wishlist
    mock_couchdb.get.side_effect = [
        {  # Share
            "_id": "share:abc123",
            "wishlist_id": "wishlist:456"
        },
        {  # Wishlist
            "_id": "wishlist:456",
            "title": "Shared List",
            "access": ["user:other"]
        }
    ]

    response = await client.post("/api/v1/share/share-token-123/access")

    assert response.status_code == 200
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
    command: 'quasar dev',
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

    // Wait for resolution (synced via PouchDB)
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
      couchdb:
        image: couchdb:3.3
        env:
          COUCHDB_USER: admin
          COUCHDB_PASSWORD: password
        ports:
          - 5984:5984
        options: >-
          --health-cmd "curl -f http://localhost:5984/"
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
        env:
          COUCHDB_URL: http://admin:password@localhost:5984
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
