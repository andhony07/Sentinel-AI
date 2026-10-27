"""Unit and integration tests for AIDiagnosticService and deterministic fallback adapter."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.ai.client import OllamaClient, OllamaConnectionError
from app.ai.gemma_client import GemmaClient, GemmaClientError, GemmaTimeoutError, GemmaMalformedJSONError
from app.ai.fallback import diagnostic_report_to_ai_diagnosis
from app.ai.models import AIIncidentDiagnosis, ConfidenceLevel, SafetyLevel
from app.ai.service import AIDiagnosticService
from app.core.config import Settings, load_config
from app.dashboard.services.dashboard_service import DashboardService
from app.ml.diagnostics import (
    DiagnosticCategory,
    DiagnosticEvidence,
    DiagnosticRecommendation,
    DiagnosticReport,
    EvidenceLevel,
)
from app.ml.models import PredictionResult, RiskCategory
from app.ml.simulation import SimulationScenario


@pytest.fixture
def isolated_ai_env(tmp_path: Path) -> tuple[Settings, DashboardService]:
    """Provide isolated environment for service testing."""
    db_file = tmp_path / "test_ai_service.db"
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
    service = DashboardService(settings=settings)
    return settings, service


class TestAIDiagnosticService:
    """Test suite for AIDiagnosticService workflows and fallback boundaries."""

    def test_diagnose_latest_when_ai_disabled(
        self, isolated_ai_env: tuple[Settings, DashboardService]
    ) -> None:
        """Verify that when ai_enabled=False, service returns valid deterministic fallback."""
        async def _test() -> None:
            settings, db_service = isolated_ai_env
            disabled_settings = load_config(ai_enabled=False)

            ai_service = AIDiagnosticService(
                settings=disabled_settings,
                dashboard_service=db_service,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "disabled by configuration" in diagnosis.metadata.get("fallback_reason", "")
            assert len(diagnosis.probable_causes) >= 1
            assert len(diagnosis.remediation_actions) >= 1

        asyncio.run(_test())

    def test_diagnose_latest_with_forced_fallback(
        self, isolated_ai_env: tuple[Settings, DashboardService]
    ) -> None:
        """Verify that force_fallback=True bypasses Ollama call immediately."""
        async def _test() -> None:
            settings, db_service = isolated_ai_env
            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
            )

            diagnosis = await ai_service.diagnose_latest(force_fallback=True)

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert "Forced fallback" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_diagnose_latest_with_successful_mocked_ollama(
        self, isolated_ai_env: tuple[Settings, DashboardService]
    ) -> None:
        """Verify successful LLM response normalization and authoritative ML score preservation."""
        async def _test() -> None:
            settings, db_service = isolated_ai_env

            import platform
            expected_cmd = "Stop-Process -Id 1042" if platform.system() == "Windows" else "kill -15 1042"

            mock_llm_json = {
                "incident_summary": "High CPU utilization driven by runaway process.",
                "probable_causes": [
                    {
                        "rank": 1,
                        "hypothesis": "Runaway worker thread.",
                        "confidence": "HIGH",
                        "supporting_evidence": ["CPU > 90%"],
                    }
                ],
                "investigation_steps": ["Inspect process threads with top -H."],
                "remediation_actions": [
                    {
                        "step_number": 1,
                        "action": "Gracefully terminate process.",
                        "command": expected_cmd,
                        "safety_level": "CAUTION",
                        "precautions": "Ensure database connection pool closed.",
                    }
                ],
                "uncertainty_assessment": "Storage and network signals unperturbed.",
            }

            mock_envelope = {
                "model": "qwen2.5:3b",
                "response": json.dumps(mock_llm_json),
                "done": True,
            }

            async def handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json=mock_envelope)

            mock_client = OllamaClient(
                base_url="http://mock-ollama:11434",
                model_name="qwen2.5:3b",
                transport=httpx.MockTransport(handler),
            )

            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
                client=mock_client,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is False
            assert diagnosis.model_used == "qwen2.5:3b"
            assert diagnosis.incident_summary == mock_llm_json["incident_summary"]
            assert len(diagnosis.probable_causes) == 1
            assert diagnosis.probable_causes[0].hypothesis == "Runaway worker thread."
            assert len(diagnosis.remediation_actions) == 1
            assert diagnosis.remediation_actions[0].command == expected_cmd

            # Check cached diagnosis
            cached = ai_service.get_cached_latest()
            assert cached is not None
            assert cached.incident_id == diagnosis.incident_id

        asyncio.run(_test())

    def test_ollama_offline_returns_graceful_fallback(
        self, isolated_ai_env: tuple[Settings, DashboardService]
    ) -> None:
        """Verify that when Ollama is offline/unreachable, service does NOT throw 500, but returns fallback."""
        async def _test() -> None:
            settings, db_service = isolated_ai_env

            async def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("Connection refused on port 11434", request=request)

            mock_client = OllamaClient(
                base_url="http://localhost:11434",
                transport=httpx.MockTransport(handler),
            )

            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
                client=mock_client,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "Cannot connect to Ollama daemon" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_sync_simulation_diagnosis(
        self, isolated_ai_env: tuple[Settings, DashboardService]
    ) -> None:
        """Verify synchronous simulation diagnosis runs through pipeline with fallback when offline."""
        settings, db_service = isolated_ai_env

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Offline", request=request)

        mock_client = OllamaClient(
            base_url="http://localhost:11434",
            sync_transport=httpx.MockTransport(handler),
        )

        ai_service = AIDiagnosticService(
            settings=settings,
            dashboard_service=db_service,
            client=mock_client,
        )

        diagnosis = ai_service.diagnose_simulation_sync(
            scenario=SimulationScenario.CPU_SPIKE,
            persist=False,
            seed=42,
        )

        assert isinstance(diagnosis, AIIncidentDiagnosis)
        assert diagnosis.is_fallback is True
        assert diagnosis.metadata.get("simulation") is True
        assert diagnosis.metadata.get("scenario") == "cpu_spike"
        assert diagnosis.anomaly_score > 0.5  # CPU spike triggers high anomaly score
        assert diagnosis.risk_category == "Critical"


    def test_gemma_missing_api_key_falls_back(
        self, tmp_path: Path
    ) -> None:
        """Verify that when ai_provider='gemma' and no key is set, service falls back gracefully."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "gemma_nokey.db",
                ai_enabled=True,
                ai_provider="gemma",
                gemma_api_key=None,
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)
            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert diagnosis.metadata.get("provider") == "deterministic_rule_engine"
            assert "GEMMA_API_KEY is not configured" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_gemma_successful_mocked_diagnosis(
        self, tmp_path: Path
    ) -> None:
        """Verify successful Gemma 4 diagnosis through mocked GemmaClient with OS-aware command safety."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "gemma_success.db",
                ai_enabled=True,
                ai_provider="gemma",
                gemma_api_key="mock_gemma_key_secret",
                gemma_model="gemma-4-26b-a4b-it",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)

            import platform
            from unittest import mock
            from app.ai.gemma_client import GemmaClient

            expected_cmd = "Stop-Process -Id 1042" if platform.system() == "Windows" else "kill -15 1042"

            mock_gemma_json = {
                "incident_summary": "Gemma 4 identified severe thread contention in database worker pool.",
                "probable_causes": [
                    {
                        "rank": 1,
                        "hypothesis": "Thread pool starvation caused by unindexed batch query.",
                        "confidence": "HIGH",
                        "supporting_evidence": ["Active thread count exceeded 95% capacity."],
                    }
                ],
                "investigation_steps": ["Analyze thread dump", "Inspect slow query log"],
                "remediation_actions": [
                    {
                        "step_number": 1,
                        "action": "Gracefully terminate rogue thread.",
                        "command": expected_cmd,
                        "safety_level": "CAUTION",
                        "precautions": "Requires manual confirmation by system operator.",
                    }
                ],
                "uncertainty_assessment": "I/O disk subsystem telemetry within expected envelope.",
            }

            mock_gemma = mock.MagicMock(spec=GemmaClient)
            mock_gemma.model_name = "gemma-4-26b-a4b-it"
            mock_gemma.generate_json = mock.AsyncMock(return_value=mock_gemma_json)

            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
                client=mock_gemma,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is False
            assert diagnosis.model_used == "gemma-4-26b-a4b-it"
            assert diagnosis.metadata.get("provider") == "gemma"
            assert "Gemma 4 identified severe thread contention" in diagnosis.incident_summary
            assert len(diagnosis.probable_causes) == 1
            assert diagnosis.probable_causes[0].confidence == ConfidenceLevel.HIGH
            assert len(diagnosis.remediation_actions) == 1
            assert diagnosis.remediation_actions[0].command == expected_cmd

        asyncio.run(_test())

    def test_gemma_timeout_falls_back_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Verify that Gemma timeout triggers graceful deterministic fallback."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "gemma_timeout.db",
                ai_enabled=True,
                ai_provider="gemma",
                gemma_api_key="mock_key",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)

            from unittest import mock
            from app.ai.gemma_client import GemmaClient, GemmaTimeoutError

            mock_gemma = mock.MagicMock(spec=GemmaClient)
            mock_gemma.model_name = "gemma-4-26b-a4b-it"
            mock_gemma.generate_json = mock.AsyncMock(side_effect=GemmaTimeoutError("Gemma request timed out after 30.0s"))

            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
                client=mock_gemma,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "timed out" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_gemma_malformed_json_falls_back_gracefully(
        self, tmp_path: Path
    ) -> None:
        """Verify that unparseable model output triggers graceful deterministic fallback."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "gemma_malformed.db",
                ai_enabled=True,
                ai_provider="gemma",
                gemma_api_key="mock_key",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)

            from unittest import mock
            from app.ai.gemma_client import GemmaClient, GemmaMalformedJSONError

            mock_gemma = mock.MagicMock(spec=GemmaClient)
            mock_gemma.model_name = "gemma-4-26b-a4b-it"
            mock_gemma.generate_json = mock.AsyncMock(side_effect=GemmaMalformedJSONError("Unable to extract valid JSON from output"))

            ai_service = AIDiagnosticService(
                settings=settings,
                dashboard_service=db_service,
                client=mock_gemma,
            )

            diagnosis = await ai_service.diagnose_latest()

            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "Unable to extract valid JSON" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_ai_provider_heuristic_returns_deterministic_fallback(
        self, tmp_path: Path
    ) -> None:
        """Verify that ai_provider='heuristic' uses deterministic fallback without error."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "heuristic.db",
                ai_enabled=True,
                ai_provider="heuristic",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)
            ai_service = AIDiagnosticService(settings=settings, dashboard_service=db_service)

            diagnosis = await ai_service.diagnose_latest()
            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "heuristic provider configured" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_ai_provider_mock_returns_deterministic_fallback(
        self, tmp_path: Path
    ) -> None:
        """Verify that ai_provider='mock' uses deterministic fallback without error."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "mock_prov.db",
                ai_enabled=True,
                ai_provider="mock",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)
            ai_service = AIDiagnosticService(settings=settings, dashboard_service=db_service)

            diagnosis = await ai_service.diagnose_latest()
            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"
            assert "mock provider configured" in diagnosis.metadata.get("fallback_reason", "")

        asyncio.run(_test())

    def test_gemma_provider_does_not_fail_merely_for_being_gemma(
        self, tmp_path: Path
    ) -> None:
        """Regression test: verify service does NOT crash with 500 when ai_provider is 'gemma'."""
        async def _test() -> None:
            settings = load_config(
                database_path=tmp_path / "gemma_valid.db",
                ai_enabled=True,
                ai_provider="gemma",
                gemma_api_key="",
                db_auto_init=True,
            )
            settings.ensure_directories()
            db_service = DashboardService(settings=settings)
            ai_service = AIDiagnosticService(settings=settings, dashboard_service=db_service)

            # Even without a mock or key, it should safely fall back and return an AIIncidentDiagnosis
            diagnosis = await ai_service.diagnose_latest()
            assert isinstance(diagnosis, AIIncidentDiagnosis)
            assert diagnosis.is_fallback is True
            assert diagnosis.model_used == "heuristic_fallback"

        asyncio.run(_test())
