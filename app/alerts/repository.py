"""Persistence repository for SentinelAI risk alert and incident records."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.database.connection import get_connection, transaction_scope
from app.database.models import RiskAlertRecord, parse_utc_timestamp

logger = get_logger("app.alerts.repository")


class AlertRepository:
    """Handles SQLite persistence and queries for the risk_alerts table."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        db_path: Optional[Union[Path, str]] = None,
    ) -> None:
        """Initialize the alert repository.

        Args:
            settings: Optional Settings container.
            db_path: Optional path to SQLite database.
        """
        self.settings: Settings = settings or get_settings()
        self.db_path: Path = Path(db_path or self.settings.database_path).resolve()
        self._timeout: float = self.settings.db_connection_timeout

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> RiskAlertRecord:
        """Convert a database query row to a typed RiskAlertRecord."""
        raw_remed = row["remediation_steps_json"] if "remediation_steps_json" in row.keys() else "[]"
        try:
            remediation_steps = json.loads(raw_remed) if raw_remed else []
        except Exception:
            remediation_steps = []

        return RiskAlertRecord(
            id=int(row["id"]),
            alert_id=str(row["alert_id"]),
            server_id=str(row["server_id"]),
            severity=str(row["severity"]),
            status=str(row["status"]),
            risk_category=str(row["risk_category"]),
            risk_score=float(row["risk_score"]),
            health_score=float(row["health_score"]) if row["health_score"] is not None else None,
            trigger_metric=str(row["trigger_metric"]),
            observed_value=float(row["observed_value"]) if row["observed_value"] is not None else None,
            observed_value_str=str(row["observed_value_str"]) if row["observed_value_str"] is not None else None,
            title=str(row["title"]),
            summary=str(row["summary"]),
            ai_explanation=str(row["ai_explanation"]) if row["ai_explanation"] is not None else None,
            diagnostic_explanation=str(row["diagnostic_explanation"]),
            recommended_action=str(row["recommended_action"]),
            remediation_steps=remediation_steps,
            created_at=parse_utc_timestamp(row["created_at"]),
            updated_at=parse_utc_timestamp(row["updated_at"]),
            acknowledged_at=parse_utc_timestamp(row["acknowledged_at"]) if row["acknowledged_at"] else None,
            acknowledged_by=str(row["acknowledged_by"]) if row["acknowledged_by"] else None,
            resolved_at=parse_utc_timestamp(row["resolved_at"]) if row["resolved_at"] else None,
            metric_id=int(row["metric_id"]) if row["metric_id"] is not None else None,
        )

    def create_alert(self, data: dict[str, Any]) -> RiskAlertRecord:
        """Insert a new risk alert record into SQLite."""
        remediation_json = json.dumps(data.get("remediation_steps", []))
        created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        updated_at = data.get("updated_at") or created_at

        with get_connection(self.db_path, timeout=self._timeout) as conn:
            with transaction_scope(conn):
                cursor = conn.execute(
                    """
                    INSERT INTO risk_alerts (
                        alert_id, server_id, severity, status, risk_category,
                        risk_score, health_score, trigger_metric, observed_value,
                        observed_value_str, title, summary, ai_explanation,
                        diagnostic_explanation, recommended_action, remediation_steps_json,
                        created_at, updated_at, metric_id
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?
                    );
                    """,
                    (
                        data["alert_id"],
                        data["server_id"],
                        data["severity"],
                        data.get("status", "ACTIVE"),
                        data["risk_category"],
                        data["risk_score"],
                        data.get("health_score"),
                        data["trigger_metric"],
                        data.get("observed_value"),
                        data.get("observed_value_str"),
                        data["title"],
                        data["summary"],
                        data.get("ai_explanation"),
                        data["diagnostic_explanation"],
                        data["recommended_action"],
                        remediation_json,
                        created_at,
                        updated_at,
                        data.get("metric_id"),
                    ),
                )

        return self.get_alert_by_id(data["alert_id"])  # type: ignore[return-value]

    def get_alert_by_id(self, alert_id: str) -> Optional[RiskAlertRecord]:
        """Fetch alert by its unique alert_id string."""
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            cursor = conn.execute(
                "SELECT * FROM risk_alerts WHERE alert_id = ? LIMIT 1;",
                (alert_id,),
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_active_or_acknowledged_alert(self, server_id: str) -> Optional[RiskAlertRecord]:
        """Find any ongoing active or acknowledged alert for the given server."""
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM risk_alerts
                WHERE server_id = ? AND status IN ('ACTIVE', 'ACKNOWLEDGED')
                ORDER BY id DESC LIMIT 1;
                """,
                (server_id,),
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def update_active_alert(
        self,
        alert_id: str,
        severity: Optional[str] = None,
        risk_score: Optional[float] = None,
        health_score: Optional[float] = None,
        observed_value: Optional[float] = None,
        observed_value_str: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> Optional[RiskAlertRecord]:
        """Update metrics or escalate severity on an active alert."""
        now_ts = updated_at or datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            with transaction_scope(conn):
                if severity:
                    conn.execute(
                        """
                        UPDATE risk_alerts SET
                            severity = ?,
                            risk_score = coalesce(?, risk_score),
                            health_score = coalesce(?, health_score),
                            observed_value = coalesce(?, observed_value),
                            observed_value_str = coalesce(?, observed_value_str),
                            updated_at = ?
                        WHERE alert_id = ?;
                        """,
                        (severity, risk_score, health_score, observed_value, observed_value_str, now_ts, alert_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE risk_alerts SET
                            risk_score = coalesce(?, risk_score),
                            health_score = coalesce(?, health_score),
                            observed_value = coalesce(?, observed_value),
                            observed_value_str = coalesce(?, observed_value_str),
                            updated_at = ?
                        WHERE alert_id = ?;
                        """,
                        (risk_score, health_score, observed_value, observed_value_str, now_ts, alert_id),
                    )
        return self.get_alert_by_id(alert_id)

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str = "operator",
        acknowledged_at: Optional[datetime] = None,
    ) -> Optional[RiskAlertRecord]:
        """Transition alert to ACKNOWLEDGED state."""
        ack_time = (acknowledged_at or datetime.now(timezone.utc)).isoformat()
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            with transaction_scope(conn):
                conn.execute(
                    """
                    UPDATE risk_alerts SET
                        status = 'ACKNOWLEDGED',
                        acknowledged_at = ?,
                        acknowledged_by = ?,
                        updated_at = ?
                    WHERE alert_id = ? AND status = 'ACTIVE';
                    """,
                    (ack_time, acknowledged_by, ack_time, alert_id),
                )
        return self.get_alert_by_id(alert_id)

    def resolve_alert(
        self,
        alert_id: str,
        resolved_at: Optional[datetime] = None,
    ) -> Optional[RiskAlertRecord]:
        """Transition alert to RESOLVED state upon recovery."""
        res_time = (resolved_at or datetime.now(timezone.utc)).isoformat()
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            with transaction_scope(conn):
                conn.execute(
                    """
                    UPDATE risk_alerts SET
                        status = 'RESOLVED',
                        resolved_at = ?,
                        updated_at = ?
                    WHERE alert_id = ? AND status IN ('ACTIVE', 'ACKNOWLEDGED');
                    """,
                    (res_time, res_time, alert_id),
                )
        return self.get_alert_by_id(alert_id)

    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        server_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RiskAlertRecord]:
        """Query alert history with optional filtering."""
        query = "SELECT * FROM risk_alerts"
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
            if len(statuses) == 1:
                conditions.append("status = ?")
                params.append(statuses[0])
            elif statuses:
                placeholders = ",".join("?" for _ in statuses)
                conditions.append(f"status IN ({placeholders})")
                params.extend(statuses)

        if severity:
            conditions.append("severity = ?")
            params.append(severity.upper())

        if server_id:
            conditions.append("server_id = ?")
            params.append(server_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?;"
        params.extend([max(1, min(limit, 500)), max(0, offset)])

        with get_connection(self.db_path, timeout=self._timeout) as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def count_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        server_id: Optional[str] = None,
    ) -> int:
        """Count alerts matching filter conditions."""
        query = "SELECT COUNT(*) FROM risk_alerts"
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
            if len(statuses) == 1:
                conditions.append("status = ?")
                params.append(statuses[0])
            elif statuses:
                placeholders = ",".join("?" for _ in statuses)
                conditions.append(f"status IN ({placeholders})")
                params.extend(statuses)

        if severity:
            conditions.append("severity = ?")
            params.append(severity.upper())

        if server_id:
            conditions.append("server_id = ?")
            params.append(server_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with get_connection(self.db_path, timeout=self._timeout) as conn:
            cursor = conn.execute(query, params)
            return int(cursor.fetchone()[0])

    def get_summary(self) -> dict[str, Any]:
        """Return executive summary counts and latest active alert."""
        with get_connection(self.db_path, timeout=self._timeout) as conn:
            cursor = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active_count,
                    SUM(CASE WHEN status = 'ACTIVE' AND severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
                    SUM(CASE WHEN status = 'ACTIVE' AND severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
                    SUM(CASE WHEN status = 'ACKNOWLEDGED' THEN 1 ELSE 0 END) AS acknowledged_count,
                    SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END) AS resolved_count,
                    COUNT(*) AS total_count
                FROM risk_alerts;
                """
            )
            row = cursor.fetchone()
            active_count = row["active_count"] or 0
            critical_count = row["critical_count"] or 0
            high_count = row["high_count"] or 0
            acknowledged_count = row["acknowledged_count"] or 0
            resolved_count = row["resolved_count"] or 0
            total_count = row["total_count"] or 0

            latest_active = None
            if active_count > 0:
                cursor2 = conn.execute(
                    "SELECT * FROM risk_alerts WHERE status = 'ACTIVE' ORDER BY id DESC LIMIT 1;"
                )
                r2 = cursor2.fetchone()
                if r2:
                    latest_active = self._row_to_record(r2).to_dict()

            return {
                "active_count": int(active_count),
                "critical_count": int(critical_count),
                "high_count": int(high_count),
                "acknowledged_count": int(acknowledged_count),
                "resolved_count": int(resolved_count),
                "total_count": int(total_count),
                "latest_active_alert": latest_active,
            }
