# Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Frontend   │    │   Backend    │    │   Ollama     │      │
│  │  (SvelteKit) │◄──►│  (FastAPI)   │◄──►│   (AI/LLM)   │      │
│  │   Port 3000  │    │   Port 8000  │    │   Port 11434 │      │
│  └──────────────┘    └──────┬───────┘    └──────────────┘      │
│                             │                                   │
│              ┌──────────────┼──────────────┐                   │
│              ▼              ▼              ▼                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Meilisearch │  │  PostgreSQL  │  │    Redis     │         │
│  │   (Search)   │  │  (Database)  │  │   (Queue)    │         │
│  │   Port 7700  │  │   Port 5432  │  │   Port 6379  │         │
│  └──────────────┘  └──────────────┘  └──────┬───────┘         │
│                                             │                  │
│                                    ┌────────┴────────┐         │
│                                    ▼                 ▼         │
│                            ┌─────────────┐  ┌─────────────┐   │
│                            │Celery Worker│  │ Celery Beat │   │
│                            │ (Scraping)  │  │ (Scheduler) │   │
│                            └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Search Request
```
User types "2207 motors under $30"
    ↓
Frontend (SearchBar.svelte)
    ↓ POST /api/products/search?q=...
Backend (products.py router)
    ↓ AI parse query
Ollama → {category: motors, max_price: 30, specs: {stator: 2207}}
    ↓ Search with filters
Meilisearch → ranked results
    ↓ Return JSON
Frontend renders ProductCard components
```

### Scraping Pipeline
```
Celery Beat (every 6h)
    ↓ dispatch task
Redis queue
    ↓ consume task
Celery Worker
    ↓ launch Playwright
Browser → FPV store website
    ↓ extract product data
Scraper normalize_product()
    ↓ upsert product + price history
PostgreSQL
    ↓ index for search
Meilisearch
    ↓ score deal with AI
Ollama → deal_score
    ↓ if score >= 7
Discord notification
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, startup, router registration |
| `backend/app/config.py` | All environment variable config |
| `backend/app/database.py` | SQLAlchemy async engine |
| `backend/app/models/product.py` | DB schema: stores, products, prices, deals |
| `backend/app/scrapers/base.py` | Base scraper with Playwright |
| `backend/app/scrapers/runner.py` | Celery tasks for scheduled scraping |
| `backend/app/services/ai.py` | Ollama/OpenAI integration |
| `backend/app/services/search.py` | Meilisearch client |
| `backend/app/services/indexer.py` | Save scraped data to DB + search |
| `backend/app/services/notifications.py` | Discord webhook sender |
| `frontend/src/lib/api.ts` | Typed API client |
| `frontend/src/routes/+page.svelte` | Home/search page |
| `config/ai.yaml` | AI model selection |

## Database Schema

```sql
stores (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE,
    base_url    VARCHAR(255),
    scrape_interval_hours INT DEFAULT 6,
    last_scraped_at TIMESTAMP,
    is_active   BOOLEAN DEFAULT TRUE
)

products (
    id          SERIAL PRIMARY KEY,
    store_id    INT REFERENCES stores(id),
    external_id VARCHAR(255),   -- Store's own product ID
    title       VARCHAR(500),
    url         TEXT,
    image_url   TEXT,
    category    VARCHAR(100),
    specs       JSONB,           -- Flexible spec storage
    created_at  TIMESTAMP,
    updated_at  TIMESTAMP
)

price_history (
    id              SERIAL PRIMARY KEY,
    product_id      INT REFERENCES products(id),
    price           DECIMAL(10,2),
    original_price  DECIMAL(10,2),
    currency        VARCHAR(3) DEFAULT 'USD',
    in_stock        BOOLEAN,
    scraped_at      TIMESTAMP
)

deals (
    id              SERIAL PRIMARY KEY,
    product_id      INT REFERENCES products(id),
    deal_type       VARCHAR(50),     -- sale, price_drop, historic_low
    discount_percent FLOAT,
    deal_score      FLOAT,           -- AI-generated 0-10
    detected_at     TIMESTAMP,
    expires_at      TIMESTAMP
)
```

## Technology Choices

See the full reasoning in `~/.claude/plans/zippy-crunching-pudding.md`.

Short version:
- **FastAPI** over Flask/Django: async, fast, auto-generated docs
- **Playwright** over Scrapy: handles JS-rendered stores natively
- **Meilisearch** over Elasticsearch: much lighter, typo-tolerant
- **Ollama** over OpenAI: free, private, runs on your GPU
- **SvelteKit** over Next.js: smaller bundle, faster, simpler
