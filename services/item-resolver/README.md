## Item Resolver Service

Stealth Playwright microservice used by an AI agent/orchestrator.

### Endpoints (all require Bearer token)

- `GET /healthz`
- `POST /v1/page_source` — fetch a product/page URL and return HTML
- `POST /v1/image_base64` — fetch an image URL and return base64 bytes

### Auth

Send the token on every request:

- Header: `Authorization: Bearer <RU_BEARER_TOKEN>`

### Required environment variables

- `RU_BEARER_TOKEN`: required

### Recommended environment variables

- `BROWSER_CHANNEL`: `chromium` (default) or `chrome`
- `HEADLESS`: `true` (default) / `false`
- `MAX_CONCURRENCY`: default `2`
- `STORAGE_STATE_DIR`: where storage_state files are persisted (default `storage_state`)
- `SSRF_ALLOWLIST_HOSTS`: optional comma-separated hostnames to bypass DNS/IP SSRF checks (use sparingly)
- `PROXY_SERVER`: optional proxy server URL (e.g. `http://proxy.example:3128`)
- `PROXY_USERNAME`: optional proxy username
- `PROXY_PASSWORD`: optional proxy password
- `PROXY_BYPASS`: optional comma-separated proxy bypass list (Playwright format)
- `PROXY_IGNORE_CERT_ERRORS`: optional `true`/`false`; allow invalid proxy TLS certs (default `false`)

### Run with Docker Compose

From this folder:

```bash
cd services/item-resolver
export RU_BEARER_TOKEN='ru_secret'
docker compose up --build
```

Service listens on `http://localhost:8000` by default (see `docker-compose.yml`).

### Run locally (no Docker)

From repo root:

```bash
cd services/item-resolver
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time: install browser binaries for Playwright
playwright install

export RU_BEARER_TOKEN='ru_secret'
export RU_FETCHER_MODE='playwright'   # use 'stub' to disable Playwright (tests/dev)
export BROWSER_CHANNEL='chromium'     # or 'chrome' if available
export HEADLESS='true'
export MAX_CONCURRENCY='2'

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Example requests (curl)

Health check:

```bash
curl -sS \
  -H "Authorization: Bearer ru_secret" \
  http://localhost:8000/healthz
```

Fetch page HTML:

```bash
curl -sS \
  -H "Authorization: Bearer ru_secret" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.ozon.ru/product/shapka-ushanka-1789434868/"}' \
  http://localhost:8000/v1/page_source
```

Fetch image base64:

```bash
curl -sS \
  -H "Authorization: Bearer ru_secret" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://ir.ozone.ru/s3/multimedia-1-p/wc1000/7234085113.jpg"}' \
  http://localhost:8000/v1/image_base64
```

### Notes

- **SSRF protections** are enabled by default (blocks localhost/private ranges). If you need internal hosts, explicitly add them to `SSRF_ALLOWLIST_HOSTS`.
- **storage_state** (cookies + localStorage) is persisted per-host under `STORAGE_STATE_DIR/<host>.json` to improve reliability on bot-protected sites.
