"""Unit tests for OllamaClient HTTP communication, timeouts, and error handling."""

from __future__ import annotations

import asyncio
import json
import httpx
import pytest

from app.ai.client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaMalformedJSONError,
    OllamaResponseError,
    OllamaTimeoutError,
)


class TestOllamaClientMocked:
    """Test suite using mock HTTP transports to test OllamaClient deterministically."""

    def test_successful_async_generate_json(self) -> None:
        """Verify successful async request parsing valid JSON response."""
        async def _test() -> None:
            mock_model_json = {
                "incident_summary": "CPU exhaustion caused by stress_worker thread.",
                "probable_causes": [
                    {
                        "rank": 1,
                        "hypothesis": "Runaway compute loop.",
                        "confidence": "HIGH",
                        "supporting_evidence": ["CPU at 96.5%"],
                    }
                ],
                "investigation_steps": ["Inspect process with top."],
                "remediation_actions": [
                    {
                        "step_number": 1,
                        "action": "Terminate thread.",
                        "command": "kill -15 1042",
                        "safety_level": "CAUTION",
                        "precautions": "Ensure state saved.",
                    }
                ],
                "uncertainty_assessment": "Nominal storage signals.",
            }

            mock_envelope = {
                "model": "qwen2.5:3b",
                "response": json.dumps(mock_model_json),
                "done": True,
            }

            async def handler(request: httpx.Request) -> httpx.Response:
                assert request.url.path == "/api/generate"
                body = json.loads(request.content)
                assert body["model"] == "qwen2.5:3b"
                assert body["format"] == "json"
                return httpx.Response(200, json=mock_envelope)

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://mock-ollama:11434",
                model_name="qwen2.5:3b",
                transport=transport,
            )

            result = await client.generate_json("System prompt", "User prompt")
            assert result["incident_summary"] == mock_model_json["incident_summary"]
            assert len(result["probable_causes"]) == 1
            assert result["probable_causes"][0]["hypothesis"] == "Runaway compute loop."

        asyncio.run(_test())

    def test_successful_sync_generate_json_with_codeblock(self) -> None:
        """Verify sync request parses JSON even if wrapped in markdown codeblock."""
        mock_model_json = {
            "incident_summary": "Memory leak detected.",
            "probable_causes": [],
            "investigation_steps": [],
            "remediation_actions": [],
            "uncertainty_assessment": "Unobserved page cache.",
        }

        raw_wrapped_text = f"```json\n{json.dumps(mock_model_json)}\n```"
        mock_envelope = {
            "model": "qwen2.5:3b",
            "response": raw_wrapped_text,
            "done": True,
        }

        def sync_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=mock_envelope)

        sync_transport = httpx.MockTransport(sync_handler)
        client = OllamaClient(
            base_url="http://mock-ollama:11434",
            model_name="qwen2.5:3b",
            sync_transport=sync_transport,
        )

        result = client.generate_json_sync("System prompt", "User prompt")
        assert result["incident_summary"] == "Memory leak detected."

    def test_connection_error_raises_ollama_connection_error(self) -> None:
        """Verify connection failure raises OllamaConnectionError."""
        async def _test() -> None:
            async def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("Connection refused on port 11434", request=request)

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://localhost:11434",
                transport=transport,
            )

            with pytest.raises(OllamaConnectionError) as exc_info:
                await client.generate_json("System", "User")
            assert "Cannot connect to Ollama daemon" in str(exc_info.value)

        asyncio.run(_test())

    def test_timeout_raises_ollama_timeout_error(self) -> None:
        """Verify timeout raises OllamaTimeoutError."""
        async def _test() -> None:
            async def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ReadTimeout("Read timed out", request=request)

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://localhost:11434",
                timeout_seconds=5.0,
                transport=transport,
            )

            with pytest.raises(OllamaTimeoutError) as exc_info:
                await client.generate_json("System", "User")
            assert "timed out after 5.0s" in str(exc_info.value)

        asyncio.run(_test())

    def test_http_500_raises_ollama_response_error(self) -> None:
        """Verify non-200 HTTP response raises OllamaResponseError."""
        async def _test() -> None:
            async def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(500, text="Internal Ollama Server Error")

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://localhost:11434",
                transport=transport,
            )

            with pytest.raises(OllamaResponseError) as exc_info:
                await client.generate_json("System", "User")
            assert "HTTP 500" in str(exc_info.value)

        asyncio.run(_test())

    def test_malformed_json_raises_ollama_malformed_json_error(self) -> None:
        """Verify unparseable text in envelope raises OllamaMalformedJSONError."""
        async def _test() -> None:
            mock_envelope = {
                "model": "qwen2.5:3b",
                "response": "Here is your analysis: Not valid JSON at all!",
                "done": True,
            }

            async def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json=mock_envelope)

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://localhost:11434",
                transport=transport,
            )

            with pytest.raises(OllamaMalformedJSONError) as exc_info:
                await client.generate_json("System", "User")
            assert "not valid JSON" in str(exc_info.value)

        asyncio.run(_test())

    def test_oversized_response_rejected(self) -> None:
        """Verify responses exceeding size limit are rejected for safety."""
        async def _test() -> None:
            async def handler(request: httpx.Request) -> httpx.Response:
                large_text = "A" * 600_000
                return httpx.Response(200, text=large_text)

            transport = httpx.MockTransport(handler)
            client = OllamaClient(
                base_url="http://localhost:11434",
                transport=transport,
            )

            with pytest.raises(OllamaResponseError) as exc_info:
                await client.generate_json("System", "User")
            assert "Oversized response" in str(exc_info.value)

        asyncio.run(_test())

    def test_check_availability_success(self) -> None:
        """Verify check_availability reports model presence when Ollama responds."""
        async def _test() -> None:
            async def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]})

            client = OllamaClient(
                base_url="http://localhost:11434",
                model_name="qwen2.5:3b",
                transport=httpx.MockTransport(handler),
            )
            status = await client.check_availability()
            assert status["available"] is True
            assert status["model_available"] is True
            assert "qwen2.5:3b" in status["models"]
            assert status["error"] is None

        asyncio.run(_test())

    def test_check_availability_sync_connection_error(self) -> None:
        """Verify check_availability_sync handles connection failure gracefully."""
        def sync_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = OllamaClient(
            base_url="http://localhost:11434",
            sync_transport=httpx.MockTransport(sync_handler),
        )
        status = client.check_availability_sync()
        assert status["available"] is False
        assert status["model_available"] is False
        assert status["error"] is not None
