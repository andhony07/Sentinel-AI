import { apiClient } from './client';
import type { AlertListResponse, AlertSummary, RiskAlert } from '../types';

export async function getAlertSummary(): Promise<AlertSummary> {
  return apiClient<AlertSummary>('/alerts/summary');
}

export async function listAlerts(params?: {
  status?: string;
  severity?: string;
  server_id?: string;
  limit?: number;
  offset?: number;
}): Promise<AlertListResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.severity) query.set('severity', params.severity);
  if (params?.server_id) query.set('server_id', params.server_id);
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));

  const qs = query.toString();
  return apiClient<AlertListResponse>(qs ? `/alerts?${qs}` : '/alerts');
}

export async function getAlertDetail(alertId: string): Promise<RiskAlert> {
  return apiClient<RiskAlert>(`/alerts/${alertId}`);
}

export async function acknowledgeAlert(alertId: string, acknowledgedBy = 'operator'): Promise<RiskAlert> {
  return apiClient<RiskAlert>(`/alerts/${alertId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ acknowledged_by: acknowledgedBy }),
  });
}

export async function resolveAlert(alertId: string): Promise<RiskAlert> {
  return apiClient<RiskAlert>(`/alerts/${alertId}/resolve`, {
    method: 'POST',
  });
}
