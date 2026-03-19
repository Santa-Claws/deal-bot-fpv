"""
RaceDayQuads scraper.

Uses Shopify's native /products.json API — 4600+ products, no browser needed.
"""

from app.scrapers.shopify import ShopifyScraper


class RaceDayQuadsScraper(ShopifyScraper):
    store_name = "RaceDayQuads"
    base_url = "https://www.racedayquads.com"
    SALE_COLLECTION = "sale"
