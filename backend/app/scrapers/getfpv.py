"""
GetFPV scraper.

GetFPV (getfpv.com) is the largest FPV store but has stronger anti-bot
protection (Cloudflare, fingerprinting, behavioral analysis).

Anti-bot strategy:
1. Extra stealth JS injection
2. Slower request rate (2.5s between requests)
3. Random mouse movements and scroll simulation
4. Session warming (visit homepage first before product pages)
5. Rotate through realistic user agents

Note: If GetFPV adds more aggressive bot detection, we may need
to use a residential proxy or skip this store.
"""

import asyncio
import random
import re

from app.scrapers.base import BaseScraper


class GetFPVScraper(BaseScraper):
    """
    Scraper for getfpv.com with enhanced stealth.

    GetFPV uses Cloudflare and has bot detection. We use extra
    stealth measures but this may still break if they update detection.
    """

    store_name = "GetFPV"
    base_url = "https://www.getfpv.com"

    # Be extra polite to avoid rate limiting
    REQUEST_DELAY_SECONDS = 2.5

    CATALOG_URL = "https://www.getfpv.com/motors.html"
    SALE_URL = "https://www.getfpv.com/sale.html"

    # GetFPV uses Magento, not Shopify - different selectors
    PRODUCT_CARD_SELECTOR = ".product-item, .item.product, .product-card"

    async def get_products(self) -> list[dict]:
        """Scrape GetFPV catalog with stealth measures."""
        all_products = []

        # Categories to scrape (GetFPV has category-based navigation)
        categories = [
            "/motors.html",
            "/escs.html",
            "/flight-controllers.html",
            "/frames.html",
        ]

        async with self:
            # Warm up session by visiting homepage first
            await self._warm_session()

            for category_path in categories:
                url = f"{self.base_url}{category_path}"
                self.log.info("Scraping GetFPV category", url=url)

                page_num = 1
                while True:
                    page_url = f"{url}?p={page_num}" if page_num > 1 else url

                    try:
                        page = await self.fetch_page(page_url, wait_for=self.PRODUCT_CARD_SELECTOR)
                        await self._simulate_human_behavior(page)
                        products = await self._extract_products(page)
                        await page.close()
                    except Exception as e:
                        self.log.warning("GetFPV page failed", url=page_url, error=str(e))
                        break

                    if not products:
                        break

                    all_products.extend(products)
                    page_num += 1

                    if page_num > 20:
                        break

                    # Extra delay between category pages
                    await asyncio.sleep(random.uniform(1.5, 3.0))

        return all_products

    async def get_deals(self) -> list[dict]:
        """Scrape GetFPV sale page."""
        deals = []

        async with self:
            await self._warm_session()

            page_num = 1
            while True:
                url = f"{self.SALE_URL}?p={page_num}" if page_num > 1 else self.SALE_URL

                try:
                    page = await self.fetch_page(url)
                    await self._simulate_human_behavior(page)
                    products = await self._extract_products(page, is_sale=True)
                    await page.close()
                except Exception:
                    break

                if not products:
                    break

                deals.extend(products)
                page_num += 1

                if page_num > 10:
                    break

        return deals

    async def _warm_session(self):
        """Visit the homepage to establish a legitimate-looking session."""
        try:
            page = await self.fetch_page(self.base_url)
            await self._simulate_human_behavior(page)
            await page.close()
            self.log.info("Session warmed up")
        except Exception as e:
            self.log.warning("Session warm-up failed", error=str(e))

    async def _simulate_human_behavior(self, page):
        """
        Simulate human-like browsing to avoid bot detection.

        Real users scroll, move their mouse, and take time to read.
        Bot detection systems look for suspiciously fast, robotic behavior.
        """
        try:
            # Random scroll
            scroll_amount = random.randint(300, 800)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Move mouse to random position
            await page.mouse.move(
                random.randint(100, 1200),
                random.randint(100, 700)
            )
        except Exception:
            pass  # Non-critical, don't fail scraping if this breaks

    async def _extract_products(self, page, is_sale: bool = False) -> list[dict]:
        """Extract products from GetFPV's Magento-based layout."""
        products_data = await page.evaluate("""
            () => {
                const products = [];

                // GetFPV/Magento selectors
                const cards = document.querySelectorAll(
                    '.product-item, .item.product, .product-card'
                );

                cards.forEach(card => {
                    const titleEl = card.querySelector(
                        '.product-item-name, .product-name, h2.product-title'
                    );
                    const priceEl = card.querySelector(
                        '.price-box .price, .special-price .price, .regular-price .price'
                    );
                    const originalPriceEl = card.querySelector(
                        '.old-price .price, .price-box .old-price'
                    );
                    const linkEl = card.querySelector('a.product-item-link, a.product-link');
                    const imgEl = card.querySelector('img.product-image-photo, img');

                    if (titleEl && linkEl) {
                        products.push({
                            title: titleEl.textContent.trim(),
                            price: priceEl ? priceEl.textContent.trim() : '',
                            original_price: originalPriceEl ? originalPriceEl.textContent.trim() : null,
                            url: linkEl.href,
                            image_url: imgEl ? (imgEl.src || imgEl.dataset.src || '') : '',
                            in_stock: !card.querySelector('.out-of-stock, .unavailable'),
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
        # GetFPV URLs: /product-name.html - extract as external_id
        external_id = url.split("/")[-1].replace(".html", "") if url else url

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
