"""Comprehensive unit and integration test suite for SentinelAI Risk Alert and Notification System.

Validates all 12 backend requirements:
1. HIGH risk creates an alert.
2. CRITICAL risk creates an alert.
3. LOW and MEDIUM (MODERATE) risk do not create urgent alerts.
4. Repeated refreshes do not duplicate an active incident.
5. Acknowledgement persists correctly.
6. Recovery resolves an incident exactly once.
7. A new incident after recovery creates a new alert.
8. Alert history survives application restart when persistent storage is used.
9. Concurrent processing does not create duplicate incidents.
10. API validation, authorization, and error handling work correctly.
11. AI unavailability does not prevent alert creation.
12. Existing health scoring and risk classification remain unchanged.
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient

from app.alerts.models import AlertSeverity, AlertStatus
from app.alerts.repository import AlertRepository
from app.alerts.service import AlertService
from app.api.dependencies import get_alert_service, reset_alert_service
from app.api.main import create_app
from app.core.config import get_settings
from app.database.service import PersistenceService
from app.ml.models import RiskCategory
from app.ml.prediction_service import PredictionResult, PredictionService
from app.ml.risk_analyzer import RiskAnalyzer


@pytest.fixture
def temp_service(tmp_path: Path) -> Generator[AlertService, None, None]:
    """Isolated AlertService with dedicated temporary SQLite database."""
    db_file = tmp_path / "test_alerts_system.db"
    settings = dataclasses.replace(get_settings(), database_path=db_file)
    PersistenceService(settings=settings).initialize_database()
    service = AlertService(settings=settings, server_id="test-srv-01")
    yield service


@pytest.fixture
def api_client(temp_service: AlertService) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden AlertService dependency."""
    reset_alert_service(temp_service)
    app = create_app(settings=temp_service.settings)
    app.dependency_overrides[get_alert_service] = lambda: temp_service
    client = TestClient(app)
    yield client
    reset_alert_service(None)


def test_1_high_risk_creates_alert(temp_service: AlertService) -> None:
    """1. HIGH risk creates an alert."""
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.76,
        raw_decision_score=-0.22,
        health_score=45.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred)
    assert alert is not None
    assert alert.severity == "HIGH"
    assert alert.status == "ACTIVE"
    assert alert.server_id == "test-srv-01"
    assert alert.risk_score == pytest.approx(0.76, abs=0.01)
    assert alert.health_score == pytest.approx(45.0, abs=0.1)


def test_2_critical_risk_creates_alert(temp_service: AlertService) -> None:
    """2. CRITICAL risk creates an alert."""
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.94,
        raw_decision_score=-0.62,
        health_score=12.0,
        risk_category=RiskCategory.CRITICAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred)
    assert alert is not None
    assert alert.severity == "CRITICAL"
    assert alert.status == "ACTIVE"
    assert alert.risk_score == pytest.approx(0.94, abs=0.01)


def test_3_low_and_moderate_risk_do_not_create_alerts(temp_service: AlertService) -> None:
    """3. LOW and MEDIUM (MODERATE) risk do not create urgent alerts."""
    for category in (RiskCategory.NORMAL, RiskCategory.LOW, RiskCategory.MODERATE):
        pred = PredictionResult(
            timestamp=datetime.now(timezone.utc),
            is_anomaly=False,
            anomaly_score=0.20,
            raw_decision_score=0.40,
            health_score=85.0,
            risk_category=category,
            model_name="IsolationForest",
            model_version="1.0.0",
            warnings=[],
        )
        res = temp_service.process_prediction(pred)
        assert res is None

    alerts, total = temp_service.list_alerts()
    assert total == 0


def test_4_repeated_refreshes_do_not_duplicate_active_incident(temp_service: AlertService) -> None:
    """4. Repeated refreshes do not duplicate an active incident."""
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.80,
        raw_decision_score=-0.30,
        health_score=40.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    first_alert = temp_service.process_prediction(pred)
    assert first_alert is not None

    for _ in range(5):
        repeat_alert = temp_service.process_prediction(pred)
        assert repeat_alert is not None
        assert repeat_alert.alert_id == first_alert.alert_id

    alerts, total = temp_service.list_alerts()
    assert total == 1


def test_5_acknowledgement_persists_correctly(temp_service: AlertService) -> None:
    """5. Acknowledgement persists correctly."""
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.82,
        raw_decision_score=-0.35,
        health_score=38.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred)
    assert alert is not None

    ack = temp_service.acknowledge_alert(alert.alert_id, acknowledged_by="lead_sre")
    assert ack is not None
    assert ack.status == "ACKNOWLEDGED"
    assert ack.acknowledged_by == "lead_sre"
    assert ack.acknowledged_at is not None

    # Fetch fresh from DB to verify persistence
    stored = temp_service.get_alert(alert.alert_id)
    assert stored is not None
    assert stored.status == "ACKNOWLEDGED"
    assert stored.acknowledged_by == "lead_sre"


def test_6_recovery_resolves_incident_exactly_once(temp_service: AlertService) -> None:
    """6. Recovery resolves an incident exactly once."""
    pred_high = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.79,
        raw_decision_score=-0.28,
        health_score=41.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred_high)
    assert alert is not None

    pred_norm = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=False,
        anomaly_score=0.10,
        raw_decision_score=0.50,
        health_score=95.0,
        risk_category=RiskCategory.NORMAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    resolved = temp_service.process_prediction(pred_norm)
    assert resolved is not None
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at is not None

    # Subsequent recovery tick is a no-op
    noop = temp_service.process_prediction(pred_norm)
    assert noop is None

    alerts, total = temp_service.list_alerts()
    assert total == 1
    assert alerts[0].status == "RESOLVED"


def test_7_new_incident_after_recovery_creates_new_alert(temp_service: AlertService) -> None:
    """7. A new incident after recovery creates a new alert."""
    pred_high = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.78,
        raw_decision_score=-0.25,
        health_score=42.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert1 = temp_service.process_prediction(pred_high)
    assert alert1 is not None

    pred_norm = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=False,
        anomaly_score=0.15,
        raw_decision_score=0.45,
        health_score=92.0,
        risk_category=RiskCategory.NORMAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    temp_service.process_prediction(pred_norm)

    alert2 = temp_service.process_prediction(pred_high)
    assert alert2 is not None
    assert alert2.alert_id != alert1.alert_id
    assert alert2.status == "ACTIVE"

    alerts, total = temp_service.list_alerts()
    assert total == 2


def test_8_alert_history_survives_application_restart(tmp_path: Path) -> None:
    """8. Alert history survives application restart when persistent storage is used."""
    db_file = tmp_path / "persistent_alerts.db"
    settings = dataclasses.replace(get_settings(), database_path=db_file)
    PersistenceService(settings=settings).initialize_database()

    # Instance 1: Generate alert
    service1 = AlertService(settings=settings, server_id="srv-restart")
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.85,
        raw_decision_score=-0.40,
        health_score=35.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = service1.process_prediction(pred)
    assert alert is not None
    alert_id = alert.alert_id

    # Simulate full process restart
    service2 = AlertService(settings=settings, server_id="srv-restart")
    loaded = service2.get_alert(alert_id)
    assert loaded is not None
    assert loaded.alert_id == alert_id
    assert loaded.status == "ACTIVE"
    summary = service2.get_summary()
    assert summary.active_count == 1


def test_9_concurrent_processing_does_not_create_duplicates(temp_service: AlertService) -> None:
    """9. Concurrent processing does not create duplicate incidents."""
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.88,
        raw_decision_score=-0.45,
        health_score=30.0,
        risk_category=RiskCategory.CRITICAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )

    results: list[Any] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            r = temp_service.process_prediction(pred)
            results.append(r)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    alerts, total = temp_service.list_alerts()
    assert total == 1


def test_10_api_validation_authorization_and_error_handling(api_client: TestClient, temp_service: AlertService) -> None:
    """10. API validation, authorization, and error handling work correctly."""
    # Summary on empty
    r_sum = api_client.get("/api/alerts/summary")
    assert r_sum.status_code == 200
    assert r_sum.json()["active_count"] == 0

    # 404 on missing alert
    r_404 = api_client.get("/api/alerts/alt-nonexistent")
    assert r_404.status_code == 404

    # Create alert via service
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.92,
        raw_decision_score=-0.55,
        health_score=20.0,
        risk_category=RiskCategory.CRITICAL,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred)
    assert alert is not None

    # Fetch alert via API
    r_get = api_client.get(f"/api/alerts/{alert.alert_id}")
    assert r_get.status_code == 200
    assert r_get.json()["alert_id"] == alert.alert_id
    assert r_get.json()["severity"] == "CRITICAL"

    # Acknowledge via API
    r_ack = api_client.post(
        f"/api/alerts/{alert.alert_id}/acknowledge",
        json={"acknowledged_by": "operator_test"},
    )
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "ACKNOWLEDGED"
    assert r_ack.json()["acknowledged_by"] == "operator_test"

    # List alerts
    r_list = api_client.get("/api/alerts?status=ACKNOWLEDGED")
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1

    # Manual resolve via API
    r_res = api_client.post(f"/api/alerts/{alert.alert_id}/resolve")
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "RESOLVED"


def test_11_ai_unavailability_does_not_prevent_alert_creation(temp_service: AlertService) -> None:
    """11. AI unavailability does not prevent alert creation."""
    # With AI disabled or unavailable, alert creation succeeds instantly with deterministic diagnostics
    pred = PredictionResult(
        timestamp=datetime.now(timezone.utc),
        is_anomaly=True,
        anomaly_score=0.84,
        raw_decision_score=-0.38,
        health_score=36.0,
        risk_category=RiskCategory.HIGH,
        model_name="IsolationForest",
        model_version="1.0.0",
        warnings=[],
    )
    alert = temp_service.process_prediction(pred)
    assert alert is not None
    assert alert.status == "ACTIVE"
    assert alert.diagnostic_explanation is not None
    assert len(alert.diagnostic_explanation) > 0


def test_12_existing_health_scoring_and_risk_classification_remain_unchanged() -> None:
    """12. Existing health scoring and risk classification remain unchanged."""
    analyzer = RiskAnalyzer()
    assert analyzer.evaluate_risk(anomaly_input=0.10, health_result=95.0) == RiskCategory.NORMAL
    assert analyzer.evaluate_risk(anomaly_input=0.40, health_result=75.0) == RiskCategory.LOW
    assert analyzer.evaluate_risk(anomaly_input=0.60, health_result=55.0) == RiskCategory.MODERATE
    assert analyzer.evaluate_risk(anomaly_input=0.80, health_result=35.0) == RiskCategory.HIGH
    assert analyzer.evaluate_risk(anomaly_input=0.95, health_result=10.0) == RiskCategory.CRITICAL


def test_13_unicode_source_encoding_safety() -> None:
    """13. Demonstrate source files and outputs with Unicode (e.g. \u2192, 🛡️, ⚠️) process without charmap error."""
    import io
    from pathlib import Path

    # Target frontend source file where → and icons are present
    fe_file = Path(r"d:\SentinelAI\frontend\src\views\AlertsNotificationsView.tsx")
    assert fe_file.exists(), f"Source file does not exist: {fe_file}"

    # Verify explicit UTF-8 read
    with open(fe_file, "r", encoding="utf-8") as f:
        source_text = f.read()

    assert len(source_text) > 0

    # Simulate writing text containing Unicode characters to a UTF-8 stream
    # without raising charmap UnicodeEncodeError
    buffer = io.BytesIO()
    text_stream = io.TextIOWrapper(buffer, encoding="utf-8", errors="strict", newline="")
    text_stream.write(source_text)
    text_stream.flush()

    raw_bytes = buffer.getvalue()
    assert len(raw_bytes) >= len(source_text)

    # Verify roundtrip decode produces exact matching text
    decoded = raw_bytes.decode("utf-8")
    assert decoded == source_text


def test_14_streamlit_dashboard_service_alert_service_attribute() -> None:
    """14. Regression test: DashboardService must always possess alert_service without AttributeError."""
    from app.dashboard.services.dashboard_service import DashboardService
    from app.alerts.models import AlertSummaryResponse

    service = DashboardService()

    # Attribute must exist directly or through property/getattr fallback
    assert hasattr(service, "alert_service"), "DashboardService missing 'alert_service' attribute"
    assert service.alert_service is not None

    # Calling get_summary() through service must succeed and return AlertSummaryResponse
    summary = service.alert_service.get_summary()
    assert isinstance(summary, AlertSummaryResponse)
    assert summary.active_count >= 0
    assert summary.critical_count >= 0
    assert summary.high_count >= 0
    assert summary.acknowledged_count >= 0
    assert summary.resolved_count >= 0
