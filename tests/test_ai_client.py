import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_client import GeminiClient


@pytest.mark.asyncio
async def test_ai_client_returns_none_when_unconfigured():
    """Verify GeminiClient safely returns None without making any network calls when unconfigured."""
    with patch("app.services.ai_client.settings.gemini_api_key", ""):
        client = GeminiClient()
        result = await client.generate_json("Test prompt")
        assert result is None


@pytest.mark.asyncio
async def test_ai_client_success_and_caching():
    """Verify GeminiClient parses valid JSON and caches result for identical prompt."""
    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()

        with patch.object(client, "_call_gemini_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"themes": [{"title": "Royal Marigold"}], "is_complete": True}

            res1 = await client.generate_json("Prompt ABC for testing cache")
            assert res1 is not None
            assert res1["is_complete"] is True
            assert mock_call.call_count == 1

            # Second identical call should hit cache and NOT call API again
            res2 = await client.generate_json("Prompt ABC for testing cache")
            assert res2 == res1
            assert mock_call.call_count == 1


@pytest.mark.asyncio
async def test_ai_client_retries_once_before_fallback():
    """Verify client attempts call twice (1 retry) on error before returning None."""
    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()

        with patch.object(client, "_call_gemini_api", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("Simulated transient network timeout")

            res = await client.generate_json("Prompt with error trigger")
            assert res is None
            # Initial call + 1 retry = 2 calls
            assert mock_call.call_count == 2


@pytest.mark.asyncio
async def test_ai_client_timeout_handling():
    """Verify client handles asyncio.TimeoutError specifically and returns None."""
    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()
        client.timeout = 0.02

        async def _slow_call(prompt):
            await asyncio.sleep(0.1)
            return {"themes": []}

        with patch.object(client, "_call_gemini_api", side_effect=_slow_call):
            res = await client.generate_json("Slow prompt")
            assert res is None


@pytest.mark.asyncio
async def test_ai_client_lru_cache_eviction():
    """Verify LRU cache evicts oldest entries when capacity is reached."""
    from app.services.ai_client import _LRU_CACHE, _MAX_CACHE_SIZE

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()

        # Fill cache up to capacity
        _LRU_CACHE.clear()
        for i in range(_MAX_CACHE_SIZE):
            _LRU_CACHE[f"key_{i}"] = {"val": i}

        assert len(_LRU_CACHE) == _MAX_CACHE_SIZE

        with patch.object(client, "_call_gemini_api", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"val": "new_entry"}
            res = await client.generate_json("Unique prompt to trigger eviction")
            assert res == {"val": "new_entry"}
            assert len(_LRU_CACHE) == _MAX_CACHE_SIZE
            # The earliest key should have been evicted
            assert "key_0" not in _LRU_CACHE


@pytest.mark.asyncio
async def test_ai_client_call_gemini_api_markdown_cleaning():
    """Verify _call_gemini_api strips ```json markdown fences and parses valid JSON."""
    from unittest.mock import MagicMock

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()

        mock_response = MagicMock()
        mock_response.text = "```json\n{\"extracted\": true, \"count\": 42}\n```"
        client._client = MagicMock()
        client._client.models.generate_content.return_value = mock_response

        parsed = await client._call_gemini_api("Test prompt")
        assert parsed == {"extracted": True, "count": 42}


@pytest.mark.asyncio
async def test_ai_client_call_gemini_api_empty_text():
    """Verify _call_gemini_api returns None if SDK returns empty text."""
    from unittest.mock import MagicMock

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        client = GeminiClient()

        mock_response = MagicMock()
        mock_response.text = ""
        client._client = MagicMock()
        client._client.models.generate_content.return_value = mock_response

        parsed = await client._call_gemini_api("Test prompt")
        assert parsed is None
