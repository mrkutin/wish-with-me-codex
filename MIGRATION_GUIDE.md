# Migration Guide: Unified Docker Compose Architecture

This guide helps you migrate from the old per-service docker-compose setup to the new unified architecture.

## What Changed

### Before (Old Architecture)
- Separate docker-compose.yml in each service directory
- External `wishwithme` network created manually
- Each service deployed independently via separate workflows
- Many GitHub secrets required
- Services expose ports directly

### After (New Architecture)
- Single docker-compose.yml at project root
- All services defined in one place
- Unified deployment workflow
- Only 1 GitHub secret required (SSH_PRIVATE_KEY)
- Production uses nginx reverse proxy
- No exposed ports in production (except nginx)

## Migration Steps

### Step 1: Backup Current State

```bash
# SSH to server
ssh montreal
cd /home/ubuntu/wish-with-me-codex

# Backup current database
docker-compose -f services/core-api/docker-compose.yml exec -T postgres \
  pg_dump -U wishwithme wishwithme | gzip > backup_before_migration.sql.gz

# Backup current .env files
cp services/core-api/.env .env.core-api.backup
cp services/item-resolver/.env .env.item-resolver.backup

# Note current container states
docker ps > container_states_before.txt
```

### Step 2: Stop Old Services

```bash
# Stop all running containers
cd /home/ubuntu/wish-with-me-codex

# Stop each service
docker stop wishwithme-frontend || true
docker stop wishwithme-core-api || true
docker stop wishwithme-item-resolver || true

# Note: Don't stop postgres and redis yet - we'll migrate them
```

### Step 3: Create Unified .env File

```bash
# Create new .env at project root
cd /home/ubuntu/wish-with-me-codex
touch .env

# Merge values from old .env files
# You can use this script to help:
```

Here's a helper script to merge environment variables:

```bash
#!/bin/bash
# merge-env.sh - Helper to migrate .env files

cd /home/ubuntu/wish-with-me-codex

echo "# Merged environment configuration" > .env
echo "# Generated: $(date)" >> .env
echo "" >> .env

# Core API variables
echo "# Core API Configuration" >> .env
if [ -f services/core-api/.env ]; then
  grep -E "^(DATABASE_URL|REDIS_URL|JWT_SECRET_KEY|GOOGLE_|APPLE_|YANDEX_|SBER_)" services/core-api/.env >> .env
fi
echo "" >> .env

# Item Resolver variables
echo "# Item Resolver Configuration" >> .env
if [ -f services/item-resolver/.env ]; then
  grep -E "^(RU_BEARER_TOKEN|BROWSER_|HEADLESS|MAX_CONCURRENCY|SSRF_|PROXY_|RANDOM_UA|LLM_)" services/item-resolver/.env >> .env
fi
echo "" >> .env

# Add production-specific variables
echo "# Production Configuration" >> .env
echo "DEBUG=false" >> .env
echo "CORS_ALLOW_ALL=false" >> .env

echo ".env file created. Please review and adjust as needed."
```

### Step 4: Pull Latest Code

```bash
cd /home/ubuntu/wish-with-me-codex

# Pull latest code with new docker-compose setup
git fetch origin
git reset --hard origin/main

# Verify new files exist
ls -la docker-compose.yml
ls -la docker-compose.prod.yml
ls -la nginx/nginx.conf
```

### Step 5: Migrate Data Volumes

The new setup uses named volumes and production persistent paths.

```bash
# Create production data directories
sudo mkdir -p /opt/wishwithme/data/{postgres,redis}
sudo chown -R $USER:$USER /opt/wishwithme

# If you have existing data in old volumes, migrate it:
# For postgres (if using volume)
docker run --rm -v wishwithme-postgres-data:/from -v /opt/wishwithme/data/postgres:/to alpine sh -c "cd /from && cp -av . /to"

# For redis (if using volume)
docker run --rm -v wishwithme-redis-data:/from -v /opt/wishwithme/data/redis:/to alpine sh -c "cd /from && cp -av . /to"
```

### Step 6: Remove Old Containers and Network

```bash
# Remove old containers
docker rm -f wishwithme-frontend || true
docker rm -f wishwithme-core-api || true
docker rm -f wishwithme-item-resolver || true
docker rm -f wishwithme-postgres || true
docker rm -f wishwithme-redis || true

# Remove old external network if it exists
docker network rm wishwithme || true

# Clean up old images
docker image prune -f
```

### Step 7: Start New Architecture

```bash
cd /home/ubuntu/wish-with-me-codex

# Build all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Wait for services to be ready
sleep 30

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api alembic upgrade head

# Check status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### Step 8: Verify Everything Works

```bash
# Check logs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs

# Test health endpoints
docker exec wishwithme-core-api python -c "import httpx; httpx.get('http://localhost:8000/live')"

source .env
docker exec wishwithme-item-resolver python -c "import httpx; httpx.get('http://localhost:8000/healthz', headers={'Authorization': 'Bearer ${RU_BEARER_TOKEN}'})"

docker exec wishwithme-frontend wget --no-verbose --tries=1 --spider http://localhost/

# Test database connection
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec postgres psql -U wishwithme wishwithme -c "SELECT COUNT(*) FROM users;"
```

### Step 9: Update GitHub Actions Secret

The new workflow only needs 1 secret instead of many.

1. Go to GitHub repository → Settings → Secrets and variables → Actions
2. Keep only `SSH_PRIVATE_KEY`
3. Remove old secrets (they're now in .env on server):
   - DATABASE_URL
   - REDIS_URL
   - JWT_SECRET_KEY
   - RU_BEARER_TOKEN
   - GOOGLE_CLIENT_ID/SECRET
   - APPLE_CLIENT_ID/SECRET
   - YANDEX_CLIENT_ID/SECRET
   - SBER_CLIENT_ID/SECRET
   - LLM_API_KEY
   - etc.

### Step 10: Test Deployment

```bash
# Make a small change locally
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test unified deployment workflow"
git push origin main

# Watch deployment
gh run watch
```

## Rollback Plan

If something goes wrong, you can rollback:

```bash
# SSH to server
ssh montreal
cd /home/ubuntu/wish-with-me-codex

# Stop new containers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down

# Restore old setup
git checkout <previous-commit-hash>

# Restore old .env files
cp .env.core-api.backup services/core-api/.env
cp .env.item-resolver.backup services/item-resolver/.env

# Start old services
cd services/core-api
docker-compose up -d
cd ../item-resolver
docker-compose up -d
cd ../frontend
docker-compose up -d

# Restore database if needed
gunzip -c backup_before_migration.sql.gz | docker exec -i wishwithme-postgres psql -U wishwithme wishwithme
```

## Key Differences to Remember

### Port Mapping

**Development (local):**
- Frontend: http://localhost:9000
- Core API: http://localhost:8000
- Item Resolver: http://localhost:8001
- Postgres: localhost:5432
- Redis: localhost:6379

**Production:**
- All traffic through Nginx: https://wishwith.me
- No direct port access to services
- All inter-service communication via Docker network

### Docker Compose Commands

**Old way:**
```bash
cd services/core-api
docker-compose up -d
```

**New way:**
```bash
cd /home/ubuntu/wish-with-me-codex
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

**Old way:**
- Each service has its own .env file
- Secrets duplicated across services

**New way:**
- Single .env file at project root
- All services share same environment
- No duplication

### Deployment

**Old way:**
- Three separate workflows
- Many GitHub secrets
- Manual coordination needed

**New way:**
- One unified workflow
- Auto-detects changed services
- Only rebuilds what changed
- Single SSH_PRIVATE_KEY secret

## Troubleshooting

### Issue: Services can't connect to each other

**Cause:** Not using the new network name

**Solution:** All services must use `wishwithme-network`. Check:
```bash
docker network inspect wishwithme-network
```

### Issue: Database connection failed

**Cause:** Environment variable mismatch

**Solution:** Verify .env file:
```bash
cat .env | grep DATABASE_URL
# Should be: postgresql+asyncpg://wishwithme:password@postgres:5432/wishwithme
```

### Issue: Nginx returns 502

**Cause:** Backend services not ready

**Solution:** Wait for health checks:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
# All services should show "Up (healthy)"
```

### Issue: Old containers interfering

**Cause:** Old containers still running

**Solution:** Clean up:
```bash
docker ps -a | grep wishwithme
docker rm -f $(docker ps -aq --filter name=wishwithme)
```

## Validation Checklist

After migration, verify:

- [ ] All containers running: `docker-compose ps`
- [ ] All services healthy: Check health status in `docker-compose ps`
- [ ] Database accessible: `docker-compose exec postgres psql -U wishwithme wishwithme -c "SELECT 1;"`
- [ ] Redis accessible: `docker-compose exec redis redis-cli ping`
- [ ] Core API responding: `curl http://localhost/health`
- [ ] Frontend loading: `curl -I http://localhost`
- [ ] GitHub Actions workflow runs successfully
- [ ] Old .env files backed up
- [ ] Backup database created
- [ ] No old containers running: `docker ps | grep wishwithme`

## Benefits of New Architecture

1. **Simplified Deployment**: Push once, deploy all changed services
2. **Reduced Secrets**: Only 1 GitHub secret instead of 15+
3. **Better Isolation**: Production ports not exposed
4. **Easier Development**: `docker-compose up` starts everything
5. **Automatic Rollback**: Failed deployments auto-rollback
6. **Resource Limits**: Production has proper CPU/memory limits
7. **Unified Configuration**: All settings in one .env file
8. **Production-Ready**: Nginx reverse proxy with SSL

## Getting Help

If you encounter issues:

1. Check logs: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f`
2. Verify .env file has all required variables
3. Compare with .env.example
4. Check GitHub Actions logs if deployment failed
5. Review this migration guide
6. Rollback if needed (see Rollback Plan above)
