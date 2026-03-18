"""
Deal feed API endpoints.

GET /api/deals         - Paginated feed of current deals
POST /api/ai/score-deal - Score a deal with AI
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_dependency
from app.models.product import Deal, PriceHistory, Product, Store

logger = structlog.get_logger()
router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/")
async def list_deals(
    category: Optional[str] = Query(default=None, description="Filter by product category"),
    store: Optional[str] = Query(default=None, description="Filter by store"),
    min_score: Optional[float] = Query(default=4.0, description="Minimum deal score (0-10)"),
    deal_type: Optional[str] = Query(default=None, description="Deal type: sale, price_drop, historic_low"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db_dependency),
):
    """
    Get the deal feed.

    Returns deals sorted by deal_score descending (best deals first).
    Each deal includes the product title, current price, discount, and
    an AI-generated quality score.
    """
    # Build query with joins to get product and store info
    query = (
        select(Deal)
        .join(Product, Deal.product_id == Product.id)
        .join(Store, Product.store_id == Store.id)
        .options(
            selectinload(Deal.product).selectinload(Product.store),
            selectinload(Deal.product).selectinload(Product.price_history),
        )
        .order_by(desc(Deal.deal_score), desc(Deal.detected_at))
    )

    # Apply filters
    if min_score is not None:
        query = query.where(Deal.deal_score >= min_score)

    if deal_type:
        query = query.where(Deal.deal_type == deal_type)

    if category:
        query = query.where(Product.category == category)

    if store:
        query = query.where(Store.name == store)

    # Pagination
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    deals = result.scalars().all()

    return {
        "deals": [_format_deal(deal) for deal in deals],
        "page": page,
        "per_page": per_page,
    }


def _format_deal(deal: Deal) -> dict:
    """Format a Deal ORM object for the API response."""
    product = deal.product
    store = product.store

    # Get current price from latest price history
    current_price = None
    original_price = None
    if product.price_history:
        latest = product.price_history[-1]
        current_price = float(latest.price)
        original_price = float(latest.original_price) if latest.original_price else None

    return {
        "id": deal.id,
        "deal_type": deal.deal_type,
        "deal_score": deal.deal_score,
        "discount_percent": deal.discount_percent,
        "detected_at": deal.detected_at.isoformat(),
        "product": {
            "id": product.id,
            "title": product.title,
            "url": product.url,
            "image_url": product.image_url,
            "category": product.category,
            "store": store.name,
            "current_price": current_price,
            "original_price": original_price,
        },
    }


@router.post("/ai/score-deal")
async def score_deal_endpoint(
    title: str,
    price: float,
    original_price: Optional[float] = None,
    category: str = "accessories",
):
    """
    Score a deal using AI.

    Useful for testing the AI scoring or manually scoring a deal
    you found outside the system.

    Returns a score 0-10 with reasoning.
    """
    from app.services.ai import ai_service

    try:
        result = await ai_service.score_deal(
            product_title=title,
            current_price=price,
            original_price=original_price,
            avg_price_30d=None,
            category=category,
        )
        return result
    except Exception as e:
        return {"score": 0, "reasoning": f"AI scoring failed: {str(e)}", "recommendation": "unknown"}
