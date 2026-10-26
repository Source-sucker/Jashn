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
