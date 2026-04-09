import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, Search } from 'lucide-react';

interface Column {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  format?: (value: unknown, row: Record<string, unknown>) => string | React.ReactNode;
  sortable?: boolean;
  width?: number | string;
  mono?: boolean;
}

interface DataTableProps {
  columns: Column[];
  data: Record<string, unknown>[];
  pageSize?: number;
  searchable?: boolean;
  searchKeys?: string[];
  emptyMessage?: string;
  compact?: boolean;
  striped?: boolean;
  onRowClick?: (row: Record<string, unknown>) => void;
  highlightFn?: (row: Record<string, unknown>) => string | undefined;
}

export default function DataTable({
  columns, data, pageSize = 20, searchable = false, searchKeys,
  emptyMessage = 'No data', compact = false, striped = false,
  onRowClick, highlightFn,
}: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => {
    let result = [...data];
    if (search && searchKeys) {
      const q = search.toLowerCase();
      result = result.filter(row =>
        searchKeys.some(k => String(row[k] ?? '').toLowerCase().includes(q))
      );
    }
    if (sortKey) {
      result.sort((a, b) => {
        const av = a[sortKey] ?? 0;
        const bv = b[sortKey] ?? 0;
        const cmp = typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv));
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return result;
  }, [data, search, searchKeys, sortKey, sortDir]);

  const totalPages = Math.ceil(filtered.length / pageSize);
  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const py = compact ? 5 : 8;

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  return (
    <div>
      {searchable && (
        <div style={{ position: 'relative', marginBottom: 10 }}>
          <Search size={13} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--muted)' }} />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0); }}
            style={{
              width: '100%', paddingLeft: 30, padding: '7px 10px 7px 30px',
              background: 'var(--bg3)', border: '1px solid var(--b1)', borderRadius: 6,
              color: 'var(--text)', fontSize: 11, outline: 'none',
            }}
          />
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: compact ? 11 : 12 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--b2)' }}>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                  style={{
                    textAlign: col.align || 'left',
                    padding: `${py}px 12px`,
                    fontFamily: 'var(--mono)', fontSize: 9,
                    textTransform: 'uppercase', letterSpacing: 1.5,
                    color: 'var(--muted)', fontWeight: 500,
                    cursor: col.sortable !== false ? 'pointer' : 'default',
                    userSelect: 'none',
                    width: col.width,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                    {col.label}
                    {sortKey === col.key && (
                      sortDir === 'asc' ? <ChevronUp size={10} /> : <ChevronDown size={10} />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paged.map((row, i) => {
                const highlight = highlightFn?.(row);
                return (
                  <tr
                    key={i}
                    onClick={() => onRowClick?.(row)}
                    style={{
                      borderBottom: '1px solid var(--b1)',
                      background: highlight || (striped && i % 2 === 1 ? 'rgba(255,255,255,.01)' : 'transparent'),
                      cursor: onRowClick ? 'pointer' : 'default',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => { if (onRowClick) e.currentTarget.style.background = 'rgba(255,255,255,.03)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = highlight || 'transparent'; }}
                  >
                    {columns.map(col => {
                      const raw = row[col.key];
                      const display = col.format ? col.format(raw, row) : String(raw ?? '');
                      return (
                        <td
                          key={col.key}
                          style={{
                            padding: `${py}px 12px`,
                            textAlign: col.align || 'left',
                            fontFamily: col.mono ? 'var(--mono)' : 'inherit',
                            color: 'var(--text)',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {display}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', fontSize: 11, color: 'var(--muted)' }}>
          <span>{filtered.length} items · Page {page + 1} of {totalPages}</span>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              style={{
                padding: '4px 10px', borderRadius: 4, fontSize: 10,
                background: 'var(--bg3)', border: '1px solid var(--b1)',
                color: page === 0 ? 'var(--dim)' : 'var(--text)', cursor: page === 0 ? 'default' : 'pointer',
              }}
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              style={{
                padding: '4px 10px', borderRadius: 4, fontSize: 10,
                background: 'var(--bg3)', border: '1px solid var(--b1)',
                color: page >= totalPages - 1 ? 'var(--dim)' : 'var(--text)', cursor: page >= totalPages - 1 ? 'default' : 'pointer',
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
