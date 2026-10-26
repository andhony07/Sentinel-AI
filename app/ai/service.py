"""Central coordination service for SentinelAI diagnostic assistant.

Integrates real-time telemetry, ML anomaly inferences, and deterministic diagnostic
rules with local open-weight instruction models via Ollama. Ensures deterministic
graceful fallback and preserves authoritative metric baselines.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, Union

from pydantic import ValidationError

from app.ai.client import (
    OllamaClient,
    OllamaClientError,
    OllamaConnectionError,
    OllamaMalformedJSONError,
    OllamaTimeoutError,
)
from app.ai.gemma_client import (
    GemmaAuthError,
    GemmaClient,
    GemmaClientError,
    GemmaMalformedJSONError,
    GemmaResponseError,
    GemmaTimeoutError,
)
from app.ai.fallback import diagnostic_report_to_ai_diagnosis
from app.ai.models import (
    AIIncidentDiagnosis,
    ConfidenceLevel,
    ProbableCause,
    RemediationAction,
    SafetyLevel,
)
from app.ai.prompts import build_diagnostic_prompt
from app.ai.safety import sanitize_remediation_and_evidence
from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.dashboard.services.dashboard_service import DashboardService
from app.ml.diagnostics import DiagnosticReport
from app.ml.models import PredictionResult, RiskCategory
from app.ml.simulation import SimulationScenario

logger = get_logger("app.ai.service")


class AIDiagnosticService:
    """Coordinates telemetry contextualization and AI incident diagnosis."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        dashboard_service: Optional[DashboardService] = None,
        client: Optional[OllamaClient] = None,
    ) -> None:
        """Initialize AIDiagnosticService.

        Args:
            settings: Application settings container.
            dashboard_service: DashboardService coordinator for telemetry and ML access.
            client: Optional custom OllamaClient.
        """
        self.settings: Settings = settings or get_settings()
        self.dashboard_service: DashboardService = (
            dashboard_service or DashboardService(settings=self.settings)
        )
        if client is not None:
            self.client: Any = client
        elif self.settings.ai_provider == "gemma":
            self.client = GemmaClient(
                api_key=self.settings.gemma_api_key,
                model_name=self.settings.ai_model_name or self.settings.gemma_model,
                alternative_model_name=self.settings.gemma_alternative_model,
                timeout_seconds=self.settings.ai_timeout_seconds,
                temperature=self.settings.ai_temperature,
            )
        elif self.settings.ai_provider == "ollama":
            self.client = OllamaClient(
                base_url=self.settings.ai_base_url,
                model_name=self.settings.ai_model_name,
                timeout_seconds=self.settings.ai_timeout_seconds,
                temperature=self.settings.ai_temperature,
            )
        else:
            # Deterministic providers ("heuristic", "mock") require no external client
            self.client = None

        self._cached_diagnosis: Optional[AIIncidentDiagnosis] = None
        self._cache_lock: threading.Lock = threading.Lock()

    def get_cached_latest(self) -> Optional[AIIncidentDiagnosis]:
        """Retrieve the most recently evaluated diagnosis from thread-safe memory."""
        with self._cache_lock:
            return self._cached_diagnosis

    def _set_cached(self, diag: AIIncidentDiagnosis) -> None:
        """Update the thread-safe in-memory cache with the latest diagnosis."""
        with self._cache_lock:
            self._cached_diagnosis = diag

    def _prepare_telemetry_dict(
        self,
        metric_record: Any,
        feature_record: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Normalize raw metric and feature records into dictionaries for prompt construction."""
        metrics_dict: dict[str, Any] = {}
        if metric_record:
            if hasattr(metric_record, "to_dict"):
                metrics_dict = metric_record.to_dict()
            elif isinstance(metric_record, dict):
                metrics_dict = metric_record
            else:
                # Map attributes directly
                metrics_dict = {
                    "timestamp": (
                        metric_record.timestamp.isoformat()
                        if hasattr(metric_record, "timestamp") and metric_record.timestamp
                        else None
                    ),
                    "cpu_percent": getattr(metric_record, "cpu_percent", None),
                    "memory_percent": getattr(metric_record, "memory_percent", None),
                    "disk_percent": getattr(metric_record, "disk_percent", None),
                    "disk_active_percent": getattr(metric_record, "disk_active_percent", None),
                    "network_bytes_sent_per_sec": getattr(metric_record, "network_bytes_sent_per_sec", None),
                    "network_bytes_recv_per_sec": getattr(metric_record, "network_bytes_recv_per_sec", None),
                    "process_count": getattr(metric_record, "process_count", None),
                    "top_process_name": getattr(metric_record, "top_process_name", None),
                    "top_process_pid": getattr(metric_record, "top_process_pid", None),
                    "top_process_cpu_percent": getattr(metric_record, "top_process_cpu_percent", None),
                    "top_process_memory_percent": getattr(metric_record, "top_process_memory_percent", None),
                }

        features_dict: dict[str, Any] = {}
        if feature_record:
            if hasattr(feature_record, "features"):
                features_dict = dict(feature_record.features)
            elif isinstance(feature_record, dict):
                features_dict = feature_record

        return metrics_dict, features_dict

    def _normalize_and_validate_diagnosis(
        self,
        raw_output: dict[str, Any],
        prediction: Optional[PredictionResult],
        diag_report: Optional[DiagnosticReport],
        latency_ms: float,
        metrics: Optional[dict[str, Any]] = None,
        target_os: Optional[str] = None,
    ) -> AIIncidentDiagnosis:
        """Validate model output against schema, enforce safety guardrails, and authoritative ML values."""
        # 1. Parse probable causes safely
        raw_causes = raw_output.get("probable_causes", [])
        parsed_causes: list[ProbableCause] = []
        if isinstance(raw_causes, list):
            for idx, c in enumerate(raw_causes[:5], start=1):
                if isinstance(c, dict) and "hypothesis" in c:
                    conf = c.get("confidence", "MEDIUM")
                    if conf not in ("HIGH", "MEDIUM", "LOW"):
                        conf = "MEDIUM"
                    evidence = c.get("supporting_evidence", [])
                    if not isinstance(evidence, list):
                        evidence = [str(evidence)]
                    parsed_causes.append(
                        ProbableCause(
                            rank=c.get("rank", idx),
                            hypothesis=str(c["hypothesis"])[:500],
                            confidence=ConfidenceLevel(conf),
                            supporting_evidence=[str(e)[:150] for e in evidence[:10]],
                        )
                    )

        # 2. Parse remediation actions safely
        raw_actions = raw_output.get("remediation_actions", [])
        parsed_actions: list[RemediationAction] = []
        if isinstance(raw_actions, list):
            for idx, a in enumerate(raw_actions[:10], start=1):
                if isinstance(a, dict) and "action" in a:
                    safety = a.get("safety_level", "SAFE")
                    if safety not in ("SAFE", "CAUTION", "CRITICAL"):
                        safety = "SAFE"
                    parsed_actions.append(
                        RemediationAction(
                            step_number=a.get("step_number", idx),
                            action=str(a["action"])[:500],
                            command=str(a["command"])[:500] if a.get("command") else None,
                            safety_level=SafetyLevel(safety),
                            precautions=str(a.get("precautions", "Human operator review required."))[:1000],
                        )
                    )

        # 3. Parse investigation steps safely
        raw_steps = raw_output.get("investigation_steps", [])
        parsed_steps: list[str] = []
        if isinstance(raw_steps, list):
            for s in raw_steps[:10]:
                if s:
                    parsed_steps.append(str(s)[:300])

        # 4. Enforce defense-in-depth operational safety filtering
        sanitized_actions, sanitized_causes, sanitized_steps, safety_notices = (
            sanitize_remediation_and_evidence(
                actions=parsed_actions,
                probable_causes=parsed_causes,
                investigation_steps=parsed_steps,
                telemetry_metrics=metrics,
                target_os=target_os,
            )
        )

        summary = raw_output.get("incident_summary") or (
            diag_report.summary_headline if diag_report else "Evaluation complete."
        )
        uncertainty = raw_output.get("uncertainty_assessment") or (
            "Telemetry signals evaluated within available hardware metrics."
        )
        if safety_notices:
            notices_str = " ".join(safety_notices)
            uncertainty = f"{uncertainty} [Safety Policy: {notices_str}]"

        # Authoritative overrides: Model cannot fabricate risk category or ML anomaly scores
        auth_risk = (
            prediction.risk_category.value
            if prediction
            else (
                diag_report.risk_category.value
                if diag_report
                else RiskCategory.NORMAL.value
            )
        )
        auth_score = (
            prediction.health_score
            if prediction
            else (diag_report.overall_health_score if diag_report else None)
        )
        auth_anom = (
            prediction.anomaly_score
            if prediction
            else (diag_report.anomaly_score if diag_report else 0.0)
        )
        is_anom = (
            prediction.is_anomaly
            if prediction
            else (diag_report.is_anomaly if diag_report else False)
        )

        status = "ANOMALY_DETECTED" if is_anom else "NOMINAL"

        return AIIncidentDiagnosis(
            incident_id=f"diag_ai_{int(time.time())}",
            timestamp=prediction.timestamp if prediction else datetime.now(timezone.utc),
            status=status,
            risk_category=auth_risk,
            health_score=auth_score,
            anomaly_score=auth_anom,
            incident_summary=str(summary)[:2000],
            probable_causes=sanitized_causes,
            investigation_steps=sanitized_steps,
            remediation_actions=sanitized_actions,
            uncertainty_assessment=str(uncertainty)[:2000],
            is_fallback=False,
            model_used=self.client.model_name,
            latency_ms=latency_ms,
            metadata={
                "provider": self.settings.ai_provider,
                "raw_model": self.client.model_name,
                "safety_notices": safety_notices,
            },
        )

    # -------------------------------------------------------------------------
    # Core Diagnostics Evaluation Workflows
    # -------------------------------------------------------------------------

    async def diagnose_latest(self, force_fallback: bool = False) -> AIIncidentDiagnosis:
        """Asynchronously diagnose latest system telemetry.

        Args:
            force_fallback: If True, bypasses LLM and returns deterministic fallback.

        Returns:
            Populated AIIncidentDiagnosis instance.
        """
        start_time = time.perf_counter()

        # 1. Fetch latest telemetry, feature vector, and ML prediction
        latest_metric = self.dashboard_service.get_latest_metrics()
        latest_feat = self.dashboard_service.get_latest_feature_vector()
        prediction = self.dashboard_service.get_latest_prediction()
        diag_report = self.dashboard_service.get_diagnostics_for_latest()

        metrics_dict, features_dict = self._prepare_telemetry_dict(
            latest_metric, latest_feat
        )

        # 2. Check if AI should be bypassed or unconfigured
        # 2. Check if AI should be bypassed or unconfigured
        ai_enabled = self.settings.ai_enabled and not force_fallback
        if not ai_enabled:
            reason = "AI disabled by configuration" if not self.settings.ai_enabled else "Forced fallback requested"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        # Check if provider is explicitly deterministic or client is unset
        if self.settings.ai_provider in ("heuristic", "mock") or self.client is None:
            reason = f"Deterministic fallback active: {self.settings.ai_provider} provider configured"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        # If Gemma is active but GEMMA_API_KEY is missing, engage deterministic fallback immediately
        if self.settings.ai_provider == "gemma" and not self.settings.gemma_api_key and not getattr(self.client, "_custom_client", None):
            reason = "GEMMA_API_KEY is not configured; deterministic fallback active"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        # 3. Build prompts and call Ollama asynchronously
        system_prompt, user_prompt = build_diagnostic_prompt(
            prediction=prediction,
            diagnostic_report=diag_report,
            metrics=metrics_dict,
            features=features_dict,
        )

        try:
            raw_output = await self.client.generate_json(system_prompt, user_prompt)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = self._normalize_and_validate_diagnosis(
                raw_output, prediction, diag_report, latency, metrics=metrics_dict
            )
        except (GemmaClientError, OllamaClientError, Exception) as exc:
            provider_label = "Gemma" if self.settings.ai_provider == "gemma" else "Ollama"
            logger.warning("%s diagnosis failed, engaging deterministic fallback: %s", provider_label, exc)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=str(exc),
                latency_ms=latency,
            )

        self._set_cached(diagnosis)
        return diagnosis

    def diagnose_latest_sync(self, force_fallback: bool = False) -> AIIncidentDiagnosis:
        """Synchronously diagnose latest system telemetry (for Streamlit and CLI)."""
        start_time = time.perf_counter()

        latest_metric = self.dashboard_service.get_latest_metrics()
        latest_feat = self.dashboard_service.get_latest_feature_vector()
        prediction = self.dashboard_service.get_latest_prediction()
        diag_report = self.dashboard_service.get_diagnostics_for_latest()

        metrics_dict, features_dict = self._prepare_telemetry_dict(
            latest_metric, latest_feat
        )

        # 2. Check if AI should be bypassed or unconfigured
        ai_enabled = self.settings.ai_enabled and not force_fallback
        if not ai_enabled:
            reason = "AI disabled by configuration" if not self.settings.ai_enabled else "Forced fallback requested"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        # Check if provider is explicitly deterministic or client is unset
        if self.settings.ai_provider in ("heuristic", "mock") or self.client is None:
            reason = f"Deterministic fallback active: {self.settings.ai_provider} provider configured"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        # If Gemma is active but GEMMA_API_KEY is missing, engage deterministic fallback immediately
        if self.settings.ai_provider == "gemma" and not self.settings.gemma_api_key and not getattr(self.client, "_custom_client", None):
            reason = "GEMMA_API_KEY is not configured; deterministic fallback active"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=reason,
                latency_ms=latency,
            )
            self._set_cached(diagnosis)
            return diagnosis

        system_prompt, user_prompt = build_diagnostic_prompt(
            prediction=prediction,
            diagnostic_report=diag_report,
            metrics=metrics_dict,
            features=features_dict,
        )

        try:
            raw_output = self.client.generate_json_sync(system_prompt, user_prompt)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = self._normalize_and_validate_diagnosis(
                raw_output, prediction, diag_report, latency, metrics=metrics_dict
            )
        except (GemmaClientError, OllamaClientError, Exception) as exc:
            provider_label = "Gemma" if self.settings.ai_provider == "gemma" else "Ollama"
            logger.warning("%s sync diagnosis failed, engaging deterministic fallback: %s", provider_label, exc)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=prediction,
                fallback_reason=str(exc),
                latency_ms=latency,
            )

        self._set_cached(diagnosis)
        return diagnosis

    async def diagnose_simulation(
        self,
        scenario: Union[SimulationScenario, str],
        persist: bool = False,
        seed: int = 42,
        force_fallback: bool = False,
        **overrides: Any,
    ) -> AIIncidentDiagnosis:
        """Asynchronously execute an anomaly simulation and generate an AI diagnosis report."""
        start_time = time.perf_counter()

        scenario_key = scenario.value if hasattr(scenario, "value") else str(scenario)
        sim_res, diag_report = self.dashboard_service.run_simulation(
            scenario=scenario,
            persist=persist,
            seed=seed,
            **overrides,
        )

        metrics_dict, features_dict = self._prepare_telemetry_dict(
            sim_res.metrics, sim_res.processed.feature_vector
        )

        ai_enabled = self.settings.ai_enabled and not force_fallback
        if not ai_enabled:
            reason = "AI disabled by configuration" if not self.settings.ai_enabled else "Forced fallback requested"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=sim_res.prediction,
                fallback_reason=reason,
                latency_ms=latency,
                metadata={"scenario": scenario_key, "simulation": True},
            )
            self._set_cached(diagnosis)
            return diagnosis

        system_prompt, user_prompt = build_diagnostic_prompt(
            prediction=sim_res.prediction,
            diagnostic_report=diag_report,
            metrics=metrics_dict,
            features=features_dict,
            context_note=f"Executed synthetic simulation scenario: '{scenario_key}'.",
        )

        try:
            raw_output = await self.client.generate_json(system_prompt, user_prompt)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = self._normalize_and_validate_diagnosis(
                raw_output, sim_res.prediction, diag_report, latency, metrics=metrics_dict
            )
            diagnosis.metadata["scenario"] = scenario_key
            diagnosis.metadata["simulation"] = True
        except (GemmaClientError, OllamaClientError, Exception) as exc:
            provider_label = "Gemma" if self.settings.ai_provider == "gemma" else "Ollama"
            logger.warning("Simulation %s diagnosis failed, engaging fallback: %s", provider_label, exc)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=sim_res.prediction,
                fallback_reason=str(exc),
                latency_ms=latency,
                metadata={"scenario": scenario_key, "simulation": True},
            )

        self._set_cached(diagnosis)
        return diagnosis

    def diagnose_simulation_sync(
        self,
        scenario: Union[SimulationScenario, str],
        persist: bool = False,
        seed: int = 42,
        force_fallback: bool = False,
        **overrides: Any,
    ) -> AIIncidentDiagnosis:
        """Synchronously execute an anomaly simulation and generate an AI diagnosis report."""
        start_time = time.perf_counter()
        scenario_key = scenario.value if hasattr(scenario, "value") else str(scenario)

        sim_res, diag_report = self.dashboard_service.run_simulation(
            scenario=scenario,
            persist=persist,
            seed=seed,
            **overrides,
        )

        metrics_dict, features_dict = self._prepare_telemetry_dict(
            sim_res.metrics, sim_res.processed.feature_vector
        )

        ai_enabled = self.settings.ai_enabled and not force_fallback
        if not ai_enabled:
            reason = "AI disabled by configuration" if not self.settings.ai_enabled else "Forced fallback requested"
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=sim_res.prediction,
                fallback_reason=reason,
                latency_ms=latency,
                metadata={"scenario": scenario_key, "simulation": True},
            )
            self._set_cached(diagnosis)
            return diagnosis

        system_prompt, user_prompt = build_diagnostic_prompt(
            prediction=sim_res.prediction,
            diagnostic_report=diag_report,
            metrics=metrics_dict,
            features=features_dict,
            context_note=f"Executed synthetic simulation scenario: '{scenario_key}'.",
        )

        try:
            raw_output = self.client.generate_json_sync(system_prompt, user_prompt)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = self._normalize_and_validate_diagnosis(
                raw_output, sim_res.prediction, diag_report, latency, metrics=metrics_dict
            )
            diagnosis.metadata["scenario"] = scenario_key
            diagnosis.metadata["simulation"] = True
        except (OllamaClientError, Exception) as exc:
            logger.warning("Sync simulation AI diagnosis failed, engaging fallback: %s", exc)
            latency = (time.perf_counter() - start_time) * 1000.0
            diagnosis = diagnostic_report_to_ai_diagnosis(
                diagnostic_report=diag_report,
                prediction=sim_res.prediction,
                fallback_reason=str(exc),
                latency_ms=latency,
                metadata={"scenario": scenario_key, "simulation": True},
            )

        self._set_cached(diagnosis)
        return diagnosis
