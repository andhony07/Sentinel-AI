import { useCallback, useEffect, useRef, useState } from 'react';
import { getAlertSummary, listAlerts } from '../api';
import type { AlertSummary, RiskAlert } from '../types';

const STORAGE_KEY_ENABLED = 'sentinel_desktop_notifications_enabled';
const SESSION_KEY_NOTIFIED = 'sentinel_notified_alert_ids';

export interface UseAlertNotificationsOptions {
  pollingIntervalMs?: number;
  onNavigateToAlerts?: (alertId?: string) => void;
}

export interface UseAlertNotificationsReturn {
  summary: AlertSummary | null;
  activeAlerts: RiskAlert[];
  permission: NotificationPermission | 'unsupported';
  isSupported: boolean;
  notificationsEnabled: boolean;
  requestPermission: () => Promise<boolean>;
  toggleNotifications: () => Promise<void>;
  refreshAlerts: () => Promise<void>;
}

export function useAlertNotifications(
  options: UseAlertNotificationsOptions = {}
): UseAlertNotificationsReturn {
  const { pollingIntervalMs = 5000, onNavigateToAlerts } = options;

  const isSupported = typeof window !== 'undefined' && 'Notification' in window;

  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    isSupported ? Notification.permission : 'unsupported'
  );

  const [notificationsEnabled, setNotificationsEnabled] = useState<boolean>(() => {
    if (!isSupported) return false;
    const saved = localStorage.getItem(STORAGE_KEY_ENABLED);
    return saved === 'true' && Notification.permission === 'granted';
  });

  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [activeAlerts, setActiveAlerts] = useState<RiskAlert[]>([]);

  // Track already-notified alert IDs to prevent repetitive desktop notifications
  const notifiedIdsRef = useRef<Set<string>>(new Set());

  // Load known notified IDs from sessionStorage on mount
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(SESSION_KEY_NOTIFIED);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          notifiedIdsRef.current = new Set(parsed);
        }
      }
    } catch {
      // Ignore sessionStorage read errors
    }
  }, []);

  const persistNotifiedIds = useCallback(() => {
    try {
      sessionStorage.setItem(
        SESSION_KEY_NOTIFIED,
        JSON.stringify(Array.from(notifiedIdsRef.current))
      );
    } catch {
      // Ignore sessionStorage write errors
    }
  }, []);

  const dispatchDesktopNotification = useCallback(
    (alert: RiskAlert) => {
      if (!isSupported || Notification.permission !== 'granted' || !notificationsEnabled) {
        return;
      }

      if (notifiedIdsRef.current.has(alert.alert_id)) {
        return;
      }

      // Mark as notified immediately
      notifiedIdsRef.current.add(alert.alert_id);
      persistNotifiedIds();

      try {
        const title = `[SentinelAI] ${alert.severity} Risk: ${alert.trigger_metric}`;
        const obs = alert.observed_value_str ? ` (${alert.observed_value_str})` : '';
        const body = `${alert.summary}${obs} on ${alert.server_id}`;

        const notification = new Notification(title, {
          body,
          tag: `sentinel-alert-${alert.alert_id}`,
          icon: '/favicon.ico',
        });

        notification.onclick = () => {
          try {
            window.focus();
            notification.close();
            if (onNavigateToAlerts) {
              onNavigateToAlerts(alert.alert_id);
            }
          } catch {
            // Ignore focus error
          }
        };
      } catch (err) {
        // Handle desktop notification failure gracefully
        console.warn('[SentinelAI] Desktop notification error:', err);
      }
    },
    [isSupported, notificationsEnabled, onNavigateToAlerts, persistNotifiedIds]
  );

  const refreshAlerts = useCallback(async () => {
    try {
      const [sum, listRes] = await Promise.all([
        getAlertSummary(),
        listAlerts({ status: 'ACTIVE,ACKNOWLEDGED', limit: 20 }),
      ]);

      setSummary(sum);
      setActiveAlerts(listRes.alerts || []);

      // If there are ongoing alerts on initial load without desktop permission, record them
      // so turning ON notifications only alerts on *newly* detected incidents.
      if (!notificationsEnabled || Notification.permission !== 'granted') {
        (listRes.alerts || []).forEach((a) => {
          notifiedIdsRef.current.add(a.alert_id);
        });
        persistNotifiedIds();
      } else {
        // Dispatch notifications for newly discovered HIGH or CRITICAL alerts
        (listRes.alerts || []).forEach((a) => {
          if (a.severity === 'CRITICAL' || a.severity === 'HIGH') {
            dispatchDesktopNotification(a);
          }
        });
      }
    } catch (err) {
      console.warn('[SentinelAI] Failed to refresh alerts:', err);
    }
  }, [dispatchDesktopNotification, notificationsEnabled, persistNotifiedIds]);

  // Polling loop
  useEffect(() => {
    refreshAlerts();
    if (pollingIntervalMs <= 0) return;

    const intervalId = setInterval(refreshAlerts, pollingIntervalMs);
    return () => clearInterval(intervalId);
  }, [pollingIntervalMs, refreshAlerts]);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setPermission('unsupported');
      return false;
    }

    try {
      const res = await Notification.requestPermission();
      setPermission(res);
      if (res === 'granted') {
        setNotificationsEnabled(true);
        localStorage.setItem(STORAGE_KEY_ENABLED, 'true');
        return true;
      } else {
        setNotificationsEnabled(false);
        localStorage.setItem(STORAGE_KEY_ENABLED, 'false');
        return false;
      }
    } catch (err) {
      console.error('[SentinelAI] Error requesting notification permission:', err);
      return false;
    }
  }, [isSupported]);

  const toggleNotifications = useCallback(async () => {
    if (!isSupported) return;

    if (notificationsEnabled) {
      setNotificationsEnabled(false);
      localStorage.setItem(STORAGE_KEY_ENABLED, 'false');
    } else {
      if (Notification.permission === 'granted') {
        setNotificationsEnabled(true);
        localStorage.setItem(STORAGE_KEY_ENABLED, 'true');
      } else {
        await requestPermission();
      }
    }
  }, [isSupported, notificationsEnabled, requestPermission]);

  return {
    summary,
    activeAlerts,
    permission,
    isSupported,
    notificationsEnabled,
    requestPermission,
    toggleNotifications,
    refreshAlerts,
  };
}
