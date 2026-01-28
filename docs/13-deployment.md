# Deployment

> Part of [Wish With Me Specification](../AGENTS.md)

---

## ⚠️ IMPORTANT: Split Server Architecture

**The application is deployed across TWO servers:**

### Ubuntu Server (Main Application)
- **IP Address**: 176.106.144.182
- **User**: ubuntu
- **Location**: /home/ubuntu/wish-with-me-codex
- **Domain**: wishwith.me (points to this server)
- **Services**: nginx, frontend, core-api, postgres, redis
- **SSH Key Secret**: `SSH_PRIVATE_KEY_UBUNTU`

### Montreal Server (Item Resolver Only)
- **IP Address**: 158.69.203.3
- **User**: ubuntu
- **Location**: /home/ubuntu/wish-with-me-codex
- **Access**: Via IP only (no domain)
- **Services**: item-resolver
- **SSH Key Secret**: `SSH_PRIVATE_KEY`

**DEPLOYMENT IS ALWAYS:**
- **Automatic**: Triggered on every push to `main` branch
- **Split by service**: Ubuntu workflow for frontend/core-api, Montreal workflow for item-resolver
- **Smart**: Only rebuilds changed services
- **Verified**: Health checks run on respective servers
- **Safe**: Automatic rollback on failure

---

## 1. Overview

### 1.1 Split Docker Compose Architecture

The application uses separate docker-compose files for each server:

| Server | Docker Compose File | Services |
|--------|---------------------|----------|
| Ubuntu (176.106.144.182) | `docker-compose.ubuntu.yml` | nginx, frontend, core-api, postgres, redis |
| Montreal (158.69.203.3) | `docker-compose.montreal.yml` | item-resolver |

**Key Change**: Core API connects to item-resolver via Montreal's external IP (`http://158.69.203.3:8001`) instead of internal Docker network.

### 1.2 Primary Deployment Method

**GitHub Actions (Automated)**

Two separate workflows handle deployment:

1. **deploy-ubuntu.yml** - Deploys frontend, core-api to Ubuntu server
2. **deploy-montreal.yml** - Deploys item-resolver to Montreal server

```bash
# Deploy by pushing to GitHub
git push origin main

# Or trigger manually
gh workflow run deploy-ubuntu.yml   # Deploy main app
gh workflow run deploy-montreal.yml # Deploy item-resolver

# Watch deployment progress
gh run watch
```

### 1.3 Components

| Component | Container | Server | External Access |
|-----------|-----------|--------|-----------------|
| Nginx (reverse proxy) | `wishwithme-nginx` | Ubuntu | 80, 443 (wishwith.me) |
| Frontend (Quasar PWA) | `wishwithme-frontend` | Ubuntu | Via nginx |
| Core API (FastAPI) | `wishwithme-core-api` | Ubuntu | Via nginx (api.wishwith.me) |
| PostgreSQL | `wishwithme-postgres` | Ubuntu | Internal only |
| Redis | `wishwithme-redis` | Ubuntu | Internal only |
| Item Resolver | `wishwithme-item-resolver` | Montreal | 8001 (IP access) |

### 1.4 Service Communication

```
Internet
    ↓
Ubuntu Server (176.106.144.182)               Montreal Server (158.69.203.3)
┌────────────────────────────────┐       ┌─────────────────────────────┐
│ Nginx (443/80)                 │       │                             │
│     ↓                          │       │                             │
│ ┌─────────┬──────────────┐     │       │   Item Resolver:8001        │
│ │         │              │     │       │   (accessible via IP)       │
│ Frontend  Core API:8000  │     │       │                             │
│           │              │     │       └─────────────────────────────┘
│           ↓              │     │                    ↑
│       Postgres:5432      │     │                    │
│           │              │     │                    │
│       Redis:6379         │     │    HTTP calls to   │
│           │              │─────┼────────────────────┘
│           └──────────────┘     │    158.69.203.3:8001
└────────────────────────────────┘
```

---

## 2. Server Access

### 2.1 Ubuntu Server (Main Application)

```bash
# SSH to Ubuntu server
ssh ubuntu@176.106.144.182

# Navigate to project directory
cd /home/ubuntu/wish-with-me-codex

# Check all service logs
docker-compose -f docker-compose.ubuntu.yml logs -f

# Check specific service
docker logs wishwithme-core-api --tail=100
docker logs wishwithme-frontend --tail=100
docker logs wishwithme-nginx --tail=100

# Check service status
docker-compose -f docker-compose.ubuntu.yml ps
```

### 2.2 Montreal Server (Item Resolver)

```bash
# SSH to Montreal server
ssh ubuntu@158.69.203.3

# Navigate to project directory
cd /home/ubuntu/wish-with-me-codex

# Check item-resolver logs
docker-compose -f docker-compose.montreal.yml logs -f

# Check service
docker logs wishwithme-item-resolver --tail=100

# Check service status
docker-compose -f docker-compose.montreal.yml ps
```

---

## 3. Initial Server Setup

### 3.1 Ubuntu Server Setup (Main Application)

Run these commands once when setting up the Ubuntu server:

```bash
# 1. SSH into the server
ssh ubuntu@176.106.144.182

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
cd /home/ubuntu
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# 6. Ensure git uses HTTPS
git remote set-url origin https://github.com/mrkutin/wish-with-me-codex.git

# 7. Create production directories
sudo mkdir -p /opt/wishwithme/data/{postgres,redis}
sudo chown -R $USER:$USER /opt/wishwithme

# 8. Create .env file with production secrets
cp .env.example .env
nano .env  # Fill in production values (JWT_SECRET_KEY, RU_BEARER_TOKEN, etc.)

# 9. SSL Certificate Setup (see section 3.3)

# 10. Initial deployment
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

### 3.2 Montreal Server Setup (Item Resolver)

Montreal should already have the repository. Update it for split deployment:

```bash
# SSH to Montreal
ssh ubuntu@158.69.203.3

cd /home/ubuntu/wish-with-me-codex

# Pull latest code
git pull origin main

# Stop old services (if running unified deployment)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start only item-resolver
docker-compose -f docker-compose.montreal.yml up -d --build
```

### 3.3 SSL Certificate Setup (Ubuntu Server)

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
# 0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/wishwith.me/*.pem /home/ubuntu/wish-with-me-codex/nginx/ssl/ && docker-compose -f /home/ubuntu/wish-with-me-codex/docker-compose.ubuntu.yml restart nginx
```

---

## 4. GitHub Actions Configuration

### 4.1 Required GitHub Secrets

TWO SSH keys are required for the split deployment:

| Secret | Description | Server |
|--------|-------------|--------|
| `SSH_PRIVATE_KEY_UBUNTU` | Ed25519 private key for Ubuntu server | 176.106.144.182 |
| `SSH_PRIVATE_KEY` | Ed25519 private key for Montreal server | 158.69.203.3 |

**Generate SSH keys:**
```bash
# For Ubuntu server
ssh-keygen -t ed25519 -C "github-actions-ubuntu@wishwith.me" -f ~/.ssh/github_actions_ubuntu
ssh-copy-id -i ~/.ssh/github_actions_ubuntu.pub ubuntu@176.106.144.182
cat ~/.ssh/github_actions_ubuntu  # Copy for GitHub secret SSH_PRIVATE_KEY_UBUNTU

# For Montreal server (if not already set up)
ssh-keygen -t ed25519 -C "github-actions@wishwith.me" -f ~/.ssh/github_actions_montreal
ssh-copy-id -i ~/.ssh/github_actions_montreal.pub ubuntu@158.69.203.3
cat ~/.ssh/github_actions_montreal  # Copy for GitHub secret SSH_PRIVATE_KEY
```

### 4.2 Workflow Files

| Workflow | File | Triggers | Services |
|----------|------|----------|----------|
| Ubuntu | `.github/workflows/deploy-ubuntu.yml` | `services/frontend/**`, `services/core-api/**`, `docker-compose.ubuntu.yml`, `nginx/**` | frontend, core-api, nginx |
| Montreal | `.github/workflows/deploy-montreal.yml` | `services/item-resolver/**`, `docker-compose.montreal.yml` | item-resolver |

### 4.3 Environment Variables

All secrets are stored in `.env` file on each server, NOT in GitHub secrets.

**Important**: The `RU_BEARER_TOKEN` must be the same on both servers for authentication between core-api and item-resolver.

---

## 5. Deployment Workflow

### 5.1 Standard Deployment Process

**Step 1: Develop & Test Locally**
```bash
# Start local development (all services)
docker-compose up -d

# View logs
docker-compose logs -f
```

**Step 2: Commit and Push**
```bash
git add .
git commit -m "Describe your changes"
git push origin main
```

**Step 3: Monitor Deployment**
```bash
# Watch GitHub Actions workflows
gh run watch

# Or view in browser
# https://github.com/mrkutin/wish-with-me-codex/actions
```

**Step 4: Verify on Servers**
```bash
# Check Ubuntu server (main app)
ssh ubuntu@176.106.144.182 "cd /home/ubuntu/wish-with-me-codex && docker-compose -f docker-compose.ubuntu.yml ps"

# Check Montreal server (item-resolver)
ssh ubuntu@158.69.203.3 "cd /home/ubuntu/wish-with-me-codex && docker-compose -f docker-compose.montreal.yml ps"
```

### 5.2 Manual Deployment

**Ubuntu Server (Main Application):**
```bash
ssh ubuntu@176.106.144.182
cd /home/ubuntu/wish-with-me-codex
git pull origin main
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

**Montreal Server (Item Resolver):**
```bash
ssh ubuntu@158.69.203.3
cd /home/ubuntu/wish-with-me-codex
git pull origin main
docker-compose -f docker-compose.montreal.yml up -d --build
```

### 5.3 Quick Reference Commands

**Ubuntu Server:**
```bash
# View status
docker-compose -f docker-compose.ubuntu.yml ps

# View logs
docker-compose -f docker-compose.ubuntu.yml logs -f

# Restart service
docker-compose -f docker-compose.ubuntu.yml restart core-api

# Run database migrations
docker-compose -f docker-compose.ubuntu.yml exec core-api alembic upgrade head

# Access database
docker-compose -f docker-compose.ubuntu.yml exec postgres psql -U wishwithme wishwithme
```

**Montreal Server:**
```bash
# View status
docker-compose -f docker-compose.montreal.yml ps

# View logs
docker-compose -f docker-compose.montreal.yml logs -f

# Restart item-resolver
docker-compose -f docker-compose.montreal.yml restart item-resolver
```

---

## 6. Database Management

All database operations are performed on the **Ubuntu server** only.

### 6.1 Migrations

```bash
# SSH to Ubuntu server
ssh ubuntu@176.106.144.182
cd /home/ubuntu/wish-with-me-codex

# Apply migrations
docker-compose -f docker-compose.ubuntu.yml exec core-api alembic upgrade head

# Rollback migration
docker-compose -f docker-compose.ubuntu.yml exec core-api alembic downgrade -1
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

| Endpoint | Server | Description |
|----------|--------|-------------|
| `https://wishwith.me/health` | Ubuntu | Main app health |
| `https://api.wishwith.me/live` | Ubuntu | API liveness |
| `http://158.69.203.3:8001/healthz` | Montreal | Item resolver health (requires Bearer token) |

### 7.2 Test Item Resolver Connectivity

From Ubuntu server, test that core-api can reach item-resolver:

```bash
# SSH to Ubuntu server
ssh ubuntu@176.106.144.182

# Test connectivity to Montreal item-resolver
source /home/ubuntu/wish-with-me-codex/.env
curl -H "Authorization: Bearer $RU_BEARER_TOKEN" http://158.69.203.3:8001/healthz
```

### 7.3 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Core API can't reach item-resolver | Firewall blocking 8001 | Open port 8001 on Montreal firewall |
| Item resolver timeout | Network latency | Check network between servers |
| 502 Bad Gateway | Service not ready | Check service logs |
| SSL certificate error | Expired cert | Run certbot renewal on Ubuntu |

### 7.4 Debug Mode

```bash
# View container details
docker inspect wishwithme-core-api

# Enter container shell
docker exec -it wishwithme-core-api bash

# View real-time resource usage
docker stats
```

---

## 8. Rollback Procedures

### 8.1 Automatic Rollback

Both GitHub Actions workflows automatically rollback if deployment fails.

### 8.2 Manual Rollback

**Ubuntu Server:**
```bash
ssh ubuntu@176.106.144.182
cd /home/ubuntu/wish-with-me-codex
git log --oneline -10
git reset --hard <commit-hash>
docker-compose -f docker-compose.ubuntu.yml up -d --build
```

**Montreal Server:**
```bash
ssh ubuntu@158.69.203.3
cd /home/ubuntu/wish-with-me-codex
git log --oneline -10
git reset --hard <commit-hash>
docker-compose -f docker-compose.montreal.yml up -d --build
```

---

## 9. Security Considerations

### 9.1 Network Security

**Ubuntu Server (176.106.144.182):**
```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

**Montreal Server (158.69.203.3):**
```bash
sudo ufw allow 22/tcp                           # SSH
sudo ufw allow from 176.106.144.182 to any port 8001  # Item Resolver (from Ubuntu server only)
sudo ufw deny 8001                              # Deny 8001 from all other IPs
sudo ufw enable
```

### 9.2 Item Resolver Protection

The item-resolver is protected by Bearer token authentication. The `RU_BEARER_TOKEN` must:
- Be identical on both servers
- Be kept secret (never commit to git)
- Be rotated periodically

---

## 10. Development Setup

### 10.1 Local Development

For local development, use the original unified docker-compose:

```bash
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex
cp .env.example .env
docker-compose up -d

# Access services locally
# Frontend: http://localhost:9000
# Core API: http://localhost:8000
# Item Resolver: http://localhost:8001
```

---

## 11. Migration from Unified to Split Deployment

If migrating from the old unified deployment:

### 11.1 On Montreal Server (keep item-resolver only)

```bash
ssh ubuntu@158.69.203.3
cd /home/ubuntu/wish-with-me-codex

# Pull latest code with split configs
git pull origin main

# Stop all old services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start only item-resolver
docker-compose -f docker-compose.montreal.yml up -d --build

# Verify
docker-compose -f docker-compose.montreal.yml ps
```

### 11.2 On Ubuntu Server (new main application)

```bash
ssh ubuntu@176.106.144.182
cd /home/ubuntu/wish-with-me-codex

# Clone if not already present
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# Create .env file
cp .env.example .env
nano .env  # Configure all secrets

# Setup SSL certificates (see section 3.3)

# Start main application
docker-compose -f docker-compose.ubuntu.yml up -d --build

# Run database migrations
docker-compose -f docker-compose.ubuntu.yml exec core-api alembic upgrade head
```

---

## 12. Quick Troubleshooting Checklist

When something goes wrong:

**Ubuntu Server (Main App):**
- [ ] Check GitHub Actions logs: `gh run list`
- [ ] SSH and check logs: `docker-compose -f docker-compose.ubuntu.yml logs -f`
- [ ] Verify containers running: `docker-compose -f docker-compose.ubuntu.yml ps`
- [ ] Check health: `curl https://wishwith.me/health`
- [ ] Verify disk space: `df -h`
- [ ] Check .env file exists

**Montreal Server (Item Resolver):**
- [ ] SSH and check logs: `docker-compose -f docker-compose.montreal.yml logs -f`
- [ ] Verify container running: `docker-compose -f docker-compose.montreal.yml ps`
- [ ] Check health: `curl -H "Authorization: Bearer $RU_BEARER_TOKEN" http://158.69.203.3:8001/healthz`
- [ ] Verify port 8001 accessible from Ubuntu

**Cross-Server:**
- [ ] Test connectivity from Ubuntu to Montreal: `curl -H "Authorization: Bearer $RU_BEARER_TOKEN" http://158.69.203.3:8001/healthz`
- [ ] Verify RU_BEARER_TOKEN matches on both servers

---

## 13. Useful Links

- **GitHub Repository**: https://github.com/mrkutin/wish-with-me-codex
- **GitHub Actions**: https://github.com/mrkutin/wish-with-me-codex/actions
- **Production Site**: https://wishwith.me
- **API Documentation**: https://api.wishwith.me/docs
