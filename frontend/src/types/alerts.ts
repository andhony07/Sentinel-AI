export type AlertSeverity = 'HIGH' | 'CRITICAL';
export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface RiskAlert {
  id: number;
  alert_id: string;
  server_id: string;
  severity: AlertSeverity;
  status: AlertStatus;
  risk_category: string;
  risk_score: number;
  health_score?: number | null;
  trigger_metric: string;
  observed_value?: number | null;
  observed_value_str?: string | null;
  title: string;
  summary: string;
  ai_explanation?: string | null;
  diagnostic_explanation: string;
  recommended_action: string;
  remediation_steps: string[];
  created_at: string;
  updated_at: string;
  acknowledged_at?: string | null;
  acknowledged_by?: string | null;
  resolved_at?: string | null;
  metric_id?: number | null;
}

export interface AlertSummary {
  active_count: number;
  critical_count: number;
  high_count: number;
  acknowledged_count: number;
  resolved_count: number;
  total_count: number;
  latest_active_alert?: RiskAlert | null;
}

export interface AlertListResponse {
  alerts: RiskAlert[];
  total: number;
  limit: number;
  offset: number;
}
