"""
Discord notification service for deal alerts.

Uses the Apprise library which supports many notification services
(Discord, Telegram, Slack, email, etc.) through a unified interface.

Discord webhook setup:
1. Open your Discord server
2. Go to Server Settings → Integrations → Webhooks
3. Click "New Webhook", choose a channel, copy the URL
4. Set DISCORD_WEBHOOK_URL in your .env file

Apprise docs: https://github.com/caronc/apprise
"""

from typing import Optional

import apprise
import structlog

from app.config import settings

logger = structlog.get_logger()


class NotificationService:
    """Handles sending deal notifications to Discord (and other services)."""

    def __init__(self):
        self._webhook_url = settings.discord_webhook_url
        self._custom_rules: list[dict] = []  # Loaded from DB

    def _build_apprise(self) -> Optional[apprise.Apprise]:
        """
        Create an Apprise instance with the configured webhook.

        Returns None if no webhook is configured.
        """
        if not self._webhook_url:
            return None

        ap = apprise.Apprise()

        # Apprise automatically detects the service from the URL format
        # Discord webhooks: https://discord.com/api/webhooks/...
        ap.add(self._webhook_url)
        return ap

    async def send_deal_alert(
        self,
        title: str,
        price: float,
        original_price: Optional[float],
        url: str,
        deal_score: float,
        category: str,
    ):
        """
        Send a deal alert to Discord.

        Formats a rich message with:
        - Product name
        - Price (with discount percentage if available)
        - Deal score (0-10 stars)
        - Direct link to the product
        """
        ap = self._build_apprise()
        if not ap:
            logger.debug("No notification webhook configured, skipping alert")
            return

        # Format the discount info
        discount_info = ""
        if original_price and original_price > price:
            discount_pct = ((original_price - price) / original_price) * 100
            discount_info = f" (was ${original_price:.2f}, {discount_pct:.0f}% off)"

        # Score visualized as stars
        stars = "⭐" * round(deal_score)
        score_text = f"{stars} {deal_score:.1f}/10"

        # Category emoji
        category_emoji = {
            "motors": "🔧",
            "escs": "⚡",
            "flight_controllers": "🧠",
            "frames": "🏗️",
            "vtx": "📡",
            "cameras": "📷",
            "props": "🌀",
            "batteries": "🔋",
            "stacks": "📦",
        }.get(category, "🛒")

        message = (
            f"{category_emoji} **{title}**\n"
            f"💰 **${price:.2f}**{discount_info}\n"
            f"Deal Score: {score_text}\n"
            f"🔗 {url}"
        )

        try:
            result = ap.notify(
                title=f"🎯 FPV Deal Alert - {category.replace('_', ' ').title()}",
                body=message,
            )
            if result:
                logger.info("Deal alert sent", product=title[:50], score=deal_score)
            else:
                logger.warning("Notification send returned False", product=title[:50])
        except Exception as e:
            logger.error("Failed to send notification", error=str(e))

    async def send_test_notification(self, webhook_url: Optional[str] = None) -> bool:
        """
        Send a test notification to verify the webhook works.

        Args:
            webhook_url: Override the configured URL (for testing new webhooks)

        Returns:
            True if notification was sent successfully
        """
        url = webhook_url or self._webhook_url
        if not url:
            return False

        ap = apprise.Apprise()
        ap.add(url)

        try:
            result = ap.notify(
                title="🎯 FPV Deal Finder - Test Notification",
                body=(
                    "✅ Your Discord notifications are working!\n"
                    "You'll receive alerts here when deals matching your criteria are found.\n\n"
                    "Example: 🔧 **BrotherHobby 2207 2450KV Motor**\n"
                    "💰 **$22.99** (was $34.99, 34% off)\n"
                    "Deal Score: ⭐⭐⭐⭐⭐⭐⭐⭐ 8.5/10"
                ),
            )
            return bool(result)
        except Exception as e:
            logger.error("Test notification failed", error=str(e))
            return False

    def update_webhook(self, new_url: str):
        """Update the webhook URL (called from settings API endpoint)."""
        self._webhook_url = new_url
        logger.info("Webhook URL updated")


# Global instance
notification_service = NotificationService()
