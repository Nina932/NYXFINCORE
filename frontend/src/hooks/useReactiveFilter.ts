import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import React from 'react';

/* ─── Types ─── */
export interface FilterStore {
  filters: Record<string, unknown>;
  setFilter: (key: string, value: unknown) => void;
  clearFilter: (key: string) => void;
  clearAll: () => void;
}

const defaultStore: FilterStore = {
  filters: {},
  setFilter: () => {},
  clearFilter: () => {},
  clearAll: () => {},
};

/* ─── Context ─── */
export const FilterContext = createContext<FilterStore>(defaultStore);

/* ─── Provider ─── */
export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Record<string, unknown>>({});

  const setFilter = useCallback((key: string, value: unknown) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const clearFilter = useCallback((key: string) => {
    setFilters(prev => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setFilters({});
  }, []);

  return React.createElement(
    FilterContext.Provider,
    { value: { filters, setFilter, clearFilter, clearAll } },
    children,
  );
}

/* ─── Hook ─── */
export interface UseReactiveFilterResult {
  value: unknown;
  set: (value: unknown) => void;
  clear: () => void;
  allFilters: Record<string, unknown>;
}

export function useReactiveFilter(key?: string): UseReactiveFilterResult {
  const store = useContext(FilterContext);

  return {
    value: key ? store.filters[key] : store.filters,
    set: (value: unknown) => { if (key) store.setFilter(key, value); },
    clear: () => { if (key) store.clearFilter(key); else store.clearAll(); },
    allFilters: store.filters,
  };
}
