# Unified Docker Compose CI/CD Architecture

## Overview

This document describes the unified docker-compose based CI/CD architecture implemented for Wish With Me.

## Problems Solved

### Before
1. **Fragmented Configuration**: Each service had its own docker-compose.yml
2. **Network Complexity**: Services used external network, hard to manage
3. **Secret Sprawl**: 15+ GitHub secrets required
4. **Manual Coordination**: Three separate deployment workflows
5. **Port Exposure**: All services exposed ports in production
6. **No Reverse Proxy**: Direct access to services

### After
1. **Unified Configuration**: Single docker-compose.yml for all services
2. **Internal Network**: All services on same bridge network
3. **Minimal Secrets**: Only 1 GitHub secret (SSH_PRIVATE_KEY)
4. **Automated Coordination**: One workflow auto-detects changes
5. **Production Isolation**: No exposed ports except nginx
6. **Nginx Reverse Proxy**: Production-grade routing layer

## Architecture Diagram

```
┌────────────────────────────────────────────────────────┐
│                     Internet                           │
└───────────────────────┬────────────────────────────────┘
                        │
                  Port 443/80
                        │
                 ┌──────▼──────┐
                 │    Nginx    │  Reverse Proxy
                 │  (Production)│  SSL Termination
                 └──────┬──────┘  Rate Limiting
                        │
        ┌───────────────┼───────────────┐
        │               │               │
  ┌─────▼─────┐   ┌────▼────┐   ┌──────▼──────┐
  │ Frontend  │   │Core API │   │Item Resolver│
  │  (Vue 3)  │   │(FastAPI)│   │  (FastAPI)  │
  │  Port 80  │   │Port 8000│   │  Port 8000  │
  └───────────┘   └────┬────┘   └──────┬──────┘
                       │                │
                  ┌────┴────┐      ┌────┴────┐
                  │         │      │         │
             ┌────▼───┐ ┌───▼────┐│         │
             │Postgres│ │ Redis  ││         │
             │Port 5432│ │Port 6379│         │
             └─────────┘ └────────┘          │
                                              │
                    All on wishwithme-network │
                                              │
└─────────────────────────────────────────────┘
```

## File Structure

```
wish-with-me-codex/
├── docker-compose.yml           # Base configuration (dev + prod)
├── docker-compose.prod.yml      # Production overrides
├── .env.example                 # Environment template
├── .env                         # Production secrets (not in git)
│
├── nginx/
│   ├── nginx.conf               # Nginx configuration
│   ├── ssl/                     # SSL certificates
│   │   ├── fullchain.pem        # Let's Encrypt cert
│   │   └── privkey.pem          # Private key
│   └── README.md                # SSL setup guide
│
├── .github/workflows/
│   └── deploy.yml               # Unified deployment workflow
│
├── services/
│   ├── frontend/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   ├── core-api/
│   │   └── Dockerfile
│   └── item-resolver/
│       └── Dockerfile
│
└── docs/
    └── 13-deployment.md         # Deployment documentation
```

## Docker Compose Configuration

### Base Configuration (docker-compose.yml)

Defines all services with:
- Health checks for proper startup order
- Internal network communication
- Environment variable defaults
- Development port mappings

**Services:**
- postgres: PostgreSQL 16 Alpine
- redis: Redis 7 Alpine with AOF persistence
- item-resolver: Playwright-based metadata extraction
- core-api: FastAPI backend with async SQLAlchemy
- frontend: Vue 3 + Quasar PWA

**Networks:**
- wishwithme-network: Bridge network for all services

**Volumes:**
- postgres_data: Database persistence
- redis_data: Redis AOF persistence
- item_resolver_storage: Playwright storage state

### Production Overrides (docker-compose.prod.yml)

Adds production-specific configuration:
- **Nginx service**: Reverse proxy with SSL
- **No exposed ports**: Only nginx exposes 80/443
- **Persistent volumes**: Maps to /opt/wishwithme/data/
- **Resource limits**: CPU and memory limits for item-resolver
- **Production settings**: DEBUG=false, CORS_ALLOW_ALL=false

## CI/CD Workflow

### Unified Deployment Workflow (.github/workflows/deploy.yml)

**Trigger:**
- Push to main branch with changes in services/**, docker-compose.*, or nginx/**
- Manual workflow dispatch

**Jobs:**

#### 1. Detect Changes
Analyzes git diff to determine which services changed:
- services/frontend/** → Rebuild frontend
- services/core-api/** → Rebuild core-api + migrations
- services/item-resolver/** → Rebuild item-resolver
- docker-compose.yml or nginx/** → Infrastructure changes

Outputs: Boolean flags for each service + infrastructure

#### 2. Deploy
**Only runs if changes detected**

Steps:
1. Setup SSH authentication
2. Display deployment plan
3. Pull latest code from git
4. Build only changed services
5. Run migrations if core-api changed
6. Restart only changed services with --no-deps
7. Wait for services to start
8. Health check each changed service
9. Verify external access (if nginx changed)
10. Display deployment summary

**Health Checks:**
- Core API: Internal HTTP check to /live endpoint
- Item Resolver: Internal HTTP check to /healthz with auth
- Frontend: Internal HTTP check to root
- Nginx: External HTTP check to /health endpoint

#### 3. Rollback on Failure
**Only runs if deploy job fails**

Steps:
1. Reset git to previous commit (HEAD~1)
2. Rebuild previous versions of changed services
3. Restart services
4. Display rollback confirmation

### Advantages

1. **Fast Deployments**: Only rebuilds changed services (30s-2min vs 5-10min)
2. **Automatic Rollback**: No manual intervention on failures
3. **Safe**: Health checks verify deployment before considering it successful
4. **Transparent**: Clear logs showing what's being deployed
5. **Idempotent**: Can run multiple times safely

## Environment Configuration

### Development (.env with defaults)

```bash
# Uses .env.example defaults
docker-compose up -d
```

Services accessible on localhost with exposed ports:
- Frontend: http://localhost:9000
- Core API: http://localhost:8000
- Item Resolver: http://localhost:8001
- Postgres: localhost:5432
- Redis: localhost:6379

### Production (.env on server)

```bash
# Uses .env file on server
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

All services internal except nginx:
- Public: https://wishwith.me (nginx 443/80)
- Internal: Services communicate via Docker network

**Secret Management:**
- All secrets in .env file on server
- File not in git (.gitignore)
- Only 1 GitHub secret needed (SSH_PRIVATE_KEY)
- Easy to rotate (edit file, restart services)

## Service Communication

### Inter-Service URLs

Services reference each other by container name:

```bash
# Core API → PostgreSQL
DATABASE_URL=postgresql+asyncpg://wishwithme:password@postgres:5432/wishwithme

# Core API → Redis
REDIS_URL=redis://redis:6379/0

# Core API → Item Resolver
ITEM_RESOLVER_URL=http://item-resolver:8000
```

### External Access (Production)

All external traffic goes through nginx:

```nginx
# Frontend
location / {
    proxy_pass http://frontend:80;
}

# API
location /api/ {
    proxy_pass http://core-api:8000/api/;
}

# Health check
location /health {
    proxy_pass http://core-api:8000/live;
}
```

## Deployment Process

### Automatic (Git Push)

```bash
# Make changes
git add .
git commit -m "Update feature"
git push origin main

# GitHub Actions automatically:
# 1. Detects changed files
# 2. Determines affected services
# 3. Pulls code on server
# 4. Builds changed services
# 5. Runs migrations if needed
# 6. Restarts services
# 7. Health checks
# 8. Rollback if failed
```

### Manual (Server)

```bash
# SSH to server
ssh montreal
cd /home/ubuntu/wish-with-me-codex

# Pull latest
git pull origin main

# Rebuild specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build core-api

# Restart specific service
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps core-api

# Or rebuild everything
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Monitoring

### Health Checks

**Internal (Docker):**
- Postgres: `pg_isready`
- Redis: `redis-cli ping`
- Core API: HTTP GET /live
- Item Resolver: HTTP GET /healthz with auth
- Frontend: HTTP GET /

**External:**
- https://wishwith.me/health → Core API /live

### Logging

```bash
# All services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Specific service
docker logs wishwithme-core-api --tail=100 -f

# Nginx access logs
docker exec wishwithme-nginx tail -f /var/log/nginx/access.log

# Nginx error logs
docker exec wishwithme-nginx tail -f /var/log/nginx/error.log
```

### Metrics

```bash
# Container stats
docker stats

# Service status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Disk usage
docker system df

# Network inspection
docker network inspect wishwithme-network
```

## Security Features

### Network Isolation
- All services on internal Docker network
- No direct external access except nginx
- Services communicate via container names

### SSL/TLS
- Let's Encrypt certificates
- Automatic renewal via cron
- TLS 1.2 and 1.3 only
- HSTS headers
- Modern cipher suites

### Rate Limiting
- API: 10 requests/second with 20 burst
- Auth: 5 requests/minute with 5 burst
- Configured in nginx

### Security Headers
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### Secrets Management
- No secrets in git
- All secrets in .env on server
- File permissions: 600 (owner read/write only)
- Only 1 GitHub secret (SSH key)

## Resource Management

### Production Limits

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

### Volume Persistence

```yaml
# Development: Named volumes
volumes:
  postgres_data:
  redis_data:

# Production: Host paths
volumes:
  postgres_data:
    driver: local
    driver_opts:
      device: /opt/wishwithme/data/postgres

  redis_data:
    driver: local
    driver_opts:
      device: /opt/wishwithme/data/redis
```

## Backup Strategy

### Database Backups

**Manual:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U wishwithme wishwithme | gzip > backup.sql.gz
```

**Automated (Cron):**
```cron
0 3 * * * cd /home/ubuntu/wish-with-me-codex && docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U wishwithme wishwithme | gzip > /opt/wishwithme/backups/db_$(date +\%Y\%m\%d).sql.gz
```

### Volume Backups

```bash
# Backup postgres data
sudo tar czf postgres-backup.tar.gz /opt/wishwithme/data/postgres

# Backup redis data
sudo tar czf redis-backup.tar.gz /opt/wishwithme/data/redis
```

## Rollback Procedures

### Automatic (GitHub Actions)
If health checks fail, workflow automatically:
1. Resets to previous commit
2. Rebuilds previous version
3. Restarts services
4. Logs rollback action

### Manual
```bash
# View history
git log --oneline -10

# Rollback to specific commit
git reset --hard <commit-hash>

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Verify
git log -1 --oneline
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## Benefits Summary

### For Development
- Simple setup: `docker-compose up -d`
- All services in one command
- Consistent environment
- Easy debugging

### For Operations
- Minimal secrets (only 1 GitHub secret)
- Automatic deployments
- Smart rebuild (only changed services)
- Automatic rollback on failure
- Clear health checks
- Comprehensive logging

### For Security
- Network isolation
- No exposed ports in production
- SSL/TLS with auto-renewal
- Rate limiting
- Security headers
- Secrets on server only

### For Performance
- Resource limits
- Health-based startup order
- Nginx caching
- Gzip compression
- Persistent volumes

## Migration from Old Setup

See [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) for step-by-step instructions to migrate from the old per-service docker-compose setup to this unified architecture.

## Future Enhancements

Potential improvements:
- [ ] Docker Swarm or Kubernetes for multi-node
- [ ] Prometheus + Grafana monitoring
- [ ] Automated database backups to S3
- [ ] Blue-green deployments
- [ ] Canary deployments
- [ ] Multi-region support
- [ ] CDN integration
- [ ] WAF (Web Application Firewall)

## Conclusion

This unified docker-compose architecture provides:
- **Simplicity**: One configuration, one workflow
- **Safety**: Health checks, automatic rollback
- **Security**: Network isolation, minimal exposed ports
- **Efficiency**: Fast deployments, only rebuild changed services
- **Maintainability**: Clear structure, comprehensive documentation

The architecture is production-ready, scalable, and easy to maintain.
