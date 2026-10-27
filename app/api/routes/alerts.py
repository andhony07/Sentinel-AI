"""FastAPI REST routes for SentinelAI Risk Alerts and Incident Management."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.alerts.models import (
    AlertAcknowledgeRequest,
    AlertListResponse,
    AlertSeverity,
    AlertStatus,
    AlertSummaryResponse,
    RiskAlertSchema,
)
from app.alerts.service import AlertService
from app.api.dependencies import get_alert_service

logger = logging.getLogger("app.api.alerts")

router = APIRouter(prefix="/alerts", tags=["Risk Alerts & Incidents"])


@router.get(
    "/summary",
    response_model=AlertSummaryResponse,
    summary="Get aggregated alert metrics",
    description="Returns total active, high, critical, acknowledged, and resolved alert counts, plus latest active alert.",
)
def get_alert_summary(
    service: AlertService = Depends(get_alert_service),
) -> AlertSummaryResponse:
    try:
        return service.get_summary()
    except Exception as exc:
        logger.error("Failed to fetch alert summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alert summary: {exc}",
        )


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List risk alert records",
    description="Returns a paginated list of risk alert records with optional status, severity, and server filtering.",
)
def list_alerts(
    status: Optional[str] = Query(
        default=None,
        description="Filter by lifecycle status (ACTIVE, ACKNOWLEDGED, RESOLVED, or comma-separated)",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity (HIGH, CRITICAL)",
    ),
    server_id: Optional[str] = Query(
        default=None,
        description="Filter by server/hostname",
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Page size limit"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    service: AlertService = Depends(get_alert_service),
) -> AlertListResponse:
    try:
        records, total = service.list_alerts(
            status=status,
            severity=severity,
            server_id=server_id,
            limit=limit,
            offset=offset,
        )
        return AlertListResponse(
            alerts=[RiskAlertSchema.from_record(r) for r in records],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.error("Failed to list alerts: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query alerts: {exc}",
        )


@router.get(
    "/{alert_id}",
    response_model=RiskAlertSchema,
    summary="Get individual alert record",
    description="Fetches details for a specific alert by its unique alert_id identifier.",
)
def get_alert_detail(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> RiskAlertSchema:
    record = service.get_alert(alert_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return RiskAlertSchema.from_record(record)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=RiskAlertSchema,
    summary="Acknowledge an active alert",
    description="Transitions an active alert to ACKNOWLEDGED status with operator attribution.",
)
def acknowledge_alert(
    alert_id: str,
    payload: Optional[AlertAcknowledgeRequest] = None,
    service: AlertService = Depends(get_alert_service),
) -> RiskAlertSchema:
    operator = payload.acknowledged_by if payload and payload.acknowledged_by else "operator"
    record = service.acknowledge_alert(alert_id, acknowledged_by=operator)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return RiskAlertSchema.from_record(record)


@router.post(
    "/{alert_id}/resolve",
    response_model=RiskAlertSchema,
    summary="Resolve an alert manually",
    description="Transitions an alert to RESOLVED status.",
)
def resolve_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> RiskAlertSchema:
    record = service.resolve_alert(alert_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found.",
        )
    return RiskAlertSchema.from_record(record)
