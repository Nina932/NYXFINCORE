import { useEffect, useCallback, useRef } from 'react';

/* ─── Types ─── */
interface UsageEvent {
  action: string;
  page: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

/* ─── Storage key ─── */
const STORAGE_KEY = 'finai_usage_metrics';
const MAX_EVENTS = 500;

/* ─── Helpers ─── */
function getStoredEvents(): UsageEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as UsageEvent[];
  } catch {
    return [];
  }
}

function storeEvent(event: UsageEvent): void {
  try {
    const events = getStoredEvents();
    events.push(event);
    // Keep only the most recent MAX_EVENTS
    const trimmed = events.length > MAX_EVENTS ? events.slice(-MAX_EVENTS) : events;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // localStorage quota or other error — silently ignore
  }
}

/* ─── Hook ─── */
export function useUsageMetrics() {
  const pageRef = useRef(typeof window !== 'undefined' ? window.location.pathname : '/');

  // Track page views on pathname change
  useEffect(() => {
    const page = window.location.pathname;
    pageRef.current = page;

    storeEvent({
      action: 'page_view',
      page,
      timestamp: new Date().toISOString(),
    });

    // Also try to post to the activity feed (best-effort, no error handling)
    const token = localStorage.getItem('token') || '';
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch('/api/agent/activity/feed', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        type: 'page_view',
        description: `Viewed ${page}`,
        status: 'completed',
        timestamp: new Date().toISOString(),
      }),
    }).catch(() => {});
  }, []);

  // Track arbitrary actions
  const trackAction = useCallback((action: string, details?: Record<string, unknown>) => {
    const event: UsageEvent = {
      action,
      page: pageRef.current,
      timestamp: new Date().toISOString(),
      details,
    };

    storeEvent(event);

    // Best-effort POST to activity feed
    const token = localStorage.getItem('token') || '';
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch('/api/agent/activity/feed', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        type: action,
        description: `${action}${details ? ': ' + JSON.stringify(details) : ''}`,
        status: 'completed',
        timestamp: new Date().toISOString(),
      }),
    }).catch(() => {});
  }, []);

  // Get recent events (for display/debug)
  const getRecentEvents = useCallback((limit = 50): UsageEvent[] => {
    return getStoredEvents().slice(-limit).reverse();
  }, []);

  return { trackAction, getRecentEvents };
}
