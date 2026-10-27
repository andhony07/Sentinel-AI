"""Pydantic data schemas for SentinelAI risk alert and notification system."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Urgency tier for risk alerts."""

    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, Enum):
    """Lifecycle status for risk alerts."""

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class RiskAlertSchema(BaseModel):
    """Pydantic response model for risk alerts."""

    id: int
    alert_id: str
    server_id: str
    severity: AlertSeverity
    status: AlertStatus
    risk_category: str
    risk_score: float
    health_score: Optional[float] = None
    trigger_metric: str
    observed_value: Optional[float] = None
    observed_value_str: Optional[str] = None
    title: str
    summary: str
    ai_explanation: Optional[str] = None
    diagnostic_explanation: str
    recommended_action: str
    remediation_steps: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    metric_id: Optional[int] = None

    @classmethod
    def from_record(cls, record: Any) -> RiskAlertSchema:
        """Construct schema from a database RiskAlertRecord or dictionary."""
        if isinstance(record, dict):
            return cls.model_validate(record)

        return cls(
            id=record.id,
            alert_id=record.alert_id,
            server_id=record.server_id,
            severity=AlertSeverity(record.severity),
            status=AlertStatus(record.status),
            risk_category=record.risk_category,
            risk_score=record.risk_score,
            health_score=record.health_score,
            trigger_metric=record.trigger_metric,
            observed_value=record.observed_value,
            observed_value_str=record.observed_value_str,
            title=record.title,
            summary=record.summary,
            ai_explanation=record.ai_explanation,
            diagnostic_explanation=record.diagnostic_explanation,
            recommended_action=record.recommended_action,
            remediation_steps=record.remediation_steps if hasattr(record, "remediation_steps") else [],
            created_at=record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
            updated_at=record.updated_at.isoformat() if hasattr(record.updated_at, "isoformat") else str(record.updated_at),
            acknowledged_at=record.acknowledged_at.isoformat() if record.acknowledged_at and hasattr(record.acknowledged_at, "isoformat") else (str(record.acknowledged_at) if record.acknowledged_at else None),
            acknowledged_by=record.acknowledged_by,
            resolved_at=record.resolved_at.isoformat() if record.resolved_at and hasattr(record.resolved_at, "isoformat") else (str(record.resolved_at) if record.resolved_at else None),
            metric_id=record.metric_id,
        )


class AlertAcknowledgeRequest(BaseModel):
    """Payload for operator alert acknowledgement."""

    acknowledged_by: Optional[str] = "operator"


class AlertSummaryResponse(BaseModel):
    """Aggregated status and count metrics for dashboard header."""

    active_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    acknowledged_count: int = 0
    resolved_count: int = 0
    total_count: int = 0
    latest_active_alert: Optional[RiskAlertSchema] = None


class AlertListResponse(BaseModel):
    """Paginated collection of alert records."""

    alerts: list[RiskAlertSchema]
    total: int
    limit: int
    offset: int
