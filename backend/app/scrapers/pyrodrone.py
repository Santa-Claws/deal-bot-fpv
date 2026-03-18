"""
PyroDrone scraper.

PyroDrone (pyrodrone.com) is a popular FPV store specializing in
racing and freestyle components. Also Shopify-based.

Scraping strategy: similar to NewBeeDrone but with PyroDrone-specific selectors.
"""

import re

from app.scrapers.base import BaseScraper


class PyroDroneScraper(BaseScraper):
    """Scraper for pyrodrone.com."""

    store_name = "PyroDrone"
    base_url = "https://pyrodrone.com"

    CATALOG_URL = "https://pyrodrone.com/collections/all"
    SALE_URL = "https://pyrodrone.com/collections/sale"

    async def get_products(self) -> list[dict]:
        """Scrape PyroDrone catalog (paginated)."""
        all_products = []
        page_num = 1

        async with self:
            while True:
                url = f"{self.CATALOG_URL}?page={page_num}"
                self.log.info("Scraping PyroDrone page", page=page_num)

                try:
                    page = await self.fetch_page(url)
                    products = await self._extract_products(page)
                    await page.close()
                except Exception as e:
                    self.log.error("Page failed", page=page_num, error=str(e))
                    break

                if not products:
                    break

                all_products.extend(products)
                page_num += 1

                if page_num > 50:
                    break

        return all_products

    async def get_deals(self) -> list[dict]:
        """Scrape PyroDrone sale section."""
        deals = []
        page_num = 1

        async with self:
            while True:
                url = f"{self.SALE_URL}?page={page_num}"
                try:
                    page = await self.fetch_page(url)
                    products = await self._extract_products(page, is_sale=True)
                    await page.close()
                except Exception:
                    break

                if not products:
                    break

                deals.extend(products)
                page_num += 1

                if page_num > 20:
                    break

        return deals

    async def _extract_products(self, page, is_sale: bool = False) -> list[dict]:
        """Extract product data via JavaScript evaluation."""
        products_data = await page.evaluate("""
            () => {
                const products = [];
                const cards = document.querySelectorAll(
                    '.product-item, .grid-product, .product-card, [data-product-id]'
                );

                cards.forEach(card => {
                    const titleEl = card.querySelector('h3, h2, .product-title, .grid-product__title');
                    const priceEl = card.querySelector('.price, .product-price, .price__current');
                    const originalPriceEl = card.querySelector('del, s, .price__compare, .compare-price');
                    const linkEl = card.querySelector('a[href*="/products/"]');
                    const imgEl = card.querySelector('img');

                    if (titleEl && linkEl) {
                        products.push({
                            title: titleEl.textContent.trim(),
                            price: priceEl ? priceEl.textContent.trim() : '',
                            original_price: originalPriceEl ? originalPriceEl.textContent.trim() : null,
                            url: linkEl.href,
                            image_url: imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                            in_stock: !card.querySelector('.sold-out'),
                        });
                    }
                });

                return products;
            }
        """)

        for p in products_data:
            p["is_sale"] = is_sale
            p["store"] = self.store_name

        return products_data

    def normalize_product(self, raw: dict) -> dict:
        """Normalize PyroDrone product data."""
        url = raw.get("url", "")
        external_id = url.split("/products/")[-1].split("?")[0] if "/products/" in url else url

        price = self.parse_price(raw.get("price", ""))
        original_price = self.parse_price(raw.get("original_price") or "")

        if not price:
            return None

        title = raw.get("title", "").strip()
        category = self.detect_category(title)
        specs = self._parse_specs(title, category)

        return {
            "external_id": external_id,
            "title": title,
            "url": url,
            "image_url": raw.get("image_url"),
            "price": price,
            "original_price": original_price,
            "in_stock": raw.get("in_stock", True),
            "category": category,
            "specs": specs,
            "is_sale": raw.get("is_sale", False),
        }

    def _parse_specs(self, title: str, category: str) -> dict:
        """Parse specs from PyroDrone product titles."""
        specs = {}
        title_lower = title.lower()

        if category == "motors":
            stator = re.search(r'\b(\d{4}(?:\.\d)?)\b', title)
            if stator:
                specs["stator"] = stator.group(1)
            kv = re.search(r'(\d{3,4})\s*kv', title_lower)
            if kv:
                specs["kv"] = int(kv.group(1))
        elif category == "escs":
            amp = re.search(r'(\d+)\s*a\b', title_lower)
            if amp:
                specs["amperage"] = int(amp.group(1))

        return specs
