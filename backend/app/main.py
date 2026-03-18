"""
FPV Deal Finder - FastAPI Application Entry Point

This is the main file that wires everything together:
- Creates the FastAPI app instance
- Registers all API routers
- Runs startup/shutdown tasks (DB init, search index setup)

Run locally (outside Docker):
    uvicorn app.main:app --reload --port 8000

API docs auto-generated at: http://localhost:8000/docs
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables
from app.routers import deals, health, notifications, prices, products

# Configure structured logging (outputs JSON in prod, pretty in dev)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(__import__("logging"), settings.log_level)
    )
)
logger = structlog.get_logger()


# ── FastAPI app ────────────────────────────────────────
app = FastAPI(
    title="FPV Deal Finder",
    description="""
A self-hosted deal tracker for FPV (First Person View) drone parts.

## Features
- **Search** - AI-enhanced search across all supported stores
- **Deals** - Aggregated deal feed with AI quality scores
- **Price History** - Track price changes over time
- **Notifications** - Discord alerts for deals that match your criteria

## Supported Stores
- NewBeeDrone
- PyroDrone
- RaceDayQuads
- GetFPV
- GEPRC
- HDZero
- Rotor Village
    """,
    version="0.1.0",
    docs_url="/docs",   # Swagger UI
    redoc_url="/redoc", # ReDoc UI
)

# ── CORS ──────────────────────────────────────────────
# Allow the SvelteKit frontend (port 3000) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://frontend:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup / Shutdown ────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """
    Runs when the application starts up.

    We use this to:
    1. Create database tables (if they don't exist yet)
    2. Set up Meilisearch indexes
    3. Seed initial store data
    """
    logger.info("Starting FPV Deal Finder...")

    # Create database tables
    try:
        await create_tables()
        logger.info("Database tables ready")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))

    # Seed stores into the database
    try:
        await seed_stores()
        logger.info("Stores seeded")
    except Exception as e:
        logger.error("Failed to seed stores", error=str(e))

    # Set up Meilisearch index
    try:
        from app.services.search import setup_index
        await setup_index()
        logger.info("Meilisearch index ready")
    except Exception as e:
        logger.warning("Meilisearch setup failed (search may not work)", error=str(e))

    logger.info("FPV Deal Finder is ready!", docs="http://localhost:8000/docs")


async def seed_stores():
    """
    Insert the FPV stores into the database on first run.

    Uses INSERT ... ON CONFLICT DO NOTHING so re-running is safe.
    """
    from sqlalchemy.dialects.postgresql import insert

    from app.database import AsyncSessionLocal
    from app.models.product import Store

    stores = [
        {"name": "NewBeeDrone", "base_url": "https://newbeedrone.com", "scrape_interval_hours": 6},
        {"name": "PyroDrone", "base_url": "https://pyrodrone.com", "scrape_interval_hours": 6},
        {"name": "RaceDayQuads", "base_url": "https://racedayquads.com", "scrape_interval_hours": 6},
        {"name": "GetFPV", "base_url": "https://www.getfpv.com", "scrape_interval_hours": 12},
        {"name": "GEPRC", "base_url": "https://geprc.com", "scrape_interval_hours": 12},
        {"name": "HDZero", "base_url": "https://shop.hdzero.com", "scrape_interval_hours": 12},
        {"name": "Rotor Village", "base_url": "https://rotorvillage.ca", "scrape_interval_hours": 12},
    ]

    async with AsyncSessionLocal() as session:
        stmt = insert(Store).values(stores)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        await session.execute(stmt)
        await session.commit()


# ── Register routers ──────────────────────────────────
# Each router handles a group of related endpoints
app.include_router(health.router)
app.include_router(products.router, prefix="/api")
app.include_router(deals.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
