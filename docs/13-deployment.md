# Deployment

> Part of [Wish With Me Specification](../AGENTS.md)

---

## ⚠️ IMPORTANT: Production Server Configuration

**PRODUCTION SERVER IS ALWAYS:**
- **Server**: Montreal (ssh alias)
- **Hostname**: 158.69.203.3
- **User**: ubuntu
- **Location**: /home/ubuntu/wish-with-me-codex

**DEPLOYMENT IS ALWAYS:**
- **Automatic**: Triggered on every push to `main` branch
- **Via GitHub Actions**: `.github/workflows/deploy.yml`
- **Smart**: Only rebuilds changed services
- **Verified**: Health checks run on Montreal server
- **Safe**: Automatic rollback on failure

**TESTING IS ALWAYS:**
- **On Production**: Test directly on Montreal server after deployment
- **Never Local Only**: Local tests are supplementary, not sufficient
- **Command**: `ssh montreal "cd /home/ubuntu/wish-with-me-codex && docker-compose logs -f"`

---

## 1. Overview

### 1.1 Unified Docker Compose Architecture

The application uses a unified docker-compose architecture with all services defined in a single configuration:

- **docker-compose.yml**: Base configuration for all services (development + production)
- **docker-compose.prod.yml**: Production overrides (nginx, no exposed ports, resource limits)

All services run on the same Docker network (`wishwithme-network`), enabling seamless inter-service communication.

### 1.2 Primary Deployment Method

**GitHub Actions (Automated)**

Deployment happens automatically when you push to the `main` branch:

1. Push changes to GitHub `main` branch
2. GitHub Actions detects which services changed
3. Only changed services are rebuilt and restarted
4. Health checks verify successful deployment
5. Automatic rollback if deployment fails

```bash
# Deploy by pushing to GitHub
git push origin main

# Or trigger manually (deploys all services)
gh workflow run deploy.yml

# Watch deployment progress
gh run watch
```

**IMPORTANT**: The unified deployment workflow minimizes downtime by only rebuilding what changed.

### 1.3 Components

| Component | Container | Ports (Dev) | Ports (Prod) |
|-----------|-----------|-------------|--------------|
| Nginx (reverse proxy) | `wishwithme-nginx` | - | 80, 443 |
| Frontend (Quasar PWA) | `wishwithme-frontend` | 9000 | Internal only |
| Core API (FastAPI) | `wishwithme-core-api` | 8000 | Internal only |
| Item Resolver | `wishwithme-item-resolver` | 8001 | Internal only |
| PostgreSQL | `wishwithme-postgres` | 5432 | Internal only |
| Redis | `wishwithme-redis` | 6379 | Internal only |

### 1.4 Server

```
Host: montreal
Hostname: 158.69.203.3
User: ubuntu
SSH Key: ~/.ssh/id_ed25519 (passphrase protected)
```

**Server Access**:
```bash
# SSH to Montreal server
ssh montreal

# Navigate to project directory
cd /home/ubuntu/wish-with-me-codex

# Check all service logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Check specific service
docker logs wishwithme-core-api --tail=100
docker logs wishwithme-frontend --tail=100
docker logs wishwithme-item-resolver --tail=100

# Check service status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

---

## 2. Architecture

### 2.1 Service Communication

```
Internet
    ↓
Nginx (443/80)
    ↓
┌───────────────┬──────────────┐
│               │              │
Frontend:80  Core API:8000  Item Resolver:8000
                │              ↑
                ↓              │
            Postgres:5432      │
                │              │
            Redis:6379 ────────┘
```

**Key Features:**
- All services on same Docker network
- Nginx reverse proxy handles external traffic
- Services reference each other by container name
- No exposed ports in production (except nginx)
- Health checks ensure proper startup order

### 2.2 Environment Configuration

Environment variables are managed via `.env` file on the server:

```bash
# On server
cd /home/ubuntu/wish-with-me-codex
cat .env  # View current configuration
```

**Development**: Uses `.env.example` defaults (suitable for local dev)
**Production**: Uses custom `.env` file with production secrets (not in git)

---

## 3. Initial Server Setup

### 3.1 One-Time Server Configuration

Run these commands once when setting up a new server:

```bash
# 1. SSH into the server
ssh ubuntu@158.69.203.3

# 2. Update system
sudo apt-get update && sudo apt-get upgrade -y

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 4. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 5. Clone repository (use HTTPS for CI/CD compatibility)
cd /home/ubuntu
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# 6. Ensure git uses HTTPS (required for GitHub Actions)
git remote set-url origin https://github.com/mrkutin/wish-with-me-codex.git

# 7. Create production directories
sudo mkdir -p /opt/wishwithme/data/{postgres,redis}
sudo chown -R $USER:$USER /opt/wishwithme

# 8. Create .env file with production secrets
cp .env.example .env
nano .env  # Fill in production values
```

### 3.2 SSL Certificate Setup

```bash
# Install certbot
sudo apt-get install -y certbot

# Stop nginx if running (to free port 80)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop nginx

# Obtain certificates
sudo certbot certonly --standalone \
  -d wishwith.me \
  -d www.wishwith.me \
  --agree-tos \
  --email your-email@example.com

# Copy certificates to nginx directory
cd /home/ubuntu/wish-with-me-codex
sudo cp /etc/letsencrypt/live/wishwith.me/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/wishwith.me/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*

# Set up auto-renewal (cron job)
sudo crontab -e
# Add this line:
# 0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/wishwith.me/*.pem /home/ubuntu/wish-with-me-codex/nginx/ssl/ && docker-compose -f /home/ubuntu/wish-with-me-codex/docker-compose.yml -f /home/ubuntu/wish-with-me-codex/docker-compose.prod.yml restart nginx
```

### 3.3 Initial Deployment

```bash
# Build and start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run database migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api alembic upgrade head

# Check everything is running
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

---

## 4. GitHub Actions Configuration

### 4.1 Required GitHub Secret

Only ONE secret is required in GitHub repository settings:

| Secret | Description | How to Generate |
|--------|-------------|-----------------|
| `SSH_PRIVATE_KEY` | Ed25519 private key for server access | See below |

**Generate SSH key:**
```bash
# On your local machine
ssh-keygen -t ed25519 -C "github-actions@wishwith.me" -f ~/.ssh/github_actions

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_actions.pub ubuntu@158.69.203.3

# Copy private key content for GitHub secret
cat ~/.ssh/github_actions
```

Add the private key content to GitHub:
1. Go to repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `SSH_PRIVATE_KEY`
4. Value: Paste the entire private key (including BEGIN and END lines)

### 4.2 How It Works

The unified deployment workflow (`.github/workflows/deploy.yml`):

1. **Detect Changes**: Analyzes which files changed
   - `services/frontend/**` → Rebuild frontend
   - `services/core-api/**` → Rebuild core-api + run migrations
   - `services/item-resolver/**` → Rebuild item-resolver
   - `docker-compose.yml` or `nginx/**` → Rebuild infrastructure

2. **Pull Code**: Updates server repository to latest commit

3. **Rebuild Services**: Only rebuilds changed services
   ```bash
   docker-compose build frontend core-api  # Only changed ones
   ```

4. **Restart Services**: Restarts only changed containers
   ```bash
   docker-compose up -d --no-deps frontend core-api
   ```

5. **Health Checks**: Verifies each service is healthy

6. **Rollback**: If any check fails, automatically rolls back to previous version

### 4.3 Environment Variables on Server

All secrets are stored in `.env` file on the server, NOT in GitHub secrets. This:
- Reduces GitHub secret sprawl (only 1 secret needed)
- Makes secret rotation easier (just edit .env on server)
- Keeps secrets closer to where they're used

---

## 5. Deployment Workflow

### 5.1 Standard Deployment Process

**Step 1: Develop & Test Locally**
```bash
# Start services locally
docker-compose up -d

# Make changes to code

# Test changes
npm test  # or pytest, etc.

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
# Watch GitHub Actions workflow
gh run watch

# Or view in browser
# https://github.com/mrkutin/wish-with-me-codex/actions
```

**Step 4: Verify on Server**
```bash
# SSH to server
ssh montreal

# Check deployment logs
cd /home/ubuntu/wish-with-me-codex
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100

# Verify services are healthy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### 5.2 Manual Deployment

If you need to deploy without pushing to GitHub:

```bash
# SSH to server
ssh montreal
cd /home/ubuntu/wish-with-me-codex

# Pull latest code
git pull origin main

# Rebuild specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build core-api

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps core-api

# Or rebuild and restart all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 5.3 Quick Reference Commands

```bash
# On Server (montreal)
cd /home/ubuntu/wish-with-me-codex

# View status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# View logs (all services)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# View logs (specific service)
docker logs wishwithme-core-api --tail=100 -f

# Restart service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart core-api

# Stop all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Rebuild and restart single service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --no-deps frontend

# Run database migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api alembic upgrade head

# Access database
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U wishwithme wishwithme

# Access Redis
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec redis redis-cli

# Clean up old images
docker image prune -f

# Clean up old volumes (DANGEROUS - only if you know what you're doing)
docker volume prune -f
```

---

## 6. Database Management

### 6.1 Migrations

```bash
# On server
cd /home/ubuntu/wish-with-me-codex

# Create new migration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api \
  alembic revision --autogenerate -m "Description of changes"

# Apply migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api \
  alembic upgrade head

# Rollback migration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api \
  alembic downgrade -1

# View migration history
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api \
  alembic history
```

### 6.2 Backups

**Manual Backup:**
```bash
# Create backup
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U wishwithme wishwithme | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Restore backup
gunzip -c backup_20260123_120000.sql.gz | \
  docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  psql -U wishwithme wishwithme
```

**Automated Backups (Cron):**
```bash
# Add to crontab
sudo crontab -e

# Add this line (daily backups at 3 AM)
0 3 * * * cd /home/ubuntu/wish-with-me-codex && docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U wishwithme wishwithme | gzip > /opt/wishwithme/backups/db_$(date +\%Y\%m\%d).sql.gz && find /opt/wishwithme/backups -name "db_*.sql.gz" -mtime +7 -delete
```

---

## 7. Monitoring & Troubleshooting

### 7.1 Health Check Endpoints

| Endpoint | Service | Access |
|----------|---------|--------|
| `http://158.69.203.3/health` | Nginx → Core API | Public (no SSL) |
| `https://wishwith.me/health` | Nginx → Core API | Public (SSL) |
| Internal health checks | All services | Docker healthcheck |

### 7.2 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 502 Bad Gateway | Service not ready | Check logs, wait for health check |
| Container not starting | Build failed | Check build logs: `docker-compose logs <service>` |
| Database connection failed | PostgreSQL not healthy | Verify postgres is running and healthy |
| SSL certificate error | Expired/missing cert | Run certbot renewal |
| Port conflict | Service using same port | Check `docker ps` and stop conflicting container |
| Out of disk space | Old images/volumes | Run `docker system prune -a` |

### 7.3 Debug Mode

```bash
# View container details
docker inspect wishwithme-core-api

# View container health status
docker inspect --format='{{json .State.Health}}' wishwithme-core-api | jq

# Enter container shell
docker exec -it wishwithme-core-api bash

# View real-time resource usage
docker stats

# View network details
docker network inspect wishwithme-network
```

### 7.4 Log Management

```bash
# View logs with timestamps
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --timestamps

# View only errors
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs | grep -i error

# Limit log output
docker logs wishwithme-core-api --tail=50

# Save logs to file
docker logs wishwithme-core-api > core-api.log 2>&1

# View nginx access logs
docker exec wishwithme-nginx tail -f /var/log/nginx/access.log

# View nginx error logs
docker exec wishwithme-nginx tail -f /var/log/nginx/error.log
```

---

## 8. Rollback Procedures

### 8.1 Automatic Rollback

The GitHub Actions workflow automatically rolls back if deployment fails. No manual intervention needed.

### 8.2 Manual Rollback

If you need to manually rollback to a previous version:

```bash
# SSH to server
ssh montreal
cd /home/ubuntu/wish-with-me-codex

# View recent commits
git log --oneline -10

# Rollback to specific commit
git reset --hard <commit-hash>

# Rebuild and restart affected services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Verify rollback
git log -1 --oneline
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### 8.3 Database Rollback

If a migration caused issues:

```bash
# Rollback last migration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api \
  alembic downgrade -1

# Or restore from backup
gunzip -c /opt/wishwithme/backups/db_20260123.sql.gz | \
  docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  psql -U wishwithme wishwithme
```

---

## 9. Development Setup

### 9.1 Local Development

```bash
# Clone repository
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access services
# Frontend: http://localhost:9000
# Core API: http://localhost:8000
# Item Resolver: http://localhost:8001
# PostgreSQL: localhost:5432
# Redis: localhost:6379
```

### 9.2 Development Commands

```bash
# Rebuild single service
docker-compose up -d --build frontend

# Run tests in container
docker-compose exec core-api pytest

# Access database
docker-compose exec postgres psql -U wishwithme wishwithme

# View specific service logs
docker-compose logs -f core-api

# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

---

## 10. Security Best Practices

### 10.1 Secrets Management

- **Never commit secrets to git**
- Store all secrets in `.env` file on server
- Use strong passwords (minimum 32 characters)
- Rotate secrets regularly
- Use different secrets for dev/staging/production

### 10.2 SSL/TLS

- Always use HTTPS in production
- Keep certificates up to date (auto-renewal via cron)
- Use modern TLS protocols (1.2 and 1.3 only)
- Implement HSTS headers

### 10.3 Network Security

- No exposed ports in production (except nginx 80/443)
- All inter-service communication via internal Docker network
- Rate limiting on API and auth endpoints
- CORS configured for production domains only

### 10.4 Server Hardening

```bash
# Update system regularly
sudo apt-get update && sudo apt-get upgrade -y

# Configure firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Disable root SSH login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart ssh
```

---

## 11. Performance Optimization

### 11.1 Resource Limits

Production services have resource limits defined in `docker-compose.prod.yml`:

```yaml
item-resolver:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 4G
      reservations:
        cpus: '1.0'
        memory: 2G
```

### 11.2 Caching

- Frontend: Static assets cached for 1 year
- Service worker: No cache (always fresh)
- Redis: Used for session and API caching

### 11.3 Database Optimization

```bash
# Analyze database performance
docker-compose exec postgres psql -U wishwithme wishwithme -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Vacuum database
docker-compose exec postgres psql -U wishwithme wishwithme -c "VACUUM ANALYZE;"
```

---

## 12. Useful Links

- **GitHub Repository**: https://github.com/mrkutin/wish-with-me-codex
- **GitHub Actions**: https://github.com/mrkutin/wish-with-me-codex/actions
- **Production Site**: https://wishwith.me
- **API Documentation**: https://wishwith.me/api/docs

---

## 13. Quick Troubleshooting Checklist

When something goes wrong:

- [ ] Check GitHub Actions logs: `gh run list`
- [ ] SSH to server and check logs: `docker-compose logs -f`
- [ ] Verify all containers running: `docker-compose ps`
- [ ] Check health endpoints: `curl http://localhost/health`
- [ ] Verify disk space: `df -h`
- [ ] Check container resources: `docker stats`
- [ ] Review recent commits: `git log --oneline -10`
- [ ] Check .env file exists and has correct values
- [ ] Verify SSL certificates are valid
- [ ] Test database connection: `docker-compose exec postgres psql -U wishwithme wishwithme -c "SELECT 1;"`
- [ ] If all else fails, rollback: `git reset --hard HEAD~1 && docker-compose up -d --build`
