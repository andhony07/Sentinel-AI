import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Cpu,
  Info,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Wrench,
  Zap,
} from 'lucide-react';
import type {
  AIIncidentDiagnosis,
  AIStatusResponse,
  ConfidenceLevel,
  SafetyLevel,
} from '../../types';
import { Button } from './Button';
import { Card } from './Card';

export interface AIDiagnosticCardProps {
  diagnosis: AIIncidentDiagnosis | null;
  status: AIStatusResponse | null;
  loading: boolean;
  error: string | null;
  onGenerate: (forceFallback?: boolean) => void;
  onRetry?: () => void;
}

const confidenceStyles: Record<ConfidenceLevel, { bg: string; text: string; border: string }> = {
  HIGH: {
    bg: 'rgba(239, 68, 68, 0.15)',
    text: '#EF4444',
    border: '#EF4444',
  },
  MEDIUM: {
    bg: 'rgba(245, 158, 11, 0.15)',
    text: '#F59E0B',
    border: '#F59E0B',
  },
  LOW: {
    bg: 'rgba(56, 189, 248, 0.15)',
    text: '#38BDF8',
    border: '#38BDF8',
  },
};

const safetyStyles: Record<SafetyLevel, { bg: string; text: string; border: string }> = {
  SAFE: {
    bg: 'rgba(16, 185, 129, 0.15)',
    text: '#10B981',
    border: '#10B981',
  },
  CAUTION: {
    bg: 'rgba(245, 158, 11, 0.15)',
    text: '#F59E0B',
    border: '#F59E0B',
  },
  CRITICAL: {
    bg: 'rgba(239, 68, 68, 0.15)',
    text: '#EF4444',
    border: '#EF4444',
  },
};

export const AIDiagnosticCard: React.FC<AIDiagnosticCardProps> = ({
  diagnosis,
  status,
  loading,
  error,
  onGenerate,
  onRetry,
}) => {
  const modelName = status?.model_name || 'gemma-4-26b-a4b-it';
  const isFallbackActive = status?.fallback_active ?? (diagnosis?.is_fallback ?? true);
  const isGemma = status?.provider === 'gemma' || modelName.toLowerCase().includes('gemma');
  const providerActiveLabel = isGemma ? 'Gemma Active' : 'Live Ollama Active';

  // Extract fallback reason if present
  const fallbackReason =
    diagnosis?.fallback_reason ||
    (diagnosis?.metadata && typeof diagnosis.metadata === 'object' && (diagnosis.metadata as Record<string, unknown>).fallback_reason as string) ||
    'AI service offline or timed out; deterministic heuristic engine engaged.';

  return (
    <div data-testid="ai-diagnostic-assistant-card" style={{ width: '100%' }}>
      <Card
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={18} style={{ color: 'var(--accent-primary)' }} />
            <span>SentinelAI Diagnostic Assistant</span>
          </div>
        }
        subtitle="Synthesizes live telemetry, top processes, and ML anomaly evaluations into an evidence-grounded incident runbook."
        action={
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            {/* Model Name & Live Provider Badge */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11,
                fontWeight: 600,
                backgroundColor: 'var(--bg-input)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)',
              }}
              data-testid="ai-model-badge"
            >
              <Cpu size={13} style={{ color: 'var(--accent-primary)' }} />
              <span>{modelName}</span>
            </div>

            {/* AI Status Badge */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 11,
                fontWeight: 600,
                backgroundColor: isFallbackActive ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                border: `1px solid ${isFallbackActive ? 'rgba(245, 158, 11, 0.35)' : 'rgba(16, 185, 129, 0.35)'}`,
                color: isFallbackActive ? 'var(--status-warning)' : 'var(--status-healthy)',
              }}
              data-testid="ai-status-badge"
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: isFallbackActive ? 'var(--status-warning)' : 'var(--status-healthy)',
                }}
              />
              <span>{isFallbackActive ? 'Fallback Active' : providerActiveLabel}</span>
            </div>

            {/* Generate Button */}
            <Button
              variant="primary"
              size="sm"
              onClick={() => onGenerate(false)}
              disabled={loading}
              data-testid="generate-ai-diagnosis-button"
            >
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
                  <span>Evaluating...</span>
                </span>
              ) : (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Sparkles size={13} style={{ color: '#FCD34D' }} />
                  <span>Generate AI Diagnosis</span>
                </span>
              )}
            </Button>
          </div>
        }
      >
        <div className="ai-diagnostic-wrapper">
          {/* Loading Indicator */}
          {loading && (
            <div
              style={{
                padding: '16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid var(--border-focus)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 12,
              }}
              data-testid="ai-loading-state"
            >
              <Loader2 size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent-primary)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent-primary)' }}>
                  Generating AI Incident Diagnosis...
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
                  Synthesizing live system metrics, anomaly vectors, and active process signatures.
                  Evaluating incident runbook via Gemma 4. If the provider times out or is unreachable, the assistant will automatically switch to the deterministic fallback.
                </div>
              </div>
            </div>
          )}

          {/* Error State Banner */}
          {error && !loading && (
            <div
              style={{
                padding: '14px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--status-critical-bg)',
                border: '1px solid var(--status-critical-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
              data-testid="ai-error-state"
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <AlertCircle size={18} style={{ color: 'var(--status-critical)', flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: '#FCA5A5' }}>
                    AI Diagnostic Evaluation Error
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 2 }}>
                    {error}
                  </div>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={onRetry || (() => onGenerate(false))}
                data-testid="ai-retry-button"
              >
                <RefreshCw size={12} style={{ marginRight: 6 }} />
                Retry
              </Button>
            </div>
          )}

          {/* Empty State */}
          {!diagnosis && !loading && !error && (
            <div
              style={{
                padding: '36px 20px',
                textAlign: 'center',
                borderRadius: 'var(--radius-md)',
                border: '1px dashed var(--border-default)',
                backgroundColor: 'rgba(15, 23, 42, 0.4)',
              }}
              data-testid="ai-empty-state"
            >
              <div
                style={{
                  display: 'inline-flex',
                  padding: 12,
                  borderRadius: '50%',
                  backgroundColor: 'var(--bg-input)',
                  color: 'var(--accent-primary)',
                  marginBottom: 12,
                }}
              >
                <Bot size={28} />
              </div>
              <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                No AI Diagnosis Generated
              </h4>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 440, margin: '0 auto 16px auto', lineHeight: 1.5 }}>
                Click &apos;Generate AI Diagnosis&apos; to synthesize live telemetry, ML anomaly evaluation, and top processes into an evidence-grounded incident runbook.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onGenerate(false)}
                data-testid="ai-empty-generate-button"
              >
                <Sparkles size={13} style={{ marginRight: 6, color: '#FCD34D' }} />
                Generate AI Diagnosis
              </Button>
            </div>
          )}

          {/* Rendered Diagnosis Content */}
          {diagnosis && (
            <div className="ai-diagnostic-wrapper" data-testid="ai-diagnosis-content">
              {/* 1. Header Banner & Executive Incident Summary */}
              <div className="ai-meta-banner">
                <div className="ai-meta-left">
                  {/* Mode Badge */}
                  {diagnosis.is_fallback ? (
                    <span
                      className="ai-source-badge fallback"
                      data-testid="diagnosis-source-badge"
                    >
                      DETERMINISTIC FALLBACK
                    </span>
                  ) : (
                    <span
                      className="ai-source-badge live"
                      data-testid="diagnosis-source-badge"
                    >
                      AI-POWERED DIAGNOSIS • {diagnosis.model_used.toUpperCase()}
                    </span>
                  )}
                  <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                    ID: <code style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{diagnosis.incident_id}</code>
                  </span>
                </div>

                <div className="ai-meta-right" data-testid="diagnosis-latency-badge">
                  {diagnosis.is_fallback ? (
                    <span style={{ color: 'var(--status-warning)' }}>
                      AI service unavailable or offline • Latency: <b style={{ fontFamily: 'var(--font-mono)' }}>{diagnosis.latency_ms.toFixed(1)}ms</b>
                    </span>
                  ) : (
                    <span style={{ color: 'var(--accent-primary)' }}>
                      Model: <b>{diagnosis.model_used}</b> • Latency: <b style={{ fontFamily: 'var(--font-mono)' }}>{diagnosis.latency_ms.toFixed(1)}ms</b>
                    </span>
                  )}
                </div>
              </div>

              {/* Clear Fallback Reason Notice when Fallback is Active */}
              {diagnosis.is_fallback && (
                <div className="ai-fallback-callout">
                  <div className="ai-fallback-callout-title">
                    <Info size={13} />
                    <span>Deterministic Fallback Engaged</span>
                  </div>
                  <div className="ai-fallback-callout-desc">
                    <strong>Reason:</strong> {fallbackReason}
                    <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>
                      Generative inference was bypassed or unreachable. The incident evaluation below is generated deterministically by the authoritative ML heuristics engine.
                    </div>
                  </div>
                </div>
              )}

              {/* Incident Summary Card */}
              <div className="ai-incident-summary-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                  <Zap size={13} style={{ color: 'var(--accent-primary)' }} />
                  <span>Executive Incident Summary</span>
                </div>

                <div className="ai-summary-text" data-testid="ai-incident-summary">
                  {diagnosis.incident_summary}
                </div>

                {/* Authoritative ML Scores Grid */}
                <div className="ai-scores-grid" data-testid="ai-scores-row">
                  <div className="ai-score-item">
                    <div className="ai-score-label">Operational Risk</div>
                    <div
                      className="ai-score-value"
                      style={{
                        color:
                          diagnosis.risk_category === 'Critical' || diagnosis.risk_category === 'High'
                            ? 'var(--status-critical)'
                            : diagnosis.risk_category === 'Moderate'
                            ? 'var(--status-warning)'
                            : 'var(--status-healthy)',
                      }}
                    >
                      {diagnosis.risk_category}
                    </div>
                  </div>

                  <div className="ai-score-item">
                    <div className="ai-score-label">Anomaly Score</div>
                    <div className="ai-score-value" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                      {diagnosis.anomaly_score.toFixed(4)}
                    </div>
                  </div>

                  <div className="ai-score-item">
                    <div className="ai-score-label">Health Score</div>
                    <div className="ai-score-value" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
                      {diagnosis.health_score !== null ? `${diagnosis.health_score.toFixed(1)}/100` : 'N/A'}
                    </div>
                  </div>

                  {diagnosis.status && (
                    <div className="ai-score-item">
                      <div className="ai-score-label">Status</div>
                      <div className="ai-score-value" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                        {diagnosis.status}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* 2. Mandatory Human Review Required Banner */}
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid var(--status-critical-border)',
                  color: '#FCA5A5',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                }}
                data-testid="mandatory-human-review-banner"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ShieldAlert size={16} style={{ color: 'var(--status-critical)', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.2px', color: 'var(--status-critical)' }}>
                    Mandatory Operator Review Required
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, paddingLeft: 24 }}>
                  AI-generated remediation suggestions are strictly advisory and generated by an untrusted language model.
                  <strong style={{ color: '#FCA5A5', marginLeft: 4 }}>Autonomous command execution is permanently disabled.</strong> Operators must independently inspect target PIDs, verify command semantics for the active OS, and confirm prerequisites before executing any operational action.
                </p>
              </div>

              {/* 3. Evidence-Based Probable Causes */}
              {diagnosis.probable_causes && diagnosis.probable_causes.length > 0 && (
                <div data-testid="ai-probable-causes-section" style={{ marginTop: 4 }}>
                  <div className="ai-section-heading">
                    <span className="ai-section-icon"><Search size={14} /></span>
                    <span>Evidence-Based Probable Causes</span>
                  </div>

                  <div>
                    {diagnosis.probable_causes.map((cause) => {
                      const cStyle = confidenceStyles[cause.confidence] || {
                        bg: 'rgba(148, 163, 184, 0.15)',
                        text: '#94A3B8',
                        border: '#94A3B8',
                      };

                      return (
                        <div
                          key={cause.rank}
                          className="ai-cause-card"
                          style={{ borderLeftColor: cStyle.border }}
                          data-testid={`probable-cause-${cause.rank}`}
                        >
                          <div className="ai-cause-header">
                            <span className="ai-cause-title">
                              Cause #{cause.rank}: {cause.hypothesis}
                            </span>
                            <span
                              className="ai-cause-confidence"
                              style={{ backgroundColor: cStyle.bg, color: cStyle.text }}
                            >
                              {cause.confidence} CONFIDENCE
                            </span>
                          </div>

                          {cause.supporting_evidence && cause.supporting_evidence.length > 0 && (
                            <ul className="ai-evidence-list">
                              {cause.supporting_evidence.map((ev, idx) => (
                                <li key={idx}>
                                  {ev}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 4. Prioritized Investigation Steps */}
              {diagnosis.investigation_steps && diagnosis.investigation_steps.length > 0 && (
                <div data-testid="ai-investigation-steps-section" style={{ marginTop: 4 }}>
                  <div className="ai-section-heading">
                    <span className="ai-section-icon"><CheckCircle2 size={14} /></span>
                    <span>Prioritized Investigation Steps</span>
                  </div>

                  <div>
                    {diagnosis.investigation_steps.map((step, idx) => (
                      <div key={idx} className="ai-step-card">
                        <span className="ai-step-number">
                          {idx + 1}
                        </span>
                        <span style={{ flex: 1 }}>{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Prioritized Remediation Runbook */}
              {diagnosis.remediation_actions && diagnosis.remediation_actions.length > 0 && (
                <div data-testid="ai-remediation-runbook-section" style={{ marginTop: 4 }}>
                  <div className="ai-section-heading">
                    <span className="ai-section-icon"><Wrench size={14} /></span>
                    <span>Prioritized Remediation Runbook (Human Review Required)</span>
                  </div>

                  <div>
                    {diagnosis.remediation_actions.map((act) => {
                      const sStyle = safetyStyles[act.safety_level] || {
                        bg: 'rgba(148, 163, 184, 0.15)',
                        text: '#94A3B8',
                        border: '#94A3B8',
                      };

                      return (
                        <div
                          key={act.step_number}
                          className="ai-remediation-card"
                          data-testid={`remediation-step-${act.step_number}`}
                        >
                          <div className="ai-remediation-header">
                            <span className="ai-remediation-title">
                              Step {act.step_number}: {act.action}
                            </span>
                            <span
                              className="ai-cause-confidence"
                              style={{ backgroundColor: sStyle.bg, color: sStyle.text }}
                            >
                              {act.safety_level}
                            </span>
                          </div>

                          {act.command ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                              <div className="ai-remediation-command-box">
                                {act.command}
                              </div>
                              <div className="ai-remediation-notice">
                                <AlertTriangle size={12} style={{ color: 'var(--status-warning)' }} />
                                <span>Manual review required — automated command execution is disabled</span>
                              </div>
                            </div>
                          ) : (
                            <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                              [No automated command provided • manual inspection required]
                            </div>
                          )}

                          <div className="ai-remediation-precaution">
                            • {act.precautions}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 6. Evidence Boundaries & Uncertainty Assessment */}
              {diagnosis.uncertainty_assessment && (
                <div
                  className="ai-uncertainty-box"
                  data-testid="ai-uncertainty-assessment"
                >
                  <div className="ai-uncertainty-title">
                    <Info size={13} />
                    <span>Evidence Boundaries &amp; Uncertainty Assessment</span>
                  </div>
                  <p style={{ margin: 0, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {diagnosis.uncertainty_assessment}
                  </p>
                  <div style={{ fontSize: 10.5, color: 'var(--text-muted)', paddingTop: 4 }}>
                    Advisory Notice: SentinelAI provides diagnostic guidance based on hardware sensors. Autonomous execution is prohibited; human operator validation is mandatory prior to remediation.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
