"""
Meilisearch integration for product search.

Meilisearch is a typo-tolerant search engine. Key advantages for FPV:
- "2207 motor" finds "2207 motors" and "2207kv motor"
- Typos like "escs" still finds "esc"
- Filters work fast (by category, price, store)

Meilisearch docs: https://docs.meilisearch.com/

Index name: "products"
"""

import asyncio
from typing import Optional

import meilisearch
import structlog

from app.config import settings

logger = structlog.get_logger()

# ── Meilisearch index configuration ───────────────────

INDEX_NAME = "products"

# Attributes that can be filtered/sorted in search queries
FILTERABLE_ATTRIBUTES = [
    "category",
    "store",
    "price",
    "in_stock",
    "is_deal",
]

# Attributes that can be sorted
SORTABLE_ATTRIBUTES = [
    "price",
]

# Attributes used to rank search results (more important = higher weight)
RANKING_RULES = [
    "words",         # Number of matching words
    "typo",          # Fewer typos = higher rank
    "proximity",     # How close the words are
    "attribute",     # Matches in more important attributes rank higher
    "sort",          # Sort criteria
    "exactness",     # Exact matches beat partial matches
    "price:asc",     # Default to cheaper first (good for deal hunting)
]

# Which attributes are searchable (in priority order)
SEARCHABLE_ATTRIBUTES = [
    "title",         # Product name - most important
    "category",      # Category match
    "store",         # Store name
    "specs",         # Specs dict (stator size, kv, etc.)
]

# Words to ignore in search queries (price words, common English)
STOP_WORDS = [
    "under", "over", "around", "about", "cheap", "cheapest", "best",
    "good", "great", "deals", "sale", "discount", "a", "an", "the",
    "for", "in", "on", "at", "with", "from", "dollars", "dollar",
    "bucks", "buck", "usd",
]


class SearchService:
    """Wraps the Meilisearch client with async support."""

    def __init__(self):
        # meilisearch-python is synchronous, so we run it in a thread pool
        self._client = meilisearch.Client(
            settings.meili_host,
            settings.meili_master_key,
        )
        self._index = self._client.index(INDEX_NAME)

    async def setup_index(self):
        """
        Create and configure the Meilisearch index.

        Called at app startup. Safe to run multiple times (idempotent).
        """
        loop = asyncio.get_event_loop()

        # Create index if it doesn't exist
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.create_index(INDEX_NAME, {"primaryKey": "id"}),
            )
            logger.info("Meilisearch index created")
        except Exception:
            pass  # Index already exists

        # Update settings
        await loop.run_in_executor(
            None,
            lambda: self._index.update_filterable_attributes(FILTERABLE_ATTRIBUTES),
        )
        await loop.run_in_executor(
            None,
            lambda: self._index.update_sortable_attributes(SORTABLE_ATTRIBUTES),
        )
        await loop.run_in_executor(
            None,
            lambda: self._index.update_ranking_rules(RANKING_RULES),
        )
        await loop.run_in_executor(
            None,
            lambda: self._index.update_searchable_attributes(SEARCHABLE_ATTRIBUTES),
        )
        await loop.run_in_executor(
            None,
            lambda: self._index.update_stop_words(STOP_WORDS),
        )
        logger.info("Meilisearch index configured")

    async def add_products(self, products: list[dict]):
        """
        Add or update products in the search index.

        Meilisearch uses "upsert" semantics - if a document with the same
        primary key exists, it gets updated. Otherwise it's created.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._index.add_documents(products),
        )

    async def search(
        self,
        query: str,
        filters: Optional[list[str]] = None,
        sort: Optional[list[str]] = None,
        limit: int = 24,
        offset: int = 0,
    ) -> dict:
        """
        Search for products.

        Args:
            query: Natural language search query
            filters: Meilisearch filter expressions, e.g.:
                     ["category = motors", "price < 50", "in_stock = true"]
            sort: Sort fields, e.g.: ["price:asc"]
            limit: Number of results per page
            offset: Pagination offset

        Returns:
            Meilisearch search response dict with:
            - hits: list of matching products
            - totalHits: total number of matches
            - processingTimeMs: how long the search took
        """
        loop = asyncio.get_event_loop()

        search_params = {
            "limit": limit,
            "offset": offset,
            "attributesToHighlight": ["title"],  # Highlight matching terms
        }

        if filters:
            search_params["filter"] = " AND ".join(filters)

        if sort:
            search_params["sort"] = sort

        result = await loop.run_in_executor(
            None,
            lambda: self._index.search(query, search_params),
        )

        return result

    async def delete_product(self, product_id: str):
        """Remove a product from the search index."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._index.delete_document(product_id),
        )

    async def get_stats(self) -> dict:
        """Get index statistics (document count, etc.)."""
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(
            None,
            lambda: self._index.get_stats(),
        )
        return stats


# Global instance
search_service = SearchService()


async def setup_index():
    """Called at startup to configure the Meilisearch index."""
    await search_service.setup_index()
