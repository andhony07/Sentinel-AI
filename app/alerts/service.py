"""Risk alert service coordinating incident lifecycle, deduplication, diagnostics, and notifications."""

from __future__ import annotations

import logging
import socket
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.alerts.models import AlertSeverity, AlertStatus, AlertSummaryResponse, RiskAlertSchema
from app.alerts.repository import AlertRepository
from app.core.config import Settings, get_settings
from app.database.models import RiskAlertRecord
from app.ml.diagnostics import DiagnosticEngine
from app.ml.prediction_service import PredictionResult
from app.ml.risk_analyzer import RiskCategory

logger = logging.getLogger("sentinel.alerts")


class AlertService:
    """Manages the authoritative lifecycle of server health risk alerts."""

    def __init__(
        self,
        repository: Optional[AlertRepository] = None,
        diagnostic_engine: Optional[DiagnosticEngine] = None,
        settings: Optional[Settings] = None,
        server_id: Optional[str] = None,
    ) -> None:
        self.settings: Settings = settings or get_settings()
        self.repository: AlertRepository = repository or AlertRepository(settings=self.settings)
        self.diagnostic_engine: DiagnosticEngine = diagnostic_engine or DiagnosticEngine()
        self.server_id: str = server_id or getattr(self.settings, "server_id", None) or socket.gethostname()
        self._lock = threading.Lock()

    def _determine_trigger(
        self,
        prediction: PredictionResult,
        metrics: Optional[Any] = None,
    ) -> tuple[str, Optional[float], str]:
        """Extract triggering metric, float value, and human-readable string representation."""
        if metrics is not None:
            # Check CPU
            cpu_val = None
            if hasattr(metrics, "cpu") and metrics.cpu is not None and hasattr(metrics.cpu, "utilization_percent"):
                cpu_val = float(metrics.cpu.utilization_percent)
            elif hasattr(metrics, "cpu_percent") and metrics.cpu_percent is not None:
                cpu_val = float(metrics.cpu_percent)

            # Check Memory
            mem_val = None
            if hasattr(metrics, "memory") and metrics.memory is not None and hasattr(metrics.memory, "utilization_percent"):
                mem_val = float(metrics.memory.utilization_percent)
            elif hasattr(metrics, "memory_percent") and metrics.memory_percent is not None:
                mem_val = float(metrics.memory_percent)

            # Check Disk
            disk_val = None
            if hasattr(metrics, "disk") and metrics.disk is not None and hasattr(metrics.disk, "utilization_percent"):
                disk_val = float(metrics.disk.utilization_percent)
            elif hasattr(metrics, "disk_percent") and metrics.disk_percent is not None:
                disk_val = float(metrics.disk_percent)

            if cpu_val is not None and cpu_val >= 90.0:
                return "CPU Utilization", cpu_val, f"{cpu_val:.1f}%"
            if mem_val is not None and mem_val >= 90.0:
                return "Memory Utilization", mem_val, f"{mem_val:.1f}%"
            if disk_val is not None and disk_val >= 90.0:
                return "Disk Utilization", disk_val, f"{disk_val:.1f}%"

            if cpu_val is not None and cpu_val >= 80.0:
                return "CPU Utilization", cpu_val, f"{cpu_val:.1f}%"
            if mem_val is not None and mem_val >= 80.0:
                return "Memory Utilization", mem_val, f"{mem_val:.1f}%"

            # Check Anomaly score
            if hasattr(prediction, "anomaly_score") and prediction.anomaly_score is not None and prediction.anomaly_score >= 0.5:
                return "Hardware Anomaly Score", float(prediction.anomaly_score), f"{prediction.anomaly_score:.2f}"

            if cpu_val is not None and mem_val is not None:
                if cpu_val >= mem_val:
                    return "CPU Utilization", cpu_val, f"{cpu_val:.1f}%"
                return "Memory Utilization", mem_val, f"{mem_val:.1f}%"

        # Fallback to risk score
        rs = float(getattr(prediction, "risk_score", prediction.anomaly_score if hasattr(prediction, "anomaly_score") else 0.0))
        return "Composite Risk Score", rs, f"{rs:.2f}"

    def process_prediction(
        self,
        prediction: PredictionResult,
        metrics: Optional[Any] = None,
        processed: Optional[Any] = None,
        server_id: Optional[str] = None,
    ) -> Optional[RiskAlertRecord]:
        """Evaluate an authoritative ML prediction for alert generation or recovery resolution."""
        with self._lock:
            return self._process_prediction_locked(
                prediction=prediction,
                metrics=metrics,
                processed=processed,
                server_id=server_id,
            )

    def _process_prediction_locked(
        self,
        prediction: PredictionResult,
        metrics: Optional[Any] = None,
        processed: Optional[Any] = None,
        server_id: Optional[str] = None,
    ) -> Optional[RiskAlertRecord]:
        """Internal serialized evaluation under thread lock.

        Strictly respects authoritative risk classification:
        - HIGH or CRITICAL: creates a new incident if none is currently ongoing, or updates existing incident.
        - NORMAL, LOW, or MODERATE: resolves any ongoing incident exactly once.

        Args:
            prediction: Authoritative PredictionResult.
            metrics: Optional raw telemetry or record.
            processed: Optional PreprocessedData containing features.
            server_id: Optional server identifier override.

        Returns:
            The created, updated, or resolved RiskAlertRecord, or None if no transition.
        """
        target_server_id = server_id or self.server_id
        category = prediction.risk_category

        # Normalize category string to uppercase tier name (e.g. HIGH, CRITICAL)
        if hasattr(category, "name"):
            category_str = category.name.upper()
        elif hasattr(category, "value"):
            category_str = str(category.value).upper()
        else:
            category_str = str(category).upper()

        if category_str in ("HIGH", "CRITICAL"):
            severity = AlertSeverity.CRITICAL if category_str == "CRITICAL" else AlertSeverity.HIGH
            existing = self.repository.get_active_or_acknowledged_alert(target_server_id)

            if existing is not None:
                # Deduplication: Ongoing incident already active/acknowledged
                # Check for escalation from HIGH to CRITICAL
                trigger_metric, obs_val, obs_val_str = self._determine_trigger(prediction, metrics)
                if existing.severity == AlertSeverity.HIGH.value and severity == AlertSeverity.CRITICAL:
                    logger.warning("Escalating incident [%s] to CRITICAL for server %s", existing.alert_id, target_server_id)
                    updated = self.repository.update_active_alert(
                        alert_id=existing.alert_id,
                        severity=AlertSeverity.CRITICAL.value,
                        risk_score=float(getattr(prediction, 'risk_score', prediction.anomaly_score if hasattr(prediction, 'anomaly_score') else 0.0)),
                        health_score=float(prediction.health_score) if prediction.health_score is not None else None,
                        observed_value=obs_val,
                        observed_value_str=obs_val_str,
                    )
                    return updated
                else:
                    # Update metrics on active incident without spamming new alerts
                    self.repository.update_active_alert(
                        alert_id=existing.alert_id,
                        risk_score=float(getattr(prediction, 'risk_score', prediction.anomaly_score if hasattr(prediction, 'anomaly_score') else 0.0)),
                        health_score=float(prediction.health_score) if prediction.health_score is not None else None,
                        observed_value=obs_val,
                        observed_value_str=obs_val_str,
                    )
                    return existing

            # No existing active/acknowledged alert -> generate a brand new alert record
            trigger_metric, obs_val, obs_val_str = self._determine_trigger(prediction, metrics)

            # Deterministic diagnostic report (<5ms execution)
            features_dict = None
            if processed is not None and hasattr(processed, "feature_vector") and hasattr(processed.feature_vector, "features"):
                features_dict = processed.feature_vector.features

            headline = f"{severity.value} risk condition detected"
            diag_risk = float(getattr(prediction, "risk_score", prediction.anomaly_score if hasattr(prediction, "anomaly_score") else 0.0))
            diag_explanation = f"Authoritative health model evaluated {severity.value} risk (Risk Score: {diag_risk:.2f})."
            rec_action = f"Inspect {trigger_metric} and active system workload."
            remed_steps = [f"Check top resource-consuming processes for {trigger_metric}."]

            try:
                diag_report = self.diagnostic_engine.generate_report(
                    prediction=prediction,
                    metrics=metrics,
                    features=features_dict,
                )
                if diag_report.summary_headline:
                    headline = diag_report.summary_headline
                if diag_report.recommendations:
                    top_rec = diag_report.recommendations[0]
                    rec_action = top_rec.summary or top_rec.root_cause_hypothesis or top_rec.title
                    remed_steps = list(top_rec.remediation_steps) if top_rec.remediation_steps else [top_rec.summary]
                    diag_explanation = f"{top_rec.title}: {top_rec.root_cause_hypothesis}"
            except Exception as ex:
                logger.warning("Diagnostic engine fallback during alert creation: %s", ex)

            metric_id = None
            if metrics is not None and hasattr(metrics, "id") and isinstance(metrics.id, int) and metrics.id > 0:
                metric_id = metrics.id

            now = datetime.now(timezone.utc)
            alert_id = f"alt-{uuid.uuid4().hex[:10]}"
            title = f"{severity.value} Risk: {trigger_metric} Alert on {target_server_id}"

            payload = {
                "alert_id": alert_id,
                "server_id": target_server_id,
                "severity": severity.value,
                "status": AlertStatus.ACTIVE.value,
                "risk_category": category_str,
                "risk_score": float(getattr(prediction, 'risk_score', prediction.anomaly_score if hasattr(prediction, 'anomaly_score') else 0.0)),
                "health_score": float(prediction.health_score) if prediction.health_score is not None else None,
                "trigger_metric": trigger_metric,
                "observed_value": obs_val,
                "observed_value_str": obs_val_str,
                "title": title,
                "summary": headline,
                "ai_explanation": None,
                "diagnostic_explanation": diag_explanation,
                "recommended_action": rec_action,
                "remediation_steps": remed_steps,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "metric_id": metric_id,
            }

            created = self.repository.create_alert(payload)
            logger.warning(
                "Triggered %s alert [%s] for server %s: %s=%s",
                severity.value,
                alert_id,
                target_server_id,
                trigger_metric,
                obs_val_str,
            )
            return created

        else:
            # Server is NORMAL, LOW, or MODERATE -> Automatic recovery
            existing = self.repository.get_active_or_acknowledged_alert(target_server_id)
            if existing is not None:
                logger.info(
                    "Server %s recovered to %s; resolving active alert [%s]",
                    target_server_id,
                    category_str,
                    existing.alert_id,
                )
                resolved = self.repository.resolve_alert(existing.alert_id)
                return resolved

            # Normal state and no active alert to resolve
            return None

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "operator") -> Optional[RiskAlertRecord]:
        """Operator acknowledgement for an active alert."""
        alert = self.repository.get_alert_by_id(alert_id)
        if alert is None:
            return None
        if alert.status == AlertStatus.RESOLVED.value:
            return alert
        return self.repository.acknowledge_alert(alert_id, acknowledged_by=acknowledged_by)

    def resolve_alert(self, alert_id: str) -> Optional[RiskAlertRecord]:
        """Manually mark an alert resolved."""
        return self.repository.resolve_alert(alert_id)

    def get_alert(self, alert_id: str) -> Optional[RiskAlertRecord]:
        """Fetch alert record by ID."""
        return self.repository.get_alert_by_id(alert_id)

    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        server_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RiskAlertRecord], int]:
        """Query alert history with optional filtering."""
        records = self.repository.list_alerts(
            status=status,
            severity=severity,
            server_id=server_id,
            limit=limit,
            offset=offset,
        )
        total = self.repository.count_alerts(
            status=status,
            severity=severity,
        )
        return records, total

    def get_summary(self) -> AlertSummaryResponse:
        """Calculate aggregated alert counts and fetch latest alert."""
        summary_dict = self.repository.get_summary()
        latest_active = summary_dict.get("latest_active_alert")
        latest_schema = RiskAlertSchema.model_validate(latest_active) if latest_active else None

        return AlertSummaryResponse(
            active_count=summary_dict.get("active_count", 0),
            critical_count=summary_dict.get("critical_count", 0),
            high_count=summary_dict.get("high_count", 0),
            acknowledged_count=summary_dict.get("acknowledged_count", 0),
            resolved_count=summary_dict.get("resolved_count", 0),
            total_count=summary_dict.get("total_count", 0),
            latest_active_alert=latest_schema,
        )

    def attach_ai_explanation(self, alert_id: str, explanation: str) -> Optional[RiskAlertRecord]:
        """Safely attach an AI explanation to an existing alert."""
        conn = self.repository._get_connection()
        now_ts = datetime.now(timezone.utc).isoformat()
        try:
            from app.database.connection import transaction_scope
            with transaction_scope(conn):
                conn.execute(
                    "UPDATE risk_alerts SET ai_explanation = ?, updated_at = ? WHERE alert_id = ?;",
                    (explanation, now_ts, alert_id),
                )
            return self.repository.get_alert_by_id(alert_id)
        finally:
            conn.close()
