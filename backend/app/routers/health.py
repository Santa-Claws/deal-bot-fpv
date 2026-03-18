"""
Health check endpoints.

These are used by:
1. Docker Compose healthchecks (to know when the app is ready)
2. Monitoring tools
3. You, when verifying the app is running: curl http://localhost:8000/health
"""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check - just confirms the API is responding.

    Docker uses this to know when the container is ready to accept traffic.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "fpv-deal-finder",
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """
    Detailed health check - tests connectivity to all dependencies.

    Returns individual status for each service so you can debug
    which component is having issues.
    """
    health = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
    }

    # ── Check PostgreSQL ──────────────────────────────
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health["services"]["postgres"] = {"status": "ok"}
    except Exception as e:
        health["services"]["postgres"] = {"status": "error", "detail": str(e)}
        health["status"] = "degraded"

    return health
