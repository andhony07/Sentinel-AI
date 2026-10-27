import React, { useState } from 'react';
import { AlertOctagon, AlertTriangle } from 'lucide-react';
import type { RiskAlert } from '../../types';
import { Sidebar } from './Sidebar';
import type { ViewType } from './Sidebar';
import { TopBar } from './TopBar';

interface LayoutProps {
  currentView: ViewType;
  onSelectView: (view: ViewType) => void;
  apiConnected: boolean;
  isBgRunning: boolean;
  isSnapshotLoading: boolean;
  isTogglingWorker: boolean;
  autoRefresh: boolean;
  refreshInterval: number;
  lastUpdated: string | null;
  activeAlertCount?: number;
  activeAlerts?: RiskAlert[];
  notificationsEnabled?: boolean;
  onToggleNotifications?: () => void;
  onCaptureSnapshot: () => void;
  onToggleWorker: () => void;
  onRefreshNow: () => void;
  onToggleAutoRefresh: (enabled: boolean) => void;
  onChangeRefreshInterval: (interval: number) => void;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({
  currentView,
  onSelectView,
  apiConnected,
  isBgRunning,
  isSnapshotLoading,
  isTogglingWorker,
  autoRefresh,
  refreshInterval,
  lastUpdated,
  activeAlertCount = 0,
  activeAlerts = [],
  notificationsEnabled = false,
  onToggleNotifications,
  onCaptureSnapshot,
  onToggleWorker,
  onRefreshNow,
  onToggleAutoRefresh,
  onChangeRefreshInterval,
  children,
}) => {
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [mobileOpen, setMobileOpen] = useState<boolean>(false);

  return (
    <div className="app-layout">
      <Sidebar
        currentView={currentView}
        onSelectView={onSelectView}
        apiConnected={apiConnected}
        activeAlertCount={activeAlertCount}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        isMobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className="main-content">
        <TopBar
          currentView={currentView}
          apiConnected={apiConnected}
          isBgRunning={isBgRunning}
          isSnapshotLoading={isSnapshotLoading}
          isTogglingWorker={isTogglingWorker}
          autoRefresh={autoRefresh}
          refreshInterval={refreshInterval}
          lastUpdated={lastUpdated}
          notificationsEnabled={notificationsEnabled}
          onToggleNotifications={onToggleNotifications}
          onCaptureSnapshot={onCaptureSnapshot}
          onToggleWorker={onToggleWorker}
          onRefreshNow={onRefreshNow}
          onToggleAutoRefresh={onToggleAutoRefresh}
          onChangeRefreshInterval={onChangeRefreshInterval}
          onOpenMobileMenu={() => setMobileOpen(true)}
        />
        {activeAlerts && activeAlerts.length > 0 && (
          <div
            id="persistent-alert-banner"
            onClick={() => onSelectView('alerts')}
            style={{
              padding: '8px 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              backgroundColor: activeAlerts.some((a) => a.severity === 'CRITICAL' && a.status === 'ACTIVE')
                ? 'rgba(159, 18, 57, 0.92)'
                : 'rgba(180, 83, 9, 0.92)',
              color: '#ffffff',
              borderBottom: activeAlerts.some((a) => a.severity === 'CRITICAL' && a.status === 'ACTIVE')
                ? '1px solid #f43f5e'
                : '1px solid #f59e0b',
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
              zIndex: 15,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
              {activeAlerts.some((a) => a.severity === 'CRITICAL' && a.status === 'ACTIVE') ? (
                <AlertOctagon size={16} style={{ flexShrink: 0, color: '#fecdd3' }} />
              ) : (
                <AlertTriangle size={16} style={{ flexShrink: 0, color: '#fef3c7' }} />
              )}
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <strong>
                  {activeAlerts.some((a) => a.severity === 'CRITICAL' && a.status === 'ACTIVE')
                    ? '[CRITICAL ALERT]'
                    : '[HIGH RISK ALERT]'}
                </strong>{' '}
                {activeAlerts[0].title} — {activeAlerts[0].summary}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, flexShrink: 0, textDecoration: 'underline' }}>
              View Incidents ({activeAlerts.length}) →
            </div>
          </div>
        )}
        <main className="main-scroll-area" id="main-scroll-container">
          {children}
        </main>
      </div>
    </div>
  );
};
