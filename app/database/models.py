"""Typed data representations for persisted database records and operation results.

Maps database row records back into structured Python dataclasses with typed
timestamps, numerical features, and parsed JSON payload contents.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def parse_utc_timestamp(ts_str: str) -> datetime:
    """Parse an ISO 8601 string into a UTC-aware datetime object.

    Args:
        ts_str: ISO formatted timestamp string.

    Returns:
        UTC datetime instance.
    """
    dt = datetime.fromisoformat(ts_str)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class SystemMetricRecord:
    """Represents a persisted row from the system_metrics table.

    Attributes:
        id: Primary key identifier.
        timestamp: Time of telemetry capture (UTC).
        cpu_percent: Overall CPU utilization percentage.
        cpu_logical_cores: Total logical core count.
        cpu_physical_cores: Physical core count.
        memory_total_bytes: Total physical RAM in bytes.
        memory_used_bytes: Memory used in bytes.
        memory_available_bytes: Memory available in bytes.
        memory_percent: Memory utilization percentage.
        disk_total_bytes: Storage total capacity in bytes.
        disk_used_bytes: Storage used in bytes.
        disk_free_bytes: Storage free in bytes.
        disk_percent: Storage utilization percentage.
        disk_active_percent: Physical disk busy/active time percentage (0.0 - 100.0).
        disk_read_bytes_per_sec: Disk read throughput in bytes/sec.
        disk_write_bytes_per_sec: Disk write throughput in bytes/sec.
        network_bytes_sent: Cumulative bytes transmitted.
        network_bytes_recv: Cumulative bytes received.
        network_bytes_sent_per_sec: Upload rate in bytes/sec.
        network_bytes_recv_per_sec: Download rate in bytes/sec.
        process_count: Number of monitored top processes.
        top_process_pid: PID of the highest CPU process.
        top_process_name: Name of the highest CPU process.
        top_process_cpu_percent: CPU% of highest CPU process.
        top_process_memory_percent: RAM% of highest CPU process.
        raw_payload: Deserialized raw telemetry dictionary.
    """

    id: int
    timestamp: datetime
    cpu_percent: Optional[float] = None
    cpu_logical_cores: Optional[int] = None
    cpu_physical_cores: Optional[int] = None
    memory_total_bytes: Optional[int] = None
    memory_used_bytes: Optional[int] = None
    memory_available_bytes: Optional[int] = None
    memory_percent: Optional[float] = None
    disk_total_bytes: Optional[int] = None
    disk_used_bytes: Optional[int] = None
    disk_free_bytes: Optional[int] = None
    disk_percent: Optional[float] = None
    disk_active_percent: Optional[float] = None
    disk_read_bytes_per_sec: Optional[float] = None
    disk_write_bytes_per_sec: Optional[float] = None
    network_bytes_sent: Optional[int] = None
    network_bytes_recv: Optional[int] = None
    network_bytes_sent_per_sec: Optional[float] = None
    network_bytes_recv_per_sec: Optional[float] = None
    process_count: Optional[int] = None
    top_process_pid: Optional[int] = None
    top_process_name: Optional[str] = None
    top_process_cpu_percent: Optional[float] = None
    top_process_memory_percent: Optional[float] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert record to a JSON-serializable dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass(frozen=True)
class FeatureVectorRecord:
    """Represents a persisted row from the feature_vectors table.

    Attributes:
        id: Primary key identifier.
        metric_id: Foreign key reference to system_metrics(id).
        timestamp: Time of feature vector computation (UTC).
        features: Mapping of all 39 engineered feature names to numerical values.
        metadata: Contextual metadata accompanying the feature vector.
    """

    id: int
    timestamp: datetime
    features: dict[str, float]
    metric_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert feature vector record to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "metric_id": self.metric_id,
            "timestamp": self.timestamp.isoformat(),
            "features": dict(self.features),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ValidationLogRecord:
    """Represents a persisted row from the validation_logs table.

    Attributes:
        id: Primary key identifier.
        metric_id: Foreign key reference to system_metrics(id).
        timestamp: Time of validation inspection (UTC).
        is_valid: True if metrics passed validation constraints without errors.
        issues_count: Total number of issues (warnings + errors) identified.
        has_errors: True if any issues had severity == 'error'.
        issues: List of structured issue detail dictionaries.
    """

    id: int
    timestamp: datetime
    is_valid: bool
    issues_count: int
    has_errors: bool
    metric_id: Optional[int] = None
    issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert validation record to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "metric_id": self.metric_id,
            "timestamp": self.timestamp.isoformat(),
            "is_valid": self.is_valid,
            "issues_count": self.issues_count,
            "has_errors": self.has_errors,
            "issues": list(self.issues),
        }


@dataclass(frozen=True)
class PersistenceResult:
    """Outcome report for a telemetry persistence operation.

    Attributes:
        success: True if the atomic persistence transaction committed.
        metric_id: Generated primary key for the raw system_metrics record.
        feature_id: Generated primary key for the feature_vectors record.
        validation_id: Generated primary key for the validation_logs record.
        error_message: Human-readable diagnostic if persistence failed.
    """

    success: bool
    metric_id: Optional[int] = None
    feature_id: Optional[int] = None
    validation_id: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert persistence result to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class RiskAlertRecord:
    """Represents a persisted risk alert record in the risk_alerts table.

    Attributes:
        id: Primary key identifier.
        alert_id: Unique incident/alert identifier (e.g. 'alt-20261027-a1b2c3d4').
        server_id: Identifier of the monitored server or instance.
        severity: Alert severity ('HIGH' or 'CRITICAL').
        status: Current incident lifecycle status ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED').
        risk_category: Assigned RiskCategory ('High' or 'Critical').
        risk_score: Normalized anomaly indicator score (0.0 - 1.0).
        health_score: Composite deterministic health score (0.0 - 100.0) or None.
        trigger_metric: Key metric that triggered the threshold (e.g. 'cpu_utilization_percent').
        observed_value: Numeric observed metric value.
        observed_value_str: Human-readable formatted observation (e.g. '96.2%').
        title: Descriptive alert title.
        summary: High-level incident summary.
        ai_explanation: Optional incident explanation synthesized by LLM.
        diagnostic_explanation: Deterministic evidence-backed diagnostic explanation.
        recommended_action: Primary recommended investigation or mitigation step.
        remediation_steps: Ordered list of suggested investigation steps.
        created_at: Incident inception timestamp (UTC).
        updated_at: Latest update timestamp (UTC).
        acknowledged_at: Operator acknowledgement timestamp (UTC) or None.
        acknowledged_by: Operator identifier or None.
        resolved_at: Incident resolution timestamp (UTC) or None.
        metric_id: Optional foreign key to triggering system_metrics record.
    """

    id: int
    alert_id: str
    server_id: str
    severity: str
    status: str
    risk_category: str
    risk_score: float
    health_score: Optional[float]
    trigger_metric: str
    observed_value: Optional[float]
    observed_value_str: Optional[str]
    title: str
    summary: str
    ai_explanation: Optional[str]
    diagnostic_explanation: str
    recommended_action: str
    remediation_steps: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    metric_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert alert record to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "server_id": self.server_id,
            "severity": self.severity,
            "status": self.status,
            "risk_category": self.risk_category,
            "risk_score": round(self.risk_score, 4),
            "health_score": round(self.health_score, 2) if self.health_score is not None else None,
            "trigger_metric": self.trigger_metric,
            "observed_value": self.observed_value,
            "observed_value_str": self.observed_value_str,
            "title": self.title,
            "summary": self.summary,
            "ai_explanation": self.ai_explanation,
            "diagnostic_explanation": self.diagnostic_explanation,
            "recommended_action": self.recommended_action,
            "remediation_steps": list(self.remediation_steps),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metric_id": self.metric_id,
        }
