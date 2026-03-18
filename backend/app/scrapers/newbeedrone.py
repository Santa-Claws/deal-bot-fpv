"""
NewBeeDrone scraper.

NewBeeDrone (newbeedrone.com) uses the Boost PFS Filter app which exposes
a JSON API at services.mybcapps.com. We use this directly instead of
browser automation - much faster, more reliable, no bot detection issues.

API endpoint: https://services.mybcapps.com/bc-sf-filter/filter
  ?shop=newbeedrone.myshopify.com
  &page=1
  &limit=250
  &collection_scope=all

Returns JSON with: total_product, total_page, products[]
"""

import asyncio
from decimal import Decimal
from typing import Optional

import httpx
import structlog

from app.scrapers.base import BaseScraper, detect_category

logger = structlog.get_logger()


class NewBeeDroneScraper(BaseScraper):
    """
    Scraper for newbeedrone.com using their Boost PFS Filter JSON API.
    No browser needed - direct HTTP requests are faster and more reliable.
    """

    store_name = "NewBeeDrone"
    base_url = "https://newbeedrone.com"

    # Boost PFS Filter API
    API_BASE = "https://services.mybcapps.com/bc-sf-filter/filter"
    API_PARAMS = {
        "_": "pf",
        "shop": "newbeedrone.myshopify.com",
        "limit": 24,
        "sort": "created-descending",
    }

    async def _fetch_api_page(self, client: httpx.AsyncClient, page: int, collection: str = "all") -> dict:
        """Fetch one page of products from the Boost PFS API."""
        params = {
            **self.API_PARAMS,
            "page": page,
            "collection_scope": collection,
        }
        response = await client.get(self.API_BASE, params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()

    async def get_products(self) -> list[dict]:
        """
        Scrape all NewBeeDrone products via the Boost PFS JSON API.
        Uses HTTP directly - no browser automation needed.

        Note: The API returns total_page=0 even with many products, so we
        paginate until we get an empty products array.
        """
        all_products = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client:
            page_num = 1
            while True:
                try:
                    data = await self._fetch_api_page(client, page=page_num)
                    products = data.get("products", [])

                    if page_num == 1:
                        self.log.info("NewBeeDrone API", total_products=data.get("total_product"))

                    if not products:
                        break

                    parsed = self._parse_api_products(products)
                    all_products.extend(parsed)
                    self.log.debug("Fetched page", page=page_num, count=len(parsed), total=len(all_products))

                    page_num += 1
                    await asyncio.sleep(0.3)  # Polite rate limiting

                    # Safety limit
                    if page_num > 200:
                        self.log.warning("Hit page limit")
                        break

                except Exception as e:
                    self.log.warning("API page failed", page=page_num, error=str(e))
                    break

        self.log.info("API scrape complete", total=len(all_products))
        return all_products

    async def get_deals(self) -> list[dict]:
        """Scrape NewBeeDrone's sale collection via API."""
        all_deals = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            follow_redirects=True,
        ) as client:
            page_num = 1
            while True:
                try:
                    data = await self._fetch_api_page(client, page=page_num, collection="sale")
                    products = self._parse_api_products(data.get("products", []), is_sale=True)
                    if not products:
                        break
                    all_deals.extend(products)
                    if page_num >= data.get("total_page", 1):
                        break
                    page_num += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.log.warning("Sale API page failed", page=page_num, error=str(e))
                    break

        self.log.info("Sale scrape complete", total=len(all_deals))
        return all_deals

    def _parse_api_products(self, products: list[dict], is_sale: bool = False) -> list[dict]:
        """Convert API response products to our standard raw format."""
        result = []
        for p in products:
            handle = p.get("handle", "")
            if not handle:
                continue

            # Price is in dollars (e.g., 18.9 = $18.90)
            price_raw = p.get("price_min") or p.get("price_min_usd", 0)
            compare_raw = p.get("compare_at_price_min") or p.get("compare_at_price_min_usd")

            # Image URL
            images = p.get("images_info", [])
            image_url = ""
            if images:
                src = images[0].get("src", "")
                image_url = ("https:" + src) if src.startswith("//") else src

            result.append({
                "title": p.get("title", ""),
                "price": str(price_raw) if price_raw else "",
                "original_price": str(compare_raw) if compare_raw else None,
                "url": f"{self.base_url}/products/{handle}",
                "image_url": image_url,
                "in_stock": bool(p.get("available", True)),
                "is_sale": is_sale or bool(compare_raw and float(compare_raw) > float(price_raw or 0)),
                "store": self.store_name,
                "handle": handle,
            })
        return result

    def normalize_product(self, raw: dict) -> Optional[dict]:
        """Convert raw API data to our standard product format."""
        price = self.parse_price(raw.get("price", ""))
        original_price = self.parse_price(raw.get("original_price") or "")

        if not price:
            return None

        title = raw.get("title", "").strip()
        if not title:
            return None

        category = detect_category(title)
        specs = self._parse_specs_from_title(title, category)

        return {
            "external_id": raw.get("handle", raw.get("url", "").split("/products/")[-1]),
            "title": title,
            "url": raw.get("url", ""),
            "image_url": raw.get("image_url"),
            "price": price,
            "original_price": original_price,
            "in_stock": raw.get("in_stock", True),
            "category": category,
            "specs": specs,
            "is_sale": raw.get("is_sale", False),
        }

    def _parse_specs_from_title(self, title: str, category: str) -> dict:
        """Extract technical specs from product title."""
        import re
        specs = {}
        title_lower = title.lower()

        if category == "motors":
            stator_match = re.search(r'\b(\d{4}(?:\.\d)?)\b', title)
            if stator_match:
                specs["stator"] = stator_match.group(1)
            kv_match = re.search(r'(\d{3,4})\s*kv', title_lower)
            if kv_match:
                specs["kv"] = int(kv_match.group(1))
        elif category == "escs":
            amp_match = re.search(r'(\d+)\s*a\b', title_lower)
            if amp_match:
                specs["amperage"] = int(amp_match.group(1))
            specs["type"] = "4in1" if "4in1" in title_lower or "4-in-1" in title_lower else "individual"
        elif category == "frames":
            size_match = re.search(r'(\d+)\s*mm', title_lower)
            if size_match:
                specs["size_mm"] = int(size_match.group(1))
            else:
                inch_match = re.search(r'(\d+)["\']', title)
                if inch_match:
                    specs["size_inch"] = int(inch_match.group(1))

        return specs
