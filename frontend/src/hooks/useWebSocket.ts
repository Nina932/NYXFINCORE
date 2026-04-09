/**
 * FinAI Real-Time WebSocket Hook
 * ================================
 * Connects to the FinAI backend WebSocket event stream.
 * Auto-reconnects on disconnect with exponential backoff.
 *
 * Usage:
 *   import { useWebSocket } from '@/hooks/useWebSocket';
 *
 *   function MyComponent() {
 *     const { connected, lastEvent, events } = useWebSocket();
 *
 *     useEffect(() => {
 *       if (lastEvent?.type === 'upload_complete') {
 *         toast.success(`Upload complete: ${lastEvent.payload.filename}`);
 *       }
 *     }, [lastEvent]);
 *
 *     return <div>Status: {connected ? 'Connected' : 'Disconnected'}</div>;
 *   }
 *
 * Event types:
 *   - data_updated     — dataset modified
 *   - alert_triggered  — monitoring alert fired
 *   - upload_complete  — smart-upload finished
 *   - analysis_ready   — orchestrator completed
 *   - action_proposed  — decision engine proposed action
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export interface WSEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

interface UseWebSocketOptions {
  /** WebSocket URL. Defaults to ws://localhost:9200/api/ws */
  url?: string;
  /** Maximum number of events to keep in memory. Default: 50 */
  maxEvents?: number;
  /** Whether to auto-connect on mount. Default: true */
  autoConnect?: boolean;
  /** Maximum reconnect attempts before giving up. Default: Infinity */
  maxReconnectAttempts?: number;
}

interface UseWebSocketReturn {
  /** Whether the WebSocket is currently connected */
  connected: boolean;
  /** The most recent event received */
  lastEvent: WSEvent | null;
  /** Array of all events received (up to maxEvents) */
  events: WSEvent[];
  /** Send a JSON message to the server */
  send: (data: Record<string, unknown>) => void;
  /** Manually connect */
  connect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
}

const DEFAULT_URL = (() => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.hostname || 'localhost';
  return `${protocol}//${host}:9200/api/ws`;
})();

const BASE_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000; // 30 seconds

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    url = DEFAULT_URL,
    maxEvents = 50,
    autoConnect = true,
    maxReconnectAttempts = Infinity,
  } = options;

  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const doConnect = useCallback(() => {
    if (unmountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmountedRef.current) return;
        setConnected(true);
        reconnectAttemptRef.current = 0;
      };

      ws.onmessage = (event) => {
        if (unmountedRef.current) return;
        try {
          const data: WSEvent = JSON.parse(event.data);
          setLastEvent(data);
          setEvents((prev) => {
            const next = [...prev, data];
            return next.length > maxEvents ? next.slice(-maxEvents) : next;
          });
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        if (unmountedRef.current) return;
        setConnected(false);
        wsRef.current = null;

        // Auto-reconnect with exponential backoff
        if (reconnectAttemptRef.current < maxReconnectAttempts) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptRef.current),
            MAX_RECONNECT_DELAY
          );
          reconnectAttemptRef.current += 1;
          clearReconnectTimer();
          reconnectTimerRef.current = setTimeout(doConnect, delay);
        }
      };

      ws.onerror = () => {
        // onclose will fire after onerror, handling reconnection
      };
    } catch {
      // Connection failed, onclose handler will retry
    }
  }, [url, maxEvents, maxReconnectAttempts, clearReconnectTimer]);

  const doDisconnect = useCallback(() => {
    clearReconnectTimer();
    reconnectAttemptRef.current = Infinity; // prevent auto-reconnect
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, [clearReconnectTimer]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  // Auto-connect on mount, cleanup on unmount
  useEffect(() => {
    unmountedRef.current = false;
    if (autoConnect) {
      doConnect();
    }
    return () => {
      unmountedRef.current = true;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [autoConnect, doConnect, clearReconnectTimer]);

  return {
    connected,
    lastEvent,
    events,
    send,
    connect: doConnect,
    disconnect: doDisconnect,
  };
}

export default useWebSocket;
