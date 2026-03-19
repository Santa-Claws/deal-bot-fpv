"""
PyroDrone scraper.

Uses Shopify's native /products.json API — 5000+ products, no browser needed.
"""

from app.scrapers.shopify import ShopifyScraper


class PyroDroneScraper(ShopifyScraper):
    store_name = "PyroDrone"
    base_url = "https://pyrodrone.com"
    SALE_COLLECTION = "sale"
