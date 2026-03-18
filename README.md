# FPV Deal Finder

A self-hosted deal tracker and price history tool for FPV drone parts. Scrapes multiple online stores, detects sales, scores deals with AI, and surfaces everything through a fast search interface. Runs entirely in Docker with no external dependencies beyond an optional Discord webhook.

---

## What It Does

- **Scrapes FPV stores** on a schedule (every 6 hours by default), storing every product and its price
- **Tracks price history** so you can see whether a "sale" is actually cheaper than usual
- **Scores deals 0–10** using AI (Ollama locally, or OpenAI as fallback) based on discount depth and price history context
- **Searches everything** with typo-tolerant full-text search powered by Meilisearch, with natural language query understanding ("2207 motors under $30" works out of the box)
- **Sends Discord alerts** when deals above your score threshold appear
- **Runs fully self-hosted** — your data stays local, no accounts required

---

## Supported Stores

| Store | Method | Notes |
|---|---|---|
| NewBeeDrone | JSON API (Boost PFS Filter) | No browser needed, fast |
| PyroDrone | Playwright (browser) | JS-rendered site |
| RaceDayQuads | Playwright (browser) | JS-rendered site |
| GetFPV | Playwright (browser) | Extra stealth headers required |
| GEPRC | Playwright (browser) | JS-rendered site |
| HDZero | Playwright (browser) | JS-rendered site |
| Rotor Village | Playwright (browser) | JS-rendered site |

---

## Tech Stack

### Backend — Python + FastAPI

**[FastAPI](https://fastapi.tiangolo.com/)** is the web framework. It handles all HTTP API routes, runs async, and auto-generates Swagger docs at `/docs`. Every endpoint is typed with Pydantic models, so the API is self-documenting and request/response validation is automatic.

**[SQLAlchemy](https://www.sqlalchemy.org/) (async)** is the ORM. Uses `asyncpg` as the PostgreSQL driver so database queries are non-blocking. The models are defined in `backend/app/models/product.py`:
- `stores` — the list of FPV stores with their scrape intervals
- `products` — one row per unique product per store, with a `specs` JSONB column for flexible category-specific data (stator size, KV rating, amperage, etc.)
- `price_history` — every scraped price point with timestamp, used for charts and deal detection
- `deals` — detected deals with score, type, and discount percentage

**[Pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)** manages configuration. All settings come from environment variables (or `.env` file), with defaults and type validation. Defined in `backend/app/config.py`.

**[structlog](https://www.structlog.org/)** handles logging. Outputs structured JSON in production, human-readable colored output in development.

---

### Scraping — Playwright + httpx

**[Playwright](https://playwright.dev/python/)** is a browser automation library. Most FPV stores render their product listings with JavaScript, so a plain HTTP request gets an empty page. Playwright launches a real headless Chromium browser, navigates to the page, waits for the JavaScript to finish, and then reads the DOM.

Key stealth techniques used to avoid bot detection:
- Sets `navigator.webdriver` to `undefined` (hides automation)
- Fakes `navigator.plugins` with a non-empty array (real browsers have plugins)
- Uses a realistic `User-Agent` string
- Sets locale (`en-US`) and timezone (`America/New_York`)
- Uses `domcontentloaded` instead of `networkidle` (faster, less detectable)

The base scraper class (`backend/app/scrapers/base.py`) provides:
- Browser lifecycle management (`async with scraper:` pattern)
- Automatic retry with exponential backoff via **[tenacity](https://tenacity.readthedocs.io/)** (3 attempts, 2–10s wait)
- Rate limiting between page loads (polite 1.5s delay)
- Helper methods: `safe_text()`, `safe_attr()`, `parse_price()` — all return defaults instead of throwing if the HTML structure changes

**[httpx](https://www.python-httpx.org/)** is used for direct HTTP requests where a store exposes an API. NewBeeDrone uses a third-party Shopify app called **Boost PFS Filter** which exposes a JSON endpoint at `services.mybcapps.com`. This was discovered by inspecting network requests while the page loaded. Using the API directly is dramatically faster and more reliable than browser automation — 1700+ products in seconds instead of minutes.

The NewBeeDrone API quirk: `total_page` in the response always returns `0` even when there are 70+ pages of products. The scraper handles this by paginating until it gets an empty `products` array.

---

### Database — PostgreSQL 16

**[PostgreSQL](https://www.postgresql.org/)** stores all persistent data. Key design decisions:

- `specs` column is `JSONB` — each product category has different specs (motors have stator size and KV, ESCs have amperage and type, frames have size in mm). JSONB lets us store arbitrary key-value pairs without schema migrations every time we add a new spec type.
- `price_history` is append-only — every scrape adds a new row rather than updating the product's price in place. This gives complete price history for charts and lets us detect when a "sale" is actually below historical average.
- `ON CONFLICT DO NOTHING` is used when upserting stores and products, making startup and re-scraping idempotent.

---

### Task Queue — Celery + Redis

**[Celery](https://docs.celeryq.dev/)** runs scraping jobs as background tasks. The API never blocks waiting for a scrape — scrapes are dispatched to the queue and run by a separate worker process.

There are two Celery services:
- **celery-worker** — picks up and executes scraping tasks. Runs with `--concurrency=2` to scrape two stores in parallel without hammering infrastructure.
- **celery-beat** — the scheduler. Triggers `scrape_all_stores` every 6 hours and `scrape_all_deals` every 2 hours using Celery's `PersistentScheduler` (schedule survives restarts).

**[Redis](https://redis.io/)** is the Celery broker. Tasks are serialized and pushed to Redis queues by the API or beat scheduler, then consumed by workers. Redis is also available as a result backend if you need to check task status.

---

### Search — Meilisearch

**[Meilisearch](https://www.meilisearch.com/)** is the search engine. It's a lightweight, typo-tolerant alternative to Elasticsearch. Products are indexed here (alongside PostgreSQL) specifically for fast full-text search with filters.

Configuration applied at startup (`backend/app/services/search.py`):

**Filterable attributes** — these can be used in filter expressions:
- `category`, `store`, `price`, `in_stock`, `is_deal`

**Sortable attributes** — `price` (used for "price: low to high" sort)

**Ranking rules** — custom ranking order: words matched → typos → proximity → attribute priority → sort → exactness → then price ascending by default (cheapest first, good for deal hunting)

**Stop words** — words that are ignored in search queries so natural language works correctly. Without this, searching "2207 motors under 30 dollars" would require products to literally contain the words "under" and "dollars". Stop words configured: `under`, `over`, `cheap`, `cheapest`, `best`, `good`, `great`, `deals`, `sale`, `discount`, `the`, `a`, `an`, `for`, `in`, `on`, `at`, `with`, `from`, `dollars`, `dollar`, `bucks`, `buck`, `usd`

Products are indexed via the `SearchService.add_products()` method after every scrape. The Meilisearch document ID is `{StoreName}-{product-handle}` so re-indexing the same product updates it in place.

---

### AI — Ollama (local) + OpenAI (fallback)

**[Ollama](https://ollama.com/)** runs LLMs locally. The default model is `mistral:7b`, which is fast enough for real-time query parsing and deal scoring on a CPU. If you have a GPU, it's much faster.

The AI does two things:

**1. Query Understanding** (`parse_search_query`)

Converts a natural language search query into structured JSON filters. Example:

```
Input:  "cheap 2207 motors under 30 dollars"
Output: {
  "category": "motors",
  "max_price": 30,
  "specs": {"stator": "2207"},
  "search_terms": ["motor", "2207"]
}
```

This structured output is then used to build Meilisearch filter expressions (`category = "motors" AND price <= 30`) and a clean search query (`motor 2207`).

**2. Deal Scoring** (`score_deal`)

Rates a deal 0–10 with reasoning. The AI receives:
- Product name and category
- Current price vs. original/list price (discount %)
- 30-day average price (how current price compares to recent history)
- FPV price context (typical price ranges per category)

Returns: `{"score": 8.5, "reasoning": "25% off a popular 2207 motor", "recommendation": "buy"}`

**Availability caching:** The AI service probes Ollama with a 2-second timeout on first use and caches the result. If Ollama is down, it skips straight to the OpenAI fallback (or keyword fallback) rather than timing out on every request.

**Fallbacks:**
- If Ollama is unavailable: tries OpenAI (`gpt-3.5-turbo`) if `OPENAI_API_KEY` is set
- If both are unavailable: uses regex-based keyword extraction for query parsing, and discount-percentage tiers for deal scoring (40%+ off → 9.0, 25%+ off → 7.5, etc.)

**Connecting to host Ollama from Docker:** If Ollama is already running on your host machine (not in Docker), set `OLLAMA_HOST=http://host.docker.internal:11434` in `.env`. The `extra_hosts: host.docker.internal:host-gateway` entries in `docker-compose.yml` make this work on Linux.

---

### Frontend — SvelteKit + TailwindCSS

**[SvelteKit](https://kit.svelte.dev/)** is the frontend framework. Pages are server-side rendered on first load (fast initial paint) and then hydrated for client-side navigation.

**[TailwindCSS](https://tailwindcss.com/)** handles styling via utility classes. The theme is dark mode with two accent colors:
- Electric blue: `#00d4ff` — prices, links, primary actions
- Electric green: `#00ff88` — in-stock indicators, discounts, positive states

Pages:
- `/` — search page with sidebar filters (category, store, price range, in-stock toggle, deals-only toggle)
- `/deals` — live deal feed sorted by AI score, filterable by category and store
- `/product/[id]` — product detail page with price history chart, specs, and stock status
- `/settings` — Discord webhook configuration and test notification

**[Chart.js](https://www.chartjs.org/)** renders the price history line chart on product detail pages. The chart shows price over time with the original/list price as a second line for context.

All API calls are typed in `frontend/src/lib/api.ts` — TypeScript interfaces match the FastAPI response models, so you get compile-time errors if the API changes shape.

---

### Notifications — Discord Webhooks via Apprise

**[Apprise](https://github.com/caronc/apprise)** is a notification library that abstracts over 80+ notification services. It's used here specifically for Discord webhooks, but could be extended to Slack, Telegram, email, etc. just by changing the URL format.

When a deal is detected during indexing (score >= threshold), `backend/app/services/notifications.py` fires a webhook with:
- Product name and store
- Current price, original price, discount %
- Deal score and AI reasoning
- Direct link to the product

Notification rules (min score, categories to watch, max price) are configurable via the settings page or `PUT /api/notifications/rules`.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Docker Compose                        │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │    │   Backend    │    │Celery Worker │  │
│  │  SvelteKit   │───▶│   FastAPI    │◀───│  (scraping)  │  │
│  │   :3000      │    │   :8000      │    │              │  │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘  │
│                             │                   │           │
│              ┌──────────────┼───────────────────┤           │
│              │              │                   │           │
│              ▼              ▼                   ▼           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  PostgreSQL  │  │ Meilisearch  │  │      Redis       │  │
│  │  :5432       │  │   :7700      │  │      :6379       │  │
│  │  (products,  │  │  (search     │  │  (task queue)    │  │
│  │  prices,     │  │   index)     │  │                  │  │
│  │  deals)      │  │              │  └──────────────────┘  │
│  └──────────────┘  └──────────────┘                        │
│                                                             │
│  ┌──────────────┐                                           │
│  │ Celery Beat  │  (triggers scrapes on schedule)           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Ollama (host)     │
                    │  mistral:7b        │
                    │  :11434            │
                    └────────────────────┘
```

**Request flow for a search:**
1. User types "2207 motors under $30" in the frontend
2. SvelteKit sends `GET /api/products/search?q=2207+motors+under+%2430` to FastAPI
3. FastAPI calls Ollama to parse the query → `{category: motors, max_price: 30, specs: {stator: "2207"}}`
4. FastAPI builds Meilisearch filters and runs the search
5. Meilisearch returns matching products (stop words strip "under", "dollars" from query before matching)
6. FastAPI returns typed JSON to the frontend
7. SvelteKit renders product cards

**Scrape flow:**
1. Celery Beat fires `scrape_all_stores` task every 6 hours
2. Worker picks up the task, instantiates the store's scraper
3. Scraper fetches all products (via API or Playwright browser)
4. `ProductIndexer.index_products()` runs for each product:
   - Upserts product record in PostgreSQL
   - Appends new price history row
   - Compares current price to original price and 30-day average
   - If discount > 10%, calls AI to score the deal
   - Saves deal record if score >= threshold
   - Indexes/updates product in Meilisearch
5. If any deal score >= notification threshold, Discord webhook fires

---

## Setup

### Prerequisites

- Docker and Docker Compose v2
- Git
- (Optional) Ollama running on your host for AI features

### Quick Start

```bash
git clone https://github.com/Santa-Claws/deal-bot-fpv.git
cd deal-bot-fpv
cp .env.example .env
```

Edit `.env` — the defaults work for local use but you should at minimum change the passwords:

```bash
# Required: change these
POSTGRES_PASSWORD=your_secure_password
MEILI_MASTER_KEY=your_secure_key

# Optional: point to your Ollama instance
OLLAMA_HOST=http://host.docker.internal:11434

# Optional: OpenAI fallback if Ollama is unavailable
OPENAI_API_KEY=sk-...

# Optional: Discord deal alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

```bash
docker compose up -d
```

Services start in dependency order. The backend waits for healthy PostgreSQL, Redis, and Meilisearch before starting.

**Verify everything is running:**

```bash
curl http://localhost:8000/health
# → {"status": "ok"}

curl "http://localhost:8000/api/products/search?q=motor"
# → {"hits": [...], "total": N}
```

Open the UI at **http://localhost:3000**

API docs (Swagger) at **http://localhost:8000/docs**

### Running the First Scrape Manually

By default, Celery Beat triggers scrapes every 6 hours. To run one immediately:

```bash
# Scrape all products from NewBeeDrone
docker exec fpv-celery-worker celery -A app.scrapers.runner call \
  app.scrapers.runner.scrape_store \
  --args '["NewBeeDrone"]'

# Scrape all stores at once
docker exec fpv-celery-worker celery -A app.scrapers.runner call \
  app.scrapers.runner.scrape_all_stores
```

### Ollama Setup (for AI search)

If Ollama isn't already installed:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull mistral:7b
```

Then in `.env`:
```
OLLAMA_HOST=http://host.docker.internal:11434
```

Restart the backend:
```bash
docker compose restart backend celery-worker
```

Test that AI parsing is working:
```bash
curl -X POST "http://localhost:8000/api/products/ai/parse-query?query=cheap+2207+motors+under+30+dollars"
# Should return: {"specs": {"stator": "2207"}, "category": "motors", "max_price": 30, ...}
```

---

## Configuration Reference

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `fpvdeals` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password |
| `POSTGRES_DB` | `fpvdeals` | PostgreSQL database name |
| `MEILI_MASTER_KEY` | `changeme` | Meilisearch API key |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama API base URL |
| `OPENAI_API_KEY` | *(empty)* | OpenAI key for AI fallback |
| `DISCORD_WEBHOOK_URL` | *(empty)* | Discord webhook for deal alerts |
| `SCRAPE_INTERVAL_HOURS` | `6` | How often to re-scrape stores |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |

AI model configuration is in `config/ai.yaml`:

```yaml
provider: ollama        # "ollama" or "openai"
ollama:
  model: mistral:7b     # any model you have pulled
  timeout: 5            # seconds before giving up and using fallback
```

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`. Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/products/search` | Search products (supports natural language via `q=`) |
| `GET` | `/api/products/{id}` | Get a single product with full details |
| `GET` | `/api/products/{id}/history` | Price history for a product (for charts) |
| `GET` | `/api/deals/` | Deal feed sorted by score |
| `POST` | `/api/products/ai/parse-query` | Debug: see how AI parses a query |
| `GET` | `/api/notifications/settings` | Get notification settings |
| `PUT` | `/api/notifications/settings` | Update notification settings |
| `POST` | `/api/notifications/test` | Send a test Discord notification |

**Search query parameters:**

| Param | Type | Description |
|---|---|---|
| `q` | string | Natural language query (AI-parsed) |
| `category` | string | Filter by category (motors, escs, frames, ...) |
| `store` | string | Filter by store name |
| `min_price` | float | Minimum price filter |
| `max_price` | float | Maximum price filter |
| `in_stock` | bool | Only show in-stock items |
| `deals_only` | bool | Only show items with an active deal |
| `sort` | string | `price:asc` or `price:desc` |
| `page` | int | Page number (default 1) |
| `per_page` | int | Results per page (default 24, max 100) |

---

## Adding a New Store

1. Create `backend/app/scrapers/yourstore.py` inheriting from `BaseScraper`
2. Implement `get_products()`, `get_deals()`, and `normalize_product()`
3. Add the store to `seed_stores()` in `backend/app/main.py`
4. Register the Celery task in `backend/app/scrapers/runner.py`

See `docs/ADDING_STORES.md` for a detailed walkthrough with code examples.

---

## Project Structure

```
deal-bot-fpv/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI app, startup, router registration
│       ├── config.py            # Settings (pydantic-settings, env vars)
│       ├── database.py          # SQLAlchemy async engine + session
│       ├── models/
│       │   └── product.py       # Store, Product, PriceHistory, Deal models
│       ├── routers/
│       │   ├── products.py      # GET /api/products/search, GET /api/products/{id}
│       │   ├── deals.py         # GET /api/deals/
│       │   ├── prices.py        # GET /api/products/{id}/history
│       │   ├── notifications.py # GET/PUT /api/notifications/settings
│       │   └── health.py        # GET /health
│       ├── scrapers/
│       │   ├── base.py          # BaseScraper (Playwright, retry, rate limiting)
│       │   ├── newbeedrone.py   # NewBeeDrone (JSON API)
│       │   ├── pyrodrone.py     # PyroDrone (Playwright)
│       │   ├── racedayquads.py  # RaceDayQuads (Playwright)
│       │   ├── getfpv.py        # GetFPV (Playwright + stealth)
│       │   └── runner.py        # Celery tasks + beat schedule
│       └── services/
│           ├── ai.py            # Ollama/OpenAI query parsing + deal scoring
│           ├── indexer.py       # Orchestrates DB upsert + Meili indexing
│           ├── search.py        # Meilisearch client wrapper
│           └── notifications.py # Discord webhook sender (Apprise)
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── lib/
│       │   ├── api.ts           # Typed API client
│       │   └── components/
│       │       ├── SearchBar.svelte
│       │       ├── ProductCard.svelte
│       │       ├── DealBadge.svelte
│       │       └── PriceChart.svelte
│       └── routes/
│           ├── +page.svelte           # Search page
│           ├── deals/+page.svelte     # Deals feed
│           ├── product/[id]/+page.svelte  # Product detail + price chart
│           └── settings/+page.svelte  # Discord config
├── config/
│   └── ai.yaml          # AI model configuration
├── scripts/
│   └── init-db.sh       # PostgreSQL initialization
├── docs/
│   ├── ARCHITECTURE.md
│   └── ADDING_STORES.md
├── docker-compose.yml
└── .env.example
```

---

## License

MIT
