# core-api

FastAPI service for auth, wishlists, sharing, and sync.

## Local run (docker-compose)

From repo root:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Core API will be at `http://localhost:8000`.

## Tests

Run inside the container:

```bash
docker compose -f infra/docker-compose.yml exec -T core-api pytest /app/tests
```

## Environment variables

- `MONGO_URI`
- `REDIS_URL`
- `RABBITMQ_URL`
- `JWT_SECRET`
- `JWT_ISSUER`
- `ACCESS_TOKEN_TTL_DAYS`
- `REFRESH_TOKEN_TTL_DAYS`
