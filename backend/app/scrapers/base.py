"""
Base scraper class for all FPV stores.

Every store-specific scraper inherits from BaseScraper and implements:
    - get_products()  : scrape the main catalog
    - get_deals()     : scrape sale/clearance pages specifically

Features built into the base class:
    - Playwright browser automation (handles JS-rendered sites)
    - Automatic retry with exponential backoff (tenacity)
    - Rate limiting (don't hammer sites)
    - User agent spoofing (look like a real browser)
    - Stealth mode (reduce bot detection)
"""

import asyncio
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation
from typing import Optional

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = structlog.get_logger()


class ScraperError(Exception):
    """Raised when a scraper encounters an unrecoverable error."""
    pass


def detect_category(title: str) -> str:
    """
    Module-level category detector usable without a scraper instance.

    Exported so the AI service can use it without importing a full scraper.
    Returns one of: motors, escs, flight_controllers, frames, stacks,
                    vtx, cameras, props, antennas, batteries, accessories
    """
    title_lower = title.lower()
    if any(kw in title_lower for kw in ["motor", "2207", "2306", "2306.5", "1404", "1507"]):
        return "motors"
    elif any(kw in title_lower for kw in ["esc", "4-in-1", "4in1", "blheli"]):
        return "escs"
    elif any(kw in title_lower for kw in ["flight controller", "fc ", " fc", "f4", "f7", "h7", "f405", "f722"]):
        return "flight_controllers"
    elif any(kw in title_lower for kw in ["frame", "freestyle", "racing frame", "x frame"]):
        return "frames"
    elif any(kw in title_lower for kw in ["vtx", "video transmitter", "hdzero", "avatar", "o3", "vista"]):
        return "vtx"
    elif any(kw in title_lower for kw in ["camera", "cam ", "caddx", "runcam", "foxeer"]):
        return "cameras"
    elif any(kw in title_lower for kw in ["prop", "propeller", "blade", "hq ", " hq"]):
        return "props"
    elif any(kw in title_lower for kw in ["antenna", "lollipop", "pagoda", "dipole"]):
        return "antennas"
    elif any(kw in title_lower for kw in ["battery", "lipo", "lihv", "4s", "6s", "mah"]):
        return "batteries"
    elif any(kw in title_lower for kw in ["stack", "combo"]):
        return "stacks"
    else:
        return "accessories"


class BaseScraper(ABC):
    """
    Base class for all FPV store scrapers.

    Subclasses only need to implement:
        - get_products() → list of raw product dicts
        - get_deals()    → list of raw product dicts from sale pages
        - normalize_product() → convert raw dict to a standard format

    The base class handles all browser setup, retry logic, and rate limiting.
    """

    # Subclasses set these
    store_name: str = ""
    base_url: str = ""

    # How long to wait between page loads (be polite to servers)
    REQUEST_DELAY_SECONDS: float = 1.5

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.log = structlog.get_logger(scraper=self.store_name)

    async def __aenter__(self):
        """Start the browser when used as an async context manager."""
        await self._start_browser()
        return self

    async def __aexit__(self, *args):
        """Close the browser when done."""
        await self._stop_browser()

    async def _start_browser(self):
        """
        Launch a Chromium browser with stealth settings.

        We use Chromium (not Firefox/WebKit) because most anti-bot systems
        are tuned for Chromium fingerprints and stealth plugins target it.
        """
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,  # Set to False to watch the browser during debugging
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",  # Hide automation
            ],
        )
        self._context = await self._browser.new_context(
            user_agent=settings.user_agent,
            viewport={"width": 1920, "height": 1080},
            # Pretend to be a real user
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Inject stealth JavaScript to hide Playwright fingerprints
        await self._context.add_init_script("""
            // Hide webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Override plugins length (real browsers have plugins)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)

        self.log.info("Browser started")

    async def _stop_browser(self):
        """Clean up browser resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.log.info("Browser stopped")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def fetch_page(self, url: str, wait_for: Optional[str] = None) -> Page:
        """
        Navigate to a URL and return the Playwright Page object.

        Args:
            url: The URL to visit
            wait_for: CSS selector to wait for before returning
                      (useful for JS-rendered pages that load asynchronously)

        Returns:
            Playwright Page object with the loaded page

        The @retry decorator automatically retries up to 3 times with
        exponential backoff if the page fails to load.
        """
        page = await self._context.new_page()

        try:
            # Navigate to the URL - use domcontentloaded (faster than networkidle)
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Wait for a specific element if requested - non-fatal if not found
            if wait_for:
                try:
                    await page.wait_for_selector(wait_for, timeout=15000)
                except Exception:
                    # Selector not found - page may use different markup, continue anyway
                    self.log.debug("wait_for selector not found, continuing", selector=wait_for, url=url)

            # Polite delay between requests
            await asyncio.sleep(self.REQUEST_DELAY_SECONDS)

            self.log.debug("Page loaded", url=url)
            return page

        except Exception as e:
            await page.close()
            self.log.warning("Page load failed, will retry", url=url, error=str(e))
            raise

    async def safe_text(self, page: Page, selector: str, default: str = "") -> str:
        """
        Safely extract text from a CSS selector.

        Returns default if the element doesn't exist (avoids crashes when
        stores change their HTML structure).
        """
        try:
            element = await page.query_selector(selector)
            if element:
                return (await element.inner_text()).strip()
        except Exception:
            pass
        return default

    async def safe_attr(
        self, page: Page, selector: str, attr: str, default: str = ""
    ) -> str:
        """Safely extract an attribute value from a CSS selector."""
        try:
            element = await page.query_selector(selector)
            if element:
                value = await element.get_attribute(attr)
                return value.strip() if value else default
        except Exception:
            pass
        return default

    def parse_price(self, price_str: str) -> Optional[Decimal]:
        """
        Parse a price string into a Decimal.

        Handles common formats:
            "$29.99"   → Decimal("29.99")
            "29.99"    → Decimal("29.99")
            "$1,299.00" → Decimal("1299.00")
            "From $29" → Decimal("29.00")
            "Sale"     → None (not a price)
        """
        if not price_str:
            return None

        # Remove common non-numeric characters
        cleaned = re.sub(r"[^\d.]", "", price_str.replace(",", ""))

        # Handle multiple decimal points (malformed data)
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = parts[0] + "." + parts[1]

        try:
            price = Decimal(cleaned)
            # Sanity check: FPV parts are typically $1-$2000
            if Decimal("0.01") <= price <= Decimal("9999.99"):
                return price
        except InvalidOperation:
            pass

        return None

    def detect_category(self, title: str) -> str:
        """Delegate to the module-level detect_category function."""
        return detect_category(title)

    @abstractmethod
    async def get_products(self) -> list[dict]:
        """
        Scrape all products from the store catalog.

        Returns a list of raw product dicts. Each dict should have at minimum:
            - title: str
            - url: str
            - price: str (will be parsed by normalize_product)

        Subclasses must implement this.
        """
        ...

    @abstractmethod
    async def get_deals(self) -> list[dict]:
        """
        Scrape products from the store's sale/clearance pages.

        Same format as get_products(). These products are flagged
        as explicit deals (deal_type="sale").
        """
        ...

    @abstractmethod
    def normalize_product(self, raw: dict) -> dict:
        """
        Convert a raw scraped dict into our standard product format.

        Standard format:
        {
            "external_id": str,      # Store's product ID
            "title": str,
            "url": str,
            "image_url": str | None,
            "price": Decimal,
            "original_price": Decimal | None,  # "Was" price if on sale
            "in_stock": bool,
            "category": str,
            "specs": dict,           # Category-specific specs
        }
        """
        ...
