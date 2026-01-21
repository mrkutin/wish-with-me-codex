# API Specification

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. API Overview

| Base URL | Description |
|----------|-------------|
| `/api/v1` | Main API prefix |
| `/api/v1/auth` | Authentication endpoints |
| `/api/v1/users` | User profile management |
| `/api/v1/wishlists` | Wishlist CRUD |
| `/api/v1/wishlists/{id}/items` | Item CRUD |
| `/api/v1/wishlists/{id}/share` | Share link management |
| `/api/v1/shared/{token}` | Shared wishlist access |
| `/api/v1/sync` | Offline sync |
| `/api/v1/notifications` | In-app notifications |

---

## 2. Authentication Endpoints

### POST `/api/v1/auth/register`

Register new user with email/password.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "John Doe",
  "locale": "ru"
}
```

**Response** `201 Created`:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "John Doe",
    "avatar_base64": "data:image/png;base64,...",
    "locale": "ru",
    "created_at": "2026-01-21T10:00:00Z"
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors**:
- `400`: Invalid input
- `409`: Email already registered

### POST `/api/v1/auth/login`

Login with email/password.

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** `200 OK`:
```json
{
  "user": { ... },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors**:
- `401`: Invalid credentials
- `403`: Account disabled

### POST `/api/v1/auth/password-reset-request`

Request password reset email.

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** `202 Accepted`:
```json
{
  "message": "If the email exists, a reset link has been sent"
}
```

### POST `/api/v1/auth/password-reset-confirm`

Confirm password reset with token.

**Request Body**:
```json
{
  "token": "reset_token_from_email",
  "new_password": "newSecurePassword123"
}
```

**Response** `200 OK`:
```json
{
  "message": "Password has been reset successfully"
}
```

**Errors**:
- `400`: Invalid or expired token
- `400`: Password does not meet requirements

### POST `/api/v1/auth/oauth/{provider}`

Initiate OAuth flow.

**Path Parameters**:
- `provider`: `google` | `apple` | `yandex` | `sber`

**Request Body**:
```json
{
  "redirect_uri": "https://app.wishwith.me/auth/callback"
}
```

**Response** `200 OK`:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random_state_token"
}
```

### POST `/api/v1/auth/oauth/{provider}/callback`

Complete OAuth flow.

**Request Body**:
```json
{
  "code": "authorization_code_from_provider",
  "state": "state_from_initiate"
}
```

**Response** `200 OK`:
```json
{
  "user": {
    "id": "uuid",
    "email": "user@gmail.com",
    "name": "John Doe",
    "avatar_base64": "data:image/png;base64,...",
    "locale": "ru"
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "is_new_user": true
}
```

### POST `/api/v1/auth/refresh`

Refresh access token.

**Request Body**:
```json
{
  "refresh_token": "eyJ..."
}
```

**Response** `200 OK`:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Errors**:
- `401`: Invalid or expired refresh token

### POST `/api/v1/auth/logout`

Logout and revoke tokens.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "refresh_token": "eyJ..."
}
```

**Response** `204 No Content`

---

## 3. User Endpoints

### GET `/api/v1/users/me`

Get current user profile.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "avatar_base64": "data:image/png;base64,...",
  "bio": "Love making wishlists!",
  "public_url_slug": "john-doe",
  "social_links": {
    "telegram": "@johndoe",
    "instagram": "johndoe"
  },
  "locale": "ru",
  "created_at": "2026-01-21T10:00:00Z",
  "updated_at": "2026-01-21T10:00:00Z"
}
```

### PATCH `/api/v1/users/me`

Update current user profile.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body** (partial update):
```json
{
  "name": "John Updated",
  "bio": "New bio",
  "avatar_base64": "data:image/jpeg;base64,...",
  "public_url_slug": "john-updated",
  "social_links": {
    "telegram": "@johnupdated"
  }
}
```

**Response** `200 OK`: Updated user object

**Errors**:
- `400`: Invalid input
- `409`: public_url_slug already taken

### DELETE `/api/v1/users/me`

Soft delete user account.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

### GET `/api/v1/users/{user_id}/public`

Get public profile of any user.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`:
```json
{
  "id": "uuid",
  "name": "John Doe",
  "avatar_base64": "data:image/png;base64,...",
  "bio": "Love making wishlists!",
  "social_links": { ... }
}
```

### GET `/api/v1/users/me/connected-accounts`

Get connected OAuth accounts.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`:
```json
{
  "accounts": [
    {
      "provider": "google",
      "email": "user@gmail.com",
      "connected_at": "2026-01-21T10:00:00Z"
    }
  ]
}
```

### POST `/api/v1/users/me/connect-account/{provider}`

Connect additional OAuth provider.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "code": "authorization_code",
  "state": "state_token"
}
```

**Response** `200 OK`: Updated connected accounts list

### DELETE `/api/v1/users/me/connected-accounts/{provider}`

Disconnect OAuth provider.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

**Errors**:
- `400`: Cannot disconnect last login method

---

## 4. Wishlist Endpoints

### GET `/api/v1/wishlists`

List user's wishlists.

**Headers**: `Authorization: Bearer <access_token>`

**Query Parameters**:
- `limit`: int (default: 20, max: 100)
- `offset`: int (default: 0)
- `sort`: `created_at` | `updated_at` | `title` (default: `updated_at`)
- `order`: `asc` | `desc` (default: `desc`)
- `search`: string (optional, search in title)

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": "uuid",
      "owner_id": "uuid",
      "title": "Birthday 2026",
      "description": "My birthday wishlist",
      "cover_image_base64": "data:image/jpeg;base64,...",
      "item_count": 5,
      "created_at": "2026-01-21T10:00:00Z",
      "updated_at": "2026-01-21T10:00:00Z",
      "sync_version": 3
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### POST `/api/v1/wishlists`

Create new wishlist.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "title": "Birthday 2026",
  "description": "My birthday wishlist",
  "cover_image_base64": "data:image/jpeg;base64,..."
}
```

**Response** `201 Created`: Wishlist object

### GET `/api/v1/wishlists/{wishlist_id}`

Get wishlist by ID.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`: Wishlist object with items

**Note**: If the requester is the owner, `marked_quantity` is hidden from items.

### PATCH `/api/v1/wishlists/{wishlist_id}`

Update wishlist.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body** (partial update):
```json
{
  "title": "Updated Title",
  "description": "Updated description"
}
```

**Response** `200 OK`: Updated wishlist object

**Errors**:
- `403`: Not the owner
- `404`: Wishlist not found

### DELETE `/api/v1/wishlists/{wishlist_id}`

Soft delete wishlist.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

---

## 5. Item Endpoints

### GET `/api/v1/wishlists/{wishlist_id}/items`

List items in wishlist.

**Headers**: `Authorization: Bearer <access_token>`

**Query Parameters**:
- `limit`: int (default: 50, max: 200)
- `offset`: int (default: 0)
- `status`: filter by status
- `search`: string (optional, search in title)

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": "uuid",
      "wishlist_id": "uuid",
      "source_url": "https://ozon.ru/product/...",
      "title": "Wireless Headphones",
      "description": "Great sound quality",
      "price_amount": "5990.00",
      "price_currency": "RUB",
      "image_url": "https://...",
      "image_base64": "data:image/jpeg;base64,...",
      "quantity": 1,
      "marked_quantity": 0,
      "status": "resolved",
      "sort_order": 0,
      "created_at": "2026-01-21T10:00:00Z",
      "updated_at": "2026-01-21T10:00:00Z",
      "sync_version": 1
    }
  ],
  "total": 1
}
```

**Note**: `marked_quantity` is returned as `0` for wishlist owners (surprise mode).

### POST `/api/v1/wishlists/{wishlist_id}/items`

Add item to wishlist (manual entry).

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "title": "Custom Item",
  "description": "A custom item",
  "price_amount": "1000.00",
  "price_currency": "RUB",
  "image_base64": "data:image/jpeg;base64,...",
  "quantity": 2
}
```

**Response** `201 Created`: Item object with `status: "manual"`

### POST `/api/v1/wishlists/{wishlist_id}/items/resolve`

Add item from URL (triggers item-resolver).

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "source_url": "https://www.ozon.ru/product/headphones-123456/",
  "quantity": 1
}
```

**Response** `202 Accepted`:
```json
{
  "id": "uuid",
  "wishlist_id": "uuid",
  "source_url": "https://www.ozon.ru/product/headphones-123456/",
  "title": "Loading...",
  "status": "resolving",
  "quantity": 1,
  "created_at": "2026-01-21T10:00:00Z",
  "sync_version": 0
}
```

The item will be updated asynchronously when resolution completes.

### GET `/api/v1/wishlists/{wishlist_id}/items/{item_id}`

Get single item.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`: Item object

### PATCH `/api/v1/wishlists/{wishlist_id}/items/{item_id}`

Update item.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body** (partial update):
```json
{
  "title": "Updated Title",
  "quantity": 3,
  "sort_order": 5
}
```

**Response** `200 OK`: Updated item object

### DELETE `/api/v1/wishlists/{wishlist_id}/items/{item_id}`

Soft delete item.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

### POST `/api/v1/wishlists/{wishlist_id}/items/{item_id}/retry-resolve`

Retry failed resolution.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `202 Accepted`: Item with `status: "resolving"`

---

## 6. Share Link Endpoints

### GET `/api/v1/wishlists/{wishlist_id}/share`

List share links for wishlist.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": "uuid",
      "wishlist_id": "uuid",
      "token": "abc123xyz",
      "link_type": "mark",
      "expires_at": null,
      "access_count": 5,
      "created_at": "2026-01-21T10:00:00Z",
      "share_url": "https://wishwith.me/s/abc123xyz"
    }
  ]
}
```

### POST `/api/v1/wishlists/{wishlist_id}/share`

Create share link.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "link_type": "mark",
  "expires_in_days": 30
}
```

**Response** `201 Created`: Share link object with QR code data

```json
{
  "id": "uuid",
  "wishlist_id": "uuid",
  "token": "abc123xyz",
  "link_type": "mark",
  "expires_at": "2026-02-20T10:00:00Z",
  "access_count": 0,
  "created_at": "2026-01-21T10:00:00Z",
  "share_url": "https://wishwith.me/s/abc123xyz",
  "qr_code_base64": "data:image/png;base64,..."
}
```

### DELETE `/api/v1/wishlists/{wishlist_id}/share/{share_id}`

Revoke share link.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

---

## 7. Shared Wishlist Access Endpoints

### GET `/api/v1/shared/{token}`

Access shared wishlist.

**Headers**: `Authorization: Bearer <access_token>` (required)

**Response** `200 OK`:
```json
{
  "wishlist": {
    "id": "uuid",
    "title": "Birthday 2026",
    "description": "My birthday wishlist",
    "owner": {
      "id": "uuid",
      "name": "John Doe",
      "avatar_base64": "data:image/png;base64,..."
    },
    "item_count": 5
  },
  "items": [
    {
      "id": "uuid",
      "title": "Wireless Headphones",
      "description": "Great sound quality",
      "price_amount": "5990.00",
      "price_currency": "RUB",
      "image_base64": "data:image/jpeg;base64,...",
      "quantity": 2,
      "marked_quantity": 1,
      "available_quantity": 1,
      "my_mark_quantity": 0
    }
  ],
  "permissions": ["view", "mark"]
}
```

**Errors**:
- `401`: Not authenticated
- `404`: Share link not found or expired

### GET `/api/v1/shared/{token}/preview`

Preview shared wishlist (unauthenticated).

**Response** `200 OK`:
```json
{
  "wishlist": {
    "title": "Birthday 2026",
    "owner_name": "John D.",
    "item_count": 5
  },
  "requires_auth": true,
  "auth_redirect": "/login?share_token=abc123xyz"
}
```

### POST `/api/v1/shared/{token}/items/{item_id}/mark`

Mark item (indicate intent to buy).

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "quantity": 1
}
```

**Response** `200 OK`:
```json
{
  "item_id": "uuid",
  "my_mark_quantity": 1,
  "total_marked_quantity": 2,
  "available_quantity": 0
}
```

**Errors**:
- `400`: Quantity exceeds available
- `403`: Cannot mark own wishlist items

### DELETE `/api/v1/shared/{token}/items/{item_id}/mark`

Unmark item.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `200 OK`:
```json
{
  "item_id": "uuid",
  "my_mark_quantity": 0,
  "total_marked_quantity": 1,
  "available_quantity": 1
}
```

---

## 8. Sync Endpoints

### POST `/api/v1/sync/pull/wishlists`

Pull wishlist changes from server (RxDB replication).

**Headers**: `Authorization: Bearer <access_token>`

**Query Parameters**:
- `checkpoint_updated_at`: ISO timestamp (optional)
- `checkpoint_id`: UUID (optional)
- `limit`: int (default: 50)

**Response** `200 OK`:
```json
{
  "documents": [ ... ],
  "checkpoint": {
    "updated_at": "2026-01-21T10:00:00Z",
    "id": "uuid"
  }
}
```

### POST `/api/v1/sync/push/wishlists`

Push wishlist changes to server (RxDB replication).

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "documents": [
    {
      "id": "uuid",
      "title": "Updated locally",
      "updated_at": "2026-01-21T09:00:00Z",
      "_deleted": false
    }
  ]
}
```

**Response** `200 OK`:
```json
{
  "conflicts": []
}
```

### POST `/api/v1/sync/pull/items`

Pull item changes from server (RxDB replication).

### POST `/api/v1/sync/push/items`

Push item changes to server (RxDB replication).

---

## 9. Notification Endpoints

### GET `/api/v1/notifications`

Get user notifications.

**Headers**: `Authorization: Bearer <access_token>`

**Query Parameters**:
- `unread_only`: boolean (default: false)
- `limit`: int (default: 20)
- `offset`: int (default: 0)

**Response** `200 OK`:
```json
{
  "items": [
    {
      "id": "uuid",
      "type": "item_resolved",
      "payload": {
        "wishlist_id": "uuid",
        "item_id": "uuid",
        "item_title": "Wireless Headphones"
      },
      "read": false,
      "created_at": "2026-01-21T10:00:00Z"
    }
  ],
  "unread_count": 3,
  "total": 15
}
```

### POST `/api/v1/notifications/read`

Mark notifications as read.

**Headers**: `Authorization: Bearer <access_token>`

**Request Body**:
```json
{
  "notification_ids": ["uuid1", "uuid2"]
}
```

**Response** `204 No Content`

### POST `/api/v1/notifications/read-all`

Mark all notifications as read.

**Headers**: `Authorization: Bearer <access_token>`

**Response** `204 No Content`

---

## 10. Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error message",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    },
    "trace_id": "abc123"
  }
}
```

**Standard Error Codes**:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request body |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
