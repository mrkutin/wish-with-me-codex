## Item Resolver Service

Stealth Playwright microservice used by an AI agent/orchestrator.

### Endpoints (all require Bearer token)

- `GET /healthz`
- `POST /resolver/v1/resolve` — resolve a page URL into item data (uses Playwright + LLM)
- `POST /v1/page_source` — fetch a product/page URL and return HTML
- `POST /v1/image_base64` — fetch an image URL and return a data URL (base64)

### Auth

Send the token on every request:

- Header: `Authorization: Bearer <RU_BEARER_TOKEN>`

### Required environment variables

- `RU_BEARER_TOKEN`: required

### Recommended environment variables

- `BROWSER_CHANNEL`: `chrome` (default) or `chromium`
- `HEADLESS`: `true` (default) / `false`
- `MAX_CONCURRENCY`: default `2`
- `STORAGE_STATE_DIR`: where storage_state files are persisted (default `storage_state`)
- `SSRF_ALLOWLIST_HOSTS`: optional comma-separated hostnames to bypass DNS/IP SSRF checks (use sparingly)
- `PROXY_SERVER`: optional proxy server URL (e.g. `http://proxy.example:3128`)
- `PROXY_USERNAME`: optional proxy username
- `PROXY_PASSWORD`: optional proxy password
- `PROXY_BYPASS`: optional comma-separated proxy bypass list (Playwright format)
- `PROXY_IGNORE_CERT_ERRORS`: optional `true`/`false`; allow invalid proxy TLS certs (default `false`)
- `LLM_MODE`: `live` (default) or `stub`
- `LLM_BASE_URL`: base URL for OpenAI-compatible chat API (required for `live`)
- `LLM_API_KEY`: API key for the LLM (required for `live`)
- `LLM_MODEL`: model name (required for `live`)
- `LLM_TIMEOUT_S`: request timeout in seconds (default `60`)
- `LLM_MAX_CHARS`: max page source characters sent to LLM for image_url (default `200000`)

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
export BROWSER_CHANNEL='chrome'       # or 'chromium'
export HEADLESS='true'
export MAX_CONCURRENCY='2'
export LLM_MODE='live'
export LLM_BASE_URL='https://api.openai.com'
export LLM_API_KEY='your_key'
export LLM_MODEL='gpt-4o-mini'

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

Fetch image data URL:

```bash
curl -sS \
  -H "Authorization: Bearer ru_secret" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://ir.ozone.ru/s3/multimedia-1-p/wc1000/7234085113.jpg"}' \
  http://localhost:8000/v1/image_base64
```

Resolve item data:

```bash
curl -sS \
  -H "Authorization: Bearer ru_secret" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.ozon.ru/product/kartholder-2817727699/"}' \
  http://localhost:8000/resolver/v1/resolve
```

### Notes

- **SSRF protections** are enabled by default (blocks localhost/private ranges). If you need internal hosts, explicitly add them to `SSRF_ALLOWLIST_HOSTS`.
- **storage_state** (cookies + localStorage) is persisted per-host under `STORAGE_STATE_DIR/<host>.json` to improve reliability on bot-protected sites.
