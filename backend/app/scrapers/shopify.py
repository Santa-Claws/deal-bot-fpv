"""
Shopify JSON API scraper base class.

All Shopify stores expose /products.json with full product data:
  GET /products.json?limit=250&page=N

No browser needed — pure HTTP, fast and reliable.
Returns up to 250 products per page. Pagination via ?page=N
until a page returns fewer than 250 products.

Data includes: title, handle, product_type, tags, variants (price,
compare_at_price, available), images.
"""

import asyncio
from decimal import Decimal
from typing import Optional

import httpx

from app.scrapers.base import BaseScraper, detect_category


class ShopifyScraper(BaseScraper):
    """
    Base scraper for any standard Shopify store.

    Subclasses only need to set store_name and base_url.
    Optionally override SALE_COLLECTION to scrape a sale page.
    """

    SALE_COLLECTION: Optional[str] = "sale"
    PAGE_SIZE = 250

    @property
    def _headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    async def _fetch_products_page(self, client: httpx.AsyncClient, page: int) -> list[dict]:
        """Fetch one page of products from /products.json."""
        r = await client.get(
            f"{self.base_url}/products.json",
            params={"limit": self.PAGE_SIZE, "page": page},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json().get("products", [])

    async def get_products(self) -> list[dict]:
        """Scrape all products via Shopify's /products.json endpoint."""
        all_products = []

        async with httpx.AsyncClient(headers=self._headers, follow_redirects=True) as client:
            page = 1
            while True:
                try:
                    products = await self._fetch_products_page(client, page)
                    if not products:
                        break

                    parsed = [self._parse_shopify_product(p) for p in products]
                    parsed = [p for p in parsed if p]
                    all_products.extend(parsed)

                    self.log.debug("Fetched page", page=page, count=len(parsed), total=len(all_products))

                    if len(products) < self.PAGE_SIZE:
                        break  # Last page

                    page += 1
                    await asyncio.sleep(0.2)

                    if page > 100:
                        self.log.warning("Hit page limit")
                        break

                except Exception as e:
                    self.log.warning("Page fetch failed", page=page, error=str(e))
                    break

        self.log.info("Shopify scrape complete", total=len(all_products))
        return all_products

    async def get_deals(self) -> list[dict]:
        """Scrape sale collection via /collections/{sale}/products.json."""
        if not self.SALE_COLLECTION:
            return []

        all_deals = []
        async with httpx.AsyncClient(headers=self._headers, follow_redirects=True) as client:
            page = 1
            while True:
                try:
                    r = await client.get(
                        f"{self.base_url}/collections/{self.SALE_COLLECTION}/products.json",
                        params={"limit": self.PAGE_SIZE, "page": page},
                        timeout=30.0,
                    )
                    r.raise_for_status()
                    products = r.json().get("products", [])
                    if not products:
                        break

                    parsed = [self._parse_shopify_product(p, is_sale=True) for p in products]
                    all_deals.extend([p for p in parsed if p])

                    if len(products) < self.PAGE_SIZE:
                        break
                    page += 1
                    await asyncio.sleep(0.3)

                except Exception as e:
                    self.log.warning("Sale page failed", page=page, error=str(e))
                    break

        self.log.info("Sale scrape complete", total=len(all_deals))
        return all_deals

    def _parse_shopify_product(self, p: dict, is_sale: bool = False) -> Optional[dict]:
        """Convert a Shopify product JSON object to our raw format."""
        handle = p.get("handle", "")
        title = p.get("title", "").strip()
        if not handle or not title:
            return None

        # Use the first available variant for price
        variants = p.get("variants", [])
        if not variants:
            return None

        variant = variants[0]
        price_str = variant.get("price", "")
        compare_str = variant.get("compare_at_price")

        # Image
        images = p.get("images", [])
        image_url = images[0].get("src", "") if images else ""

        in_stock = any(v.get("available", False) for v in variants)

        on_sale = False
        if compare_str:
            try:
                if float(compare_str) > float(price_str or 0):
                    on_sale = True
            except (ValueError, TypeError):
                pass

        return {
            "title": title,
            "price": price_str,
            "original_price": compare_str if on_sale else None,
            "url": f"{self.base_url}/products/{handle}",
            "image_url": image_url,
            "in_stock": in_stock,
            "is_sale": is_sale or on_sale,
            "store": self.store_name,
            "handle": handle,
            "product_type": p.get("product_type", ""),
            "tags": p.get("tags", []),
        }

    def normalize_product(self, raw: dict) -> Optional[dict]:
        """Convert raw Shopify product to standard format."""
        price = self.parse_price(raw.get("price", ""))
        original_price = self.parse_price(raw.get("original_price") or "")

        if not price:
            return None

        title = raw.get("title", "").strip()
        if not title:
            return None

        # Use product_type hint from Shopify if available, else detect from title
        product_type = raw.get("product_type", "").lower()
        category = self._map_product_type(product_type) or detect_category(title)

        specs = self._parse_specs(title, category, raw.get("tags", []))

        return {
            "external_id": raw.get("handle", ""),
            "title": title,
            "url": raw.get("url", ""),
            "image_url": raw.get("image_url") or None,
            "price": price,
            "original_price": original_price,
            "in_stock": raw.get("in_stock", True),
            "category": category,
            "specs": specs,
            "is_sale": raw.get("is_sale", False),
        }

    def _map_product_type(self, product_type: str) -> Optional[str]:
        """Map Shopify product_type string to our category names."""
        mapping = {
            "motors": "motors",
            "motor": "motors",
            "esc": "escs",
            "escs": "escs",
            "speed controller": "escs",
            "flight controller": "flight_controllers",
            "flight controllers": "flight_controllers",
            "frame": "frames",
            "frames": "frames",
            "vtx": "vtx",
            "video transmitter": "vtx",
            "camera": "cameras",
            "cameras": "cameras",
            "props": "props",
            "propellers": "props",
            "propeller": "props",
            "batteries": "batteries",
            "battery": "batteries",
            "lipo": "batteries",
            "antenna": "antennas",
            "antennas": "antennas",
            "stack": "stacks",
            "combo": "stacks",
        }
        for key, val in mapping.items():
            if key in product_type:
                return val
        return None

    def _parse_specs(self, title: str, category: str, tags: list) -> dict:
        """Extract specs from title and Shopify tags."""
        import re
        specs = {}
        title_lower = title.lower()
        tags_lower = [t.lower() for t in tags]

        if category == "motors":
            # Stator from title (e.g. 2207, 2306.5)
            m = re.search(r'\b(\d{4}(?:\.\d)?)\b', title)
            if m:
                specs["stator"] = m.group(1)
            # KV from title or tags
            kv_m = re.search(r'(\d{3,4})\s*kv', title_lower)
            if kv_m:
                specs["kv"] = int(kv_m.group(1))
            else:
                for tag in tags_lower:
                    kv_t = re.search(r'(\d{3,4})\s*kv', tag)
                    if kv_t:
                        specs["kv"] = int(kv_t.group(1))
                        break

        elif category == "escs":
            amp_m = re.search(r'(\d+)\s*a\b', title_lower)
            if amp_m:
                specs["amperage"] = int(amp_m.group(1))
            specs["type"] = "4in1" if any(x in title_lower for x in ["4in1", "4-in-1"]) else "individual"

        elif category == "frames":
            mm_m = re.search(r'(\d+)\s*mm', title_lower)
            if mm_m:
                specs["size_mm"] = int(mm_m.group(1))
            inch_m = re.search(r'(\d+(?:\.\d)?)\s*["\']?\s*(?:inch|size)', title_lower)
            if inch_m:
                specs["size_inch"] = float(inch_m.group(1))

        elif category == "props":
            prop_m = re.search(r'(\d+(?:\.\d)?)\s*["\']', title)
            if prop_m:
                specs["size_inch"] = float(prop_m.group(1))

        return specs
