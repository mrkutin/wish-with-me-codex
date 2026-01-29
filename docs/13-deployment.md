# Deployment

> Part of [Wish With Me Specification](../AGENTS.md)

---

## Overview

**The application is deployed on a single Ubuntu server:**

### Ubuntu Server
- **IP Address**: 176.106.144.182
- **User**: mrkutin
- **Location**: /home/mrkutin/wish-with-me-codex
- **Domain**: wishwith.me, api.wishwith.me
- **Services**: nginx, frontend, core-api-1, core-api-2, item-resolver-1, item-resolver-2, postgres, redis
- **Load Balancing**: nginx uses `ip_hash` for SSE sticky sessions
- **SSH Key Secret**: `SSH_PRIVATE_KEY_UBUNTU`

**DEPLOYMENT IS ALWAYS:**
- **Automatic**: Triggered on every push to `main` branch
- **Smart**: Only rebuilds changed services
- **Verified**: Health checks run after deployment
- **Safe**: Automatic rollback on failure

---

## 1. Architecture

### 1.1 Docker Compose Configuration

| File | Services |
|------|----------|
| `docker-compose.ubuntu.yml` | nginx, frontend, core-api-1, core-api-2, item-resolver-1, item-resolver-2, postgres, redis |

### 1.2 Components

| Component | Container(s) | External Access |
|-----------|--------------|-----------------|
| Nginx (reverse proxy) | `wishwithme-nginx` | 80, 443 (wishwith.me, api.wishwith.me) |
| Frontend (Quasar PWA) | `wishwithme-frontend` | Via nginx |
| Core API (FastAPI) | `wishwithme-core-api-1`, `wishwithme-core-api-2` | Via nginx (api.wishwith.me), load balanced |
| Item Resolver (DeepSeek + Playwright) | `wishwithme-item-resolver-1`, `wishwithme-item-resolver-2` | Internal Docker network |
| PostgreSQL | `wishwithme-postgres` | Internal only |
| Redis | `wishwithme-redis` | Internal only |

### 1.3 Service Communication

```
Internet
    ↓
Ubuntu Server (176.106.144.182)
┌──────────────────────────────────────────────────────────────────┐
│ Nginx (443/80) - ip_hash LB                                      │
│     ↓                                                            │
│ ┌─────────┬───────────────────────┬─────────────────────────────┐│
│ │         │                       │                             ││
│ │Frontend │   Core API (2x)       │   Item Resolver (2x)        ││
│ │         │   ┌─────────────────┐ │   ┌─────────────────────┐   ││
│ │         │   │ core-api-1     ├─┼───┤ item-resolver-1     │   ││
│ │         │   │ core-api-2     │ │   │ item-resolver-2     │   ││
│ │         │   └────────┬────────┘ │   │ (Playwright+DeepSeek)   ││
│ │         │            │          │   └─────────────────────┘   ││
│ │         │            ↓          │                             ││
│ │         │   Redis:6379 (pub/sub)│                             ││
│ │         │            │          │                             ││
│ │         │            ↓          │                             ││
│ │         │   Postgres:5432       │                             ││
│ └─────────┴───────────────────────┴─────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘

Key Features:
- SSE uses Redis pub/sub for cross-instance communication
- nginx ip_hash ensures SSE connections stick to same core-api instance
- Item resolver accessed via internal Docker network (http://item-resolver-1:8000)
- DeepSeek API used for product data extraction (text-based, no vision)
```

---

## 2. Server Access

```bash
# SSH to server
ssh mrkutin@176.106.144.182

# Navigate to project directory
cd /home/mrkutin/wish-with-me-codex

# Check all service logs
docker-compose -f docker-compose.ubuntu.yml logs -f

# Check specific services
docker logs wishwithme-core-api-1 --tail=100
docker logs wishwithme-core-api-2 --tail=100
docker logs wishwithme-item-resolver-1 --tail=100
docker logs wishwithme-item-resolver-2 --tail=100
docker logs wishwithme-frontend --tail=100
docker logs wishwithme-nginx --tail=100

# Check service status
docker-compose -f docker-compose.ubuntu.yml ps
```

---

## 3. Initial Server Setup

Run these commands once when setting up the server:

```bash
# 1. SSH into the server
ssh mrkutin@176.106.144.182

# 2. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 4. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. Clone repository
cd /home/mrkutin
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# 6. Ensure git uses HTTPS
git remote set-url origin https://github.com/mrkutin/wish-with-me-codex.git

# 7. Create production directories
mkdir -p /home/mrkutin/wishwithme-data/{postgres,redis}

# 8. Create .env file with production secrets
cp .env.example .env
nano .env  # Fill in production values

# 9. SSL Certificate Setup (see section 3.1)

# 10. Initial deployment
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

### 3.1 SSL Certificate Setup

```bash
# Install certbot
sudo apt-get install -y certbot

# Stop nginx if running (to free port 80)
docker-compose -f docker-compose.ubuntu.yml stop nginx

# Obtain certificates for all domains
sudo certbot certonly --standalone \
  -d wishwith.me \
  -d www.wishwith.me \
  -d api.wishwith.me \
  --agree-tos \
  --email your-email@example.com

# Create nginx SSL directory
mkdir -p nginx/ssl

# Copy certificates
sudo cp /etc/letsencrypt/live/wishwith.me/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/wishwith.me/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*

# Set up auto-renewal (cron job)
sudo crontab -e
# Add this line:
# 0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/wishwith.me/*.pem /home/mrkutin/wish-with-me-codex/nginx/ssl/ && docker-compose -f /home/mrkutin/wish-with-me-codex/docker-compose.ubuntu.yml restart nginx
```

---

## 4. GitHub Actions Configuration

### 4.1 Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `SSH_PRIVATE_KEY_UBUNTU` | Ed25519 private key for Ubuntu server |

**Generate SSH key:**
```bash
ssh-keygen -t ed25519 -C "github-actions-ubuntu@wishwith.me" -f ~/.ssh/github_actions_ubuntu
ssh-copy-id -i ~/.ssh/github_actions_ubuntu.pub mrkutin@176.106.144.182
cat ~/.ssh/github_actions_ubuntu  # Copy for GitHub secret SSH_PRIVATE_KEY_UBUNTU
```

### 4.2 Workflow File

| Workflow | File | Triggers | Services |
|----------|------|----------|----------|
| Ubuntu | `.github/workflows/deploy-ubuntu.yml` | `services/frontend/**`, `services/core-api/**`, `services/item-resolver/**`, `docker-compose.ubuntu.yml`, `nginx/**` | All services |

### 4.3 Environment Variables

All secrets are stored in `.env` file on the server, NOT in GitHub secrets.

**Required `.env` variables:**
```bash
# Security
JWT_SECRET_KEY=your-production-secret-min-32-chars
RU_BEARER_TOKEN=your-item-resolver-token

# Database
POSTGRES_USER=wishwithme
POSTGRES_PASSWORD=your-db-password
POSTGRES_DB=wishwithme

# DeepSeek LLM (for item-resolver)
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your-deepseek-api-key
LLM_MODEL=deepseek-chat
LLM_MAX_CHARS=50000

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=
```

---

## 5. Deployment Workflow

### 5.1 Standard Deployment Process

**Step 1: Commit and Push**
```bash
git add .
git commit -m "Describe your changes"
git push origin main
```

**Step 2: Monitor Deployment**
```bash
# Watch GitHub Actions workflows
gh run watch

# Or view in browser
# https://github.com/mrkutin/wish-with-me-codex/actions
```

**Step 3: Verify**
```bash
ssh mrkutin@176.106.144.182 "cd /home/mrkutin/wish-with-me-codex && docker-compose -f docker-compose.ubuntu.yml ps"
```

### 5.2 Manual Deployment

```bash
ssh mrkutin@176.106.144.182
cd /home/mrkutin/wish-with-me-codex
git pull origin main
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

### 5.3 Quick Reference Commands

```bash
# View status
docker-compose -f docker-compose.ubuntu.yml ps

# View logs
docker-compose -f docker-compose.ubuntu.yml logs -f

# Restart core-api instances
docker-compose -f docker-compose.ubuntu.yml restart core-api-1 core-api-2

# Restart item-resolver instances
docker-compose -f docker-compose.ubuntu.yml restart item-resolver-1 item-resolver-2

# Run database migrations
docker-compose -f docker-compose.ubuntu.yml exec core-api-1 alembic upgrade head

# Access database
docker-compose -f docker-compose.ubuntu.yml exec postgres psql -U wishwithme wishwithme
```

---

## 6. Database Management

### 6.1 Migrations

```bash
# Apply migrations
docker-compose -f docker-compose.ubuntu.yml exec core-api-1 alembic upgrade head

# Rollback migration
docker-compose -f docker-compose.ubuntu.yml exec core-api-1 alembic downgrade -1
```

### 6.2 Backups

```bash
# Create backup
docker-compose -f docker-compose.ubuntu.yml exec -T postgres \
  pg_dump -U wishwithme wishwithme | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore backup
gunzip -c backup_20260123_120000.sql.gz | \
  docker-compose -f docker-compose.ubuntu.yml exec -T postgres \
  psql -U wishwithme wishwithme
```

---

## 7. Monitoring & Troubleshooting

### 7.1 Health Check Endpoints

| Endpoint | Description |
|----------|-------------|
| `https://wishwith.me/health` | Main app health |
| `https://api.wishwith.me/live` | API liveness |

### 7.2 Test Item Resolver

```bash
# SSH to server
ssh mrkutin@176.106.144.182

# Test item-resolver health (internal)
source /home/mrkutin/wish-with-me-codex/.env
docker exec wishwithme-item-resolver-1 wget -qO- --header="Authorization: Bearer $RU_BEARER_TOKEN" http://127.0.0.1:8000/healthz
```

### 7.3 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 502 Bad Gateway | Service not ready | Check service logs |
| SSL certificate error | Expired cert | Run certbot renewal |
| Item resolver timeout | DeepSeek API slow | Check LLM_TIMEOUT_S setting |
| Out of memory | Playwright instances | Reduce MAX_CONCURRENCY |

### 7.4 Debug Mode

```bash
# View container details
docker inspect wishwithme-core-api-1

# Enter container shell
docker exec -it wishwithme-core-api-1 bash

# View real-time resource usage
docker stats
```

---

## 8. Rollback Procedures

### 8.1 Automatic Rollback

GitHub Actions workflow automatically rolls back if deployment fails.

### 8.2 Manual Rollback

```bash
ssh mrkutin@176.106.144.182
cd /home/mrkutin/wish-with-me-codex
git log --oneline -10
git reset --hard <commit-hash>
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

---

## 9. Security Considerations

### 9.1 Network Security

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 9.2 Secrets Management

- All secrets in `.env` file (never committed to git)
- `RU_BEARER_TOKEN` protects item-resolver endpoints
- `LLM_API_KEY` for DeepSeek API access
- Rotate secrets periodically

---

## 10. Quick Troubleshooting Checklist

When something goes wrong:

- [ ] Check GitHub Actions logs: `gh run list`
- [ ] SSH and check logs: `docker-compose -f docker-compose.ubuntu.yml logs -f`
- [ ] Verify containers running: `docker-compose -f docker-compose.ubuntu.yml ps`
- [ ] Check health: `curl https://wishwith.me/health`
- [ ] Verify disk space: `df -h`
- [ ] Check .env file exists and has correct values

---

## 11. Useful Links

- **GitHub Repository**: https://github.com/mrkutin/wish-with-me-codex
- **GitHub Actions**: https://github.com/mrkutin/wish-with-me-codex/actions
- **Production Site**: https://wishwith.me
- **API Documentation**: https://api.wishwith.me/docs
