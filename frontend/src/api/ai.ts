/**
 * AI Diagnostic Assistant API client functions.
 * Connects to FastAPI /api/ai endpoints.
 */

import { apiClient } from './client';
import type {
  AIDiagnosisRequest,
  AIIncidentDiagnosis,
  AIStatusResponse,
} from '../types';

/**
 * Inspect AI Diagnostic Assistant status (provider, reachability, model name).
 */
export async function getAIStatus(checkReachability = true): Promise<AIStatusResponse> {
  const query = checkReachability ? '?check_reachability=true' : '?check_reachability=false';
  return apiClient<AIStatusResponse>(`/ai/status${query}`);
}

/**
 * Retrieve the latest cached or evaluated AI incident diagnosis.
 */
export async function getLatestAIDiagnosis(): Promise<AIIncidentDiagnosis> {
  return apiClient<AIIncidentDiagnosis>('/ai/latest');
}

/**
 * Generate on-demand AI incident diagnosis.
 * Always resolves to a valid diagnosis, falling back gracefully if Ollama is unreachable.
 */
export async function generateAIDiagnosis(
  payload?: AIDiagnosisRequest
): Promise<AIIncidentDiagnosis> {
  return apiClient<AIIncidentDiagnosis>('/ai/diagnose', {
    method: 'POST',
    body: JSON.stringify(payload ?? {}),
  });
}
