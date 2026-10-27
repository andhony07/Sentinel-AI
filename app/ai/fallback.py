"""Deterministic fallback adapter for SentinelAI diagnostic assistant.

Converts existing DiagnosticEngine reports and ML PredictionResult objects into
the standardized AIIncidentDiagnosis schema when generative AI (Ollama) is
disabled, unreachable, times out, or produces malformed output.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.ai.models import (
    AIIncidentDiagnosis,
    ConfidenceLevel,
    ProbableCause,
    RemediationAction,
    SafetyLevel,
)
from app.ai.safety import sanitize_remediation_and_evidence
from app.ml.diagnostics import DiagnosticReport, EvidenceLevel
from app.ml.models import PredictionResult, RiskCategory


def _map_evidence_level_to_confidence(level: EvidenceLevel) -> ConfidenceLevel:
    """Map diagnostic evidence severity to hypothesis confidence."""
    if level in (EvidenceLevel.CRITICAL, EvidenceLevel.HIGH):
        return ConfidenceLevel.HIGH
    if level == EvidenceLevel.MODERATE:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _map_step_to_safety_level(step_text: str) -> tuple[SafetyLevel, str]:
    """Classify remediation step safety level and attach appropriate precautions."""
    step_lower = step_text.lower()
    if any(k in step_lower for k in ("kill", "terminate", "stop service", "restart")):
        return (
            SafetyLevel.CAUTION,
            "Service interruption risk. Verify process identity and active connections before terminating or restarting.",
        )
    if any(k in step_lower for k in ("delete", "purge", "truncate", "drop")):
        return (
            SafetyLevel.CRITICAL,
            "Data loss risk. Ensure recent backups exist before purging persistent volumes or cache files.",
        )
    return (
        SafetyLevel.SAFE,
        "Non-destructive diagnostic action. Safe to execute in production environments.",
    )


def diagnostic_report_to_ai_diagnosis(
    diagnostic_report: Optional[DiagnosticReport] = None,
    prediction: Optional[PredictionResult] = None,
    fallback_reason: str = "Generative AI service unavailable",
    latency_ms: float = 0.0,
    metadata: Optional[dict[str, Any]] = None,
) -> AIIncidentDiagnosis:
    """Convert DiagnosticReport into standardized AIIncidentDiagnosis.

    Guarantees that when Ollama is offline or disabled, operators receive an
    empirically grounded, structured diagnosis without errors.

    Args:
        diagnostic_report: Authoritative DiagnosticReport from DiagnosticEngine.
        prediction: Authoritative PredictionResult from PredictionService.
        fallback_reason: Human-readable explanation of why fallback was engaged.
        latency_ms: Execution duration in milliseconds.
        metadata: Optional auxiliary tracking metadata.

    Returns:
        Fully populated AIIncidentDiagnosis conforming to schema.
    """
    ts = (
        diagnostic_report.timestamp
        if diagnostic_report
        else (prediction.timestamp if prediction else datetime.now(timezone.utc))
    )
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    # Resolve authoritative ML metrics
    is_anomaly = (
        prediction.is_anomaly
        if prediction
        else (diagnostic_report.is_anomaly if diagnostic_report else False)
    )
    anomaly_score = (
        prediction.anomaly_score
        if prediction
        else (diagnostic_report.anomaly_score if diagnostic_report else 0.0)
    )
    risk_cat = (
        prediction.risk_category.value
        if prediction
        else (
            diagnostic_report.risk_category.value
            if diagnostic_report
            else RiskCategory.NORMAL.value
        )
    )
    health_score = (
        prediction.health_score
        if prediction
        else (diagnostic_report.overall_health_score if diagnostic_report else 100.0)
    )

    # Determine status label
    if is_anomaly or (prediction and prediction.risk_category in (RiskCategory.CRITICAL, RiskCategory.HIGH)):
        status = "ANOMALY_DETECTED"
    elif diagnostic_report and (diagnostic_report.critical_count > 0 or diagnostic_report.warning_count > 0):
        status = "RESOURCE_PRESSURE"
    else:
        status = "NOMINAL"

    # Build incident summary
    if diagnostic_report and diagnostic_report.summary_headline:
        incident_summary = diagnostic_report.summary_headline
        if diagnostic_report.primary_concern and diagnostic_report.primary_concern != "Nominal":
            incident_summary += f" Primary operational concern: {diagnostic_report.primary_concern}."
    else:
        incident_summary = (
            "System telemetry operates within normal baseline tolerances. "
            "No anomalous hardware resource pressure detected."
        )

    # Build probable causes and remediation actions from recommendations
    probable_causes: list[ProbableCause] = []
    investigation_steps: list[str] = []
    remediation_actions: list[RemediationAction] = []
    action_counter = 1

    if diagnostic_report and diagnostic_report.recommendations:
        for idx, rec in enumerate(diagnostic_report.recommendations[:5], start=1):
            evidence_summaries = [
                f"{ev.metric_name}: observed {ev.observed_value} ({ev.description})"
                for ev in rec.evidence
            ]
            probable_causes.append(
                ProbableCause(
                    rank=idx,
                    hypothesis=rec.root_cause_hypothesis or rec.summary,
                    confidence=_map_evidence_level_to_confidence(rec.severity),
                    supporting_evidence=evidence_summaries,
                )
            )

            # Process remediation steps
            for step in rec.remediation_steps:
                if any(w in step.lower() for w in ("inspect", "review", "check", "top", "htop", "monitor")):
                    if step not in investigation_steps:
                        investigation_steps.append(step)
                else:
                    safety_lvl, precaution_text = _map_step_to_safety_level(step)
                    cmd = None
                    if "'" in step:
                        parts = step.split("'")
                        if len(parts) >= 2 and parts[1].strip():
                            cmd = parts[1].strip()

                    remediation_actions.append(
                        RemediationAction(
                            step_number=action_counter,
                            action=step,
                            command=cmd,
                            safety_level=safety_lvl,
                            precautions=precaution_text,
                        )
                    )
                    action_counter += 1

    # Ensure at least one nominal entry if empty
    if not probable_causes:
        probable_causes.append(
            ProbableCause(
                rank=1,
                hypothesis="System telemetry operates within nominal expected baselines.",
                confidence=ConfidenceLevel.HIGH,
                supporting_evidence=["All monitored subsystem signals remain below warning thresholds."],
            )
        )

    if not investigation_steps:
        investigation_steps.append(
            "Continue periodic host telemetry sampling; verify background monitoring worker remains active."
        )

    if not remediation_actions:
        remediation_actions.append(
            RemediationAction(
                step_number=1,
                action="No immediate remediation required. System operational status is healthy.",
                command=None,
                safety_level=SafetyLevel.SAFE,
                precautions="Routine operational baseline maintenance.",
            )
        )

    # Enforce defense-in-depth safety guardrails across fallback output
    remediation_actions, probable_causes, investigation_steps, safety_notices = (
        sanitize_remediation_and_evidence(
            actions=remediation_actions,
            probable_causes=probable_causes,
            investigation_steps=investigation_steps,
        )
    )

    # Uncertainty assessment statement
    uncertainty_statement = (
        f"Deterministic diagnostic evaluation generated via heuristic rules engine. "
        f"Generative AI fallback engaged: {fallback_reason}. "
        f"Findings are grounded in deterministic metric limits and Isolation Forest anomaly scoring."
    )
    if safety_notices:
        uncertainty_statement += f" [Safety Policy: {' '.join(safety_notices)}]"

    meta = dict(metadata or {})
    meta["fallback_reason"] = fallback_reason
    meta["provider"] = "deterministic_rule_engine"
    if safety_notices:
        meta["safety_notices"] = safety_notices

    return AIIncidentDiagnosis(
        incident_id=f"diag_fallback_{uuid.uuid4().hex[:8]}",
        timestamp=ts,
        status=status,
        risk_category=risk_cat,
        health_score=health_score,
        anomaly_score=anomaly_score,
        incident_summary=incident_summary,
        probable_causes=probable_causes,
        investigation_steps=investigation_steps[:10],
        remediation_actions=remediation_actions[:10],
        uncertainty_assessment=uncertainty_statement,
        is_fallback=True,
        model_used="heuristic_fallback",
        latency_ms=latency_ms,
        fallback_reason=fallback_reason,
        metadata=meta,
    )
