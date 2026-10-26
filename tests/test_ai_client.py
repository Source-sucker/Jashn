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


def test_settings_task_timeouts():
    """Verify default timeout is 40 and per-task timeouts are correctly resolved."""
    from app.config import Settings

    s = Settings(
        ai_timeout_seconds=40,
        ai_timeout_intake=35,
        ai_timeout_plan=45,
        ai_timeout_refine=30,
        ai_timeout_replan=25,
    )
    assert s.ai_timeout_seconds == 40
    assert s.get_task_timeout("intake") == 35.0
    assert s.get_task_timeout("plan") == 45.0
    assert s.get_task_timeout("enrich") == 45.0
    assert s.get_task_timeout("refine") == 30.0
    assert s.get_task_timeout("replan") == 25.0
    assert s.get_task_timeout("unknown_task") == 40.0


@pytest.mark.asyncio
async def test_ai_client_model_fallback_on_not_found():
    """Verify GeminiClient tries fallback models on 404 Not Found error."""
    from unittest.mock import MagicMock

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        with patch("app.services.ai_client.settings.gemini_model", "gemini-old-model"):
            with patch("app.services.ai_client.settings.gemini_model_fallbacks_raw", "gemini-fallback-1,gemini-fallback-2"):
                client = GeminiClient()
                assert client.model_name == "gemini-old-model"
                assert client.fallback_models == ["gemini-fallback-1", "gemini-fallback-2"]

                mock_sdk = MagicMock()
                mock_success_res = MagicMock()
                mock_success_res.text = "```json\n{\"status\": \"fallback_worked\"}\n```"

                # First model throws 404, fallback model succeeds
                mock_sdk.models.generate_content.side_effect = [
                    Exception("404 Not Found: model gemini-old-model is not found"),
                    mock_success_res
                ]
                client._client = mock_sdk

                result = await client._call_gemini_api("Test prompt", task="plan")
                assert result == {"status": "fallback_worked"}
                assert mock_sdk.models.generate_content.call_count == 2
                called_models = [call.kwargs.get("model") for call in mock_sdk.models.generate_content.call_args_list]
                assert called_models == ["gemini-old-model", "gemini-fallback-1"]


@pytest.mark.asyncio
async def test_ai_client_model_fallback_on_overload():
    """Verify GeminiClient tries fallback models on 503 / 429 overload error."""
    from unittest.mock import MagicMock

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        with patch("app.services.ai_client.settings.gemini_model", "gemini-primary"):
            with patch("app.services.ai_client.settings.gemini_model_fallbacks_raw", "gemini-backup"):
                client = GeminiClient()
                mock_sdk = MagicMock()
                mock_success_res = MagicMock()
                mock_success_res.text = "{\"status\": \"overload_recovered\"}"

                mock_sdk.models.generate_content.side_effect = [
                    Exception("503 Service Unavailable: High demand, model overloaded"),
                    mock_success_res
                ]
                client._client = mock_sdk

                result = await client._call_gemini_api("Test prompt", task="refine")
                assert result == {"status": "overload_recovered"}
                assert mock_sdk.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_ai_client_model_fallback_exhausted():
    """Verify GeminiClient safely returns None when all models in fallback chain fail."""
    from unittest.mock import MagicMock

    with patch("app.services.ai_client.settings.gemini_api_key", "fake-key-for-test"):
        with patch("app.services.ai_client.settings.gemini_model", "gemini-primary"):
            with patch("app.services.ai_client.settings.gemini_model_fallbacks_raw", "gemini-backup"):
                client = GeminiClient()
                mock_sdk = MagicMock()
                mock_sdk.models.generate_content.side_effect = Exception("503 Service Unavailable")
                client._client = mock_sdk

                # generate_json catches exceptions across retries and returns None
                res = await client.generate_json("Prompt triggering all fallbacks to fail")
                assert res is None

