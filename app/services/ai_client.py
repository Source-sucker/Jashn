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
        self.fallback_models = settings.gemini_model_fallbacks
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

    async def generate_json(
        self,
        prompt: str,
        schema_class: Optional[Any] = None,
        task: str = "general",
        timeout: Optional[float] = None
    ) -> Optional[dict[str, Any]]:
        """
        Executes Gemini content generation expecting a JSON response.
        Enforces:
        - Instant return if no API key
        - In-memory cache hit return
        - Strict timeout (AI_TIMEOUT_SECONDS or per-task override)
        - Exactly 1 retry on transient failure
        - Markdown/fenced JSON extraction
        """
        if not self.is_available():
            logger.info("Gemini API key not configured. Using deterministic fallback.")
            return None

        effective_timeout = timeout if timeout is not None else settings.get_task_timeout(task)

        cache_key = _get_cache_key(prompt)
        if cache_key in _LRU_CACHE:
            logger.info("AI Cache hit for prompt.")
            return _LRU_CACHE[cache_key]

        last_error = None
        for attempt in range(2):  # initial attempt + 1 retry
            try:
                result_json = await asyncio.wait_for(
                    self._call_gemini_api(prompt, task=task),
                    timeout=effective_timeout
                )
                if result_json:
                    # Update cache
                    if len(_LRU_CACHE) >= _MAX_CACHE_SIZE:
                        # Pop oldest item
                        _LRU_CACHE.pop(next(iter(_LRU_CACHE)))
                    _LRU_CACHE[cache_key] = result_json
                    return result_json
            except asyncio.TimeoutError as e:
                logger.warning(f"Gemini API timed out after {effective_timeout}s (attempt {attempt + 1}): {e}")
                last_error = e
            except Exception as e:
                logger.warning(f"Gemini API call failed (attempt {attempt + 1}): {e}")
                last_error = e

            if attempt == 0:
                await asyncio.sleep(0.5)

        logger.error(f"Gemini API exhausted attempts. Falling back. Last error: {last_error}")
        return None

    TASK_TOKEN_LIMITS = {
        "intake": 450,
        "plan": 900,
        "enrich": 900,
        "refine": 750,
        "replan": 350,
    }

    @staticmethod
    def _is_model_fallback_error(exc: Exception) -> bool:
        """
        Returns True if exception indicates model not found (404) or overload (503, 429).
        """
        err_str = str(exc).lower()
        code = getattr(exc, "code", None)
        if code in (404, 429, 503):
            return True

        status_attr = getattr(exc, "status", None)
        if status_attr in ("NOT_FOUND", "RESOURCE_EXHAUSTED", "UNAVAILABLE"):
            return True

        indicators = [
            "not found", "404", "not_found", "does not exist",
            "unavailable", "503", "overloaded", "high demand",
            "resource exhausted", "resource_exhausted", "429", "quota", "too many requests"
        ]
        return any(ind in err_str for ind in indicators)

    async def _call_gemini_api(self, prompt: str, task: str = "general") -> Optional[dict[str, Any]]:
        """
        Runs synchronous SDK call inside default thread pool executor to remain async-friendly.
        Caps max_output_tokens per task and implements fallback model chain on model-not-found or overload.
        Logs only model names, never secret keys.
        """
        loop = asyncio.get_running_loop()
        models_to_try = [self.model_name] + [m for m in self.fallback_models if m != self.model_name]

        for idx, model_to_call in enumerate(models_to_try):
            def _sync_call(target_model: str):
                max_tokens = self.TASK_TOKEN_LIMITS.get(task, 750)
                config_kwargs: dict[str, Any] = {
                    "response_mime_type": "application/json",
                    "temperature": 0.2,
                    "max_output_tokens": max_tokens,
                }
                if "thinking" in target_model.lower():
                    config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=256)

                config = types.GenerateContentConfig(**config_kwargs)
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=prompt,
                    config=config
                )
                return response.text

            try:
                raw_text = await loop.run_in_executor(None, _sync_call, model_to_call)
                if not raw_text:
                    continue

                cleaned = raw_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                return json.loads(cleaned)

            except Exception as e:
                has_next = (idx + 1) < len(models_to_try)
                if has_next and self._is_model_fallback_error(e):
                    next_model = models_to_try[idx + 1]
                    logger.warning(
                        f"Gemini model '{model_to_call}' error ({e.__class__.__name__}). Falling back to model '{next_model}'."
                    )
                    continue
                else:
                    raise e

        return None


# Global singleton instance
ai_client = GeminiClient()
