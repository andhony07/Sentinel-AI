"""SentinelAI AI Diagnostic Assistant Package.

Exposes the standardized diagnostic models, prompt engineering routines, Gemma client,
Ollama client, fallback adapter, and AIDiagnosticService coordinator.
"""

from __future__ import annotations

from app.ai.gemma_client import (
    DEFAULT_GEMMA_MODEL,
    ALTERNATIVE_GEMMA_MODEL,
    GemmaAuthError,
    GemmaClient,
    GemmaClientError,
    GemmaMalformedJSONError,
    GemmaResponseError,
    GemmaTimeoutError,
)
from app.ai.client import (
    OllamaClient,
    OllamaClientError,
    OllamaConnectionError,
    OllamaMalformedJSONError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from app.ai.fallback import diagnostic_report_to_ai_diagnosis
from app.ai.models import (
    AIDiagnosisRequest,
    AIIncidentDiagnosis,
    ConfidenceLevel,
    InvestigationStep,
    ProbableCause,
    RemediationAction,
    SafetyLevel,
)
from app.ai.prompts import build_diagnostic_prompt
from app.ai.service import AIDiagnosticService
from app.ai.safety import (
    get_target_os,
    is_critical_process,
    is_dangerous_command,
    is_command_compatible_with_os,
    sanitize_remediation_and_evidence,
)

__all__ = [
    "AIDiagnosisRequest",
    "AIIncidentDiagnosis",
    "AIDiagnosticService",
    "ConfidenceLevel",
    "DEFAULT_GEMMA_MODEL",
    "ALTERNATIVE_GEMMA_MODEL",
    "GemmaAuthError",
    "GemmaClient",
    "GemmaClientError",
    "GemmaMalformedJSONError",
    "GemmaResponseError",
    "GemmaTimeoutError",
    "InvestigationStep",
    "OllamaClient",
    "OllamaClientError",
    "OllamaConnectionError",
    "OllamaMalformedJSONError",
    "OllamaResponseError",
    "OllamaTimeoutError",
    "ProbableCause",
    "RemediationAction",
    "SafetyLevel",
    "build_diagnostic_prompt",
    "diagnostic_report_to_ai_diagnosis",
    "get_target_os",
    "is_critical_process",
    "is_dangerous_command",
    "is_command_compatible_with_os",
    "sanitize_remediation_and_evidence",
]
