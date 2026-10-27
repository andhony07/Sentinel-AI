import React, { useEffect, useState, useMemo } from 'react';
import {
  AlertTriangle,
  AlertOctagon,
  ArrowRight,
  Bell,
  BellOff,
  CheckCircle2,
  Clock,
  Eye,
  RefreshCw,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  Zap,
} from 'lucide-react';
import { acknowledgeAlert, listAlerts, resolveAlert } from '../api';
import type { RiskAlert } from '../types';
import { Card, Button } from '../components/common';

interface AlertsNotificationsViewProps {
  notificationsEnabled: boolean;
  permission: NotificationPermission | 'unsupported';
  isSupported: boolean;
  onToggleNotifications: () => Promise<void>;
  onRequestPermission: () => Promise<boolean>;
  onNavigateToDiagnostic?: () => void;
}

export const AlertsNotificationsView: React.FC<AlertsNotificationsViewProps> = ({
  notificationsEnabled,
  permission,
  isSupported,
  onToggleNotifications,
  onRequestPermission,
  onNavigateToDiagnostic,
}) => {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [isActionPending, setIsActionPending] = useState<string | null>(null);

  const fetchAlerts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await listAlerts({ limit: 100 });
      setAlerts(res.alerts || []);
      if (res.alerts && res.alerts.length > 0 && !selectedAlertId) {
        const active = res.alerts.find((a) => a.status === 'ACTIVE') || res.alerts[0];
        setSelectedAlertId(active.alert_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve alert records from SentinelAI backend.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleAcknowledge = async (alertId: string) => {
    setIsActionPending(alertId);
    try {
      const updated = await acknowledgeAlert(alertId, 'lead_operator');
      setAlerts((prev) => prev.map((a) => (a.alert_id === alertId ? updated : a)));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      alert(`Acknowledgement error: ${msg}`);
    } finally {
      setIsActionPending(null);
    }
  };

  const handleResolve = async (alertId: string) => {
    setIsActionPending(alertId);
    try {
      const updated = await resolveAlert(alertId);
      setAlerts((prev) => prev.map((a) => (a.alert_id === alertId ? updated : a)));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      alert(`Resolution error: ${msg}`);
    } finally {
      setIsActionPending(null);
    }
  };

  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      if (statusFilter !== 'ALL' && alert.status !== statusFilter) return false;
      if (severityFilter !== 'ALL' && alert.severity !== severityFilter) return false;
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        return (
          alert.server_id.toLowerCase().includes(query) ||
          alert.trigger_metric.toLowerCase().includes(query) ||
          alert.title.toLowerCase().includes(query) ||
          alert.summary.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [alerts, statusFilter, severityFilter, searchQuery]);

  const selectedAlert = useMemo(() => {
    return alerts.find((a) => a.alert_id === selectedAlertId) || null;
  }, [alerts, selectedAlertId]);

  const stats = useMemo(() => {
    const active = alerts.filter((a) => a.status === 'ACTIVE').length;
    const critical = alerts.filter((a) => a.status === 'ACTIVE' && a.severity === 'CRITICAL').length;
    const high = alerts.filter((a) => a.status === 'ACTIVE' && a.severity === 'HIGH').length;
    const acknowledged = alerts.filter((a) => a.status === 'ACKNOWLEDGED').length;
    const resolved = alerts.filter((a) => a.status === 'RESOLVED').length;
    return { active, critical, high, acknowledged, resolved, total: alerts.length };
  }, [alerts]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* View Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
            <ShieldAlert size={20} style={{ color: 'var(--status-warning)' }} />
            <span>Risk Alerts & Incident Notifications</span>
          </h1>
          <div className="page-subtitle">
            Authoritative lifecycle alerts for HIGH and CRITICAL server operational risk conditions
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchAlerts}
            disabled={isLoading}
            icon={<RefreshCw size={13} style={{ animation: isLoading ? 'spin 1s linear infinite' : 'none' }} />}
          >
            Refresh
          </Button>

          {isSupported && (
            <Button
              variant={notificationsEnabled ? 'secondary' : 'primary'}
              size="sm"
              onClick={onToggleNotifications}
              icon={
                notificationsEnabled ? (
                  <Bell size={13} style={{ color: 'var(--status-healthy)' }} />
                ) : (
                  <BellOff size={13} />
                )
              }
            >
              {notificationsEnabled ? 'Desktop Alerts: Enabled' : 'Enable Desktop Alerts'}
            </Button>
          )}
        </div>
      </div>

      {/* KPI Stats Cards - 5 Columns */}
      <div className="grid-cols-5">
        <div
          style={{
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Active Incidents
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 }}>
            {stats.active}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Requiring attention
          </div>
        </div>

        <div
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.08)',
            border: '1px solid var(--status-critical-border)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--status-critical)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertOctagon size={14} />
            <span>Critical Risk</span>
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--status-critical)', marginTop: 4 }}>
            {stats.critical}
          </div>
          <div style={{ fontSize: 11, color: '#fca5a5', marginTop: 2 }}>
            Immediate threat
          </div>
        </div>

        <div
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid var(--status-warning-border)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--status-warning)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={14} />
            <span>High Risk</span>
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--status-warning)', marginTop: 4 }}>
            {stats.high}
          </div>
          <div style={{ fontSize: 11, color: '#fcd34d', marginTop: 2 }}>
            Threshold breach
          </div>
        </div>

        <div
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.08)',
            border: '1px solid var(--status-info-border)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
            <UserCheck size={14} />
            <span>Acknowledged</span>
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--accent-primary)', marginTop: 4 }}>
            {stats.acknowledged}
          </div>
          <div style={{ fontSize: 11, color: '#bae6fd', marginTop: 2 }}>
            Operator reviewing
          </div>
        </div>

        <div
          style={{
            backgroundColor: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid var(--status-healthy-border)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--status-healthy)', textTransform: 'uppercase', letterSpacing: 0.5, display: 'flex', alignItems: 'center', gap: 6 }}>
            <CheckCircle2 size={14} />
            <span>Resolved</span>
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--status-healthy)', marginTop: 4 }}>
            {stats.resolved}
          </div>
          <div style={{ fontSize: 11, color: '#a7f3d0', marginTop: 2 }}>
            Automatic or manual
          </div>
        </div>
      </div>

      {/* Error Alert Box */}
      {error && (
        <div className="alert-box alert-danger">
          <AlertOctagon size={16} style={{ flexShrink: 0 }} />
          <span style={{ flex: 1 }}>{error}</span>
          <Button size="sm" variant="secondary" onClick={fetchAlerts}>
            Retry
          </Button>
        </div>
      )}

      {/* Permission Warning Notice if Denied */}
      {permission === 'denied' && (
        <div className="alert-box alert-warning">
          <BellOff size={16} style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            Desktop notifications are currently blocked in your browser settings. In-app alerts remain fully operational.
          </div>
          <button
            type="button"
            onClick={onRequestPermission}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-primary)',
              textDecoration: 'underline',
              cursor: 'pointer',
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            Review Site Permissions
          </button>
        </div>
      )}

      {/* Search and Filters Bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search by server, metric, or headline..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 12px 7px 32px',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: 12,
              outline: 'none',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)' }}>Status:</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: 12,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="ALL">All Statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="RESOLVED">Resolved</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
          <span style={{ color: 'var(--text-muted)' }}>Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              fontSize: 12,
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
          </select>
        </div>
      </div>

      {/* Main Split Grid: Left Feed (400px), Right Detail Inspector (1fr) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(340px, 420px) 1fr',
          gap: 18,
          alignItems: 'start',
          width: '100%',
        }}
      >
        {/* Left Column: Alerts Feed List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, padding: '0 4px' }}>
            <span>Incident Feed ({filteredAlerts.length})</span>
            {statusFilter !== 'ALL' && <span style={{ color: 'var(--accent-primary)' }}>Filtered</span>}
          </div>

          {isLoading && alerts.length === 0 ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
              <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 8px auto', color: 'var(--accent-primary)' }} />
              <div>Loading incident records...</div>
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="state-box" style={{ border: '1px dashed var(--border-default)', borderRadius: 'var(--radius-md)', backgroundColor: 'rgba(15, 23, 42, 0.4)' }}>
              <ShieldCheck size={36} style={{ color: 'var(--status-healthy)' }} />
              <div className="state-box-title">All Systems Normal</div>
              <div className="state-box-desc">
                No alerts match the active filter criteria. Hardware telemetry remains in healthy operational bands.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 660, overflowY: 'auto', paddingRight: 4 }}>
              {filteredAlerts.map((alert) => {
                const isSelected = alert.alert_id === selectedAlertId;
                const isCritical = alert.severity === 'CRITICAL';
                const isActive = alert.status === 'ACTIVE';

                let borderCol = 'var(--border-default)';
                let bgCol = 'var(--bg-card)';
                if (isSelected) {
                  borderCol = isCritical ? 'var(--status-critical)' : 'var(--status-warning)';
                  bgCol = isCritical ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)';
                } else if (isCritical) {
                  borderCol = 'var(--status-critical-border)';
                }

                return (
                  <div
                    key={alert.alert_id}
                    onClick={() => setSelectedAlertId(alert.alert_id)}
                    className="cursor-pointer"
                    style={{
                      padding: '12px 14px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: bgCol,
                      border: `1px solid ${borderCol}`,
                      cursor: 'pointer',
                      transition: 'all 150ms ease',
                      boxShadow: isSelected ? '0 2px 10px rgba(0,0,0,0.35)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: '50%',
                            backgroundColor: isCritical ? 'var(--status-critical)' : 'var(--status-warning)',
                            boxShadow: isCritical && isActive ? '0 0 8px var(--status-critical)' : 'none',
                          }}
                        />
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 800,
                            letterSpacing: 0.5,
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-xs)',
                            backgroundColor: isCritical ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                            color: isCritical ? 'var(--status-critical)' : 'var(--status-warning)',
                            border: `1px solid ${isCritical ? 'rgba(239, 68, 68, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`,
                          }}
                        >
                          {alert.severity}
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-xs)',
                            backgroundColor:
                              alert.status === 'ACTIVE'
                                ? 'rgba(239, 68, 68, 0.15)'
                                : alert.status === 'ACKNOWLEDGED'
                                ? 'rgba(56, 189, 248, 0.15)'
                                : 'rgba(16, 185, 129, 0.15)',
                            color:
                              alert.status === 'ACTIVE'
                                ? 'var(--status-critical)'
                                : alert.status === 'ACKNOWLEDGED'
                                ? 'var(--accent-primary)'
                                : 'var(--status-healthy)',
                          }}
                        >
                          {alert.status}
                        </span>
                      </div>

                      <div style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={11} />
                        <span>{new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>

                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 8, lineHeight: 1.3 }}>
                      {alert.title}
                    </div>

                    <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {alert.summary}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--text-muted)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'var(--font-mono)' }}>
                        <Server size={12} /> {alert.server_id}
                      </span>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {alert.trigger_metric}: {alert.observed_value_str || alert.observed_value}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Detailed Incident Inspection */}
        <div>
          {selectedAlert ? (
            <Card
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span
                    style={{
                      fontSize: 10.5,
                      fontWeight: 800,
                      letterSpacing: 0.6,
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-xs)',
                      backgroundColor: selectedAlert.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                      color: selectedAlert.severity === 'CRITICAL' ? 'var(--status-critical)' : 'var(--status-warning)',
                      border: `1px solid ${selectedAlert.severity === 'CRITICAL' ? 'var(--status-critical-border)' : 'var(--status-warning-border)'}`,
                    }}
                  >
                    {selectedAlert.severity} RISK
                  </span>
                  <span
                    style={{
                      fontSize: 10.5,
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-xs)',
                      backgroundColor:
                        selectedAlert.status === 'ACTIVE'
                          ? 'rgba(239, 68, 68, 0.15)'
                          : selectedAlert.status === 'ACKNOWLEDGED'
                          ? 'rgba(56, 189, 248, 0.15)'
                          : 'rgba(16, 185, 129, 0.15)',
                      color:
                        selectedAlert.status === 'ACTIVE'
                          ? 'var(--status-critical)'
                          : selectedAlert.status === 'ACKNOWLEDGED'
                          ? 'var(--accent-primary)'
                          : 'var(--status-healthy)',
                    }}
                  >
                    {selectedAlert.status}
                  </span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {selectedAlert.alert_id}
                  </span>
                </div>
              }
              action={
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {selectedAlert.status === 'ACTIVE' && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleAcknowledge(selectedAlert.alert_id)}
                      disabled={isActionPending === selectedAlert.alert_id}
                      icon={<UserCheck size={13} />}
                    >
                      Acknowledge
                    </Button>
                  )}
                  {selectedAlert.status !== 'RESOLVED' && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleResolve(selectedAlert.alert_id)}
                      disabled={isActionPending === selectedAlert.alert_id}
                      icon={<CheckCircle2 size={13} />}
                    >
                      Mark Resolved
                    </Button>
                  )}
                </div>
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Title & Metadata */}
                <div>
                  <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                    {selectedAlert.title}
                  </h2>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--accent-primary)' }}>
                      <Server size={13} /> {selectedAlert.server_id}
                    </span>
                    <span>•</span>
                    <span>Created: {new Date(selectedAlert.created_at).toLocaleString()}</span>
                  </div>
                </div>

                {/* 4 Metric KPI Boxes */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Composite Risk
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: selectedAlert.severity === 'CRITICAL' ? 'var(--status-critical)' : 'var(--status-warning)', marginTop: 2 }}>
                      {selectedAlert.risk_score.toFixed(2)}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{selectedAlert.risk_category}</div>
                  </div>

                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Health Score
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: (selectedAlert.health_score ?? 100) < 50 ? 'var(--status-critical)' : 'var(--status-warning)', marginTop: 2 }}>
                      {selectedAlert.health_score !== null && selectedAlert.health_score !== undefined ? `${selectedAlert.health_score.toFixed(1)}/100` : '--'}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Deterministic</div>
                  </div>

                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Trigger Metric
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={selectedAlert.trigger_metric}>
                      {selectedAlert.trigger_metric}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Primary Breach</div>
                  </div>

                  <div style={{ padding: '10px 12px', backgroundColor: 'var(--bg-input)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      Observed Value
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent-primary)', marginTop: 2 }}>
                      {selectedAlert.observed_value_str || selectedAlert.observed_value}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Threshold Exceeded</div>
                  </div>
                </div>

                {/* Deterministic Diagnostic Findings Box */}
                <div style={{ padding: '14px 16px', backgroundColor: 'var(--bg-card-subtle)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Zap size={14} style={{ color: 'var(--accent-primary)' }} />
                      <span>Deterministic Diagnostic Findings</span>
                    </div>
                    {onNavigateToDiagnostic && (
                      <button
                        type="button"
                        onClick={onNavigateToDiagnostic}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent-primary)',
                          fontSize: 11,
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 4,
                        }}
                      >
                        Open Live Diagnostic Assistant <ArrowRight size={12} />
                      </button>
                    )}
                  </div>

                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                    {selectedAlert.diagnostic_explanation}
                  </div>

                  {selectedAlert.summary && (
                    <div style={{ marginTop: 10, padding: '8px 12px', backgroundColor: 'rgba(56, 189, 248, 0.08)', borderLeft: '3px solid var(--accent-primary)', borderRadius: '0 var(--radius-sm) var(--radius-sm) 0', fontSize: 11.5, color: '#e0f2fe' }}>
                      {selectedAlert.summary}
                    </div>
                  )}
                </div>

                {/* Recommended Investigation & Action */}
                <div style={{ padding: '14px 16px', backgroundColor: 'var(--bg-card-subtle)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                    <Eye size={14} style={{ color: 'var(--status-warning)' }} />
                    <span>Recommended Investigation & Action</span>
                  </div>

                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 10 }}>
                    {selectedAlert.recommended_action}
                  </div>

                  {selectedAlert.remediation_steps && selectedAlert.remediation_steps.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Actionable Remediation Runbook:
                      </div>
                      {selectedAlert.remediation_steps.map((step, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 8,
                            padding: '6px 10px',
                            backgroundColor: 'var(--bg-input)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-xs)',
                            fontSize: 11.5,
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <span style={{ fontWeight: 700, color: 'var(--accent-primary)', minWidth: 16 }}>{idx + 1}.</span>
                          <span style={{ flex: 1, fontFamily: step.startsWith('sudo') || step.startsWith('systemctl') ? 'var(--font-mono)' : 'inherit' }}>{step}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* AI Explanation If Present */}
                {selectedAlert.ai_explanation && (
                  <div style={{ padding: '12px 14px', backgroundColor: 'rgba(168, 85, 247, 0.08)', border: '1px solid rgba(168, 85, 247, 0.35)', borderRadius: 'var(--radius-md)', fontSize: 12 }}>
                    <div style={{ fontSize: 11.5, fontWeight: 700, color: '#d8b4fe', marginBottom: 4 }}>
                      Gemma 4 AI Root-Cause Diagnostic:
                    </div>
                    <div style={{ color: '#f3e8ff', lineHeight: 1.5 }}>
                      {selectedAlert.ai_explanation}
                    </div>
                  </div>
                )}

                {/* Audit Trail Footer */}
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingTop: 10, borderTop: '1px solid var(--border-subtle)', fontSize: 11, color: 'var(--text-muted)' }}>
                  <div>
                    {selectedAlert.acknowledged_at && (
                      <span>
                        Acknowledged by <strong style={{ color: 'var(--text-secondary)' }}>{selectedAlert.acknowledged_by || 'operator'}</strong> at {new Date(selectedAlert.acknowledged_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  <div>
                    {selectedAlert.resolved_at && (
                      <span>
                        Resolved at {new Date(selectedAlert.resolved_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            <Card>
              <div className="state-box">
                <ShieldCheck size={40} style={{ color: 'var(--text-muted)' }} />
                <div className="state-box-title">No Incident Selected</div>
                <div className="state-box-desc">
                  Select an alert card from the Incident Feed on the left to inspect detailed telemetry metrics, deterministic findings, and remediation steps.
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
};
