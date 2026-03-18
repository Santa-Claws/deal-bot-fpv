"""
Price history API endpoints.

GET /api/products/{id}/history - Full price history for a product
                                  Used to power the price chart on product pages
"""

from typing import Optional
from datetime import datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_dependency
from app.models.product import PriceHistory, Product

logger = structlog.get_logger()
router = APIRouter(tags=["prices"])


@router.get("/products/{product_id}/history")
async def get_price_history(
    product_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    db: AsyncSession = Depends(get_db_dependency),
):
    """
    Get price history for a product.

    Returns a list of {price, scraped_at} data points for charting.
    Default: last 30 days.

    The frontend uses this to render a Chart.js price history graph
    showing how the price has changed over time.
    """
    # Verify product exists
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get price history within the requested date range
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(PriceHistory)
        .where(
            PriceHistory.product_id == product_id,
            PriceHistory.scraped_at >= cutoff,
        )
        .order_by(PriceHistory.scraped_at)
    )
    history = result.scalars().all()

    # Format for Chart.js
    data_points = [
        {
            "price": float(entry.price),
            "original_price": float(entry.original_price) if entry.original_price else None,
            "in_stock": entry.in_stock,
            "date": entry.scraped_at.isoformat(),
        }
        for entry in history
    ]

    # Calculate stats
    prices = [p["price"] for p in data_points]
    stats = {}
    if prices:
        stats = {
            "current": prices[-1],
            "min": min(prices),
            "max": max(prices),
            "avg": round(sum(prices) / len(prices), 2),
            "all_time_low": prices[-1] == min(prices),
        }

    return {
        "product_id": product_id,
        "product_title": product.title,
        "days": days,
        "data_points": data_points,
        "stats": stats,
    }
