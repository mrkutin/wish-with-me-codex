# Database Design

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ WISHLISTS : owns
    USERS ||--o{ SOCIAL_ACCOUNTS : has
    USERS ||--o{ REFRESH_TOKENS : has
    WISHLISTS ||--o{ ITEMS : contains
    WISHLISTS ||--o{ SHARE_LINKS : has
    ITEMS ||--o{ MARKS : has
    USERS ||--o{ MARKS : creates
    USERS ||--o{ NOTIFICATIONS : receives

    USERS {
        uuid id PK
        string email UK
        string password_hash NULL
        string name
        text avatar_base64
        text bio NULL
        string public_url_slug UK NULL
        jsonb social_links NULL
        string locale
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at NULL
    }

    SOCIAL_ACCOUNTS {
        uuid id PK
        uuid user_id FK
        string provider
        string provider_user_id
        string email NULL
        jsonb profile_data
        timestamp created_at
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        string device_info NULL
        timestamp expires_at
        timestamp created_at
        boolean revoked
    }

    WISHLISTS {
        uuid id PK
        uuid owner_id FK
        string title
        text description NULL
        string cover_image_base64 NULL
        integer item_count
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at NULL
        bigint sync_version
    }

    ITEMS {
        uuid id PK
        uuid wishlist_id FK
        string source_url NULL
        string title
        text description NULL
        decimal price_amount NULL
        string price_currency NULL
        text image_url NULL
        text image_base64 NULL
        integer quantity
        integer marked_quantity
        string status
        jsonb resolution_error NULL
        integer sort_order
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at NULL
        bigint sync_version
    }

    SHARE_LINKS {
        uuid id PK
        uuid wishlist_id FK
        string token UK
        string link_type
        timestamp expires_at NULL
        integer access_count
        timestamp created_at
        boolean revoked
    }

    MARKS {
        uuid id PK
        uuid item_id FK
        uuid user_id FK
        integer quantity
        timestamp created_at
        timestamp updated_at
    }

    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        string type
        jsonb payload
        boolean read
        timestamp created_at
    }
```

---

## 2. Schema Definitions

### 2.1 Users Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),  -- NULL for social-only users
    name VARCHAR(100) NOT NULL,
    avatar_base64 TEXT NOT NULL,  -- Required, default provided on registration
    bio TEXT,
    public_url_slug VARCHAR(50) UNIQUE,  -- e.g., "john-doe" for /u/john-doe
    social_links JSONB DEFAULT '{}',  -- {"instagram": "...", "telegram": "..."}
    locale VARCHAR(10) NOT NULL DEFAULT 'ru',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,

    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT slug_format CHECK (public_url_slug IS NULL OR public_url_slug ~* '^[a-z0-9-]+$')
);

CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_public_url_slug ON users(public_url_slug) WHERE deleted_at IS NULL AND public_url_slug IS NOT NULL;
```

### 2.2 Social Accounts Table

```sql
CREATE TABLE social_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,  -- 'google', 'apple', 'yandex', 'sber'
    provider_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    profile_data JSONB DEFAULT '{}',  -- Store available social data for future features
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_provider_user UNIQUE (provider, provider_user_id)
);

CREATE INDEX idx_social_accounts_user_id ON social_accounts(user_id);
CREATE INDEX idx_social_accounts_provider_lookup ON social_accounts(provider, provider_user_id);
```

### 2.3 Refresh Tokens Table

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    device_info VARCHAR(255),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at) WHERE NOT revoked;
```

### 2.4 Wishlists Table

```sql
CREATE TABLE wishlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    cover_image_base64 TEXT,
    item_count INTEGER NOT NULL DEFAULT 0,  -- Denormalized for performance
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    sync_version BIGINT NOT NULL DEFAULT 0  -- For offline sync conflict detection
);

CREATE INDEX idx_wishlists_owner_id ON wishlists(owner_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_wishlists_updated_at ON wishlists(updated_at);
```

### 2.5 Items Table

```sql
CREATE TYPE item_status AS ENUM ('pending', 'resolving', 'resolved', 'failed', 'manual');

CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wishlist_id UUID NOT NULL REFERENCES wishlists(id) ON DELETE CASCADE,
    source_url TEXT,  -- Original marketplace URL
    title VARCHAR(500) NOT NULL,
    description TEXT,
    price_amount DECIMAL(12, 2),
    price_currency VARCHAR(3),  -- ISO 4217
    image_url TEXT,  -- Original image URL (for reference)
    image_base64 TEXT,  -- Stored image data
    quantity INTEGER NOT NULL DEFAULT 1,
    marked_quantity INTEGER NOT NULL DEFAULT 0,  -- Denormalized
    status item_status NOT NULL DEFAULT 'manual',
    resolution_error JSONB,  -- Store error details if resolution failed
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    sync_version BIGINT NOT NULL DEFAULT 0,

    CONSTRAINT quantity_positive CHECK (quantity > 0),
    CONSTRAINT marked_quantity_valid CHECK (marked_quantity >= 0 AND marked_quantity <= quantity)
);

CREATE INDEX idx_items_wishlist_id ON items(wishlist_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_items_status ON items(status) WHERE status IN ('pending', 'resolving');
CREATE INDEX idx_items_updated_at ON items(updated_at);
```

### 2.6 Share Links Table

```sql
CREATE TYPE share_link_type AS ENUM ('view', 'mark');  -- Future: 'edit', 'admin'

CREATE TABLE share_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wishlist_id UUID NOT NULL REFERENCES wishlists(id) ON DELETE CASCADE,
    token VARCHAR(32) NOT NULL UNIQUE,  -- URL-safe random token
    link_type share_link_type NOT NULL DEFAULT 'mark',
    expires_at TIMESTAMPTZ,  -- NULL = never expires
    access_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_share_links_token ON share_links(token) WHERE NOT revoked;
CREATE INDEX idx_share_links_wishlist_id ON share_links(wishlist_id);
```

### 2.7 Marks Table

```sql
CREATE TABLE marks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_user_item_mark UNIQUE (item_id, user_id),
    CONSTRAINT mark_quantity_positive CHECK (quantity > 0)
);

CREATE INDEX idx_marks_item_id ON marks(item_id);
CREATE INDEX idx_marks_user_id ON marks(user_id);
```

### 2.8 Notifications Table

```sql
CREATE TYPE notification_type AS ENUM (
    'wishlist_shared',
    'item_marked',
    'item_unmarked',
    'item_resolved',
    'item_resolution_failed'
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type notification_type NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id) WHERE NOT read;
```

---

## 3. Pydantic Models (Python)

### 3.1 User Models

```python
# /services/core-api/app/models/user.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class SocialLinks(BaseModel):
    instagram: Optional[str] = None
    telegram: Optional[str] = None
    vk: Optional[str] = None
    twitter: Optional[str] = None
    facebook: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    public_url_slug: Optional[str] = Field(None, pattern=r'^[a-z0-9-]+$', max_length=50)
    social_links: Optional[SocialLinks] = None
    locale: str = Field(default='ru', pattern=r'^(ru|en)$')


class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=8)
    avatar_base64: Optional[str] = None  # Default avatar assigned if not provided


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    public_url_slug: Optional[str] = Field(None, pattern=r'^[a-z0-9-]+$', max_length=50)
    social_links: Optional[SocialLinks] = None
    avatar_base64: Optional[str] = None
    locale: Optional[str] = Field(None, pattern=r'^(ru|en)$')


class UserResponse(UserBase):
    id: UUID
    avatar_base64: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserPublicProfile(BaseModel):
    """Public profile visible to other users"""
    id: UUID
    name: str
    avatar_base64: str
    bio: Optional[str]
    social_links: Optional[SocialLinks]
```

### 3.2 Wishlist & Item Models

```python
# /services/core-api/app/models/wishlist.py

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ItemStatus(str, Enum):
    PENDING = 'pending'
    RESOLVING = 'resolving'
    RESOLVED = 'resolved'
    FAILED = 'failed'
    MANUAL = 'manual'


class WishlistBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)


class WishlistCreate(WishlistBase):
    cover_image_base64: Optional[str] = None


class WishlistUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    cover_image_base64: Optional[str] = None


class WishlistResponse(WishlistBase):
    id: UUID
    owner_id: UUID
    cover_image_base64: Optional[str]
    item_count: int
    created_at: datetime
    updated_at: datetime
    sync_version: int

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    price_amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    price_currency: Optional[str] = Field(None, pattern=r'^[A-Z]{3}$')
    quantity: int = Field(default=1, ge=1, le=999)


class ItemCreateFromUrl(BaseModel):
    source_url: HttpUrl
    quantity: int = Field(default=1, ge=1, le=999)


class ItemCreateManual(ItemBase):
    image_base64: Optional[str] = None


class ItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    price_amount: Optional[Decimal] = Field(None, ge=0)
    price_currency: Optional[str] = Field(None, pattern=r'^[A-Z]{3}$')
    image_base64: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1, le=999)
    sort_order: Optional[int] = None


class ItemResponse(ItemBase):
    id: UUID
    wishlist_id: UUID
    source_url: Optional[str]
    image_url: Optional[str]
    image_base64: Optional[str]
    status: ItemStatus
    resolution_error: Optional[dict]
    marked_quantity: int  # Visible to all EXCEPT owner
    sort_order: int
    created_at: datetime
    updated_at: datetime
    sync_version: int

    class Config:
        from_attributes = True


class ItemResponseForOwner(ItemBase):
    """Item response for wishlist owner - marked_quantity hidden"""
    id: UUID
    wishlist_id: UUID
    source_url: Optional[str]
    image_url: Optional[str]
    image_base64: Optional[str]
    status: ItemStatus
    resolution_error: Optional[dict]
    sort_order: int
    created_at: datetime
    updated_at: datetime
    sync_version: int

    class Config:
        from_attributes = True


class MarkCreate(BaseModel):
    quantity: int = Field(default=1, ge=1)


class MarkResponse(BaseModel):
    id: UUID
    item_id: UUID
    user_id: UUID
    quantity: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

### 3.3 Share Link Models

```python
# /services/core-api/app/models/share.py

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ShareLinkType(str, Enum):
    VIEW = 'view'
    MARK = 'mark'


class ShareLinkCreate(BaseModel):
    link_type: ShareLinkType = ShareLinkType.MARK
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ShareLinkResponse(BaseModel):
    id: UUID
    wishlist_id: UUID
    token: str
    link_type: ShareLinkType
    expires_at: Optional[datetime]
    access_count: int
    created_at: datetime
    share_url: str  # Full URL constructed by API

    class Config:
        from_attributes = True
```

### 3.4 Sync Models

```python
# /services/core-api/app/models/sync.py

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class SyncPullRequest(BaseModel):
    """Request to pull changes from server"""
    last_sync_at: Optional[datetime] = None
    wishlist_ids: Optional[List[UUID]] = None  # None = all user's wishlists


class SyncPushRequest(BaseModel):
    """Request to push local changes to server"""
    wishlists: List[dict]  # WishlistUpdate with id and sync_version
    items: List[dict]  # ItemUpdate with id, wishlist_id, and sync_version
    deleted_wishlist_ids: List[UUID] = []
    deleted_item_ids: List[UUID] = []
    client_timestamp: datetime


class SyncConflict(BaseModel):
    entity_type: str  # 'wishlist' or 'item'
    entity_id: UUID
    client_version: int
    server_version: int
    server_data: dict
    resolution: str = 'server_wins'  # For LWW, always server if newer


class SyncResponse(BaseModel):
    wishlists: List[dict]
    items: List[dict]
    deleted_wishlist_ids: List[UUID]
    deleted_item_ids: List[UUID]
    conflicts: List[SyncConflict]
    server_timestamp: datetime
```
