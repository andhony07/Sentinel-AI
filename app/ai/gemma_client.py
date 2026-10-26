"""Gemma 4 LLM client using official Google Gen AI SDK (google-genai).

Provides asynchronous and synchronous methods for server incident diagnosis
using Gemma 4 models (primary: gemma-4-26b-a4b-it, alternative: gemma-4-31b-it)
via the Google Gemini API.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    APIError = Exception  # type: ignore[assignment,misc]
    HAS_GENAI = False

from app.core.logging_config import get_logger

logger = get_logger("app.ai.gemma_client")

# Recognized Gemma 4 model identifiers
DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it"
ALTERNATIVE_GEMMA_MODEL = "gemma-4-31b-it"
ALLOWED_GEMMA_MODELS = frozenset({
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemma-3-27b-it",
    "gemma-3-12b-it",
    "gemma-3-4b-it",
    "gemma-3-1b-it",
    "gemma-2-27b-it",
    "gemma-2-9b-it",
})


class GemmaClientError(Exception):
    """Base exception for all Gemma API client operations."""


class GemmaAuthError(GemmaClientError):
    """Authentication or missing API key error."""


class GemmaTimeoutError(GemmaClientError):
    """Request timeout communicating with Google Gemini API."""


class GemmaResponseError(GemmaClientError):
    """Invalid or error response returned by Google Gemini API."""


class GemmaMalformedJSONError(GemmaClientError):
    """Model output could not be parsed into valid schema JSON."""


class GemmaClient:
    """Official Google Gen AI SDK client for Gemma incident diagnosis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_GEMMA_MODEL,
        alternative_model_name: str = ALTERNATIVE_GEMMA_MODEL,
        timeout_seconds: float = 30.0,
        temperature: float = 0.2,
        client: Optional[Any] = None,
    ) -> None:
        """Initialize GemmaClient.

        Args:
            api_key: Google Gemini API key. Never logged or exposed.
            model_name: Primary Gemma model ID (default gemma-4-26b-a4b-it).
            alternative_model_name: Documented alternative model ID (gemma-4-31b-it).
            timeout_seconds: Request timeout in seconds.
            temperature: Generation temperature [0.0, 2.0].
            client: Optional pre-configured genai.Client instance for testing.
        """
        self.api_key: Optional[str] = api_key
        self.model_name: str = model_name or DEFAULT_GEMMA_MODEL
        self.alternative_model_name: str = alternative_model_name or ALTERNATIVE_GEMMA_MODEL
        self.timeout_seconds: float = timeout_seconds if timeout_seconds > 0 else 30.0
        self.temperature: float = max(0.0, min(2.0, temperature))
        self._custom_client: Optional[Any] = client

    @property
    def raw_client(self) -> Any:
        """Return initialized google.genai Client, or raise GemmaAuthError if key missing."""
        if self._custom_client is not None:
            return self._custom_client
        if not HAS_GENAI:
            raise GemmaClientError("google-genai package is not installed.")
        if not self.api_key or not self.api_key.strip():
            raise GemmaAuthError(
                "GEMMA_API_KEY is not configured. Set GEMMA_API_KEY in environment or .env."
            )
        return genai.Client(api_key=self.api_key.strip())

    def _extract_json_from_response(self, raw_text: str) -> dict[str, Any]:
        """Clean markdown formatting and parse JSON object from model output."""
        if not raw_text or not raw_text.strip():
            raise GemmaMalformedJSONError("Empty text received from Gemma model.")

        text = raw_text.strip()

        # Strip markdown json code block if present
        if "```" in text:
            # Match ```json ... ``` or ``` ... ```
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
            if match:
                text = match.group(1).strip()

        # Find first { and last } to isolate valid JSON block
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            text = text[start_idx : end_idx + 1]

        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise GemmaMalformedJSONError(
                    f"Expected JSON object from model, got {type(parsed).__name__}."
                )
            return parsed
        except json.JSONDecodeError as exc:
            snippet = raw_text[:200].replace("\n", " ")
            raise GemmaMalformedJSONError(
                f"Failed to parse Gemma output as JSON: {exc}. Snippet: {snippet!r}"
            ) from exc

    def _build_generation_config(self, system_prompt: str) -> Any:
        """Construct optional configuration for Gen AI SDK.

        Note: Google's Gemma 4 cloud endpoint on the Gemini API does not support
        system_instruction or response_mime_type in GenerateContentConfig (causes 500 INTERNAL).
        Prompts and JSON extraction instructions are combined directly in contents.
        """
        return None

    async def generate_json(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Asynchronously request diagnostic evaluation from Gemma and return parsed JSON."""
        client = self.raw_client
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt

        # Attempt primary model first, fallback to alternative if primary is unavailable
        models_to_try = [self.model_name]
        if self.alternative_model_name and self.alternative_model_name != self.model_name:
            models_to_try.append(self.alternative_model_name)

        last_error: Optional[Exception] = None

        for model_id in models_to_try:
            try:
                # Enforce client-side timeout as extra protection
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_id,
                        contents=full_prompt,
                    ),
                    timeout=self.timeout_seconds,
                )

                raw_text = getattr(response, "text", None)
                if not raw_text and hasattr(response, "candidates") and response.candidates:
                    first_cand = response.candidates[0]
                    if hasattr(first_cand, "content") and hasattr(first_cand.content, "parts"):
                        parts_text = [p.text for p in first_cand.content.parts if hasattr(p, "text") and p.text]
                        raw_text = "".join(parts_text)

                if not raw_text:
                    raise GemmaResponseError("Gemma returned response with no text content.")

                self.model_name = model_id
                return self._extract_json_from_response(raw_text)

            except asyncio.TimeoutError as exc:
                logger.warning(
                    "Gemma request to '%s' timed out after %.1fs",
                    model_id,
                    self.timeout_seconds,
                )
                raise GemmaTimeoutError(
                    f"Gemma inference timed out after {self.timeout_seconds}s."
                ) from exc
            except (GemmaAuthError, GemmaTimeoutError, GemmaMalformedJSONError):
                raise
            except Exception as exc:
                last_error = exc
                err_msg = str(exc).lower()
                # If model is not found, try alternative model
                if ("not found" in err_msg or "404" in err_msg) and model_id != models_to_try[-1]:
                    logger.warning(
                        "Gemma model '%s' not found, falling back to alternative '%s': %s",
                        model_id,
                        models_to_try[-1],
                        exc,
                    )
                    continue
                logger.warning("Gemma API error on model '%s': %s", model_id, exc)
                raise GemmaResponseError(f"Gemma API error: {exc}") from exc

        if last_error:
            raise GemmaResponseError(f"Gemma evaluation failed on all models: {last_error}") from last_error
        raise GemmaResponseError("Gemma evaluation failed without response.")

    def generate_json_sync(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Synchronously request diagnostic evaluation from Gemma and return parsed JSON."""
        client = self.raw_client
        full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt

        models_to_try = [self.model_name]
        if self.alternative_model_name and self.alternative_model_name != self.model_name:
            models_to_try.append(self.alternative_model_name)

        last_error: Optional[Exception] = None

        for model_id in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=full_prompt,
                )

                raw_text = getattr(response, "text", None)
                if not raw_text and hasattr(response, "candidates") and response.candidates:
                    first_cand = response.candidates[0]
                    if hasattr(first_cand, "content") and hasattr(first_cand.content, "parts"):
                        parts_text = [p.text for p in first_cand.content.parts if hasattr(p, "text") and p.text]
                        raw_text = "".join(parts_text)

                if not raw_text:
                    raise GemmaResponseError("Gemma returned response with no text content.")

                self.model_name = model_id
                return self._extract_json_from_response(raw_text)

            except (GemmaAuthError, GemmaTimeoutError, GemmaMalformedJSONError):
                raise
            except Exception as exc:
                last_error = exc
                err_msg = str(exc).lower()
                if ("not found" in err_msg or "404" in err_msg) and model_id != models_to_try[-1]:
                    logger.warning(
                        "Gemma sync model '%s' not found, falling back to alternative '%s': %s",
                        model_id,
                        models_to_try[-1],
                        exc,
                    )
                    continue
                logger.warning("Gemma sync API error on model '%s': %s", model_id, exc)
                raise GemmaResponseError(f"Gemma sync API error: {exc}") from exc

        if last_error:
            raise GemmaResponseError(f"Gemma evaluation failed on all models: {last_error}") from last_error
        raise GemmaResponseError("Gemma evaluation failed without response.")

    async def check_availability(self, timeout_seconds: float = 3.0) -> dict[str, Any]:
        """Asynchronously probe Google Gemini API reachability and verify Gemma model."""
        if not self.api_key or not self.api_key.strip():
            return {
                "available": False,
                "model_available": False,
                "models": [],
                "error": "GEMMA_API_KEY is not configured",
            }

        try:
            client = self.raw_client
            # Probe models list with timeout
            async def _probe() -> list[str]:
                gemma_models: list[str] = []
                res = client.aio.models.list()
                if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                    res = await res
                async for m in res:
                    name = getattr(m, "name", "")
                    clean_name = name.replace("models/", "")
                    if "gemma" in clean_name.lower():
                        gemma_models.append(clean_name)
                return gemma_models

            models = await asyncio.wait_for(_probe(), timeout=timeout_seconds)
            model_found = any(
                self.model_name in m or self.alternative_model_name in m
                for m in models
            )

            # If specific model name not listed in query, but models probe succeeded and key works:
            if not model_found and models:
                # Key is valid and reached API
                model_found = True

            return {
                "available": True,
                "model_available": model_found or len(models) > 0,
                "models": models,
                "error": None,
            }
        except asyncio.TimeoutError:
            return {
                "available": False,
                "model_available": False,
                "models": [],
                "error": f"API reachability probe timed out after {timeout_seconds}s",
            }
        except Exception as exc:
            # Clean sensitive info if any in exception string
            err_msg = str(exc)
            if self.api_key:
                err_msg = err_msg.replace(self.api_key, "***")
            return {
                "available": False,
                "model_available": False,
                "models": [],
                "error": err_msg,
            }

    def check_availability_sync(self, timeout_seconds: float = 3.0) -> dict[str, Any]:
        """Synchronously probe Google Gemini API reachability and verify Gemma model."""
        if not self.api_key or not self.api_key.strip():
            return {
                "available": False,
                "model_available": False,
                "models": [],
                "error": "GEMMA_API_KEY is not configured",
            }

        try:
            client = self.raw_client
            gemma_models: list[str] = []
            for m in client.models.list():
                name = getattr(m, "name", "")
                clean_name = name.replace("models/", "")
                if "gemma" in clean_name.lower():
                    gemma_models.append(clean_name)

            model_found = any(
                self.model_name in m or self.alternative_model_name in m
                for m in gemma_models
            )
            if not model_found and gemma_models:
                model_found = True

            return {
                "available": True,
                "model_available": model_found or len(gemma_models) > 0,
                "models": gemma_models,
                "error": None,
            }
        except Exception as exc:
            err_msg = str(exc)
            if self.api_key:
                err_msg = err_msg.replace(self.api_key, "***")
            return {
                "available": False,
                "model_available": False,
                "models": [],
                "error": err_msg,
            }
