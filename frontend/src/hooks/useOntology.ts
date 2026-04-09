import { useState, useEffect, useCallback, useRef } from 'react';
import { useStore } from '../store/useStore';

/* ─── Cache ─── */
const cache = new Map<string, { data: unknown; ts: number }>();
const CACHE_TTL = 60_000; // 60s

function getCached<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL) { cache.delete(key); return null; }
  return entry.data as T;
}

function setCache(key: string, data: unknown): void {
  cache.set(key, { data, ts: Date.now() });
}

/* ─── Shared fetch helper ─── */
async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, { ...options, headers: { ...headers, ...(options?.headers || {}) } });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/* ═══════════════════════════════════════════════
   useObjects — fetch a list of ontology objects
   ═══════════════════════════════════════════════ */
export interface UseObjectsOptions {
  type: string;
  where?: Record<string, unknown>;
  orderBy?: string;
  limit?: number;
  enabled?: boolean;
}

export interface UseObjectsResult {
  objects: Record<string, unknown>[];
  count: number;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useObjects(options: UseObjectsOptions): UseObjectsResult {
  const { type, where, orderBy, limit = 100, enabled = true } = options;
  const [objects, setObjects] = useState<Record<string, unknown>[]>([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cacheKey = `objects:${type}:${JSON.stringify(where || {})}:${limit}`;

  const fetchData = useCallback(async () => {
    if (!enabled || !type) return;
    setIsLoading(true);
    setError(null);

    const cached = getCached<{ objects: Record<string, unknown>[]; count: number }>(cacheKey);
    if (cached) {
      let filtered = cached.objects;
      if (where) {
        filtered = filtered.filter(obj => {
          const props = (obj.properties || obj) as Record<string, unknown>;
          return Object.entries(where).every(([k, v]) => props[k] === v);
        });
      }
      if (orderBy) {
        filtered.sort((a, b) => {
          const pa = ((a.properties || a) as Record<string, unknown>)[orderBy];
          const pb = ((b.properties || b) as Record<string, unknown>)[orderBy];
          if (typeof pa === 'number' && typeof pb === 'number') return pb - pa;
          return String(pa || '').localeCompare(String(pb || ''));
        });
      }
      setObjects(filtered);
      setCount(filtered.length);
      setIsLoading(false);
      return;
    }

    try {
      const url = `/api/ontology/objects?type=${encodeURIComponent(type)}&limit=${limit}`;
      const data = await apiFetch<{ objects?: Record<string, unknown>[]; count?: number }>(url);
      let results = data.objects || [];

      setCache(cacheKey, { objects: results, count: results.length });

      // Apply client-side where filter
      if (where) {
        results = results.filter(obj => {
          const props = (obj.properties || obj) as Record<string, unknown>;
          return Object.entries(where).every(([k, v]) => props[k] === v);
        });
      }

      // Apply client-side orderBy
      if (orderBy) {
        results.sort((a, b) => {
          const pa = ((a.properties || a) as Record<string, unknown>)[orderBy];
          const pb = ((b.properties || b) as Record<string, unknown>)[orderBy];
          if (typeof pa === 'number' && typeof pb === 'number') return pb - pa;
          return String(pa || '').localeCompare(String(pb || ''));
        });
      }

      setObjects(results);
      setCount(results.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch objects');
    } finally {
      setIsLoading(false);
    }
  }, [type, cacheKey, enabled, limit, orderBy, where]);

  useEffect(() => {
    fetchData();

    // Auto-refetch every 60 seconds
    intervalRef.current = setInterval(fetchData, 60_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  return { objects, count, isLoading, error, refetch: fetchData };
}

/* ═══════════════════════════════════════════════
   useObject — fetch a single ontology object (rich view)
   ═══════════════════════════════════════════════ */
export interface UseObjectResult {
  object: Record<string, unknown> | null;
  properties: Record<string, unknown>;
  linkedObjects: Record<string, Record<string, unknown>[]>;
  charts: Record<string, unknown>[];
  isLoading: boolean;
  error: string | null;
}

export function useObject(objectId: string | null): UseObjectResult {
  const [object, setObject] = useState<Record<string, unknown> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!objectId) {
      setObject(null);
      return;
    }

    const cacheKey = `object:${objectId}`;
    const cached = getCached<Record<string, unknown>>(cacheKey);
    if (cached) {
      setObject(cached);
      return;
    }

    setIsLoading(true);
    setError(null);

    apiFetch<Record<string, unknown>>(`/api/ontology/objects/${encodeURIComponent(objectId)}/view`)
      .then(data => {
        setCache(cacheKey, data);
        setObject(data);
      })
      .catch(err => {
        // Fall back to basic object endpoint
        apiFetch<Record<string, unknown>>(`/api/ontology/objects/${encodeURIComponent(objectId)}`)
          .then(data => {
            setCache(cacheKey, data);
            setObject(data);
          })
          .catch(() => {
            setError(err instanceof Error ? err.message : 'Failed to fetch object');
          });
      })
      .finally(() => setIsLoading(false));
  }, [objectId]);

  const properties = (object?.properties || {}) as Record<string, unknown>;
  const linkedObjects = (object?.relationships || object?.linked_objects || {}) as Record<string, Record<string, unknown>[]>;
  const charts = (object?.charts || []) as Record<string, unknown>[];

  return { object, properties, linkedObjects, charts, isLoading, error };
}

/* ═══════════════════════════════════════════════
   useAction — execute ontology actions
   ═══════════════════════════════════════════════ */
export interface UseActionResult {
  execute: (description: string, category: string, params?: Record<string, unknown>) => Promise<Record<string, unknown> | null>;
  isExecuting: boolean;
  lastResult: Record<string, unknown> | null;
  error: string | null;
}

export function useAction(): UseActionResult {
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const execute = useCallback(async (
    description: string,
    category: string,
    params?: Record<string, unknown>,
  ): Promise<Record<string, unknown> | null> => {
    setIsExecuting(true);
    setError(null);
    try {
      const result = await apiFetch<Record<string, unknown>>('/api/ontology/actions/propose', {
        method: 'POST',
        body: JSON.stringify({ description, category, params: params || {} }),
      });
      setLastResult(result);
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      setError(msg);
      return null;
    } finally {
      setIsExecuting(false);
    }
  }, []);

  return { execute, isExecuting, lastResult, error };
}

/* ═══════════════════════════════════════════════
   useWarehouse — query the data warehouse
   ═══════════════════════════════════════════════ */
export interface UseWarehouseResult {
  results: Record<string, unknown>[];
  count: number;
  isLoading: boolean;
  error: string | null;
}

export function useWarehouse(sql: string, enabled = true): UseWarehouseResult {
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !sql.trim()) {
      setResults([]);
      setCount(0);
      return;
    }

    const cacheKey = `wh:${sql}`;
    const cached = getCached<{ rows: Record<string, unknown>[]; count: number }>(cacheKey);
    if (cached) {
      setResults(cached.rows);
      setCount(cached.count);
      return;
    }

    setIsLoading(true);
    setError(null);

    apiFetch<{ rows?: Record<string, unknown>[]; count?: number; row_count?: number }>(
      '/api/ontology/warehouse/query',
      { method: 'POST', body: JSON.stringify({ sql }) },
    )
      .then(data => {
        const rows = data.rows || [];
        const cnt = data.count ?? data.row_count ?? rows.length;
        setCache(cacheKey, { rows, count: cnt });
        setResults(rows);
        setCount(cnt);
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Warehouse query failed');
      })
      .finally(() => setIsLoading(false));
  }, [sql, enabled]);

  return { results, count, isLoading, error };
}

/* ═══════════════════════════════════════════════
   useIntelligence — read intelligence from store
   ═══════════════════════════════════════════════ */
export interface IntelligenceData {
  health: Record<string, unknown> | null;
  risks: Record<string, unknown>[];
  opportunities: Record<string, unknown>[];
  recommendations: Record<string, unknown>[];
  kpiAlerts: Record<string, unknown>[];
  narrative: string;
}

export function useIntelligence(): IntelligenceData {
  const intelligence = useStore(s => s.intelligence);

  const intl = (intelligence || {}) as Record<string, unknown>;

  return {
    health: (intl.health_summary || intl.health || null) as Record<string, unknown> | null,
    risks: (intl.key_risks || intl.critical_risks || []) as Record<string, unknown>[],
    opportunities: (intl.opportunities || []) as Record<string, unknown>[],
    recommendations: (intl.recommendations || []) as Record<string, unknown>[],
    kpiAlerts: (intl.kpi_alerts || intl.kpis || []) as Record<string, unknown>[],
    narrative: (intl.narrative || '') as string,
  };
}
