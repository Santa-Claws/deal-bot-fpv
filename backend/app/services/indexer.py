"""
Product indexer: saves scraped products to PostgreSQL and Meilisearch.

Called by the Celery scraper tasks after scraping completes.

Flow:
1. Upsert products to PostgreSQL (update if exists, insert if new)
2. Append price_history rows for each product
3. Detect deals (explicit sale + price drops)
4. Index products to Meilisearch for search
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.database import AsyncSessionLocal
from app.models.product import Deal, PriceHistory, Product, Store
from app.services.search import search_service

logger = structlog.get_logger()


async def index_products(store_name: str, products: list[dict]):
    """
    Save scraped products to DB and search index.

    Args:
        store_name: Name matching Store.name in the database
        products: List of normalized product dicts from the scraper
    """
    if not products:
        return

    async with AsyncSessionLocal() as session:
        # Get the store ID
        result = await session.execute(
            select(Store).where(Store.name == store_name)
        )
        store = result.scalar_one_or_none()
        if not store:
            logger.error("Store not found", store=store_name)
            return

        saved_count = 0
        updated_count = 0
        deal_count = 0

        for product_data in products:
            try:
                # Check if this product already exists (by external_id + store)
                result = await session.execute(
                    select(Product).where(
                        Product.store_id == store.id,
                        Product.external_id == product_data["external_id"],
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing product metadata
                    existing.title = product_data["title"]
                    existing.image_url = product_data.get("image_url")
                    existing.category = product_data.get("category")
                    existing.specs = product_data.get("specs", {})
                    existing.updated_at = datetime.utcnow()
                    product = existing
                    updated_count += 1
                else:
                    # Create new product
                    product = Product(
                        store_id=store.id,
                        external_id=product_data["external_id"],
                        title=product_data["title"],
                        url=product_data["url"],
                        image_url=product_data.get("image_url"),
                        category=product_data.get("category"),
                        specs=product_data.get("specs", {}),
                    )
                    session.add(product)
                    await session.flush()  # Get the product.id
                    saved_count += 1

                # Always record price history (even if price hasn't changed)
                price_entry = PriceHistory(
                    product_id=product.id,
                    price=product_data["price"],
                    original_price=product_data.get("original_price"),
                    in_stock=product_data.get("in_stock", True),
                )
                session.add(price_entry)

                # Detect and record deals
                if await _is_deal(session, product, product_data):
                    deal = await _create_deal(session, product, product_data)
                    if deal:
                        deal_count += 1

                        # Send notification for good deals
                        await _maybe_notify(product, deal, product_data)

            except Exception as e:
                logger.warning(
                    "Failed to save product",
                    title=product_data.get("title", "unknown"),
                    error=str(e),
                )
                continue

        await session.commit()
        logger.info(
            "Indexing complete",
            store=store_name,
            saved=saved_count,
            updated=updated_count,
            deals=deal_count,
        )

    # Index to Meilisearch for search
    await _index_to_search(store_name, products)


async def _is_deal(session, product: Product, product_data: dict) -> bool:
    """
    Determine if this product is currently a deal.

    Criteria:
    1. Explicitly on sale (store marked it as sale)
    2. Price dropped 10%+ compared to 30-day average
    3. This is the lowest price we've ever seen
    """
    # Explicit sale from the scraper
    if product_data.get("is_sale") and product_data.get("original_price"):
        return True

    # Check price history for drops
    price = product_data.get("price")
    if not price:
        return False

    # Get 30-day price history
    from sqlalchemy import func

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    result = await session.execute(
        select(func.avg(PriceHistory.price)).where(
            PriceHistory.product_id == product.id,
            PriceHistory.scraped_at >= thirty_days_ago,
        )
    )
    avg_price = result.scalar()

    if avg_price and price < avg_price * Decimal("0.90"):
        return True  # 10%+ below 30-day average

    return False


async def _create_deal(session, product: Product, product_data: dict) -> Optional[Deal]:
    """Create a Deal record and score it with AI."""
    from app.services.ai import ai_service

    price = float(product_data["price"])
    original_price = float(product_data["original_price"]) if product_data.get("original_price") else None
    discount_pct = None

    if original_price:
        discount_pct = ((original_price - price) / original_price) * 100

    deal_type = "sale" if product_data.get("is_sale") else "price_drop"

    # Score with AI
    try:
        score_result = await ai_service.score_deal(
            product_title=product_data["title"],
            current_price=price,
            original_price=original_price,
            avg_price_30d=None,  # TODO: pass actual 30d avg
            category=product_data.get("category", "accessories"),
        )
        deal_score = score_result.get("score", 5.0)
    except Exception:
        deal_score = 5.0  # Default middle score if AI fails

    # Only save deals with score >= 4 to avoid noise
    if deal_score < 4.0:
        return None

    deal = Deal(
        product_id=product.id,
        deal_type=deal_type,
        discount_percent=discount_pct,
        deal_score=deal_score,
    )
    session.add(deal)
    return deal


async def _maybe_notify(product: Product, deal: Deal, product_data: dict):
    """Send Discord notification for high-score deals."""
    # Only notify for deals scoring 7+
    if deal.deal_score and deal.deal_score >= 7.0:
        try:
            from app.services.notifications import notification_service
            await notification_service.send_deal_alert(
                title=product_data["title"],
                price=float(product_data["price"]),
                original_price=float(product_data["original_price"]) if product_data.get("original_price") else None,
                url=product_data["url"],
                deal_score=deal.deal_score,
                category=product_data.get("category", ""),
            )
        except Exception as e:
            logger.warning("Notification failed", error=str(e))


async def _index_to_search(store_name: str, products: list[dict]):
    """Index products to Meilisearch for fast search."""
    try:
        # Convert products to search documents
        docs = []
        for p in products:
            if not p.get("price"):
                continue
            docs.append({
                "id": f"{store_name}-{p['external_id']}",
                "store": store_name,
                "title": p["title"],
                "url": p["url"],
                "image_url": p.get("image_url", ""),
                "price": float(p["price"]),
                "original_price": float(p["original_price"]) if p.get("original_price") else None,
                "category": p.get("category", "accessories"),
                "specs": p.get("specs", {}),
                "in_stock": p.get("in_stock", True),
                "is_deal": p.get("is_sale", False),
            })

        if docs:
            await search_service.add_products(docs)
            logger.info("Indexed to Meilisearch", count=len(docs), store=store_name)
    except Exception as e:
        logger.warning("Meilisearch indexing failed", error=str(e))
