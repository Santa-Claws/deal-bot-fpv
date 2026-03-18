"""
Database models for FPV product tracking.

Schema overview:
    stores       - FPV stores we scrape (NewBeeDrone, GetFPV, etc.)
    products     - Individual products with specs
    price_history - Price at each scrape time (enables history charts)
    deals        - Detected deals with scores

SQLAlchemy maps these Python classes to PostgreSQL tables.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Store(Base):
    """
    An FPV store that we scrape.

    Each store has a dedicated scraper module in app/scrapers/.
    The scrape_interval_hours controls how often we re-check for new deals.
    """

    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    scrape_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    last_scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship: one store → many products
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="store", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Store {self.name}>"


class Product(Base):
    """
    A product listed on an FPV store.

    Key fields:
    - external_id: the store's own ID for the product (for dedup)
    - specs: JSONB field for flexible spec storage
      Examples:
        Motors: {"stator": "2207", "kv": 2450, "weight_g": 28.5}
        ESCs: {"amperage": 45, "cell_count": "4S", "protocol": "DSHOT600"}
        Frames: {"size_mm": 220, "material": "carbon", "style": "freestyle"}
    - category: high-level category for filtering
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)

    # Store's internal product ID - used to avoid re-inserting the same product
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Categories: motors, escs, flight_controllers, frames, vtx, cameras,
    #             props, antennas, batteries, accessories
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Flexible spec storage - schema varies by category
    specs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    store: Mapped[Store] = relationship("Store", back_populates="products")
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan",
        order_by="PriceHistory.scraped_at"
    )
    deals: Mapped[list["Deal"]] = relationship(
        "Deal", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Product {self.title[:50]}>"

    @property
    def current_price(self) -> Optional[Decimal]:
        """Return the most recent price from price history."""
        if self.price_history:
            return self.price_history[-1].price
        return None


class PriceHistory(Base):
    """
    Price snapshot taken at each scrape.

    This is how we track "was $45, now $30" type deals.
    We insert a new row every scrape cycle so we build up
    a history that feeds the price chart on the product page.

    original_price = the crossed-out "was" price (if the store shows it)
    price = what you actually pay right now
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    original_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # Relationship back to product
    product: Mapped[Product] = relationship("Product", back_populates="price_history")

    def __repr__(self) -> str:
        return f"<PriceHistory ${self.price} at {self.scraped_at}>"

    @property
    def discount_percent(self) -> Optional[float]:
        """
        Calculate discount percentage if original_price is set.

        Example: original=$50, price=$35 → 30% off
        """
        if self.original_price and self.original_price > 0:
            discount = (self.original_price - self.price) / self.original_price
            return round(float(discount) * 100, 1)
        return None


class Deal(Base):
    """
    A detected deal with an AI-generated quality score.

    deal_types:
    - "sale"        : explicitly marked as on sale by the store
    - "price_drop"  : price dropped compared to 7-day average
    - "historic_low": lowest price we've ever seen for this product
    - "cross_store" : cheaper than the same item at another store

    deal_score: 0-10 (AI-generated), higher = better deal
    """

    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)

    deal_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # sale, price_drop, historic_low, cross_store
    discount_percent: Mapped[Optional[float]] = mapped_column(nullable=True)
    deal_score: Mapped[Optional[float]] = mapped_column(nullable=True)  # 0-10 AI score

    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship back to product
    product: Mapped[Product] = relationship("Product", back_populates="deals")

    def __repr__(self) -> str:
        return f"<Deal {self.deal_type} {self.discount_percent}% off>"
