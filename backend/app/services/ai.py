"""
AI service for query understanding and deal scoring.

Uses Ollama for local inference (private, free) with optional OpenAI fallback.
The AI helps with two main tasks:

1. Query Understanding: "cheap 2207 motors" → structured filters
   {category: "motors", max_price: 30, specs: {stator: "2207"}}

2. Deal Scoring: Rate how good a deal is on a 0-10 scale
   Takes product details and price history to give context-aware scores

Ollama docs: https://github.com/ollama/ollama/blob/main/docs/api.md
OpenAI-compatible endpoint: http://ollama:11434/v1
"""

import json
from typing import Optional

import httpx
import structlog

from app.config import load_ai_config, settings

logger = structlog.get_logger()


class AIService:
    """
    Handles all AI interactions.

    Tries Ollama first (local, free), falls back to OpenAI if:
    - Ollama is not running
    - The model isn't loaded
    - The request times out
    """

    def __init__(self):
        self.ai_config = load_ai_config()
        self.ollama_host = settings.ollama_host
        self.openai_key = settings.openai_api_key
        self._ollama_available: bool | None = None  # None = unknown, cached after first check

    async def _check_ollama_available(self) -> bool:
        """
        Quick check if Ollama is reachable. Cached so we don't hammer it.
        Resets to None every 5 minutes to re-check after restarts.
        """
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.ollama_host}/api/version")
                self._ollama_available = resp.status_code == 200
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    @property
    def ollama_model(self) -> str:
        """Get the configured Ollama model name."""
        return self.ai_config.get("ollama", {}).get("model", "mistral:7b")

    async def parse_search_query(self, query: str) -> dict:
        """
        Convert a natural language search query into structured filters.

        Examples:
            "cheap 2207 motors" →
                {"category": "motors", "max_price": 35, "specs": {"stator": "2207"}}

            "5 inch freestyle motors around 30 bucks" →
                {"category": "motors", "max_price": 35, "specs": {"stator": "2207"}}

            "best getfpv ESC deals" →
                {"category": "escs", "store": "GetFPV", "deals_only": true}

        Falls back to simple keyword extraction if AI fails.
        """
        prompt = f"""You are an FPV drone parts search assistant. Convert this search query into structured JSON filters.

Query: "{query}"

Return ONLY a JSON object (no markdown, no explanation) with these optional fields:
- category: one of [motors, escs, flight_controllers, frames, vtx, cameras, props, antennas, batteries, accessories]
- max_price: number (if user mentions price)
- min_price: number (if user mentions minimum price)
- store: store name if mentioned (NewBeeDrone, PyroDrone, RaceDayQuads, GetFPV, GEPRC, HDZero, RotorVillage)
- deals_only: true if user wants deals/sales only
- in_stock_only: true if user wants in-stock items only
- specs: object with category-specific specs like {{stator: "2207", kv: 2450}}
- search_terms: array of important keywords to search for

Example for "2207 2450kv motor under 30 dollars":
{{"category": "motors", "max_price": 30, "specs": {{"stator": "2207", "kv": 2450}}, "search_terms": ["motor", "2207", "2450kv"]}}"""

        if await self._check_ollama_available():
            try:
                result = await self._call_ollama(prompt)
                return self._parse_json_response(result)
            except Exception as e:
                logger.warning("Ollama query parse failed, trying fallback", error=str(e))
                self._ollama_available = None  # Reset so next call re-checks

        # Try OpenAI fallback
        if self.openai_key:
            try:
                result = await self._call_openai(prompt)
                return self._parse_json_response(result)
            except Exception as e:
                logger.warning("OpenAI query parse failed", error=str(e))

        # Last resort: basic keyword extraction
        return self._fallback_parse_query(query)

    async def score_deal(
        self,
        product_title: str,
        current_price: float,
        original_price: Optional[float],
        avg_price_30d: Optional[float],
        category: str,
    ) -> dict:
        """
        Rate the quality of a deal on a 0-10 scale.

        Context provided to the AI:
        - Product name and category
        - Current price vs original/list price
        - 30-day average price (if available)

        Returns:
            {
                "score": 7.5,
                "reasoning": "Good discount on a popular motor size",
                "recommendation": "Buy if you need motors soon"
            }
        """
        # Build context for the AI
        discount_info = ""
        if original_price and original_price > 0:
            discount_pct = ((original_price - current_price) / original_price) * 100
            discount_info = f"Originally ${original_price:.2f} ({discount_pct:.0f}% off)"

        avg_info = ""
        if avg_price_30d:
            vs_avg = ((avg_price_30d - current_price) / avg_price_30d) * 100
            avg_info = f"30-day average: ${avg_price_30d:.2f} (current is {vs_avg:.0f}% {'below' if vs_avg > 0 else 'above'} average)"

        prompt = f"""Rate this FPV drone parts deal from 0 to 10.

Product: {product_title}
Category: {category}
Current Price: ${current_price:.2f}
{discount_info}
{avg_info}

FPV context: Motors typically cost $20-60, ESCs $40-120, Flight Controllers $30-100, Frames $30-150.

Return ONLY JSON with these fields:
- score: number 0-10 (10 = incredible deal, 0 = bad deal / marked up)
- reasoning: one sentence explaining the score
- recommendation: "buy", "wait", or "skip"

Example: {{"score": 8.5, "reasoning": "25% off a well-reviewed 2207 motor is genuinely good", "recommendation": "buy"}}"""

        if await self._check_ollama_available():
            try:
                result = await self._call_ollama(prompt)
                return self._parse_json_response(result)
            except Exception as e:
                logger.warning("Deal scoring failed", error=str(e))
                self._ollama_available = None

        if self.openai_key:
            try:
                result = await self._call_openai(prompt)
                return self._parse_json_response(result)
            except Exception as e:
                logger.warning("OpenAI deal scoring failed", error=str(e))

        # Fallback: calculate score from discount percentage alone
        return self._fallback_score_deal(current_price, original_price)

    async def _call_ollama(self, prompt: str, timeout: float = 5.0) -> str:
        """
        Call Ollama's chat API.

        Ollama exposes an OpenAI-compatible endpoint at /v1/chat/completions
        and its own native API at /api/generate. We use the native API
        for simplicity.
        """
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,   # Low temperature = more deterministic
                        "num_predict": 256,    # Limit response length
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def _call_openai(self, prompt: str) -> str:
        """
        Call OpenAI API as fallback.

        Uses the httpx client directly instead of the openai SDK
        to keep dependencies minimal.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 256,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def _parse_json_response(self, text: str) -> dict:
        """
        Parse JSON from an AI response.

        AI responses sometimes include extra text around the JSON,
        so we extract just the JSON part.
        """
        text = text.strip()

        # Find the first { and last } to extract JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            return json.loads(json_str)

        # If no JSON found, return empty dict
        return {}

    def _fallback_parse_query(self, query: str) -> dict:
        """
        Simple keyword-based query parsing when AI is unavailable.

        Not as smart as AI but works offline.
        """
        from app.scrapers.base import detect_category

        # Detect category from query
        category = detect_category(query)

        # Look for price mentions: "under $30", "$20-40", "30 bucks"
        import re
        max_price = None
        price_match = re.search(r'under\s*\$?(\d+)|less\s*than\s*\$?(\d+)|\$?(\d+)\s*(?:dollars?|bucks?)', query.lower())
        if price_match:
            for g in price_match.groups():
                if g:
                    max_price = float(g)
                    break

        return {
            "category": category if category != "accessories" else None,
            "max_price": max_price,
            "search_terms": query.split(),
        }

    def _fallback_score_deal(
        self,
        current_price: float,
        original_price: Optional[float],
    ) -> dict:
        """Calculate a basic deal score from discount percentage."""
        if not original_price or original_price <= current_price:
            return {"score": 3.0, "reasoning": "No discount data available", "recommendation": "wait"}

        discount_pct = ((original_price - current_price) / original_price) * 100

        if discount_pct >= 40:
            score, rec = 9.0, "buy"
        elif discount_pct >= 25:
            score, rec = 7.5, "buy"
        elif discount_pct >= 15:
            score, rec = 6.0, "buy"
        elif discount_pct >= 10:
            score, rec = 4.5, "wait"
        else:
            score, rec = 3.0, "skip"

        return {
            "score": score,
            "reasoning": f"{discount_pct:.0f}% discount",
            "recommendation": rec,
        }


# Global instance
ai_service = AIService()
