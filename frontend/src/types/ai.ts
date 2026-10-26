/**
 * Type definitions for SentinelAI AI Diagnostic Assistant.
 * Matches backend schemas in app/ai/models.py.
 */

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW';
export type SafetyLevel = 'SAFE' | 'CAUTION' | 'CRITICAL';

export interface ProbableCause {
  rank: number;
  hypothesis: string;
  confidence: ConfidenceLevel;
  supporting_evidence: string[];
}

export interface RemediationAction {
  step_number: number;
  action: string;
  command: string | null;
  safety_level: SafetyLevel;
  precautions: string;
}

export interface InvestigationStep {
  step_number: number;
  description: string;
  command?: string | null;
  target_subsystem?: string | null;
}

export interface AIIncidentDiagnosis {
  incident_id: string;
  timestamp: string;
  status: string;
  risk_category: string;
  health_score: number | null;
  anomaly_score: number;
  incident_summary: string;
  probable_causes: ProbableCause[];
  investigation_steps: string[];
  remediation_actions: RemediationAction[];
  uncertainty_assessment: string;
  is_fallback: boolean;
  model_used: string;
  latency_ms: number;
  metadata?: Record<string, unknown>;
}

export interface AIDiagnosisRequest {
  scenario?: string;
  persist?: boolean;
  force_fallback?: boolean;
}

export interface AIStatusResponse {
  enabled: boolean;
  provider: string;
  model_name: string;
  base_url: string;
  timeout_seconds: number;
  temperature?: number;
  has_cached_diagnosis: boolean;
  cached_diagnosis_source: string | null;
  provider_available?: boolean | null;
  ollama_available?: boolean | null;
  gemma_available?: boolean | null;
  has_api_key?: boolean;
  model_available: boolean | null;
  fallback_active: boolean;
}
