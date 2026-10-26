import React from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Cpu,
  Info,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
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
  const isFallbackActive = status?.fallback_active ?? true;
  const isGemma = status?.provider === 'gemma' || modelName.toLowerCase().includes('gemma');
  const providerActiveLabel = isGemma ? 'Gemma Active' : 'Live Ollama Active';

  return (
    <div data-testid="ai-diagnostic-assistant-card">
      <Card
        title={
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-sky-400" />
            <span>SentinelAI Diagnostic Assistant</span>
          </div>
        }
        subtitle="Synthesizes live telemetry, top processes, and ML anomaly evaluations into an evidence-grounded incident runbook."
        action={
          <div className="flex flex-wrap items-center gap-2">
            {/* Model Name & Live Provider Badge */}
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-800/80 border border-slate-700/60 text-slate-300"
              data-testid="ai-model-badge"
            >
              <Cpu className="w-3.5 h-3.5 text-sky-400" />
              <span>{modelName}</span>
            </div>

            {/* AI Status Badge */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${
                isFallbackActive
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
              }`}
              data-testid="ai-status-badge"
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isFallbackActive ? 'bg-amber-400' : 'bg-emerald-400'
                }`}
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
              className="flex items-center gap-1.5"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                  <span>Generate AI Diagnosis</span>
                </>
              )}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Loading Indicator (Non-blocking inline feedback) */}
          {loading && (
            <div
              className="p-4 rounded-lg bg-sky-950/20 border border-sky-500/30 text-sky-200 animate-pulse flex items-start gap-3"
              data-testid="ai-loading-state"
            >
              <Loader2 className="w-5 h-5 animate-spin text-sky-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="text-sm font-semibold text-sky-300">
                  Generating AI Incident Diagnosis...
                </div>
                <div className="text-xs text-sky-200/80 leading-relaxed">
                  Synthesizing live system metrics, anomaly vectors, and active process signatures.
                  Evaluating incident runbook via Gemma 4. If the provider times out or is unreachable, the assistant will automatically switch to the deterministic fallback.
                </div>
              </div>
            </div>
          )}

          {/* Error State Banner */}
          {error && !loading && (
            <div
              className="p-4 rounded-lg bg-rose-950/30 border border-rose-500/40 text-rose-200 flex items-start justify-between gap-3"
              data-testid="ai-error-state"
            >
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-sm font-semibold text-rose-300">
                    AI Diagnostic Evaluation Error
                  </div>
                  <div className="text-xs text-rose-200/80 mt-0.5">{error}</div>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={onRetry || (() => onGenerate(false))}
                data-testid="ai-retry-button"
                className="shrink-0"
              >
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                Retry
              </Button>
            </div>
          )}

          {/* Empty State (when no diagnosis exists yet and not loading) */}
          {!diagnosis && !loading && !error && (
            <div
              className="p-8 text-center rounded-lg border border-dashed border-slate-700/70 bg-slate-900/40"
              data-testid="ai-empty-state"
            >
              <div className="inline-flex p-3 rounded-full bg-slate-800/80 text-sky-400 mb-3">
                <Bot className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-semibold text-slate-200">No AI Diagnosis Generated</h4>
              <p className="text-xs text-slate-400 max-w-md mx-auto mt-1 mb-4 leading-relaxed">
                Click &apos;Generate AI Diagnosis&apos; to synthesize live telemetry, ML anomaly evaluation, and top processes into an evidence-grounded incident runbook.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onGenerate(false)}
                data-testid="ai-empty-generate-button"
                className="inline-flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                <span>Generate AI Diagnosis</span>
              </Button>
            </div>
          )}

          {/* Rendered Diagnosis Content */}
          {diagnosis && (
            <div className="space-y-4" data-testid="ai-diagnosis-content">
              {/* 1. Header Banner & Executive Incident Summary */}
              <div className="p-4 rounded-lg bg-slate-900/60 border border-slate-700/60 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Mode Badge */}
                    {diagnosis.is_fallback ? (
                      <span
                        className="px-2 py-0.5 rounded text-[11px] font-bold tracking-wider uppercase bg-amber-500/15 text-amber-400 border border-amber-500/40"
                        data-testid="diagnosis-source-badge"
                      >
                        DETERMINISTIC FALLBACK
                      </span>
                    ) : (
                      <span
                        className="px-2 py-0.5 rounded text-[11px] font-bold tracking-wider uppercase bg-sky-500/15 text-sky-400 border border-sky-500/40"
                        data-testid="diagnosis-source-badge"
                      >
                        AI-POWERED DIAGNOSIS • {diagnosis.model_used.toUpperCase()}
                      </span>
                    )}
                    <span className="text-xs text-slate-400">
                      ID: <code className="text-slate-300 font-mono text-[11px]">{diagnosis.incident_id}</code>
                    </span>
                  </div>

                  <div className="text-xs text-slate-400" data-testid="diagnosis-latency-badge">
                    {diagnosis.is_fallback ? (
                      <span className="text-amber-400/90">
                        AI service unavailable or offline • Latency: <b className="font-mono">{diagnosis.latency_ms.toFixed(1)}ms</b>
                      </span>
                    ) : (
                      <span className="text-sky-400/90">
                        Model: <b>{diagnosis.model_used}</b> • Latency: <b className="font-mono">{diagnosis.latency_ms.toFixed(1)}ms</b>
                      </span>
                    )}
                  </div>
                </div>

                {/* Natural Language Summary */}
                <div
                  className="text-sm font-medium text-slate-100 leading-relaxed"
                  data-testid="ai-incident-summary"
                >
                  {diagnosis.incident_summary}
                </div>

                {/* Authoritative ML Scores Row */}
                <div
                  className="flex flex-wrap items-center gap-4 pt-2 border-t border-slate-800/80 text-xs text-slate-400"
                  data-testid="ai-scores-row"
                >
                  <div>
                    Operational Risk:{' '}
                    <b
                      className={`font-semibold ${
                        diagnosis.risk_category === 'Critical' || diagnosis.risk_category === 'High'
                          ? 'text-rose-400'
                          : diagnosis.risk_category === 'Moderate'
                          ? 'text-amber-400'
                          : 'text-emerald-400'
                      }`}
                    >
                      {diagnosis.risk_category}
                    </b>
                  </div>
                  <div>
                    Anomaly Score:{' '}
                    <b className="font-mono text-slate-200">
                      {diagnosis.anomaly_score.toFixed(4)}
                    </b>
                  </div>
                  <div>
                    Health Score:{' '}
                    <b className="font-mono text-slate-200">
                      {diagnosis.health_score !== null ? `${diagnosis.health_score.toFixed(1)}/100` : 'N/A'}
                    </b>
                  </div>
                  {diagnosis.status && (
                    <div>
                      Status:{' '}
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-slate-800 text-slate-300">
                        {diagnosis.status}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* 2. Mandatory Human Review Required Banner */}
              <div
                className="p-3.5 rounded-lg bg-rose-950/25 border border-rose-500/40 text-rose-200 space-y-1.5"
                data-testid="mandatory-human-review-banner"
              >
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                  <span className="text-xs font-bold uppercase tracking-wider text-rose-400">
                    Mandatory Operator Review Required
                  </span>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed pl-6">
                  AI-generated remediation suggestions are strictly advisory and generated by an untrusted language model.
                  <strong className="text-rose-300 ml-1">Autonomous command execution is permanently disabled.</strong> Operators must independently inspect target PIDs, verify command semantics for the active OS, and confirm prerequisites before executing any operational action.
                </p>
              </div>

              {/* 3. Evidence-Based Probable Causes */}
              {diagnosis.probable_causes && diagnosis.probable_causes.length > 0 && (
                <div className="space-y-2.5" data-testid="ai-probable-causes-section">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <span>🔍</span>
                    <span>Evidence-Based Probable Causes</span>
                  </div>

                  <div className="space-y-2">
                    {diagnosis.probable_causes.map((cause) => {
                      const cStyle = confidenceStyles[cause.confidence] || {
                        bg: 'rgba(148, 163, 184, 0.15)',
                        text: '#94A3B8',
                        border: '#94A3B8',
                      };

                      return (
                        <div
                          key={cause.rank}
                          className="p-3 rounded-md bg-slate-900/50 border-l-4 transition-all"
                          style={{
                            borderLeftColor: cStyle.border,
                            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
                            borderRight: '1px solid rgba(255, 255, 255, 0.05)',
                            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          }}
                          data-testid={`probable-cause-${cause.rank}`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1.5">
                            <span className="text-xs font-semibold text-slate-100">
                              Cause #{cause.rank}: {cause.hypothesis}
                            </span>
                            <span
                              className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded tracking-wider"
                              style={{ backgroundColor: cStyle.bg, color: cStyle.text }}
                            >
                              {cause.confidence} CONFIDENCE
                            </span>
                          </div>

                          {cause.supporting_evidence && cause.supporting_evidence.length > 0 && (
                            <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside pl-1 pt-1">
                              {cause.supporting_evidence.map((ev, idx) => (
                                <li key={idx} className="leading-relaxed">
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
                <div className="space-y-2.5" data-testid="ai-investigation-steps-section">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <span>🔬</span>
                    <span>Prioritized Investigation Steps</span>
                  </div>

                  <div className="space-y-2">
                    {diagnosis.investigation_steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2.5 text-xs text-slate-200 p-2 rounded-md bg-slate-900/40 border border-slate-800/80"
                      >
                        <span className="flex items-center justify-center w-4 h-4 rounded-full bg-slate-800 text-[10px] font-bold text-slate-400 shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        <span className="leading-relaxed">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. Prioritized Remediation Runbook */}
              {diagnosis.remediation_actions && diagnosis.remediation_actions.length > 0 && (
                <div className="space-y-2.5" data-testid="ai-remediation-runbook-section">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <span>🛠️</span>
                    <span>Prioritized Remediation Runbook (Human Review Required)</span>
                  </div>

                  <div className="space-y-2">
                    {diagnosis.remediation_actions.map((act) => {
                      const sStyle = safetyStyles[act.safety_level] || {
                        bg: 'rgba(148, 163, 184, 0.15)',
                        text: '#94A3B8',
                        border: '#94A3B8',
                      };

                      return (
                        <div
                          key={act.step_number}
                          className="p-3 rounded-md bg-slate-900/50 border border-slate-800/80 space-y-2"
                          data-testid={`remediation-step-${act.step_number}`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-slate-100">
                              Step {act.step_number}: {act.action}
                            </span>
                            <span
                              className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded tracking-wider"
                              style={{ backgroundColor: sStyle.bg, color: sStyle.text }}
                            >
                              {act.safety_level}
                            </span>
                          </div>

                          {act.command ? (
                            <div className="space-y-1">
                              <div className="p-2 rounded bg-slate-950 border border-slate-800 overflow-x-auto">
                                <code className="text-xs font-mono text-sky-300 whitespace-pre">
                                  {act.command}
                                </code>
                              </div>
                              <div className="text-[10px] text-slate-400 flex items-center gap-1 italic">
                                <AlertTriangle className="w-3 h-3 text-amber-400" />
                                <span>Manual review required — command execution is disabled</span>
                              </div>
                            </div>
                          ) : (
                            <div className="text-xs text-slate-500 italic">
                              [No automated command provided • manual inspection required]
                            </div>
                          )}

                          <div className="text-xs text-slate-400 italic">
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
                  className="p-3 rounded-md bg-slate-800/30 border-l-4 border-slate-600 text-xs space-y-1.5"
                  data-testid="ai-uncertainty-assessment"
                >
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1">
                    <Info className="w-3.5 h-3.5 text-slate-400" />
                    <span>Evidence Boundaries &amp; Uncertainty Assessment</span>
                  </div>
                  <p className="text-slate-400 leading-relaxed">
                    {diagnosis.uncertainty_assessment}
                  </p>
                  <div className="text-[10px] text-slate-500 pt-1">
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
