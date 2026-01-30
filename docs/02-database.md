# Database Design

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Overview

**Database**: CouchDB 3.x (document database with native sync protocol)

**Key Features**:
- Document-oriented storage (JSON)
- Native sync protocol for PouchDB
- _changes feed for item resolver
- Revision-based conflict resolution
- JWT authentication support

---

## 2. Document Types

### 2.1 Entity Relationships

```
USER --owns--> WISHLIST --contains--> ITEM
  |               |                      |
  |               +--has--> SHARE        +--has--> MARK
  |
  +--has--> SOCIAL_ACCOUNT
```

### 2.2 Access Control Model

Each document has an `access[]` array containing user IDs who can read/write the document.
PouchDB uses filtered replication to sync only documents the user has access to.

```javascript
// Example: Wishlist accessible by owner and one viewer
{
  "_id": "wishlist:abc123",
  "access": ["user:owner-id", "user:viewer-id"]
}
```

---

## 3. Document Schemas

### 3.1 User Document

```javascript
{
  "_id": "user:<uuid>",
  "_rev": "1-abc123",
  "type": "user",
  "email": "user@example.com",
  "password_hash": "$2b$12$...",  // bcrypt hash
  "name": "John Doe",
  "avatar_base64": "data:image/png;base64,...",
  "bio": "Love making wishlists!",
  "public_url_slug": "john-doe",
  "social_links": {
    "telegram": "@johndoe",
    "instagram": "johndoe"
  },
  "locale": "ru",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "deleted_at": null,
  "access": ["user:<uuid>"]  // Only self can access
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | string | Yes | `user:<uuid>` format |
| `type` | string | Yes | Always `"user"` |
| `email` | string | Yes | Unique email address |
| `password_hash` | string | No | bcrypt hash (null for social-only) |
| `name` | string | Yes | Display name (1-100 chars) |
| `avatar_base64` | string | Yes | Base64 encoded avatar image |
| `bio` | string | No | User bio (max 500 chars) |
| `public_url_slug` | string | No | Unique URL slug for public profile |
| `social_links` | object | No | Social media links |
| `locale` | string | Yes | `ru` or `en` |
| `access` | array | Yes | User IDs with access (self only) |

### 3.2 Social Account Document

```javascript
{
  "_id": "social:<uuid>",
  "_rev": "1-abc123",
  "type": "social_account",
  "user_id": "user:<uuid>",
  "provider": "google",  // google | apple | yandex | sber
  "provider_user_id": "12345678901234567890",
  "email": "user@gmail.com",
  "profile_data": {
    "name": "John Doe",
    "picture": "https://..."
  },
  "created_at": "2024-01-01T00:00:00Z",
  "access": ["user:<uuid>"]
}
```

### 3.3 Wishlist Document

```javascript
{
  "_id": "wishlist:<uuid>",
  "_rev": "2-def456",
  "type": "wishlist",
  "owner_id": "user:<uuid>",
  "title": "Birthday 2024",
  "description": "Things I want for my birthday",
  "cover_image_base64": "data:image/jpeg;base64,...",
  "icon": "🎂",
  "item_count": 5,  // Denormalized for display
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "deleted_at": null,
  "access": ["user:<owner-uuid>", "user:<viewer-uuid>"]
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `_id` | string | Yes | `wishlist:<uuid>` format |
| `type` | string | Yes | Always `"wishlist"` |
| `owner_id` | string | Yes | Reference to user document |
| `title` | string | Yes | Wishlist title (1-200 chars) |
| `description` | string | No | Description (max 2000 chars) |
| `cover_image_base64` | string | No | Cover image |
| `icon` | string | No | Emoji icon |
| `item_count` | integer | Yes | Denormalized item count |
| `access` | array | Yes | User IDs with access |

### 3.4 Item Document

```javascript
{
  "_id": "item:<uuid>",
  "_rev": "3-ghi789",
  "type": "item",
  "wishlist_id": "wishlist:<uuid>",
  "owner_id": "user:<uuid>",  // Denormalized from wishlist
  "source_url": "https://ozon.ru/product/123456",
  "title": "Wireless Headphones",
  "description": "Great sound quality, noise canceling",
  "price_amount": 5990.00,
  "price_currency": "RUB",
  "image_url": "https://cdn.ozon.ru/...",
  "image_base64": "data:image/jpeg;base64,...",
  "quantity": 2,
  "marked_quantity": 1,  // Denormalized, hidden from owner
  "status": "resolved",  // pending | resolving | resolved | failed | manual
  "resolution_error": null,
  "sort_order": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "deleted_at": null,
  "access": ["user:<owner-uuid>", "user:<viewer-uuid>"]  // Inherited from wishlist
}
```

**Status Values**:
| Status | Description |
|--------|-------------|
| `pending` | Waiting to be resolved |
| `resolving` | Currently being processed |
| `resolved` | Successfully extracted data |
| `failed` | Resolution failed |
| `manual` | Manually created item |

### 3.5 Mark Document

```javascript
{
  "_id": "mark:<uuid>",
  "_rev": "1-jkl012",
  "type": "mark",
  "item_id": "item:<uuid>",
  "wishlist_id": "wishlist:<uuid>",  // Denormalized
  "owner_id": "user:<uuid>",  // Wishlist owner (excluded from access)
  "marked_by": "user:<uuid>",  // Who created this mark
  "quantity": 1,
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z",
  "access": ["user:<viewer1>", "user:<viewer2>"]  // All viewers EXCEPT owner
}
```

**Important**: Mark documents have access arrays that EXCLUDE the wishlist owner.
This implements "surprise mode" - owners cannot see who marked their items.

### 3.6 Share Document

```javascript
{
  "_id": "share:<uuid>",
  "_rev": "1-mno345",
  "type": "share",
  "wishlist_id": "wishlist:<uuid>",
  "owner_id": "user:<uuid>",
  "token": "abc123def456ghi789",  // 32-char URL-safe token
  "link_type": "mark",  // view | mark
  "expires_at": "2024-06-01T00:00:00Z",  // null = never
  "access_count": 5,
  "revoked": false,
  "revoked_at": null,
  "granted_users": ["user:<viewer1>", "user:<viewer2>"],
  "created_at": "2024-01-01T00:00:00Z",
  "access": ["user:<owner-uuid>"]  // Only owner sees share docs
}
```

### 3.7 Notification Document

```javascript
{
  "_id": "notification:<uuid>",
  "_rev": "1-pqr678",
  "type": "notification",
  "user_id": "user:<uuid>",
  "notification_type": "item_resolved",
  "payload": {
    "wishlist_id": "wishlist:<uuid>",
    "item_id": "item:<uuid>",
    "item_title": "Wireless Headphones"
  },
  "read": false,
  "created_at": "2024-01-15T10:30:00Z",
  "access": ["user:<uuid>"]
}
```

**Notification Types**:
| Type | Description |
|------|-------------|
| `wishlist_shared` | Someone accessed a shared wishlist |
| `item_marked` | An item was marked (only for marks, not owner) |
| `item_unmarked` | An item was unmarked |
| `item_resolved` | Item resolution completed |
| `item_resolution_failed` | Item resolution failed |

---

## 4. Indexes

### 4.1 Mango Indexes

```javascript
// Index for access-based filtering (primary use case)
{
  "index": {
    "fields": ["access", "type"]
  },
  "name": "access-type-index",
  "type": "json"
}

// Index for items by wishlist
{
  "index": {
    "fields": ["wishlist_id", "type", "sort_order"]
  },
  "name": "items-by-wishlist-index",
  "type": "json"
}

// Index for pending items (for item resolver)
{
  "index": {
    "fields": ["type", "status"]
  },
  "name": "items-by-status-index",
  "type": "json"
}

// Index for marks by item
{
  "index": {
    "fields": ["item_id", "type"]
  },
  "name": "marks-by-item-index",
  "type": "json"
}
```

### 4.2 Design Documents

```javascript
// _design/app
{
  "_id": "_design/app",
  "views": {
    "by_type": {
      "map": "function(doc) { if(doc.type) emit(doc.type, null); }"
    },
    "pending_items": {
      "map": "function(doc) { if(doc.type === 'item' && doc.status === 'pending') emit(doc._id, null); }"
    },
    "items_by_wishlist": {
      "map": "function(doc) { if(doc.type === 'item' && !doc.deleted_at) emit([doc.wishlist_id, doc.sort_order], null); }"
    }
  }
}
```

---

## 5. TypeScript Types (Frontend)

```typescript
// /services/frontend/src/types/documents.ts

export interface BaseDocument {
  _id: string;
  _rev?: string;
  type: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  access: string[];
}

export interface User extends BaseDocument {
  type: 'user';
  email: string;
  password_hash?: string;
  name: string;
  avatar_base64: string;
  bio?: string;
  public_url_slug?: string;
  social_links?: Record<string, string>;
  locale: 'ru' | 'en';
}

export interface Wishlist extends BaseDocument {
  type: 'wishlist';
  owner_id: string;
  title: string;
  description?: string;
  cover_image_base64?: string;
  icon?: string;
  item_count: number;
}

export type ItemStatus = 'pending' | 'resolving' | 'resolved' | 'failed' | 'manual';

export interface Item extends BaseDocument {
  type: 'item';
  wishlist_id: string;
  owner_id: string;
  source_url?: string;
  title: string;
  description?: string;
  price_amount?: number;
  price_currency?: string;
  image_url?: string;
  image_base64?: string;
  quantity: number;
  marked_quantity: number;
  status: ItemStatus;
  resolution_error?: Record<string, unknown>;
  sort_order: number;
}

export interface Mark extends BaseDocument {
  type: 'mark';
  item_id: string;
  wishlist_id: string;
  owner_id: string;
  marked_by: string;
  quantity: number;
}

export type ShareLinkType = 'view' | 'mark';

export interface Share extends BaseDocument {
  type: 'share';
  wishlist_id: string;
  owner_id: string;
  token: string;
  link_type: ShareLinkType;
  expires_at?: string | null;
  access_count: number;
  revoked: boolean;
  revoked_at?: string | null;
  granted_users: string[];
}

export type NotificationType =
  | 'wishlist_shared'
  | 'item_marked'
  | 'item_unmarked'
  | 'item_resolved'
  | 'item_resolution_failed';

export interface Notification extends BaseDocument {
  type: 'notification';
  user_id: string;
  notification_type: NotificationType;
  payload: Record<string, unknown>;
  read: boolean;
}
```

---

## 6. Python Models (Backend)

```python
# /services/core-api/app/schemas.py

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class ItemStatus(str, Enum):
    PENDING = 'pending'
    RESOLVING = 'resolving'
    RESOLVED = 'resolved'
    FAILED = 'failed'
    MANUAL = 'manual'


class ShareLinkType(str, Enum):
    VIEW = 'view'
    MARK = 'mark'


# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8)
    name: str = Field(..., min_length=1, max_length=100)
    locale: str = Field(default='ru', pattern=r'^(ru|en)$')


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_base64: str
    bio: Optional[str] = None
    public_url_slug: Optional[str] = None
    social_links: Optional[dict] = None
    locale: str
    created_at: datetime
    updated_at: datetime


# Wishlist Schemas
class WishlistCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    cover_image_base64: Optional[str] = None
    icon: Optional[str] = None


class WishlistResponse(BaseModel):
    id: str
    owner_id: str
    title: str
    description: Optional[str]
    cover_image_base64: Optional[str]
    icon: Optional[str]
    item_count: int
    created_at: datetime
    updated_at: datetime


# Item Schemas
class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    price_amount: Optional[Decimal] = Field(None, ge=0)
    price_currency: Optional[str] = Field(None, pattern=r'^[A-Z]{3}$')
    image_base64: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=999)
    source_url: Optional[str] = None


class ItemResponse(BaseModel):
    id: str
    wishlist_id: str
    source_url: Optional[str]
    title: str
    description: Optional[str]
    price_amount: Optional[Decimal]
    price_currency: Optional[str]
    image_url: Optional[str]
    image_base64: Optional[str]
    quantity: int
    marked_quantity: int  # Hidden from owner
    status: ItemStatus
    resolution_error: Optional[dict]
    sort_order: int
    created_at: datetime
    updated_at: datetime


# Share Schemas
class ShareCreate(BaseModel):
    link_type: ShareLinkType = ShareLinkType.MARK
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ShareResponse(BaseModel):
    id: str
    wishlist_id: str
    token: str
    link_type: ShareLinkType
    expires_at: Optional[datetime]
    access_count: int
    created_at: datetime
    share_url: str


# Mark Schemas
class MarkCreate(BaseModel):
    quantity: int = Field(default=1, ge=1)


class MarkResponse(BaseModel):
    id: str
    item_id: str
    marked_by: str
    quantity: int
    created_at: datetime
```

---

## 7. CouchDB Configuration

### 7.1 Local Configuration

```ini
# /couchdb/local.ini

[chttpd]
port = 5984
bind_address = 0.0.0.0

[chttpd_auth]
authentication_handlers = {chttpd_auth, jwt_authentication_handler}, {chttpd_auth, cookie_authentication_handler}, {chttpd_auth, default_authentication_handler}

[jwt_auth]
required_claims = exp, sub
algorithms = HS256

[cors]
origins = https://wishwith.me, http://localhost:9000
credentials = true
methods = GET, PUT, POST, DELETE, OPTIONS
headers = accept, authorization, content-type, origin, referer

[couchdb]
single_node = true
max_document_size = 8388608  # 8MB for base64 images
```

### 7.2 Database Setup

```bash
# Create database
curl -X PUT http://admin:password@localhost:5984/wishwithme

# Create indexes
curl -X POST http://admin:password@localhost:5984/wishwithme/_index \
  -H "Content-Type: application/json" \
  -d '{"index": {"fields": ["access", "type"]}, "name": "access-type-index"}'

# Upload design document
curl -X PUT http://admin:password@localhost:5984/wishwithme/_design/app \
  -H "Content-Type: application/json" \
  -d @design-doc.json
```

---

## 8. Data Integrity

### 8.1 Soft Deletes

All documents use `deleted_at` field for soft deletes:
- `null` = active
- ISO timestamp = deleted

Queries must filter: `deleted_at: { $eq: null }`

### 8.2 Denormalization

For performance, some data is denormalized:
- `item_count` on wishlists
- `marked_quantity` on items
- `owner_id` on items (from wishlist)

Update triggers must maintain consistency.

### 8.3 Access Array Consistency

When sharing a wishlist:
1. Add user to wishlist's `access[]`
2. Add user to all items' `access[]`
3. Add user to share's `granted_users[]`

When revoking:
1. Remove user from all related documents
2. Set share's `revoked = true`
