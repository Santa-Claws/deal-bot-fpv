# Adding a New Store

This guide walks through adding a new FPV store scraper.

## 1. Create the scraper file

Create `backend/app/scrapers/yourstore.py`:

```python
from app.scrapers.base import BaseScraper

class YourStoreScraper(BaseScraper):
    store_name = "YourStore"
    base_url = "https://yourstore.com"

    async def get_products(self) -> list[dict]:
        """Scrape the main catalog."""
        all_products = []
        async with self:
            page = await self.fetch_page(f"{self.base_url}/products")
            products = await self._extract_products(page)
            await page.close()
        return products

    async def get_deals(self) -> list[dict]:
        """Scrape the sale section."""
        async with self:
            page = await self.fetch_page(f"{self.base_url}/sale")
            products = await self._extract_products(page, is_sale=True)
            await page.close()
        return products

    async def _extract_products(self, page, is_sale=False) -> list[dict]:
        """Extract products using JavaScript evaluation."""
        return await page.evaluate("""
            () => {
                const products = [];
                document.querySelectorAll('.product').forEach(card => {
                    products.push({
                        title: card.querySelector('h3')?.textContent?.trim(),
                        price: card.querySelector('.price')?.textContent?.trim(),
                        url: card.querySelector('a')?.href,
                        image_url: card.querySelector('img')?.src,
                        in_stock: true,
                    });
                });
                return products;
            }
        """)

    def normalize_product(self, raw: dict) -> dict:
        price = self.parse_price(raw.get("price", ""))
        if not price:
            return None
        return {
            "external_id": raw["url"].split("/")[-1],
            "title": raw["title"],
            "url": raw["url"],
            "image_url": raw.get("image_url"),
            "price": price,
            "original_price": None,
            "in_stock": raw.get("in_stock", True),
            "category": self.detect_category(raw["title"]),
            "specs": {},
            "is_sale": raw.get("is_sale", False),
        }
```

## 2. Register in runner.py

In `backend/app/scrapers/runner.py`, add to the `SCRAPERS` dict:

```python
from app.scrapers.yourstore import YourStoreScraper

SCRAPERS = {
    "NewBeeDrone": NewBeeDroneScraper,
    "YourStore": YourStoreScraper,  # Add this
    ...
}
```

## 3. Add to the stores seed in main.py

In `backend/app/main.py`, add to the `stores` list in `seed_stores()`:

```python
stores = [
    ...
    {"name": "YourStore", "base_url": "https://yourstore.com", "scrape_interval_hours": 6},
]
```

## 4. Test it

```bash
# Restart the backend to pick up changes
docker compose restart backend celery-worker

# Run the scraper manually
docker exec fpv-celery-worker celery -A app.scrapers.runner call \
  app.scrapers.runner.scrape_store --args '["YourStore"]'

# Check the logs
docker compose logs celery-worker -f
```

## Tips

### Finding CSS selectors

1. Open the store in Chrome
2. Right-click a product card → Inspect
3. Look for patterns like `class="product-card"` or `data-product-id`
4. Test in the browser console: `document.querySelectorAll('.product-card').length`

### Debugging selectors

Set `headless=False` in `base.py` to watch the browser:
```python
self._browser = await self._playwright.chromium.launch(headless=False)
```

### Handling pagination

```python
page_num = 1
while True:
    url = f"{self.CATALOG_URL}?page={page_num}"
    page = await self.fetch_page(url)
    products = await self._extract_products(page)
    if not products:
        break
    all_products.extend(products)
    page_num += 1
    if page_num > 50:  # Safety limit
        break
```

### Handling anti-bot protection

For sites with Cloudflare or other bot detection:
1. Increase `REQUEST_DELAY_SECONDS` to 3+ seconds
2. Use `_simulate_human_behavior()` after each page load
3. Warm up the session by visiting the homepage first
4. See `getfpv.py` for a full example
