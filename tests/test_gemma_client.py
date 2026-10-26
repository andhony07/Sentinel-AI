"""Unit tests for GemmaClient using official Google Gen AI SDK patterns and mocks."""

from __future__ import annotations

import asyncio
from unittest import mock
import pytest

from app.ai.gemma_client import (
    DEFAULT_GEMMA_MODEL,
    ALTERNATIVE_GEMMA_MODEL,
    GemmaAuthError,
    GemmaClient,
    GemmaClientError,
    GemmaMalformedJSONError,
    GemmaResponseError,
    GemmaTimeoutError,
)


class TestGemmaClientInitialization:
    """Test GemmaClient initialization and validation."""

    def test_default_initialization(self) -> None:
        """Verify default model names and parameters."""
        client = GemmaClient(api_key="mock_test_key_12345")
        assert client.model_name == DEFAULT_GEMMA_MODEL
        assert client.alternative_model_name == ALTERNATIVE_GEMMA_MODEL
        assert client.timeout_seconds == 30.0
        assert client.temperature == 0.2
        assert client.api_key == "mock_test_key_12345"

    def test_custom_parameters(self) -> None:
        """Verify custom model name, timeout, and temperature bounds."""
        client = GemmaClient(
            api_key="mock_key",
            model_name="gemma-4-31b-it",
            timeout_seconds=45.0,
            temperature=0.7,
        )
        assert client.model_name == "gemma-4-31b-it"
        assert client.timeout_seconds == 45.0
        assert client.temperature == 0.7

    def test_raw_client_without_api_key_raises_auth_error(self) -> None:
        """Verify raw_client raises GemmaAuthError when API key is missing."""
        client = GemmaClient(api_key=None)
        with pytest.raises(GemmaAuthError) as exc_info:
            _ = client.raw_client
        assert "GEMMA_API_KEY is not configured" in str(exc_info.value)

    def test_raw_client_with_custom_injected_client(self) -> None:
        """Verify custom injected client is returned without checking api_key."""
        mock_raw = mock.MagicMock()
        client = GemmaClient(api_key=None, client=mock_raw)
        assert client.raw_client is mock_raw


class TestGemmaClientJSONParsing:
    """Test robust JSON extraction and error handling."""

    def test_extract_clean_json(self) -> None:
        """Verify clean JSON parsing."""
        client = GemmaClient(api_key="test")
        raw = '{"incident_summary": "System healthy.", "probable_causes": []}'
        data = client._extract_json_from_response(raw)
        assert data["incident_summary"] == "System healthy."
        assert data["probable_causes"] == []

    def test_extract_json_from_markdown_fences(self) -> None:
        """Verify markdown code block stripping."""
        client = GemmaClient(api_key="test")
        raw = """```json
{
  "incident_summary": "Memory saturation detected.",
  "probable_causes": [{"rank": 1, "hypothesis": "Memory leak"}]
}
```"""
        data = client._extract_json_from_response(raw)
        assert data["incident_summary"] == "Memory saturation detected."
        assert len(data["probable_causes"]) == 1

    def test_extract_json_with_conversational_chatter(self) -> None:
        """Verify extraction when model includes preamble and epilogue."""
        client = GemmaClient(api_key="test")
        raw = """Here is the diagnostic evaluation:
{
  "incident_summary": "I/O bottleneck observed."
}
Hope this helps operator!"""
        data = client._extract_json_from_response(raw)
        assert data["incident_summary"] == "I/O bottleneck observed."

    def test_extract_empty_string_raises_malformed_error(self) -> None:
        """Verify empty string raises GemmaMalformedJSONError."""
        client = GemmaClient(api_key="test")
        with pytest.raises(GemmaMalformedJSONError) as exc_info:
            client._extract_json_from_response("")
        assert "Empty text received" in str(exc_info.value)

    def test_extract_invalid_json_raises_malformed_error(self) -> None:
        """Verify unparseable content raises GemmaMalformedJSONError."""
        client = GemmaClient(api_key="test")
        with pytest.raises(GemmaMalformedJSONError):
            client._extract_json_from_response("Not a JSON object at all")


class TestGemmaClientGenerationMocked:
    """Test asynchronous and synchronous generation flows with mocked GenAI SDK."""

    def test_async_generate_json_success(self) -> None:
        """Verify async generation calls aio.models.generate_content and parses output."""
        async def _test() -> None:
            mock_raw = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.text = '{"incident_summary": "High compute pressure.", "probable_causes": []}'

            future: asyncio.Future = asyncio.Future()
            future.set_result(mock_response)
            mock_raw.aio.models.generate_content.return_value = future

            client = GemmaClient(api_key="test_key", client=mock_raw)
            data = await client.generate_json("System prompt", "User prompt")

            assert data["incident_summary"] == "High compute pressure."
            mock_raw.aio.models.generate_content.assert_called_once()
            call_kwargs = mock_raw.aio.models.generate_content.call_args.kwargs
            assert call_kwargs["model"] == DEFAULT_GEMMA_MODEL
            assert "User prompt" in call_kwargs["contents"] and "System prompt" in call_kwargs["contents"]

        asyncio.run(_test())

    def test_sync_generate_json_success(self) -> None:
        """Verify sync generation calls models.generate_content and parses output."""
        mock_raw = mock.MagicMock()
        mock_response = mock.MagicMock()
        mock_response.text = '{"incident_summary": "Network congestion.", "probable_causes": []}'
        mock_raw.models.generate_content.return_value = mock_response

        client = GemmaClient(api_key="test_key", client=mock_raw)
        data = client.generate_json_sync("System prompt", "User prompt")

        assert data["incident_summary"] == "Network congestion."
        mock_raw.models.generate_content.assert_called_once()
        call_kwargs = mock_raw.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == DEFAULT_GEMMA_MODEL

    def test_async_fallback_to_alternative_model_on_404(self) -> None:
        """Verify client automatically falls back to alternative model if primary is 404."""
        async def _test() -> None:
            mock_raw = mock.MagicMock()

            # First call raises 404 / Not Found, second succeeds
            fut1: asyncio.Future = asyncio.Future()
            fut1.set_exception(Exception("Model 'gemma-4-26b-a4b-it' was not found (404)"))

            fut2: asyncio.Future = asyncio.Future()
            mock_resp2 = mock.MagicMock()
            mock_resp2.text = '{"incident_summary": "Evaluated via alternative model."}'
            fut2.set_result(mock_resp2)

            mock_raw.aio.models.generate_content.side_effect = [fut1, fut2]

            client = GemmaClient(
                api_key="test_key",
                model_name="gemma-4-26b-a4b-it",
                alternative_model_name="gemma-4-31b-it",
                client=mock_raw,
            )

            data = await client.generate_json("Sys", "User")
            assert data["incident_summary"] == "Evaluated via alternative model."
            assert client.model_name == "gemma-4-31b-it"
            assert mock_raw.aio.models.generate_content.call_count == 2

        asyncio.run(_test())

    def test_async_timeout_raises_gemma_timeout_error(self) -> None:
        """Verify asyncio.TimeoutError translates to GemmaTimeoutError."""
        async def _test() -> None:
            mock_raw = mock.MagicMock()

            async def slow_call(*args, **kwargs):
                await asyncio.sleep(0.5)
                return mock.MagicMock()

            mock_raw.aio.models.generate_content.side_effect = slow_call

            client = GemmaClient(api_key="test_key", timeout_seconds=0.05, client=mock_raw)
            with pytest.raises(GemmaTimeoutError) as exc_info:
                await client.generate_json("Sys", "User")
            assert "timed out" in str(exc_info.value)

        asyncio.run(_test())


class TestGemmaClientAvailability:
    """Test availability and reachability checking."""

    def test_check_availability_no_key(self) -> None:
        """Verify check_availability reports unavailable when key is missing."""
        async def _test() -> None:
            client = GemmaClient(api_key=None)
            res = await client.check_availability()
            assert res["available"] is False
            assert res["model_available"] is False
            assert "GEMMA_API_KEY is not configured" in res["error"]

        asyncio.run(_test())

    def test_check_availability_sync_no_key(self) -> None:
        """Verify check_availability_sync reports unavailable when key is missing."""
        client = GemmaClient(api_key="")
        res = client.check_availability_sync()
        assert res["available"] is False
        assert "GEMMA_API_KEY is not configured" in res["error"]

    def test_check_availability_with_mocked_models(self) -> None:
        """Verify check_availability identifies Gemma models in list."""
        async def _test() -> None:
            mock_raw = mock.MagicMock()

            class MockModel:
                def __init__(self, name: str):
                    self.name = name

            async def mock_async_pager():
                for m in [MockModel("models/gemma-4-26b-a4b-it"), MockModel("models/gemini-2.5")]:
                    yield m

            mock_raw.aio.models.list.return_value = mock_async_pager()

            client = GemmaClient(api_key="test_key", client=mock_raw)
            res = await client.check_availability()

            assert res["available"] is True
            assert res["model_available"] is True
            assert "gemma-4-26b-a4b-it" in res["models"]
            assert res["error"] is None

        asyncio.run(_test())

    def test_check_availability_error_does_not_leak_key(self) -> None:
        """Verify exceptions during availability check sanitize any key text."""
        async def _test() -> None:
            mock_raw = mock.MagicMock()

            async def fail_pager():
                raise Exception("Failed with key secret_value_987654321")
                yield  # unreachable

            mock_raw.aio.models.list.return_value = fail_pager()

            client = GemmaClient(api_key="secret_value_987654321", client=mock_raw)
            res = await client.check_availability()

            assert res["available"] is False
            assert "secret_value_987654321" not in res["error"]
            assert "***" in res["error"]

        asyncio.run(_test())
