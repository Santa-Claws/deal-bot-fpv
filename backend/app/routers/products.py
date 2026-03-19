"""
Product search and detail API endpoints.

GET /api/products/search  - Search products with optional AI query parsing
GET /api/products/{id}    - Get a single product's details
GET /api/products/        - List products with filters
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_dependency
from app.models.product import Product, Store
from app.services.ai import ai_service
from app.services.search import search_service

logger = structlog.get_logger()
router = APIRouter(prefix="/products", tags=["products"])


# ── Response models ────────────────────────────────────
# Pydantic models define the shape of API responses
# FastAPI uses these to validate and serialize responses

class ProductSummary(BaseModel):
    """Compact product info for search results."""
    id: str
    store: str
    title: str
    url: str
    image_url: Optional[str]
    price: float
    original_price: Optional[float]
    category: Optional[str]
    in_stock: bool
    is_deal: bool
    discount_percent: Optional[float] = None

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Search endpoint response."""
    hits: list[ProductSummary]
    total: int
    query: str
    parsed_filters: dict  # What the AI understood from your query
    processing_time_ms: int


# ── Endpoints ──────────────────────────────────────────

@router.get("/search", response_model=SearchResponse)
async def search_products(
    q: str = Query(default="", description="Search query (natural language supported)"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    store: Optional[str] = Query(default=None, description="Filter by store name"),
    min_price: Optional[float] = Query(default=None, description="Minimum price"),
    max_price: Optional[float] = Query(default=None, description="Maximum price"),
    in_stock: Optional[bool] = Query(default=None, description="Only show in-stock items"),
    deals_only: Optional[bool] = Query(default=None, description="Only show deals"),
    sort: Optional[str] = Query(default="price:asc", description="Sort: price:asc, price:desc"),
    page: int = Query(default=1, ge=1, description="Page number"),
    per_page: int = Query(default=24, ge=1, le=100, description="Results per page"),
):
    """
    Search for FPV products.

    Supports natural language queries:
    - "2207 motors under 30 dollars"
    - "cheap freestyle ESC 4in1"
    - "getfpv sale motors"

    The AI parses your query to extract:
    - Category (motors, ESCs, frames, etc.)
    - Price range
    - Store preference
    - Technical specs (stator size, KV rating, etc.)

    Results are returned from Meilisearch (typo-tolerant, fast).
    """
    parsed_filters = {}

    # Use AI to parse natural language query if provided
    if q:
        try:
            parsed_filters = await ai_service.parse_search_query(q)
            logger.debug("AI parsed query", query=q, parsed=parsed_filters)
        except Exception as e:
            logger.warning("AI query parsing failed", error=str(e))

    # Build Meilisearch filter expressions
    # Explicit URL params override AI-parsed values
    filters = []

    effective_category = category or parsed_filters.get("category")
    # "store" is not a real product category — AI sometimes sets it when the query
    # is a brand/manufacturer name (e.g. "hdzero", "geprc"). Skip it.
    if effective_category and effective_category != "store":
        filters.append(f'category = "{effective_category}"')

    # Only apply store as a hard filter when it comes from an explicit URL param
    # (sidebar dropdown). AI-parsed store names are often brand/manufacturer names
    # (e.g. "hdzero" = brand sold by many stores, not just the HDZero store),
    # so we let the search query find them by title instead.
    if store:
        filters.append(f'store = "{store}"')

    effective_max_price = max_price or parsed_filters.get("max_price")
    if effective_max_price:
        filters.append(f"price <= {effective_max_price}")

    effective_min_price = min_price or parsed_filters.get("min_price")
    if effective_min_price:
        filters.append(f"price >= {effective_min_price}")

    if in_stock is True or parsed_filters.get("in_stock_only"):
        filters.append("in_stock = true")

    if deals_only is True or parsed_filters.get("deals_only"):
        filters.append("is_deal = true")

    # Always use the original query so brand/manufacturer names in the query
    # match product titles (e.g. "hdzero" finds products with HDZero in the name)
    effective_query = q

    # Run the search
    try:
        results = await search_service.search(
            query=effective_query,
            filters=filters if filters else None,
            sort=[sort] if sort else None,
            limit=per_page,
            offset=(page - 1) * per_page,
        )
    except Exception as e:
        logger.error("Search failed", error=str(e))
        raise HTTPException(status_code=503, detail="Search service unavailable")

    # Map search hits to response model
    hits = []
    for hit in results.get("hits", []):
        discount_pct = None
        if hit.get("original_price") and hit.get("price"):
            if hit["original_price"] > hit["price"]:
                discount_pct = ((hit["original_price"] - hit["price"]) / hit["original_price"]) * 100

        hits.append(ProductSummary(
            id=hit["id"],
            store=hit["store"],
            title=hit["title"],
            url=hit["url"],
            image_url=hit.get("image_url"),
            price=hit["price"],
            original_price=hit.get("original_price"),
            category=hit.get("category"),
            in_stock=hit.get("in_stock", True),
            is_deal=hit.get("is_deal", False),
            discount_percent=discount_pct,
        ))

    return SearchResponse(
        hits=hits,
        total=results.get("estimatedTotalHits", results.get("totalHits", len(hits))),
        query=q,
        parsed_filters=parsed_filters,
        processing_time_ms=results.get("processingTimeMs", 0),
    )


@router.get("/{product_id}")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db_dependency),
):
    """
    Get a single product by database ID.

    Returns full product details including:
    - All metadata
    - Current price from latest price history
    - Store information
    """
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.store),
            selectinload(Product.price_history),
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Get current price from latest history entry
    current_price = None
    original_price = None
    if product.price_history:
        latest = product.price_history[-1]
        current_price = float(latest.price)
        original_price = float(latest.original_price) if latest.original_price else None

    return {
        "id": product.id,
        "store": product.store.name,
        "external_id": product.external_id,
        "title": product.title,
        "url": product.url,
        "image_url": product.image_url,
        "category": product.category,
        "specs": product.specs,
        "current_price": current_price,
        "original_price": original_price,
        "in_stock": product.price_history[-1].in_stock if product.price_history else None,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


@router.post("/ai/parse-query")
async def parse_query(query: str):
    """
    Parse a natural language search query using AI.

    Useful for debugging AI query understanding.

    Example:
        POST /api/products/ai/parse-query?query=cheap 2207 motors
        →
        {
            "category": "motors",
            "max_price": 30,
            "specs": {"stator": "2207"}
        }
    """
    try:
        result = await ai_service.parse_search_query(query)
        return {"query": query, "parsed": result}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")
