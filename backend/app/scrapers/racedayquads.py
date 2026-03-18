"""
RaceDayQuads scraper.

RaceDayQuads (racedayquads.com) is a popular source for racing components.
Also Shopify-based with a sale section.
"""

import re

from app.scrapers.base import BaseScraper


class RaceDayQuadsScraper(BaseScraper):
    """Scraper for racedayquads.com."""

    store_name = "RaceDayQuads"
    base_url = "https://racedayquads.com"

    CATALOG_URL = "https://racedayquads.com/collections/all"
    SALE_URL = "https://racedayquads.com/collections/sale"

    async def get_products(self) -> list[dict]:
        all_products = []
        page_num = 1

        async with self:
            while True:
                url = f"{self.CATALOG_URL}?page={page_num}"
                self.log.info("Scraping RDQ page", page=page_num)

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
        products_data = await page.evaluate("""
            () => {
                const products = [];
                const cards = document.querySelectorAll(
                    '.product-item, .grid-product, [data-product-id], .product-card'
                );

                cards.forEach(card => {
                    const titleEl = card.querySelector('h3, h2, .product-title, .product-item__title');
                    const priceEl = card.querySelector('.price__current, .price, .product-price');
                    const originalPriceEl = card.querySelector('del, .price__compare, s');
                    const linkEl = card.querySelector('a[href*="/products/"]');
                    const imgEl = card.querySelector('img');

                    if (titleEl && linkEl) {
                        products.push({
                            title: titleEl.textContent.trim(),
                            price: priceEl ? priceEl.textContent.trim() : '',
                            original_price: originalPriceEl ? originalPriceEl.textContent.trim() : null,
                            url: linkEl.href,
                            image_url: imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                            in_stock: !card.querySelector('.sold-out, [aria-label*="sold"]'),
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
        url = raw.get("url", "")
        external_id = url.split("/products/")[-1].split("?")[0] if "/products/" in url else url

        price = self.parse_price(raw.get("price", ""))
        original_price = self.parse_price(raw.get("original_price") or "")

        if not price:
            return None

        title = raw.get("title", "").strip()
        category = self.detect_category(title)

        return {
            "external_id": external_id,
            "title": title,
            "url": url,
            "image_url": raw.get("image_url"),
            "price": price,
            "original_price": original_price,
            "in_stock": raw.get("in_stock", True),
            "category": category,
            "specs": {},
            "is_sale": raw.get("is_sale", False),
        }
