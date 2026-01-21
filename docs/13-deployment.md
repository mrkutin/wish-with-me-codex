# Deployment

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Overview

| Component | Container | Port |
|-----------|-----------|------|
| Frontend (Quasar PWA) | `frontend` | 80 (internal) → 443 (external) |
| Core API (FastAPI) | `core-api` | 8000 |
| Item Resolver | `item-resolver` | 8080 |
| PostgreSQL | `postgres` | 5432 |
| Redis | `redis` | 6379 |
| Nginx (reverse proxy) | `nginx` | 80, 443 |

### 1.1 Server

```
Host: montreal
Hostname: 158.69.203.3
User: ubuntu
SSH Key: ~/.ssh/id_ed25519 (passphrase protected)
```

---

## 2. SSH Setup

### 2.1 Load SSH Key (Before Deployment)

```bash
# Add SSH key to agent (will prompt for passphrase)
ssh-add ~/.ssh/id_ed25519

# Verify key is loaded
ssh-add -l

# Test connection
ssh montreal "echo 'Connection successful'"
```

### 2.2 SSH Config

Ensure `~/.ssh/config` contains:

```
Host montreal
    Hostname 158.69.203.3
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
```

---

## 3. Directory Structure on Server

```
/home/ubuntu/wish-with-me-codex
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env                      # Production secrets (not in git)
├── nginx/
│   ├── nginx.conf
│   └── ssl/
│       ├── fullchain.pem
│       └── privkey.pem
├── data/
│   ├── postgres/             # PostgreSQL data volume
│   └── redis/                # Redis data volume
└── backups/                  # Database backups
```

---

## 4. Docker Compose Configuration

### 4.1 Base Configuration

```yaml
# docker-compose.yml

version: '3.8'

services:
  frontend:
    build:
      context: ./services/frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      - core-api
    networks:
      - wishwithme

  core-api:
    build:
      context: ./services/core-api
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - ITEM_RESOLVER_URL=http://item-resolver:8080
      - ITEM_RESOLVER_TOKEN=${ITEM_RESOLVER_TOKEN}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - APPLE_CLIENT_ID=${APPLE_CLIENT_ID}
      - APPLE_CLIENT_SECRET=${APPLE_CLIENT_SECRET}
      - YANDEX_CLIENT_ID=${YANDEX_CLIENT_ID}
      - YANDEX_CLIENT_SECRET=${YANDEX_CLIENT_SECRET}
      - SBER_CLIENT_ID=${SBER_CLIENT_ID}
      - SBER_CLIENT_SECRET=${SBER_CLIENT_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - wishwithme

  item-resolver:
    build:
      context: ./services/item-resolver
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      - RU_BEARER_TOKEN=${ITEM_RESOLVER_TOKEN}
      - LLM_MODE=${LLM_MODE:-live}
      - LLM_BASE_URL=${LLM_BASE_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL:-gpt-4o-mini}
    networks:
      - wishwithme
    # Playwright needs more resources
    shm_size: '2gb'

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wishwithme

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - wishwithme

networks:
  wishwithme:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

### 4.2 Production Override

```yaml
# docker-compose.prod.yml

version: '3.8'

services:
  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - core-api
    networks:
      - wishwithme

  frontend:
    # No exposed ports - nginx handles traffic

  core-api:
    # No exposed ports - nginx handles traffic
    environment:
      - DEBUG=false

  item-resolver:
    # No exposed ports - internal only
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  postgres:
    # No exposed ports in production
    volumes:
      - /opt/wishwithme/data/postgres:/var/lib/postgresql/data

  redis:
    # No exposed ports in production
    volumes:
      - /opt/wishwithme/data/redis:/data
```

---

## 5. Nginx Configuration

```nginx
# nginx/nginx.conf

user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript
               application/rss+xml application/atom+xml image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name wishwith.me www.wishwith.me;
        return 301 https://$server_name$request_uri;
    }

    # Main HTTPS server
    server {
        listen 443 ssl http2;
        server_name wishwith.me www.wishwith.me;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_session_tickets off;

        # Modern SSL configuration
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # HSTS
        add_header Strict-Transport-Security "max-age=63072000" always;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # API endpoints
        location /api/ {
            limit_req zone=api burst=20 nodelay;

            proxy_pass http://core-api:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # WebSocket support (for future live sync)
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        # Auth endpoints with stricter rate limiting
        location /api/v1/auth/ {
            limit_req zone=auth burst=5 nodelay;

            proxy_pass http://core-api:8000;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Frontend (PWA)
        location / {
            proxy_pass http://frontend:80;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # PWA caching
            location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
                proxy_pass http://frontend:80;
                expires 1y;
                add_header Cache-Control "public, immutable";
            }

            # Service worker - no cache
            location = /sw.js {
                proxy_pass http://frontend:80;
                expires off;
                add_header Cache-Control "no-cache, no-store, must-revalidate";
            }
        }

        # Health check endpoint
        location /health {
            proxy_pass http://core-api:8000/healthz;
        }
    }
}
```

---

## 6. Dockerfiles

### 6.1 Frontend Dockerfile

```dockerfile
# /services/frontend/Dockerfile

# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built PWA
COPY --from=builder /app/dist/pwa /usr/share/nginx/html

# Custom nginx config for SPA
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ { \
        expires 1y; \
        add_header Cache-Control "public, immutable"; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 6.2 Core API Dockerfile

```dockerfile
# /services/core-api/Dockerfile

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.3 Item Resolver Dockerfile

```dockerfile
# /services/item-resolver/Dockerfile

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 7. Environment Variables

### 7.1 Production .env Template

```bash
# /opt/wishwithme/.env

# Database
POSTGRES_USER=wishwithme
POSTGRES_PASSWORD=<generate-strong-password>
POSTGRES_DB=wishwithme

# Security
JWT_SECRET_KEY=<generate-32-char-secret>

# Item Resolver
ITEM_RESOLVER_TOKEN=<generate-token>
LLM_MODE=live
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<your-openai-key>
LLM_MODEL=gpt-4o-mini

# OAuth - Google
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# OAuth - Apple
APPLE_CLIENT_ID=
APPLE_CLIENT_SECRET=

# OAuth - Yandex
YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=

# OAuth - Sber
SBER_CLIENT_ID=
SBER_CLIENT_SECRET=
```

### 7.2 Generate Secrets

```bash
# Generate JWT secret
openssl rand -base64 32

# Generate database password
openssl rand -base64 24

# Generate API tokens
openssl rand -hex 32
```

---

## 8. Deployment Scripts

### 8.1 Initial Server Setup

```bash
#!/bin/bash
# scripts/server-setup.sh

set -e

echo "=== Setting up WishWithMe server ==="

# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create directories
sudo mkdir -p /opt/wishwithme/{nginx/ssl,data/postgres,data/redis,backups}
sudo chown -R $USER:$USER /opt/wishwithme

# Install certbot for SSL
sudo apt-get install -y certbot

echo "=== Server setup complete ==="
echo "Next steps:"
echo "1. Copy docker-compose files to /opt/wishwithme/"
echo "2. Create .env file with production secrets"
echo "3. Obtain SSL certificates with certbot"
echo "4. Run: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
```

### 8.2 Deploy Script

```bash
#!/bin/bash
# scripts/deploy.sh

set -e

# Configuration
SERVER="montreal"
DEPLOY_PATH="/opt/wishwithme"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "=== Deploying WishWithMe ==="

# Ensure SSH key is loaded
if ! ssh-add -l | grep -q "id_ed25519"; then
    echo "Loading SSH key..."
    ssh-add ~/.ssh/id_ed25519
fi

# Sync files to server
echo "Syncing files..."
rsync -avz --exclude 'node_modules' --exclude '.git' --exclude '__pycache__' \
    --exclude 'data' --exclude '.env' \
    ./ ${SERVER}:${DEPLOY_PATH}/

# Build and deploy on server
echo "Building and deploying..."
ssh ${SERVER} << EOF
    cd ${DEPLOY_PATH}

    # Pull latest images
    docker-compose ${COMPOSE_FILES} pull

    # Build custom images
    docker-compose ${COMPOSE_FILES} build

    # Run database migrations
    docker-compose ${COMPOSE_FILES} run --rm core-api alembic upgrade head

    # Restart services
    docker-compose ${COMPOSE_FILES} up -d

    # Cleanup old images
    docker image prune -f

    echo "Deployment complete!"
EOF

echo "=== Deployment finished ==="
```

### 8.3 Rollback Script

```bash
#!/bin/bash
# scripts/rollback.sh

set -e

SERVER="montreal"
DEPLOY_PATH="/opt/wishwithme"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "=== Rolling back WishWithMe ==="

ssh ${SERVER} << EOF
    cd ${DEPLOY_PATH}

    # Stop current deployment
    docker-compose ${COMPOSE_FILES} down

    # Restore from previous images (tagged)
    docker-compose ${COMPOSE_FILES} up -d --no-build

    echo "Rollback complete!"
EOF
```

---

## 9. SSL Certificate Setup

### 9.1 Initial Certificate (Certbot)

```bash
# On server
sudo certbot certonly --standalone -d wishwith.me -d www.wishwith.me

# Copy certificates to nginx directory
sudo cp /etc/letsencrypt/live/wishwith.me/fullchain.pem /opt/wishwithme/nginx/ssl/
sudo cp /etc/letsencrypt/live/wishwith.me/privkey.pem /opt/wishwithme/nginx/ssl/
sudo chown ubuntu:ubuntu /opt/wishwithme/nginx/ssl/*
```

### 9.2 Auto-Renewal

```bash
# Add to crontab
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/wishwith.me/*.pem /opt/wishwithme/nginx/ssl/ && docker-compose -f /opt/wishwithme/docker-compose.yml -f /opt/wishwithme/docker-compose.prod.yml restart nginx
```

---

## 10. Database Backup

### 10.1 Backup Script

```bash
#!/bin/bash
# scripts/backup-db.sh

set -e

BACKUP_DIR="/opt/wishwithme/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/wishwithme_${DATE}.sql.gz"

# Create backup
docker-compose exec -T postgres pg_dump -U wishwithme wishwithme | gzip > ${BACKUP_FILE}

# Keep only last 7 days of backups
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete

echo "Backup created: ${BACKUP_FILE}"
```

### 10.2 Restore Script

```bash
#!/bin/bash
# scripts/restore-db.sh

set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore-db.sh <backup-file.sql.gz>"
    exit 1
fi

BACKUP_FILE=$1

# Restore
gunzip -c ${BACKUP_FILE} | docker-compose exec -T postgres psql -U wishwithme wishwithme

echo "Database restored from: ${BACKUP_FILE}"
```

### 10.3 Automated Backups (Cron)

```bash
# Add to crontab on server
0 3 * * * /opt/wishwithme/scripts/backup-db.sh >> /var/log/wishwithme-backup.log 2>&1
```

---

## 11. Monitoring

### 11.1 Health Check Endpoints

| Endpoint | Service | Expected Response |
|----------|---------|-------------------|
| `/health` | Nginx → Core API | `{"status": "ok"}` |
| `/healthz` | Core API | `{"status": "ok", "checks": {...}}` |
| `/healthz` | Item Resolver | `{"status": "ok"}` |

### 11.2 Log Access

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f core-api
docker-compose logs -f item-resolver

# View nginx access logs
docker-compose exec nginx tail -f /var/log/nginx/access.log
```

### 11.3 Resource Monitoring

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

---

## 12. Useful Commands

### 12.1 Service Management

```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart core-api

# View service status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Scale item-resolver (if needed)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale item-resolver=2
```

### 12.2 Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U wishwithme wishwithme

# Connect to Redis
docker-compose exec redis redis-cli
```

### 12.3 Run Migrations

```bash
# Generate new migration
docker-compose exec core-api alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec core-api alembic upgrade head

# Rollback migration
docker-compose exec core-api alembic downgrade -1
```

---

## 13. Troubleshooting

### 13.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 502 Bad Gateway | Service not ready | Check service logs, wait for health check |
| Database connection failed | PostgreSQL not healthy | Check postgres logs, verify credentials |
| Item resolver timeout | Playwright resources | Increase `shm_size`, check memory |
| SSL certificate error | Expired/missing cert | Run certbot renewal |

### 13.2 Debug Mode

```bash
# Run with debug output
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up

# Check container health
docker inspect --format='{{json .State.Health}}' wishwithme-core-api-1
```

---

## 14. GitHub Actions CI/CD

### 14.1 Initial Server Setup for CI/CD

Before GitHub Actions can deploy to the server, you must perform this one-time setup:

```bash
# 1. SSH into the server
ssh ubuntu@158.69.203.3

# 2. Clone the repository (use HTTPS, not SSH)
cd /home/ubuntu
git clone https://github.com/mrkutin/wish-with-me-codex.git

# 3. Ensure git remote uses HTTPS (required for CI/CD)
cd wish-with-me-codex
git remote set-url origin https://github.com/mrkutin/wish-with-me-codex.git

# 4. Verify remote URL
git remote -v
# Should show: https://github.com/mrkutin/wish-with-me-codex.git
```

**Why HTTPS?** GitHub Actions uses a deployment SSH key to connect to the server, but that key doesn't have access to GitHub. Using HTTPS allows `git fetch` to work without authentication for public repos.

### 14.2 GitHub Secrets Required

Configure these secrets in GitHub repo → Settings → Secrets and variables → Actions:

**Common (Required for all):**

| Secret | Description |
|--------|-------------|
| `SSH_PRIVATE_KEY` | Ed25519 private key for server access |

**Item Resolver:**

| Secret | Description |
|--------|-------------|
| `RU_BEARER_TOKEN` | Item resolver API token |
| `BROWSER_CHANNEL` | Playwright browser channel |
| `HEADLESS` | Run browser headless (true/false) |
| `MAX_CONCURRENCY` | Max concurrent browser instances |
| `SSRF_ALLOWLIST_HOSTS` | Allowed hosts for SSRF protection |
| `PROXY_SERVER` | Proxy server URL (optional) |
| `PROXY_USERNAME` | Proxy username (optional) |
| `PROXY_PASSWORD` | Proxy password (optional) |
| `PROXY_BYPASS` | Proxy bypass list (optional) |
| `PROXY_IGNORE_CERT_ERRORS` | Ignore proxy cert errors (optional) |
| `RANDOM_UA` | Randomize user agent (optional) |
| `LLM_MODE` | LLM mode (live/mock) |
| `LLM_BASE_URL` | LLM API base URL |
| `LLM_API_KEY` | LLM API key |
| `LLM_MODEL` | LLM model name |
| `LLM_TIMEOUT_S` | LLM timeout in seconds |
| `LLM_MAX_CHARS` | Max chars for LLM context |

**Core API:**

| Secret | Description |
|--------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET_KEY` | JWT signing secret |
| `ITEM_RESOLVER_URL` | Item resolver service URL |
| `ITEM_RESOLVER_TOKEN` | Token for item resolver API |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `APPLE_CLIENT_ID` | Apple OAuth client ID |
| `APPLE_CLIENT_SECRET` | Apple OAuth client secret |
| `YANDEX_CLIENT_ID` | Yandex OAuth client ID |
| `YANDEX_CLIENT_SECRET` | Yandex OAuth client secret |
| `SBER_CLIENT_ID` | Sber OAuth client ID |
| `SBER_CLIENT_SECRET` | Sber OAuth client secret |

### 14.3 Deployment Workflows

Workflows are located in `.github/workflows/`:

| Workflow | File | Triggers |
|----------|------|----------|
| Item Resolver | `deploy-item-resolver.yml` | Push to `services/item-resolver/**` or manual |
| Frontend | `deploy-frontend.yml` | Push to `services/frontend/**` or manual |
| Core API | `deploy-core-api.yml` | Push to `services/core-api/**` or manual |

Each workflow:
1. Copies environment file to server
2. Pulls latest code via `git fetch && git reset --hard origin/main`
3. Rebuilds and restarts the Docker container
4. Runs health check to verify deployment

### 14.4 Manual Deployment

To manually trigger a deployment:

```bash
# Using GitHub CLI
gh workflow run deploy-item-resolver.yml
gh workflow run deploy-frontend.yml
gh workflow run deploy-core-api.yml

# Watch deployment progress
gh run watch
```

### 14.5 Troubleshooting CI/CD

| Issue | Cause | Solution |
|-------|-------|----------|
| `Permission denied (publickey)` on git fetch | Remote uses SSH | Run `git remote set-url origin https://...` on server |
| `No such file or directory` on scp | Repo not cloned | Clone repo on server first |
| Health check failed | Service didn't start | Check Docker logs on server |

---

## 15. Quick Reference

### 15.1 Server Access

```bash
# Load SSH key (required once per session)
ssh-add ~/.ssh/id_ed25519

# Connect to server
ssh montreal

# Direct command execution
ssh montreal "docker-compose -f /opt/wishwithme/docker-compose.yml ps"
```

### 15.2 Deploy Commands

```bash
# Full deployment
./scripts/deploy.sh

# Quick restart (no rebuild)
ssh montreal "cd /opt/wishwithme && docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart"

# View logs
ssh montreal "cd /opt/wishwithme && docker-compose logs -f --tail=100"
```
