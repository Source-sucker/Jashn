import asyncio
import hashlib
import json
import logging
import re
from typing import Any, Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger("jashn.ai_client")

# Simple thread-safe bounded in-memory cache for identical requests
_LRU_CACHE: dict[str, dict[str, Any]] = {}
_MAX_CACHE_SIZE = 128


def _get_cache_key(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", prompt.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AIUnavailableException(Exception):
    pass


class GeminiClient:
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model or "gemini-flash-latest"
        self.timeout = settings.ai_timeout_seconds
        self._client: Optional[genai.Client] = None

        if self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Google GenAI Client: {e}")
                self._client = None

    def is_available(self) -> bool:
        return bool(self._client and self.api_key)

    async def generate_json(self, prompt: str, schema_class: Optional[Any] = None) -> Optional[dict[str, Any]]:
        """
        Executes Gemini content generation expecting a JSON response.
        Enforces:
        - Instant return if no API key
        - In-memory cache hit return
        - Strict timeout (AI_TIMEOUT_SECONDS)
        - Exactly 1 retry on transient failure
        - Markdown/fenced JSON extraction
        """
        if not self.is_available():
            logger.info("Gemini API key not configured. Using deterministic fallback.")
            return None

        cache_key = _get_cache_key(prompt)
        if cache_key in _LRU_CACHE:
            logger.info("AI Cache hit for prompt.")
            return _LRU_CACHE[cache_key]

        last_error = None
        for attempt in range(2):  # initial attempt + 1 retry
            try:
                result_json = await asyncio.wait_for(
                    self._call_gemini_api(prompt),
                    timeout=self.timeout
                )
                if result_json:
                    # Update cache
                    if len(_LRU_CACHE) >= _MAX_CACHE_SIZE:
                        # Pop oldest item
                        _LRU_CACHE.pop(next(iter(_LRU_CACHE)))
                    _LRU_CACHE[cache_key] = result_json
                    return result_json
            except asyncio.TimeoutError as e:
                logger.warning(f"Gemini API timed out after {self.timeout}s (attempt {attempt + 1}): {e}")
                last_error = e
            except Exception as e:
                logger.warning(f"Gemini API call failed (attempt {attempt + 1}): {e}")
                last_error = e

            if attempt == 0:
                await asyncio.sleep(0.5)

        logger.error(f"Gemini API exhausted attempts. Falling back. Last error: {last_error}")
        return None

    async def _call_gemini_api(self, prompt: str) -> Optional[dict[str, Any]]:
        """
        Runs synchronous SDK call inside default thread pool executor to remain async-friendly.
        """
        loop = asyncio.get_running_loop()

        def _sync_call():
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text

        raw_text = await loop.run_in_executor(None, _sync_call)
        if not raw_text:
            return None

        # Clean code fence if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return json.loads(cleaned)


# Global singleton instance
ai_client = GeminiClient()
