"""Integration tests for AI Diagnostic Assistant FastAPI REST endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.ai.client import OllamaClient
from app.ai.service import AIDiagnosticService
from app.api.dependencies import (
    get_ai_diagnostic_service,
    get_api_settings,
    get_dashboard_service,
)
from app.api.main import create_app
from app.core.config import Settings, load_config
from app.dashboard.services.dashboard_service import DashboardService


@pytest.fixture
def ai_api_client(tmp_path: Path) -> Generator[tuple[TestClient, AIDiagnosticService, Settings], None, None]:
    """Create test client with isolated database and mocked Ollama client."""
    db_file = tmp_path / "test_ai_api.db"
    settings = load_config(
        database_path=db_file,
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        ai_enabled=True,
        ai_provider="ollama",
        ai_model_name="qwen2.5:3b",
        db_auto_init=True,
    )
    settings.ensure_directories()

    dash_service = DashboardService(settings=settings)

    # Mock Ollama transport returning valid diagnosis JSON
    mock_llm_json = {
        "incident_summary": "System healthy under nominal load.",
        "probable_causes": [
            {
                "rank": 1,
                "hypothesis": "Nominal operations within tolerances.",
                "confidence": "HIGH",
                "supporting_evidence": ["All signals nominal."],
            }
        ],
        "investigation_steps": ["Maintain standard telemetry polling."],
        "remediation_actions": [
            {
                "step_number": 1,
                "action": "No operational remediation required.",
                "command": None,
                "safety_level": "SAFE",
                "precautions": "Routine maintenance.",
            }
        ],
        "uncertainty_assessment": "Nominal hardware telemetry bounds.",
    }

    mock_envelope = {
        "model": "qwen2.5:3b",
        "response": json.dumps(mock_llm_json),
        "done": True,
    }

    async def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_envelope)

    mock_client = OllamaClient(
        base_url="http://mock-ollama:11434",
        model_name="qwen2.5:3b",
        transport=httpx.MockTransport(mock_handler),
    )

    ai_service = AIDiagnosticService(
        settings=settings,
        dashboard_service=dash_service,
        client=mock_client,
    )

    app = create_app(settings=settings)
    app.dependency_overrides[get_api_settings] = lambda: settings
    app.dependency_overrides[get_dashboard_service] = lambda: dash_service
    app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

    with TestClient(app) as client:
        yield client, ai_service, settings

    app.dependency_overrides.clear()


class TestAIDiagnosticEndpoints:
    """Test suite for /api/ai routes."""

    def test_get_ai_status(self, ai_api_client: tuple[TestClient, AIDiagnosticService, Settings]) -> None:
        """Verify GET /api/ai/status returns configuration, readiness, and fallback status."""
        client, _, settings = ai_api_client
        resp = client.get("/api/ai/status?check_ollama=false")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["enabled"] is True
        assert data["provider"] == "ollama"
        assert data["model_name"] == "qwen2.5:3b"
        assert "has_cached_diagnosis" in data
        assert "fallback_active" in data
        assert "cached_diagnosis_source" in data


    def test_post_ai_diagnose_latest_mocked(
        self, ai_api_client: tuple[TestClient, AIDiagnosticService, Settings]
    ) -> None:
        """Verify POST /api/ai/diagnose returns structured AI diagnosis."""
        client, _, _ = ai_api_client
        resp = client.post("/api/ai/diagnose", json={})
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "incident_id" in data
        assert "incident_summary" in data
        assert "probable_causes" in data
        assert "remediation_actions" in data
        assert "uncertainty_assessment" in data
        assert data["is_fallback"] is False
        assert data["model_used"] == "qwen2.5:3b"

    def test_post_ai_diagnose_simulation(
        self, ai_api_client: tuple[TestClient, AIDiagnosticService, Settings]
    ) -> None:
        """Verify POST /api/ai/diagnose with simulation scenario payload."""
        client, _, _ = ai_api_client
        payload = {
            "scenario": "cpu_spike",
            "persist": False,
            "force_fallback": False,
        }
        resp = client.post("/api/ai/diagnose", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "incident_id" in data
        assert data["metadata"].get("simulation") is True
        assert data["metadata"].get("scenario") == "cpu_spike"

    def test_post_ai_diagnose_forced_fallback(
        self, ai_api_client: tuple[TestClient, AIDiagnosticService, Settings]
    ) -> None:
        """Verify POST /api/ai/diagnose with force_fallback=True returns fallback."""
        client, _, _ = ai_api_client
        payload = {"force_fallback": True}
        resp = client.post("/api/ai/diagnose", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["is_fallback"] is True
        assert data["model_used"] == "heuristic_fallback"

    def test_get_ai_latest_cached_or_fresh(
        self, ai_api_client: tuple[TestClient, AIDiagnosticService, Settings]
    ) -> None:
        """Verify GET /api/ai/latest retrieves latest diagnosis."""
        client, _, _ = ai_api_client
        # First trigger diagnosis
        post_resp = client.post("/api/ai/diagnose", json={})
        assert post_resp.status_code == status.HTTP_200_OK
        first_id = post_resp.json()["incident_id"]

        # Now GET latest should return the cached diagnosis
        get_resp = client.get("/api/ai/latest")
        assert get_resp.status_code == status.HTTP_200_OK
        assert get_resp.json()["incident_id"] == first_id

    def test_ai_offline_returns_graceful_fallback_200(self, tmp_path: Path) -> None:
        """Verify that when Ollama is offline, POST /api/ai/diagnose returns 200 with fallback."""
        settings = load_config(
            database_path=tmp_path / "offline_ai.db",
            ai_enabled=True,
            ai_provider="ollama",
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)

        async def offline_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Offline", request=request)

        mock_offline_client = OllamaClient(
            base_url="http://localhost:11434",
            transport=httpx.MockTransport(offline_handler),
        )

        offline_ai_service = AIDiagnosticService(
            settings=settings,
            dashboard_service=dash_service,
            client=mock_offline_client,
        )

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: offline_ai_service

        with TestClient(app) as client:
            resp = client.post("/api/ai/diagnose", json={})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["is_fallback"] is True
            assert data["model_used"] == "heuristic_fallback"
            assert "Cannot connect to Ollama daemon" in data["metadata"].get("fallback_reason", "")

    def test_get_ai_status_gemma(self, tmp_path: Path) -> None:
        """Verify GET /api/ai/status when Gemma is configured as primary provider."""
        settings = load_config(
            database_path=tmp_path / "gemma_status.db",
            ai_enabled=True,
            ai_provider="gemma",
            gemma_model="gemma-4-26b-a4b-it",
            gemma_api_key="secret_test_key_12345",
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)
        ai_service = AIDiagnosticService(settings=settings, dashboard_service=dash_service)

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.get("/api/ai/status?check_gemma=false")
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["enabled"] is True
            assert data["provider"] == "gemma"
            assert data["model_name"] == "gemma-4-26b-a4b-it"
            assert data["has_api_key"] is True
            # CRITICAL: Verify secret key is never leaked in status response
            assert "secret_test_key_12345" not in json.dumps(data)

    def test_post_ai_diagnose_gemma_mocked(self, tmp_path: Path) -> None:
        """Verify POST /api/ai/diagnose returns 200 with Gemma model diagnosis."""
        from unittest import mock
        from app.ai.gemma_client import GemmaClient

        settings = load_config(
            database_path=tmp_path / "gemma_route_mock.db",
            ai_enabled=True,
            ai_provider="gemma",
            gemma_model="gemma-4-26b-a4b-it",
            gemma_api_key="mock_key",
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)

        mock_gemma_json = {
            "incident_summary": "Gemma 4 evaluated compute anomalies under simulated saturation.",
            "probable_causes": [
                {
                    "rank": 1,
                    "hypothesis": "Burst telemetry ingestion loop.",
                    "confidence": "HIGH",
                    "supporting_evidence": ["CPU spike to 92%"],
                }
            ],
            "investigation_steps": ["Inspect telemetry worker logs"],
            "remediation_actions": [
                {
                    "step_number": 1,
                    "action": "Audit batch sizes.",
                    "command": None,
                    "safety_level": "SAFE",
                    "precautions": "Non-destructive read-only audit.",
                }
            ],
            "uncertainty_assessment": "Host telemetry envelope nominal.",
        }

        mock_gemma = mock.MagicMock(spec=GemmaClient)
        mock_gemma.model_name = "gemma-4-26b-a4b-it"
        mock_gemma.generate_json = mock.AsyncMock(return_value=mock_gemma_json)

        ai_service = AIDiagnosticService(
            settings=settings,
            dashboard_service=dash_service,
            client=mock_gemma,
        )

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.post("/api/ai/diagnose", json={})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["is_fallback"] is False
            assert data["model_used"] == "gemma-4-26b-a4b-it"
            assert "Gemma 4 evaluated compute anomalies" in data["incident_summary"]
            assert len(data["probable_causes"]) == 1
            assert data["remediation_actions"][0]["safety_level"] == "SAFE"

    def test_post_ai_diagnose_gemma_missing_key_returns_fallback_200(self, tmp_path: Path) -> None:
        """Verify POST /api/ai/diagnose returns 200 with fallback when GEMMA_API_KEY is not configured."""
        settings = load_config(
            database_path=tmp_path / "gemma_no_key_route.db",
            ai_enabled=True,
            ai_provider="gemma",
            gemma_model="gemma-4-26b-a4b-it",
            gemma_api_key=None,
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)
        ai_service = AIDiagnosticService(settings=settings, dashboard_service=dash_service)

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.post("/api/ai/diagnose", json={})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["is_fallback"] is True
            assert data["model_used"] == "heuristic_fallback"
            assert "GEMMA_API_KEY is not configured" in data["metadata"].get("fallback_reason", "")

    def test_post_ai_diagnose_heuristic_provider_200(self, tmp_path: Path) -> None:
        """Verify POST /api/ai/diagnose returns 200 with deterministic fallback when provider is 'heuristic'."""
        settings = load_config(
            database_path=tmp_path / "heuristic_route.db",
            ai_enabled=True,
            ai_provider="heuristic",
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)
        ai_service = AIDiagnosticService(settings=settings, dashboard_service=dash_service)

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.post("/api/ai/diagnose", json={})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["is_fallback"] is True
            assert data["model_used"] == "heuristic_fallback"
            assert "heuristic provider configured" in data["metadata"].get("fallback_reason", "")

    def test_get_ai_status_heuristic_provider_200(self, tmp_path: Path) -> None:
        """Verify GET /api/ai/status returns 200 without error when provider is 'heuristic'."""
        settings = load_config(
            database_path=tmp_path / "heuristic_status.db",
            ai_enabled=True,
            ai_provider="heuristic",
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)
        ai_service = AIDiagnosticService(settings=settings, dashboard_service=dash_service)

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.get("/api/ai/status")
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["provider"] == "heuristic"
            assert data["fallback_active"] is True

    def test_gemma_provider_route_never_fails_500_merely_for_being_gemma(self, tmp_path: Path) -> None:
        """Regression test: verify POST /api/ai/diagnose never throws 500 when ai_provider is 'gemma'."""
        settings = load_config(
            database_path=tmp_path / "gemma_no500.db",
            ai_enabled=True,
            ai_provider="gemma",
            gemma_api_key=None,
            db_auto_init=True,
        )
        settings.ensure_directories()
        dash_service = DashboardService(settings=settings)
        ai_service = AIDiagnosticService(settings=settings, dashboard_service=dash_service)

        app = create_app(settings=settings)
        app.dependency_overrides[get_api_settings] = lambda: settings
        app.dependency_overrides[get_dashboard_service] = lambda: dash_service
        app.dependency_overrides[get_ai_diagnostic_service] = lambda: ai_service

        with TestClient(app) as client:
            resp = client.post("/api/ai/diagnose", json={})
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert data["is_fallback"] is True
            assert data["model_used"] == "heuristic_fallback"
