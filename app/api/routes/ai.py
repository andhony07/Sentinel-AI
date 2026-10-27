"""AI Diagnostic Assistant REST routes.

Provides endpoints for on-demand incident contextualization, evidence-based root-cause
hypotheses, prioritized remediation suggestions, and retrieval of latest AI diagnoses.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.models import AIDiagnosisRequest, AIIncidentDiagnosis
from app.ai.service import AIDiagnosticService
from app.api.dependencies import get_ai_diagnostic_service

router = APIRouter(prefix="/ai", tags=["AI Diagnostic Assistant"])


@router.post(
    "/diagnose",
    response_model=AIIncidentDiagnosis,
    summary="Generate on-demand AI incident diagnosis",
    description=(
        "Synthesizes live telemetry, top processes, Isolation Forest anomaly evaluations, "
        "and deterministic diagnostic findings into an evidence-grounded incident summary, "
        "probable causes, and prioritized remediation runbook via Ollama (with deterministic fallback)."
    ),
)
async def generate_ai_diagnosis(
    payload: Optional[AIDiagnosisRequest] = None,
    service: AIDiagnosticService = Depends(get_ai_diagnostic_service),
) -> AIIncidentDiagnosis:
    """Generate on-demand AI incident diagnosis.

    Evaluates latest telemetry or executes a deterministic simulation scenario.
    Always returns a valid schema-compliant diagnosis, falling back gracefully
    if Ollama is stopped or unavailable.
    """
    force_fallback = payload.force_fallback if payload else False

    try:
        if payload and payload.scenario:
            return await service.diagnose_simulation(
                scenario=payload.scenario,
                persist=payload.persist,
                force_fallback=force_fallback,
            )
        return await service.diagnose_latest(force_fallback=force_fallback)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnostic evaluation failed: {exc}",
        ) from exc


@router.get(
    "/latest",
    response_model=AIIncidentDiagnosis,
    summary="Get latest AI incident diagnosis",
    description="Returns the most recently evaluated diagnosis from memory, or evaluates latest telemetry if none is cached.",
)
async def get_latest_ai_diagnosis(
    service: AIDiagnosticService = Depends(get_ai_diagnostic_service),
) -> AIIncidentDiagnosis:
    """Retrieve the latest AI incident diagnosis."""
    cached = service.get_cached_latest()
    if cached is not None:
        return cached

    # If no cached diagnosis exists, evaluate latest telemetry snapshot with deterministic fallback
    # to avoid blocking passive page loading queries for 30+ seconds when the LLM service is offline or cold
    return await service.diagnose_latest(force_fallback=True)


@router.get(
    "/status",
    summary="Inspect AI Diagnostic Assistant status",
    description="Returns configuration metadata, provider type, model name, live Ollama availability, and fallback status.",
)
async def get_ai_status(
    check_ollama: bool = Query(True, description="Whether to probe live model reachability"),
    check_gemma: Optional[bool] = Query(None, description="Whether to probe live Gemma reachability"),
    check_reachability: Optional[bool] = Query(None, description="Whether to probe live model reachability"),
    service: AIDiagnosticService = Depends(get_ai_diagnostic_service),
) -> dict[str, Any]:
    """Inspect AI diagnostic configuration and service status."""
    cached = service.get_cached_latest()
    cached_source = None
    if cached is not None:
        cached_source = "heuristic_fallback" if cached.is_fallback else "live_model"

    if check_gemma is not None:
        should_check = check_gemma
    elif check_reachability is not None:
        should_check = check_reachability
    else:
        should_check = check_ollama

    provider_info: dict[str, Any] = {"available": False, "model_available": False, "models": [], "error": None}
    if should_check and service.settings.ai_enabled:
        if service.settings.ai_provider in ("heuristic", "mock"):
            provider_info = {"available": True, "model_available": True, "models": [service.settings.ai_provider], "error": None}
        elif service.client is not None and hasattr(service.client, "check_availability"):
            provider_info = await service.client.check_availability(timeout_seconds=2.0)

    fallback_active = (
        not service.settings.ai_enabled
        or service.settings.ai_provider in ("heuristic", "mock")
        or (service.settings.ai_provider == "gemma" and not service.settings.gemma_api_key and not getattr(service.client, "_custom_client", None))
        or (should_check and not provider_info["available"])
        or (should_check and not provider_info["model_available"])
    )

    return {
        "enabled": service.settings.ai_enabled,
        "provider": service.settings.ai_provider,
        "model_name": service.settings.ai_model_name,
        "base_url": service.settings.ai_base_url,
        "timeout_seconds": service.settings.ai_timeout_seconds,
        "temperature": service.settings.ai_temperature,
        "has_cached_diagnosis": cached is not None,
        "cached_diagnosis_source": cached_source,
        "provider_available": provider_info["available"] if should_check else None,
        "model_available": provider_info["model_available"] if should_check else None,
        "ollama_available": provider_info["available"] if should_check else None,
        "gemma_available": provider_info["available"] if (should_check and service.settings.ai_provider == "gemma") else None,
        "has_api_key": bool(service.settings.gemma_api_key),
        "fallback_active": fallback_active,
    }
