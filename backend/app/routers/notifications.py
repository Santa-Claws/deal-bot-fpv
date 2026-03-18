"""
Notification settings API endpoints.

POST /api/notifications/test        - Send a test Discord notification
GET  /api/notifications/settings    - Get notification configuration
PUT  /api/notifications/settings    - Update notification configuration
"""

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.notifications import notification_service

logger = structlog.get_logger()
router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    """Notification configuration from the frontend settings page."""
    discord_webhook_url: Optional[str] = None
    min_deal_score: float = 7.0       # Only notify for deals scoring >= this
    categories: Optional[list[str]] = None   # Only notify for these categories (None = all)
    max_price: Optional[float] = None  # Only notify for deals under this price
    enabled: bool = True


class TestNotificationRequest(BaseModel):
    webhook_url: Optional[str] = None  # Use configured URL if not provided


# In-memory settings (in a full app you'd persist these to DB)
_settings = NotificationSettings()


@router.get("/settings")
async def get_notification_settings():
    """Get current notification settings."""
    return _settings


@router.put("/settings")
async def update_notification_settings(new_settings: NotificationSettings):
    """
    Update notification settings.

    Changes take effect immediately for new deals.
    """
    global _settings
    _settings = new_settings

    # Update the webhook URL in the notification service
    if new_settings.discord_webhook_url:
        notification_service.update_webhook(new_settings.discord_webhook_url)

    logger.info("Notification settings updated", settings=new_settings.dict())
    return {"status": "ok", "settings": _settings}


@router.post("/test")
async def send_test_notification(request: TestNotificationRequest = TestNotificationRequest()):
    """
    Send a test notification to verify the Discord webhook works.

    If webhook_url is provided, uses that instead of the configured URL.
    This lets you test a new webhook before saving it.
    """
    success = await notification_service.send_test_notification(
        webhook_url=request.webhook_url
    )

    if success:
        return {"status": "ok", "message": "Test notification sent successfully"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to send notification. Check your webhook URL and Discord settings.",
        )
