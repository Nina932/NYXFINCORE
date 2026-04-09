/**
 * PivotTable — Enterprise pivot table with grouping, aggregation, sorting, expand/collapse
 * Pure React implementation — no external pivot library needed.
 */
import { useState, useMemo, useCallback } from 'react';
import { ChevronDown, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown, Download, Filter } from 'lucide-react';

/* ─── Types ─── */
export interface PivotConfig {
  rows: string[];      // fields to pivot on rows
  columns: string[];   // fields to pivot on columns (cross-tab)
  values: string[];    // fields to aggregate
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max';
}

interface PivotTableProps {
  data: Record<string, any>[];
  config: PivotConfig;
  title?: string;
  formatValue?: (value: number, field: string) => string;
  onCellClick?: (rowKey: string, colKey: string, value: number) => void;
}

type SortDir = 'asc' | 'desc' | null;

/* ─── Helpers ─── */
function aggregate(values: number[], method: string): number {
  if (!values.length) return 0;
  switch (method) {
    case 'sum': return values.reduce((a, b) => a + b, 0);
    case 'avg': return values.reduce((a, b) => a + b, 0) / values.length;
    case 'count': return values.length;
    case 'min': return Math.min(...values);
    case 'max': return Math.max(...values);
    default: return values.reduce((a, b) => a + b, 0);
  }
}

function getNestedKey(row: Record<string, any>, fields: string[]): string {
  return fields.map(f => String(row[f] ?? '')).join(' › ');
}

const defaultFormat = (v: number) => {
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(v === Math.floor(v) ? 0 : 2);
};

export function PivotTable({ data, config, title, formatValue, onCellClick }: PivotTableProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [filterText, setFilterText] = useState('');

  const fmt = useCallback((v: number, field: string) => {
    if (formatValue) return formatValue(v, field);
    return defaultFormat(v);
  }, [formatValue]);

  /* ─── Compute unique column keys ─── */
  const columnKeys = useMemo(() => {
    if (config.columns.length === 0) return ['Total'];
    const keys = new Set<string>();
    data.forEach(row => keys.add(getNestedKey(row, config.columns)));
    return Array.from(keys).sort();
  }, [data, config.columns]);

  /* ─── Build pivot structure ─── */
  const pivotRows = useMemo(() => {
    // Group data by row keys
    const groups = new Map<string, Map<string, number[]>>();
    const rowParents = new Map<string, Set<string>>(); // parent -> children

    data.forEach(row => {
      const rowKey = getNestedKey(row, config.rows);
      const colKey = config.columns.length > 0 ? getNestedKey(row, config.columns) : 'Total';

      if (!groups.has(rowKey)) groups.set(rowKey, new Map());
      const colMap = groups.get(rowKey)!;
      if (!colMap.has(colKey)) colMap.set(colKey, []);

      config.values.forEach(vf => {
        const val = Number(row[vf]) || 0;
        colMap.get(colKey)!.push(val);
      });

      // Track hierarchy for multi-level rows
      if (config.rows.length > 1) {
        const parentKey = String(row[config.rows[0]] ?? '');
        if (!rowParents.has(parentKey)) rowParents.set(parentKey, new Set());
        rowParents.get(parentKey)!.add(rowKey);
      }
    });

    // Build row entries with aggregated values
    const entries = Array.from(groups.entries()).map(([rowKey, colMap]) => {
      const values: Record<string, number> = {};
      let grandTotal = 0;

      columnKeys.forEach(ck => {
        const raw = colMap.get(ck) || [];
        const agg = aggregate(raw, config.aggregation);
        values[ck] = agg;
        grandTotal += agg;
      });

      values['__grandTotal'] = grandTotal;
      return { rowKey, values, depth: config.rows.length > 1 ? (rowKey.includes(' › ') ? 1 : 0) : 0 };
    });

    // Sort if needed
    if (sortCol && sortDir) {
      entries.sort((a, b) => {
        const av = a.values[sortCol] || 0;
        const bv = b.values[sortCol] || 0;
        return sortDir === 'asc' ? av - bv : bv - av;
      });
    }

    // Filter
    if (filterText) {
      const ft = filterText.toLowerCase();
      return entries.filter(e => e.rowKey.toLowerCase().includes(ft));
    }

    return entries;
  }, [data, config, columnKeys, sortCol, sortDir, filterText]);

  /* ─── Column totals ─── */
  const columnTotals = useMemo(() => {
    const totals: Record<string, number> = {};
    columnKeys.forEach(ck => {
      totals[ck] = pivotRows.reduce((sum, r) => sum + (r.values[ck] || 0), 0);
    });
    totals['__grandTotal'] = pivotRows.reduce((sum, r) => sum + (r.values['__grandTotal'] || 0), 0);
    return totals;
  }, [pivotRows, columnKeys]);

  const toggleExpand = (key: string) => {
    const next = new Set(expanded);
    if (next.has(key)) next.delete(key); else next.add(key);
    setExpanded(next);
  };

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : sortDir === 'desc' ? null : 'asc');
      if (sortDir === 'desc') setSortCol(null);
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  const handleExport = () => {
    const headers = ['Row', ...columnKeys, 'Grand Total'];
    const csvRows = [headers.join(',')];
    pivotRows.forEach(r => {
      csvRows.push([
        `"${r.rowKey}"`,
        ...columnKeys.map(ck => String(r.values[ck] || 0)),
        String(r.values['__grandTotal'] || 0),
      ].join(','));
    });
    csvRows.push(['Total', ...columnKeys.map(ck => String(columnTotals[ck] || 0)), String(columnTotals['__grandTotal'] || 0)].join(','));

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'pivot-export.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortCol !== col) return <ArrowUpDown size={10} style={{ opacity: 0.3 }} />;
    if (sortDir === 'asc') return <ArrowUp size={10} style={{ color: 'var(--sky)' }} />;
    return <ArrowDown size={10} style={{ color: 'var(--sky)' }} />;
  };

  return (
    <div className="glass" style={{ padding: 16, overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{title || 'Pivot Table'}</div>
          <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>
            {pivotRows.length} rows × {columnKeys.length} columns — {config.aggregation.toUpperCase()}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Filter size={12} style={{ position: 'absolute', left: 8, top: 7, color: 'var(--dim)' }} />
            <input
              type="text"
              placeholder="Filter rows..."
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              style={{
                padding: '4px 8px 4px 26px', fontSize: 10, fontFamily: "var(--mono)",
                background: 'var(--bg3)', border: '1px solid var(--b2)', borderRadius: 4,
                color: 'var(--text)', width: 140, outline: 'none',
              }}
            />
          </div>
          <button onClick={handleExport} style={{
            display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px', fontSize: 10,
            background: 'rgba(0,216,255,0.08)', border: '1px solid rgba(0,216,255,0.2)', borderRadius: 4,
            color: 'var(--sky)', cursor: 'pointer', fontFamily: "var(--mono)",
          }}>
            <Download size={10} /> CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflow: 'auto', maxHeight: 500 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--b2)' }}>
              <th style={{
                padding: '8px 12px', textAlign: 'left', fontSize: 9, textTransform: 'uppercase',
                letterSpacing: 1, color: 'var(--dim)', fontFamily: "var(--mono)",
                position: 'sticky', top: 0, background: 'var(--bg2)', zIndex: 1,
                minWidth: 200,
              }}>
                {config.rows.join(' / ')}
              </th>
              {columnKeys.map(ck => (
                <th
                  key={ck}
                  onClick={() => handleSort(ck)}
                  style={{
                    padding: '8px 10px', textAlign: 'right', fontSize: 9, textTransform: 'uppercase',
                    letterSpacing: 1, color: 'var(--dim)', fontFamily: "var(--mono)",
                    cursor: 'pointer', userSelect: 'none',
                    position: 'sticky', top: 0, background: 'var(--bg2)', zIndex: 1,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    {ck} <SortIcon col={ck} />
                  </span>
                </th>
              ))}
              <th
                onClick={() => handleSort('__grandTotal')}
                style={{
                  padding: '8px 10px', textAlign: 'right', fontSize: 9, textTransform: 'uppercase',
                  letterSpacing: 1, color: 'var(--sky)', fontFamily: "var(--mono)",
                  cursor: 'pointer', userSelect: 'none', fontWeight: 700,
                  position: 'sticky', top: 0, background: 'var(--bg2)', zIndex: 1,
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  TOTAL <SortIcon col="__grandTotal" />
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {pivotRows.map((row, i) => (
              <tr
                key={row.rowKey}
                style={{
                  borderBottom: '1px solid var(--b1)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                }}
              >
                <td style={{
                  padding: '6px 12px', paddingLeft: 12 + row.depth * 20,
                  color: row.depth === 0 ? 'var(--heading)' : 'var(--text)',
                  fontWeight: row.depth === 0 ? 600 : 400,
                  whiteSpace: 'nowrap',
                }}>
                  {config.rows.length > 1 && row.depth === 0 && (
                    <span onClick={() => toggleExpand(row.rowKey)} style={{ cursor: 'pointer', marginRight: 4, display: 'inline-flex' }}>
                      {expanded.has(row.rowKey) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </span>
                  )}
                  {row.rowKey}
                </td>
                {columnKeys.map(ck => (
                  <td
                    key={ck}
                    onClick={() => onCellClick?.(row.rowKey, ck, row.values[ck] || 0)}
                    style={{
                      padding: '6px 10px', textAlign: 'right', fontFamily: "var(--mono)",
                      color: (row.values[ck] || 0) < 0 ? 'var(--rose)' : 'var(--text)',
                      cursor: onCellClick ? 'pointer' : 'default',
                    }}
                  >
                    {fmt(row.values[ck] || 0, config.values[0])}
                  </td>
                ))}
                <td style={{
                  padding: '6px 10px', textAlign: 'right', fontFamily: "var(--mono)",
                  fontWeight: 700, color: 'var(--sky)',
                }}>
                  {fmt(row.values['__grandTotal'] || 0, config.values[0])}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ borderTop: '2px solid var(--b2)', background: 'rgba(0,216,255,0.03)' }}>
              <td style={{ padding: '8px 12px', fontWeight: 700, color: 'var(--heading)', fontSize: 11 }}>
                Grand Total
              </td>
              {columnKeys.map(ck => (
                <td key={ck} style={{
                  padding: '8px 10px', textAlign: 'right', fontFamily: "var(--mono)",
                  fontWeight: 700, color: 'var(--heading)',
                }}>
                  {fmt(columnTotals[ck] || 0, config.values[0])}
                </td>
              ))}
              <td style={{
                padding: '8px 10px', textAlign: 'right', fontFamily: "var(--mono)",
                fontWeight: 800, color: 'var(--sky)', fontSize: 12,
              }}>
                {fmt(columnTotals['__grandTotal'] || 0, config.values[0])}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
