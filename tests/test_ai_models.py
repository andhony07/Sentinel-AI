"""Unit tests for SentinelAI Pydantic models, prompt construction, and sanitization."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.ai.models import (
    AIDiagnosisRequest,
    AIIncidentDiagnosis,
    ConfidenceLevel,
    ProbableCause,
    RemediationAction,
    SafetyLevel,
)
from app.ai.prompts import build_diagnostic_prompt, sanitize_string
from app.ml.diagnostics import (
    DiagnosticCategory,
    DiagnosticEvidence,
    DiagnosticRecommendation,
    DiagnosticReport,
    EvidenceLevel,
)
from app.ml.models import PredictionResult, RiskCategory


class TestAIModelsValidation:
    """Test suite validating Pydantic models, constraints, and boundaries."""

    def test_valid_ai_incident_diagnosis_model(self) -> None:
        """Verify that a well-formed dictionary instantiates AIIncidentDiagnosis."""
        diagnosis = AIIncidentDiagnosis(
            incident_id="diag_test_001",
            timestamp=datetime.now(timezone.utc),
            status="ANOMALY_DETECTED",
            risk_category="CRITICAL",
            health_score=42.5,
            anomaly_score=0.892,
            incident_summary="Severe CPU saturation driven by stress_worker thread.",
            probable_causes=[
                ProbableCause(
                    rank=1,
                    hypothesis="Infinite compute loop in thread worker.",
                    confidence=ConfidenceLevel.HIGH,
                    supporting_evidence=["CPU at 96.5%", "Process CPU at 92.0%"],
                )
            ],
            investigation_steps=[
                "Inspect process threads via 'top -H -p 1042'."
            ],
            remediation_actions=[
                RemediationAction(
                    step_number=1,
                    action="Gracefully signal process to terminate.",
                    command="kill -15 1042",
                    safety_level=SafetyLevel.CAUTION,
                    precautions="Ensure transaction buffers have flushed before terminating.",
                )
            ],
            uncertainty_assessment="Memory and storage signals nominal; thread-level profiling unobserved.",
            is_fallback=False,
            model_used="qwen2.5:3b",
            latency_ms=1250.0,
        )

        assert diagnosis.incident_id == "diag_test_001"
        assert diagnosis.risk_category == "CRITICAL"
        assert diagnosis.health_score == 42.5
        assert diagnosis.anomaly_score == 0.892
        assert len(diagnosis.probable_causes) == 1
        assert diagnosis.probable_causes[0].confidence == ConfidenceLevel.HIGH
        assert len(diagnosis.remediation_actions) == 1
        assert diagnosis.remediation_actions[0].safety_level == SafetyLevel.CAUTION
        assert diagnosis.is_fallback is False

        # Verify serialization
        data = diagnosis.to_dict()
        assert isinstance(data, dict)
        assert data["incident_id"] == "diag_test_001"
        assert data["health_score"] == 42.5
        assert data["anomaly_score"] == 0.892

    def test_invalid_anomaly_score_boundary(self) -> None:
        """Verify anomaly score > 1.0 or < 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            AIIncidentDiagnosis(
                risk_category="Normal",
                anomaly_score=1.5,  # Exceeds max 1.0
                incident_summary="Test summary",
                uncertainty_assessment="Test uncertainty",
            )

        with pytest.raises(ValidationError):
            AIIncidentDiagnosis(
                risk_category="Normal",
                anomaly_score=-0.1,  # Below min 0.0
                incident_summary="Test summary",
                uncertainty_assessment="Test uncertainty",
            )

    def test_invalid_health_score_boundary(self) -> None:
        """Verify health score > 100.0 or < 0.0 raises ValidationError."""
        with pytest.raises(ValidationError):
            AIIncidentDiagnosis(
                risk_category="Normal",
                anomaly_score=0.2,
                health_score=105.0,  # Exceeds max 100.0
                incident_summary="Test summary",
                uncertainty_assessment="Test uncertainty",
            )

    def test_invalid_confidence_enum(self) -> None:
        """Verify invalid confidence strings fail validation."""
        with pytest.raises(ValidationError):
            ProbableCause(
                rank=1,
                hypothesis="Hypothesis test",
                confidence="EXTREME",  # Invalid enum value
            )

    def test_invalid_safety_level_enum(self) -> None:
        """Verify invalid safety level strings fail validation."""
        with pytest.raises(ValidationError):
            RemediationAction(
                step_number=1,
                action="Action test",
                safety_level="DEADLY",  # Invalid enum value
                precautions="None",
            )

    def test_ai_diagnosis_request_defaults(self) -> None:
        """Verify AIDiagnosisRequest default values and customization."""
        req = AIDiagnosisRequest()
        assert req.scenario is None
        assert req.persist is False
        assert req.force_fallback is False

        req_custom = AIDiagnosisRequest(
            scenario="cpu_spike",
            persist=True,
            force_fallback=True,
        )
        assert req_custom.scenario == "cpu_spike"
        assert req_custom.persist is True
        assert req_custom.force_fallback is True


class TestPromptBuilderAndSanitization:
    """Test suite for prompt engineering, XML delimiters, and input sanitization."""

    def test_sanitize_string_strips_control_chars_and_tags(self) -> None:
        """Verify untrusted strings have control characters and tags stripped."""
        dirty = "process_worker\x00\x08<script>alert('hack')</script>"
        clean = sanitize_string(dirty)
        assert "\x00" not in clean
        assert "<script>" not in clean
        assert "</script>" not in clean

    def test_sanitize_string_length_bound(self) -> None:
        """Verify string length bounds prevent prompt injection overflow."""
        very_long = "A" * 500
        bounded = sanitize_string(very_long, max_length=50)
        assert len(bounded) <= 50
        assert bounded.endswith("...")

    def test_build_diagnostic_prompt_structure(self) -> None:
        """Verify build_diagnostic_prompt creates delimited context without fabrication."""
        pred = PredictionResult(
            timestamp=datetime.now(timezone.utc),
            is_anomaly=True,
            anomaly_score=0.88,
            raw_decision_score=-0.25,
            health_score=38.0,
            risk_category=RiskCategory.CRITICAL,
            model_name="IsolationForestDetector",
            model_version="1.0.0",
        )

        ev = DiagnosticEvidence(
            metric_name="cpu_percent",
            observed_value="96.5%",
            threshold=">= 90.0%",
            level=EvidenceLevel.CRITICAL,
            description="CPU saturation exceeded threshold.",
        )
        rec = DiagnosticRecommendation(
            id="cpu_saturation",
            category=DiagnosticCategory.CPU,
            severity=EvidenceLevel.CRITICAL,
            title="CPU Saturated",
            summary="Host CPU saturated.",
            root_cause_hypothesis="Compute runaway in stress_worker",
            evidence=[ev],
            remediation_steps=["Inspect threads with 'top -H'"],
        )
        diag = DiagnosticReport(
            timestamp=datetime.now(timezone.utc),
            overall_health_score=38.0,
            risk_category=RiskCategory.CRITICAL,
            anomaly_score=0.88,
            is_anomaly=True,
            recommendations=[rec],
            summary_headline="Host Under Critical Pressure",
            primary_concern="CPU",
            critical_count=1,
            warning_count=0,
        )

        metrics = {
            "timestamp": "2026-10-24T12:00:00Z",
            "cpu_percent": 96.5,
            "memory_percent": 45.0,
            "disk_percent": 50.0,
            "top_process_name": "stress_worker",
            "top_process_pid": 1042,
            "top_process_cpu_percent": 92.0,
        }

        system_prompt, user_prompt = build_diagnostic_prompt(
            prediction=pred,
            diagnostic_report=diag,
            metrics=metrics,
        )

        assert "You are SentinelAI" in system_prompt
        assert "<telemetry_context>" in user_prompt
        assert "<ml_evaluation>" in user_prompt
        assert "<empirical_evidence>" in user_prompt
        assert "stress_worker" in user_prompt
        assert "96.5" in user_prompt
        assert "0.88" in user_prompt
        assert "CRITICAL" in user_prompt
