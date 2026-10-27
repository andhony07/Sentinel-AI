"""FastAPI dependency injection providers.

Provides cached and test-overridable access to application Settings and
the central DashboardService coordinator.
"""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.dashboard.services.dashboard_service import DashboardService

_service_instance: Optional[DashboardService] = None
_service_lock = threading.Lock()


def get_api_settings() -> Settings:
    """Provide application configuration settings for route dependencies.

    Returns:
        Active Settings instance.
    """
    return get_settings()


def get_dashboard_service(
    settings: Settings = Depends(get_api_settings),
) -> DashboardService:
    """Provide a shared DashboardService instance.

    Thread-safe lazy initialization ensures a single service coordinator
    is reused across API requests within the server process.

    Args:
        settings: Injected or resolved Settings instance.

    Returns:
        Configured DashboardService instance.
    """
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            active_settings = settings if isinstance(settings, Settings) else get_api_settings()
            _service_instance = DashboardService(settings=active_settings)
        return _service_instance


def reset_dashboard_service(new_service: Optional[DashboardService] = None) -> None:
    """Reset or override the global service coordinator (primarily for testing).

    Args:
        new_service: Optional custom DashboardService to inject.
    """
    global _service_instance
    with _service_lock:
        _service_instance = new_service


_ai_service_instance: Optional[Any] = None
_ai_service_lock = threading.Lock()


def get_ai_diagnostic_service(
    settings: Settings = Depends(get_api_settings),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> Any:
    """Provide a shared AIDiagnosticService instance.

    Thread-safe lazy initialization ensures a single AI diagnostic service coordinator
    is reused across API requests within the server process.

    Args:
        settings: Injected or resolved Settings instance.
        dashboard_service: Injected DashboardService instance.

    Returns:
        Configured AIDiagnosticService instance.
    """
    from app.ai.service import AIDiagnosticService

    global _ai_service_instance
    with _ai_service_lock:
        if _ai_service_instance is None:
            active_settings = settings if isinstance(settings, Settings) else get_api_settings()
            _ai_service_instance = AIDiagnosticService(
                settings=active_settings,
                dashboard_service=dashboard_service,
            )
        return _ai_service_instance


def reset_ai_diagnostic_service(new_service: Optional[Any] = None) -> None:
    """Reset or override the global AI service coordinator (primarily for testing).

    Args:
        new_service: Optional custom AIDiagnosticService to inject.
    """
    global _ai_service_instance
    with _ai_service_lock:
        _ai_service_instance = new_service

_alert_service_instance: Optional[Any] = None
_alert_service_lock = threading.Lock()


def get_alert_service(
    settings: Settings = Depends(get_api_settings),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
) -> Any:
    """Provide a shared AlertService instance coordinated with DashboardService.

    Thread-safe lazy initialization ensures a single alert service coordinator
    is reused across API requests and background monitoring tasks within the server process.
    """
    global _alert_service_instance
    with _alert_service_lock:
        if _alert_service_instance is not None:
            return _alert_service_instance
        return dashboard_service.alert_service


def reset_alert_service(new_service: Optional[Any] = None) -> None:
    """Reset or override the global alert service coordinator (primarily for testing)."""
    global _alert_service_instance
    with _alert_service_lock:
        _alert_service_instance = new_service
