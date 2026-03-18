"""
Celery task runner for scheduled scraping.

Celery is a distributed task queue. We use it to:
1. Run scrapers in the background without blocking the API
2. Schedule regular scraping (every 6 hours by default)
3. Retry failed scrapes automatically

Architecture:
    - celery-worker: processes tasks from the Redis queue
    - celery-beat: schedules periodic tasks (like a cron job)
    - Redis: the message broker between beat and worker

Task flow:
    celery-beat → Redis queue → celery-worker → scrape store → save to DB
"""

import asyncio
from datetime import datetime, timedelta

import structlog
from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = structlog.get_logger()

# ── Celery app instance ────────────────────────────────
# broker: Redis handles task messaging
# backend: Redis stores task results
celery_app = Celery(
    "fpv-scraper",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# ── Celery configuration ───────────────────────────────
celery_app.conf.update(
    # Serialize tasks as JSON (human readable, debuggable)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Don't keep task results forever (save memory)
    result_expires=3600,  # 1 hour

    # Retry failed tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Scheduled tasks (cron-like) ───────────────────────
# celery-beat runs these on schedule
celery_app.conf.beat_schedule = {
    # Scrape all active stores every 6 hours
    "scrape-all-stores": {
        "task": "app.scrapers.runner.scrape_all_stores",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
    # Specifically hunt for deals every 2 hours (more frequent)
    "scrape-all-deals": {
        "task": "app.scrapers.runner.scrape_all_deals",
        "schedule": crontab(minute=0, hour="*/2"),  # Every 2 hours
    },
}


# ── Task definitions ───────────────────────────────────

@celery_app.task(
    name="app.scrapers.runner.scrape_store",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes between retries
)
def scrape_store(self, store_name: str):
    """
    Scrape all products from a single store.

    This runs in a Celery worker process (separate from the API).
    We use asyncio.run() to run async scraper code in the sync Celery context.

    Args:
        store_name: Name matching Store.name in the database
    """
    logger.info("Starting store scrape", store=store_name)

    try:
        asyncio.run(_async_scrape_store(store_name, scrape_type="products"))
        logger.info("Store scrape complete", store=store_name)
    except Exception as e:
        logger.error("Store scrape failed", store=store_name, error=str(e))
        # Celery retry: wait 5 mins, try up to 3 times
        raise self.retry(exc=e)


@celery_app.task(
    name="app.scrapers.runner.scrape_store_deals",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def scrape_store_deals(self, store_name: str):
    """Scrape only the deals/sale section of a store."""
    logger.info("Starting deal scrape", store=store_name)

    try:
        asyncio.run(_async_scrape_store(store_name, scrape_type="deals"))
        logger.info("Deal scrape complete", store=store_name)
    except Exception as e:
        logger.error("Deal scrape failed", store=store_name, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(name="app.scrapers.runner.scrape_all_stores")
def scrape_all_stores():
    """
    Dispatch scrape tasks for all active stores.

    This runs on the beat schedule and fans out individual
    store scrape tasks to the worker pool.
    """
    logger.info("Dispatching scrape tasks for all stores")
    asyncio.run(_dispatch_store_tasks("products"))


@celery_app.task(name="app.scrapers.runner.scrape_all_deals")
def scrape_all_deals():
    """Dispatch deal scrape tasks for all active stores."""
    logger.info("Dispatching deal scrape tasks for all stores")
    asyncio.run(_dispatch_store_tasks("deals"))


# ── Async helpers ──────────────────────────────────────

async def _dispatch_store_tasks(scrape_type: str):
    """
    Look up active stores in DB and dispatch a Celery task for each.
    """
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.product import Store

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Store).where(Store.is_active == True)
        )
        stores = result.scalars().all()

    for store in stores:
        if scrape_type == "products":
            scrape_store.delay(store.name)
        else:
            scrape_store_deals.delay(store.name)

    logger.info("Dispatched scrape tasks", count=len(stores), type=scrape_type)


async def _async_scrape_store(store_name: str, scrape_type: str):
    """
    Actually run the scraper for a given store.

    Maps store names to their scraper classes, runs the scraper,
    then saves results to the database and indexes to Meilisearch.
    """
    from app.scrapers.getfpv import GetFPVScraper
    from app.scrapers.newbeedrone import NewBeeDroneScraper
    from app.scrapers.pyrodrone import PyroDroneScraper
    from app.scrapers.racedayquads import RaceDayQuadsScraper
    from app.services.indexer import index_products

    # Map store names to their scraper classes
    SCRAPERS = {
        "NewBeeDrone": NewBeeDroneScraper,
        "PyroDrone": PyroDroneScraper,
        "RaceDayQuads": RaceDayQuadsScraper,
        "GetFPV": GetFPVScraper,
    }

    scraper_class = SCRAPERS.get(store_name)
    if not scraper_class:
        logger.warning("No scraper found for store", store=store_name)
        return

    scraper = scraper_class()

    # Run the appropriate scrape method
    if scrape_type == "products":
        raw_products = await scraper.get_products()
    else:
        raw_products = await scraper.get_deals()

    if not raw_products:
        logger.warning("Scraper returned no products", store=store_name)
        return

    # Normalize raw data into standard format
    normalized = []
    for raw in raw_products:
        try:
            product = scraper.normalize_product(raw)
            if product:
                normalized.append(product)
        except Exception as e:
            logger.warning("Failed to normalize product", store=store_name, error=str(e))

    logger.info("Normalized products", store=store_name, count=len(normalized))

    # Save to database and index to Meilisearch
    await index_products(store_name, normalized)

    # Update last_scraped_at timestamp
    from sqlalchemy import select, update

    from app.database import AsyncSessionLocal
    from app.models.product import Store

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Store)
            .where(Store.name == store_name)
            .values(last_scraped_at=datetime.utcnow())
        )
        await session.commit()
