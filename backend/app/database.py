"""
Database connection and session management.

We use SQLAlchemy's async engine with asyncpg as the PostgreSQL driver.
This lets us use async/await throughout the app without blocking the
event loop during database queries.

Pattern:
    async with get_db() as db:
        result = await db.execute(select(Product))
        products = result.scalars().all()
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── Base class for all SQLAlchemy models ──────────────
class Base(DeclarativeBase):
    """
    All models inherit from this. SQLAlchemy uses it to track
    which tables exist and how they map to Python classes.
    """
    pass


# ── Async engine ──────────────────────────────────────
# echo=True prints all SQL queries (useful for debugging, noisy in prod)
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_pre_ping=True,  # Verify connections before using them (handles DB restarts)
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────
# async_sessionmaker creates AsyncSession instances
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects usable after commit
)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager that provides a database session.

    Usage:
        async with get_db() as db:
            ...

    Always commits on success, rolls back on error.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency injection version of get_db.

    Usage in routers:
        @router.get("/products")
        async def list_products(db: AsyncSession = Depends(get_db_dependency)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables():
    """
    Create all database tables defined in models.
    Called at app startup if tables don't exist.

    In production, use Alembic migrations instead of this.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
