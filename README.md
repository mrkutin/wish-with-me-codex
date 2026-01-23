# Wish With Me

An offline-first wishlist PWA built with Vue 3, Quasar, FastAPI, and PostgreSQL.

## Quick Start

### Development

```bash
# Clone repository
git clone https://github.com/mrkutin/wish-with-me-codex.git
cd wish-with-me-codex

# Create environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

Access services at:
- **Frontend**: http://localhost:9000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Item Resolver**: http://localhost:8001

### Production Deployment

Deployment happens automatically when you push to `main`:

```bash
git push origin main
```

GitHub Actions will:
1. Detect which services changed
2. Deploy only changed services
3. Run health checks
4. Automatically rollback on failure

See [docs/13-deployment.md](./docs/13-deployment.md) for details.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Internet                                       │
└─────────────────┬───────────────────────────────┘
                  │
            Nginx (443/80)
                  │
      ┌───────────┼───────────┐
      │           │           │
  Frontend    Core API    Item Resolver
   (Vue)      (FastAPI)   (FastAPI+Playwright)
              │           │
              ├───────────┘
              │
        ┌─────┴─────┐
   PostgreSQL     Redis
```

### Services

| Service | Description | Tech Stack |
|---------|-------------|------------|
| **Frontend** | Offline-first PWA | Vue 3 + Quasar + RxDB |
| **Core API** | REST API + Auth | FastAPI + SQLAlchemy |
| **Item Resolver** | URL metadata extraction | FastAPI + Playwright |
| **PostgreSQL** | Primary database | PostgreSQL 16 |
| **Redis** | Cache + sessions | Redis 7 |
| **Nginx** | Reverse proxy (prod) | Nginx Alpine |

## Project Structure

```
wish-with-me-codex/
├── services/
│   ├── frontend/          # Vue 3 + Quasar PWA
│   ├── core-api/          # FastAPI backend
│   └── item-resolver/     # URL metadata service
├── docs/                  # Documentation
├── nginx/                 # Nginx configuration
├── .github/workflows/     # CI/CD workflows
├── docker-compose.yml     # Base configuration
├── docker-compose.prod.yml # Production overrides
├── .env.example           # Environment template
└── MIGRATION_GUIDE.md     # Migration instructions
```

## Documentation

- [Architecture Overview](./docs/01-architecture.md)
- [Database Design](./docs/02-database.md)
- [API Specification](./docs/03-api.md)
- [Frontend Architecture](./docs/04-frontend.md)
- [Offline Sync Strategy](./docs/05-offline-sync.md)
- [Deployment Guide](./docs/13-deployment.md)
- [Development Workflow](./CLAUDE.md)

## Key Features

- **Offline-First**: Full functionality without internet connection
- **Real-time Sync**: Automatic synchronization when online
- **OAuth Support**: Google, Apple, Yandex, Sber ID
- **Smart URL Parsing**: Automatic product metadata extraction
- **Multi-language**: Russian and English support
- **PWA**: Installable on mobile and desktop
- **Collaborative**: Share wishlists with family and friends

## Development Workflow

1. **Make Changes**: Edit code in `services/` directories
2. **Test Locally**: Use `docker-compose up -d`
3. **Push to GitHub**: `git push origin main`
4. **Auto Deploy**: GitHub Actions handles deployment
5. **Verify**: Check production health

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Required

```bash
# Database
POSTGRES_PASSWORD=your-strong-password
DATABASE_URL=postgresql+asyncpg://wishwithme:password@postgres:5432/wishwithme

# Security
JWT_SECRET_KEY=generate-with-openssl-rand-base64-32

# Item Resolver
RU_BEARER_TOKEN=generate-with-openssl-rand-hex-32
LLM_API_KEY=your-openai-api-key
```

### Optional

- OAuth provider credentials
- Proxy settings
- LLM configuration
- Resource limits

See `.env.example` for complete list.

## Docker Compose

### Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild service
docker-compose up -d --build frontend

# Stop all services
docker-compose down
```

### Production

```bash
# Start with production overrides
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec core-api alembic upgrade head

# View status
docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

## Testing

### Frontend

```bash
cd services/frontend
npm run test:unit
npm run test:e2e
```

### Backend

```bash
cd services/core-api
pytest
ruff check .
mypy .
```

## Monitoring

### Health Checks

- **Production**: https://wishwith.me/health
- **Development**: http://localhost:8000/live

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker logs wishwithme-core-api --tail=100 -f
```

### Metrics

```bash
# Container stats
docker stats

# Database size
docker-compose exec postgres psql -U wishwithme wishwithme -c "\l+"
```

## Database Migrations

```bash
# Create migration
docker-compose exec core-api alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec core-api alembic upgrade head

# Rollback
docker-compose exec core-api alembic downgrade -1
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Port conflict | Check `docker ps`, stop conflicting container |
| Container won't start | Check logs: `docker-compose logs <service>` |
| Database connection failed | Verify DATABASE_URL in .env |
| 502 Bad Gateway | Wait for services to be healthy |

### Debug Commands

```bash
# Enter container shell
docker exec -it wishwithme-core-api bash

# Check container health
docker inspect --format='{{json .State.Health}}' wishwithme-core-api | jq

# View network
docker network inspect wishwithme-network

# Clean up
docker system prune -a
```

## CI/CD

### GitHub Actions Workflows

- **deploy.yml**: Unified deployment workflow
  - Auto-detects changed services
  - Deploys only what changed
  - Runs health checks
  - Auto-rollback on failure

### Required GitHub Secret

Only 1 secret needed:
- `SSH_PRIVATE_KEY`: Ed25519 key for server access

All other secrets stored in `.env` on server.

### Manual Deployment

```bash
# Trigger deployment
gh workflow run deploy.yml

# Watch progress
gh run watch
```

## Security

- **HTTPS Only**: SSL/TLS certificates via Let's Encrypt
- **Rate Limiting**: API and auth endpoints protected
- **CORS**: Configured for production domains
- **No Exposed Ports**: Production services isolated
- **Secrets Management**: Server-side .env file
- **HSTS**: Strict Transport Security headers
- **Security Headers**: XSS, frame, content-type protection

## Performance

- **Resource Limits**: CPU and memory limits in production
- **Caching**: Redis for sessions and API responses
- **Static Assets**: Long-term caching (1 year)
- **Gzip Compression**: Enabled for all text content
- **Database Indexing**: Optimized queries
- **Health Checks**: Ensure service readiness

## License

MIT

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## Support

- **Documentation**: [docs/](./docs/)
- **GitHub Issues**: https://github.com/mrkutin/wish-with-me-codex/issues
- **Deployment Guide**: [docs/13-deployment.md](./docs/13-deployment.md)
- **Migration Guide**: [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
