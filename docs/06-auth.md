# Authentication & Security

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Authentication Methods

| Method | Provider | Notes |
|--------|----------|-------|
| Email/Password | Native | Min 8 characters |
| OAuth 2.0 | Google | Most common |
| OAuth 2.0 | Apple | Required for iOS |
| OAuth 2.0 | Yandex ID | Popular in Russia |
| OAuth 2.0 | Sber ID | Popular in Russia |

---

## 2. Token Strategy

### 2.1 Access Token

- **Type**: JWT
- **Expiry**: 15 minutes
- **Storage**: In-memory (Pinia store)
- **Claims**: `sub` (user_id), `exp`, `iat`

### 2.2 Refresh Token

- **Type**: Opaque random string
- **Expiry**: 30 days
- **Storage**: httpOnly cookie + hashed in DB
- **Rotation**: New token on each refresh

### 2.3 Token Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB
    participant Redis

    Client->>API: POST /auth/login
    API->>DB: Verify credentials
    API->>DB: Create refresh_token record
    API->>Redis: Store access_token in blocklist (for revocation)
    API-->>Client: { access_token, refresh_token }

    Note over Client: Store access_token in memory
    Note over Client: Store refresh_token in httpOnly cookie

    Client->>API: GET /wishlists (with access_token)
    API->>Redis: Check blocklist
    API-->>Client: 200 OK

    Note over Client: Access token expires after 15 min

    Client->>API: POST /auth/refresh (with refresh_token cookie)
    API->>DB: Verify refresh_token, rotate
    API-->>Client: { new_access_token, new_refresh_token }
```

---

## 3. OAuth Configuration

### 3.1 Google OAuth

```python
# /services/core-api/app/oauth/google.py

from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
```

### 3.2 Apple OAuth

```python
# /services/core-api/app/oauth/apple.py

oauth.register(
    name='apple',
    client_id=settings.APPLE_CLIENT_ID,
    client_secret=settings.APPLE_CLIENT_SECRET,  # Generated JWT
    authorize_url='https://appleid.apple.com/auth/authorize',
    access_token_url='https://appleid.apple.com/auth/token',
    client_kwargs={'scope': 'name email'}
)
```

### 3.3 Yandex ID

```python
# /services/core-api/app/oauth/yandex.py

oauth.register(
    name='yandex',
    client_id=settings.YANDEX_CLIENT_ID,
    client_secret=settings.YANDEX_CLIENT_SECRET,
    authorize_url='https://oauth.yandex.ru/authorize',
    access_token_url='https://oauth.yandex.ru/token',
    userinfo_endpoint='https://login.yandex.ru/info',
    client_kwargs={'scope': 'login:email login:info login:avatar'}
)
```

### 3.4 Sber ID

```python
# /services/core-api/app/oauth/sber.py

oauth.register(
    name='sber',
    client_id=settings.SBER_CLIENT_ID,
    client_secret=settings.SBER_CLIENT_SECRET,
    authorize_url='https://online.sberbank.ru/CSAFront/oidc/authorize',
    access_token_url='https://online.sberbank.ru/CSAFront/oidc/token',
    userinfo_endpoint='https://online.sberbank.ru/CSAFront/oidc/userinfo',
    client_kwargs={'scope': 'openid name email'}
)
```

---

## 4. Password Security

### 4.1 Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### 4.2 Password Requirements

- Minimum 8 characters
- No maximum length (reasonable limit: 128)
- No complexity requirements (per NIST guidelines)
- Check against common password list

### 4.3 Password Reset

```python
# Generate reset token
import secrets
reset_token = secrets.token_urlsafe(32)

# Store hashed token with expiry (1 hour)
await db.execute(
    password_resets.insert().values(
        user_id=user.id,
        token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
)

# Send email with reset link
reset_url = f"https://wishwith.me/password-reset/{reset_token}"
```

---

## 5. JWT Configuration

```python
# /services/core-api/app/security.py

from datetime import datetime, timedelta
from jose import jwt

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

---

## 6. API Security

### 6.1 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginRequest):
    ...

@app.post("/api/v1/auth/register")
@limiter.limit("3/minute")
async def register(request: Request, data: RegisterRequest):
    ...
```

### 6.2 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://wishwith.me",
        "https://www.wishwith.me",
        "http://localhost:9000"  # Dev only
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 6.3 Security Headers

```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

---

## 7. Authorization

### 7.1 Wishlist Access Rules

| Role | View | Edit | Delete | Mark |
|------|------|------|--------|------|
| Owner | Yes | Yes | Yes | No |
| Viewer (via share link) | Yes | No | No | Yes |
| Non-authenticated | No | No | No | No |

### 7.2 Surprise Mode

Wishlist owners MUST NOT see:
- `marked_quantity` on items
- Who marked items
- Mark timestamps

```python
def serialize_item(item: Item, is_owner: bool) -> dict:
    data = item.dict()
    if is_owner:
        # Hide marking info from owner (surprise mode)
        data.pop('marked_quantity', None)
    return data
```

---

## 8. Environment Variables

```bash
# Authentication
JWT_SECRET_KEY=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# OAuth - Google
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx

# OAuth - Apple
APPLE_CLIENT_ID=com.wishwithme.app
APPLE_TEAM_ID=xxx
APPLE_KEY_ID=xxx
APPLE_PRIVATE_KEY_PATH=/secrets/apple.p8

# OAuth - Yandex
YANDEX_CLIENT_ID=xxx
YANDEX_CLIENT_SECRET=xxx

# OAuth - Sber
SBER_CLIENT_ID=xxx
SBER_CLIENT_SECRET=xxx

# Redis (for token blocklist)
REDIS_URL=redis://localhost:6379/0
```
