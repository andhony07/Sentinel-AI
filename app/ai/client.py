"""Lightweight, resilient Ollama HTTP client for SentinelAI.

Communicates with locally hosted open-weight models via Ollama's REST API.
Implements asynchronous and synchronous generation, strict timeouts, JSON extraction,
and comprehensive error boundaries.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import httpx

from app.core.logging_config import get_logger

logger = get_logger("app.ai.client")


class OllamaClientError(Exception):
    """Base exception for all Ollama client failures."""


class OllamaConnectionError(OllamaClientError):
    """Raised when the Ollama daemon is unreachable or stopped."""


class OllamaTimeoutError(OllamaClientError):
    """Raised when Ollama request exceeds configured timeout."""


class OllamaResponseError(OllamaClientError):
    """Raised when Ollama returns non-200 HTTP status code."""


class OllamaMalformedJSONError(OllamaClientError):
    """Raised when model output cannot be parsed into valid JSON."""


class OllamaClient:
    """HTTP client for communicating with local Ollama service."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "qwen2.5:3b",
        timeout_seconds: float = 90.0,
        temperature: float = 0.2,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        sync_transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        """Initialize the Ollama HTTP client.

        Args:
            base_url: Base URL of local Ollama server (e.g. http://localhost:11434).
            model_name: Target model identifier (e.g. qwen2.5:3b, llama3.1:8b).
            timeout_seconds: Request timeout in seconds.
            temperature: Sampling temperature for generation.
            transport: Optional custom async transport for unit testing with mocks.
            sync_transport: Optional custom sync transport for unit testing.
        """
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self._transport = transport
        self._sync_transport = sync_transport

    def _build_request_payload(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Construct the Ollama /api/generate request payload."""
        return {
            "model": self.model_name,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
            },
        }

    def _extract_json_from_response(self, text: str) -> dict[str, Any]:
        """Extract and parse a JSON dictionary from raw model response text."""
        cleaned = text.strip()
        # Handle optional markdown codeblocks
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise OllamaMalformedJSONError(
                    f"Model output parsed as {type(parsed).__name__}, expected JSON object (dict)."
                )
            return parsed
        except json.JSONDecodeError as err:
            logger.warning("Failed to decode model JSON output: %s", err)
            raise OllamaMalformedJSONError(
                f"Model response is not valid JSON: {err}. Snippet: {cleaned[:150]}"
            ) from err

    async def generate_json(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Asynchronously send generation request to Ollama and parse JSON response.

        Args:
            system_prompt: System instruction prompt.
            user_prompt: User evaluation and telemetry prompt.

        Returns:
            Parsed JSON dictionary returned by the model.

        Raises:
            OllamaConnectionError: If Ollama daemon is unreachable.
            OllamaTimeoutError: If generation exceeds timeout.
            OllamaResponseError: If Ollama returns HTTP error.
            OllamaMalformedJSONError: If model response is invalid JSON.
        """
        endpoint = f"{self.base_url}/api/generate"
        payload = self._build_request_payload(system_prompt, user_prompt)
        timeout = httpx.Timeout(self.timeout_seconds, connect=3.0)

        async with httpx.AsyncClient(
            transport=self._transport, timeout=timeout
        ) as client:
            try:
                resp = await client.post(endpoint, json=payload)
            except httpx.ConnectError as exc:
                logger.warning("Ollama connection failed on %s: %s", endpoint, exc)
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama daemon at '{self.base_url}'. "
                    f"Ensure Ollama is running ('ollama serve')."
                ) from exc
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Ollama request timed out after %.1fs on %s",
                    self.timeout_seconds,
                    endpoint,
                )
                raise OllamaTimeoutError(
                    f"Ollama inference timed out after {self.timeout_seconds}s."
                ) from exc
            except httpx.RequestError as exc:
                logger.warning("Ollama HTTP request error: %s", exc)
                raise OllamaConnectionError(f"HTTP request error: {exc}") from exc

            # Protect against oversized responses
            if len(resp.content) > 500_000:
                raise OllamaResponseError("Oversized response from Ollama (>500KB).")

            if resp.status_code != 200:
                logger.warning(
                    "Ollama returned HTTP error %d: %s", resp.status_code, resp.text[:200]
                )
                raise OllamaResponseError(
                    f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
                )

            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                raise OllamaResponseError(
                    f"Malformed HTTP response envelope from Ollama: {exc}"
                ) from exc

            raw_response = data.get("response")
            if not raw_response or not isinstance(raw_response, str):
                raise OllamaResponseError(
                    "Ollama response envelope missing non-empty 'response' text field."
                )

            return self._extract_json_from_response(raw_response)

    def generate_json_sync(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Synchronously send generation request to Ollama and parse JSON response.

        Used by Streamlit dashboard components and non-async services.

        Args:
            system_prompt: System instruction prompt.
            user_prompt: User evaluation and telemetry prompt.

        Returns:
            Parsed JSON dictionary returned by the model.
        """
        endpoint = f"{self.base_url}/api/generate"
        payload = self._build_request_payload(system_prompt, user_prompt)
        timeout = httpx.Timeout(self.timeout_seconds, connect=3.0)

        with httpx.Client(transport=self._sync_transport, timeout=timeout) as client:
            try:
                resp = client.post(endpoint, json=payload)
            except httpx.ConnectError as exc:
                logger.warning("Ollama sync connection failed on %s: %s", endpoint, exc)
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama daemon at '{self.base_url}'."
                ) from exc
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Ollama sync request timed out after %.1fs", self.timeout_seconds
                )
                raise OllamaTimeoutError(
                    f"Ollama inference timed out after {self.timeout_seconds}s."
                ) from exc
            except httpx.RequestError as exc:
                logger.warning("Ollama sync HTTP error: %s", exc)
                raise OllamaConnectionError(f"HTTP request error: {exc}") from exc

            if len(resp.content) > 500_000:
                raise OllamaResponseError("Oversized response from Ollama (>500KB).")

            if resp.status_code != 200:
                raise OllamaResponseError(
                    f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
                )

            try:
                data = resp.json()
            except json.JSONDecodeError as exc:
                raise OllamaResponseError(
                    f"Malformed HTTP envelope from Ollama: {exc}"
                ) from exc

            raw_response = data.get("response")
            if not raw_response or not isinstance(raw_response, str):
                raise OllamaResponseError("Missing 'response' field in Ollama envelope.")

            return self._extract_json_from_response(raw_response)

    async def check_availability(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        """Asynchronously probe Ollama daemon reachability and verify configured model.

        Args:
            timeout_seconds: Probe timeout in seconds (default 2.0s to avoid blocking).

        Returns:
            Dictionary with availability status, model presence, and error summary.
        """
        endpoint = f"{self.base_url}/api/tags"
        timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)

        async with httpx.AsyncClient(
            transport=self._transport, timeout=timeout
        ) as client:
            try:
                resp = await client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [
                        m.get("name", "")
                        for m in data.get("models", [])
                        if isinstance(m, dict) and "name" in m
                    ]
                    model_found = any(
                        self.model_name == m or self.model_name in m
                        for m in models
                    )
                    return {
                        "available": True,
                        "model_available": model_found,
                        "models": models,
                        "error": None,
                    }
                return {
                    "available": False,
                    "model_available": False,
                    "models": [],
                    "error": f"Ollama returned HTTP {resp.status_code}",
                }
            except Exception as exc:
                return {
                    "available": False,
                    "model_available": False,
                    "models": [],
                    "error": str(exc),
                }

    def check_availability_sync(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        """Synchronously probe Ollama daemon reachability and verify configured model.

        Args:
            timeout_seconds: Probe timeout in seconds (default 2.0s to avoid blocking).

        Returns:
            Dictionary with availability status, model presence, and error summary.
        """
        endpoint = f"{self.base_url}/api/tags"
        timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)

        with httpx.Client(
            transport=self._sync_transport, timeout=timeout
        ) as client:
            try:
                resp = client.get(endpoint)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [
                        m.get("name", "")
                        for m in data.get("models", [])
                        if isinstance(m, dict) and "name" in m
                    ]
                    model_found = any(
                        self.model_name == m or self.model_name in m
                        for m in models
                    )
                    return {
                        "available": True,
                        "model_available": model_found,
                        "models": models,
                        "error": None,
                    }
                return {
                    "available": False,
                    "model_available": False,
                    "models": [],
                    "error": f"Ollama returned HTTP {resp.status_code}",
                }
            except Exception as exc:
                return {
                    "available": False,
                    "model_available": False,
                    "models": [],
                    "error": str(exc),
                }
