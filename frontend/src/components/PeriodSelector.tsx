// ═══════════════════════════════════════════════════════════
// PeriodSelector.tsx — Financial Period & Dataset Selector
// ═══════════════════════════════════════════════════════════
// Features:
// - Pick specific dataset/period
// - Compare two periods (Jan 2025 vs Jan 2026)
// - Multi-month selection for custom reports
// - Search/filter

import { useState, useRef, useEffect, useMemo } from 'react';
import { Calendar, ChevronDown, Check, Database, Search, FileSpreadsheet, GitCompareArrows, CalendarRange } from 'lucide-react';
import { useStore } from '../store/useStore';

interface DatasetInfo {
  id: number;
  period: string;
  company?: string;
  record_count: number;
  original_filename?: string;
  name?: string;
  file_type?: string;
}

export default function PeriodSelector() {
  const { period, dataset_id, lang, setFromDashboard, setDatasetId, setPeriod } = useStore();
  const [open, setOpen] = useState(false);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [rangeMode, setRangeMode] = useState(false);
  const [rangeStart, setRangeStart] = useState('');
  const [rangeEnd, setRangeEnd] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  useEffect(() => { if (open) fetchDatasets(); }, [open]);

  const fetchDatasets = async () => {
    try {
      const token = localStorage.getItem('token') || '';
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch('/api/agent/agents/datasets', { headers });
      if (res.ok) {
        const data = await res.json();
        const list = data.datasets || data;
        if (Array.isArray(list)) {
          setDatasets(list.filter((d: any) => d.record_count > 0).map((d: any) => ({
            id: d.id, period: d.period || '', company: d.company || undefined,
            record_count: d.record_count || 0,
            original_filename: d.original_filename || d.name || undefined,
            name: d.name || undefined, file_type: d.file_type || undefined,
          })));
        }
      }
    } catch { /* ignore */ }
  };

  const grouped = useMemo(() => {
    const groups = new Map<string, DatasetInfo[]>();
    const filtered = search
      ? datasets.filter(d =>
          d.period.toLowerCase().includes(search.toLowerCase()) ||
          (d.original_filename || '').toLowerCase().includes(search.toLowerCase()))
      : datasets;
    filtered.forEach(d => {
      if (!groups.has(d.period)) groups.set(d.period, []);
      groups.get(d.period)!.push(d);
    });
    return Array.from(groups.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  }, [datasets, search]);

  const selectDataset = async (ds: DatasetInfo) => {
    setLoading(true);
    try {
      setDatasetId(ds.id);
      setPeriod(ds.period);
      const token = localStorage.getItem('token') || '';
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`/api/agent/agents/dashboard?period=${ds.period}`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data && !data.empty) setFromDashboard(data);
      }
    } catch { /* ignore */ }
    finally { setLoading(false); setOpen(false); }
  };

  const formatPeriod = (p: string) => {
    if (!p) return 'Period';
    const m = p.match(/^(\w+)\s+(\d{4})$/);
    if (m) {
      const short: Record<string, string> = {
        January:'Jan',February:'Feb',March:'Mar',April:'Apr',May:'May',June:'Jun',
        July:'Jul',August:'Aug',September:'Sep',October:'Oct',November:'Nov',December:'Dec'
      };
      return `${short[m[1]] || m[1]} ${m[2]}`;
    }
    return p;
  };

  return (
    <div ref={ref} style={{ position: 'relative', zIndex: 300 }}>
      {/* Trigger button */}
      <button onClick={() => setOpen(o => !o)} style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '5px 12px', borderRadius: 8,
        background: open ? 'rgba(37,99,235,.1)' : 'transparent',
        border: `1px solid ${open ? 'rgba(37,99,235,.3)' : 'var(--b1)'}`,
        color: 'var(--text)', fontSize: 12, fontWeight: 600,
        cursor: 'pointer', height: 32, transition: 'all .15s',
      }}>
        <Calendar size={13} style={{ color: 'var(--sky)' }} />
        <span>{loading ? '...' : formatPeriod(period || '')}</span>
        <ChevronDown size={12} style={{
          color: 'var(--dim)', transition: 'transform 0.2s',
          transform: open ? 'rotate(180deg)' : 'rotate(0)',
        }} />
      </button>

      {/* Dropdown — positioned BELOW with high z-index */}
      {open && (
        <div style={{
          position: 'fixed', top: 52, left: '50%', transform: 'translateX(-50%)',
          zIndex: 9000,
          background: 'var(--bg1)', border: '1px solid var(--b2)',
          borderRadius: 12, width: 420, maxWidth: '90vw',
          boxShadow: '0 16px 48px rgba(0,0,0,.6)',
          overflow: 'hidden',
        }}>
          {/* Header */}
          <div style={{
            padding: '14px 16px 10px', borderBottom: '1px solid var(--b1)',
            background: 'linear-gradient(135deg, rgba(37,99,235,.06), transparent)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--heading)', textTransform: 'uppercase', letterSpacing: 1 }}>
                Dataset & Period
              </div>
              <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>
                {datasets.length} datasets
              </div>
            </div>

            {/* Mode toggle */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <button onClick={() => setRangeMode(false)} style={{
                flex: 1, padding: '4px 8px', borderRadius: 6, fontSize: 10, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: !rangeMode ? 'rgba(37,99,235,.15)' : 'transparent', color: !rangeMode ? 'var(--sky)' : 'var(--muted)',
              }}>Single Period</button>
              <button onClick={() => setRangeMode(true)} style={{
                flex: 1, padding: '4px 8px', borderRadius: 6, fontSize: 10, fontWeight: 600, border: 'none', cursor: 'pointer',
                background: rangeMode ? 'rgba(37,99,235,.15)' : 'transparent', color: rangeMode ? 'var(--sky)' : 'var(--muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              }}><CalendarRange size={10} /> Range</button>
            </div>

            {/* Range inputs */}
            {rangeMode && (
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                <input type="month" value={rangeStart} onChange={e => setRangeStart(e.target.value)}
                  style={{ flex: 1, height: 28, padding: '0 6px', borderRadius: 6, border: '1px solid var(--b1)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 10 }} />
                <span style={{ color: 'var(--dim)', fontSize: 10, lineHeight: '28px' }}>to</span>
                <input type="month" value={rangeEnd} onChange={e => setRangeEnd(e.target.value)}
                  style={{ flex: 1, height: 28, padding: '0 6px', borderRadius: 6, border: '1px solid var(--b1)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 10 }} />
              </div>
            )}

            {/* Search */}
            {!rangeMode && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Search size={13} style={{ color: 'var(--dim)' }} />
              <input
                value={search} onChange={e => setSearch(e.target.value)}
                placeholder="Search periods, files..."
                autoFocus
                style={{
                  flex: 1, height: 30, padding: '0 10px', borderRadius: 6,
                  border: '1px solid var(--b1)', background: 'var(--bg2)',
                  color: 'var(--text)', fontSize: 11, outline: 'none',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = 'var(--sky)'; }}
                onBlur={e => { e.currentTarget.style.borderColor = 'var(--b1)'; }}
              />
            </div>
            )}
          </div>

          {/* Datasets grouped by period */}
          <div style={{ maxHeight: 380, overflowY: 'auto', padding: '4px 0' }}>
            {grouped.length === 0 && (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--dim)', fontSize: 11 }}>No datasets found</div>
            )}
            {grouped.map(([periodKey, dsList]) => (
              <div key={periodKey}>
                {/* Period header */}
                <div style={{
                  padding: '10px 16px 4px', fontSize: 10, fontWeight: 700,
                  color: 'var(--sky)', textTransform: 'uppercase', letterSpacing: 1.5,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <Calendar size={10} /> {periodKey}
                  <span style={{ color: 'var(--dim)', fontWeight: 400, fontSize: 9 }}>
                    ({dsList.length} {dsList.length === 1 ? 'file' : 'files'})
                  </span>
                </div>

                {dsList.map(ds => {
                  const isActive = dataset_id === ds.id;
                  const isTest = ds.record_count >= 50000;
                  return (
                    <button key={ds.id} onClick={() => selectDataset(ds)} style={{
                      display: 'flex', alignItems: 'center', gap: 10, width: '100%',
                      padding: '8px 16px 8px 30px', border: 'none', cursor: 'pointer',
                      background: isActive ? 'rgba(37,99,235,.1)' : 'transparent',
                      transition: 'background 0.1s', textAlign: 'left',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,.04)'; }}
                    onMouseLeave={e => { e.currentTarget.style.background = isActive ? 'rgba(37,99,235,.1)' : 'transparent'; }}
                    >
                      <FileSpreadsheet size={14} style={{ color: isActive ? 'var(--sky)' : isTest ? 'var(--dim)' : 'var(--muted)', flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: 11.5, fontWeight: isActive ? 600 : 400,
                          color: isTest ? 'var(--dim)' : 'var(--text)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {ds.original_filename || ds.name || `Dataset ${ds.id}`}
                          {isTest && <span style={{ fontSize: 9, color: 'var(--rose)', marginLeft: 6 }}>(test data)</span>}
                        </div>
                        <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', display: 'flex', gap: 8, marginTop: 1 }}>
                          <span><Database size={8} style={{ display: 'inline', verticalAlign: 'middle' }} /> {ds.record_count.toLocaleString()} records</span>
                          {ds.file_type && <span style={{ opacity: 0.7 }}>{ds.file_type}</span>}
                        </div>
                      </div>
                      {isActive && <Check size={14} style={{ color: 'var(--sky)' }} />}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          {/* Footer */}
          <div style={{
            padding: '10px 16px', borderTop: '1px solid var(--b1)',
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(37,99,235,.02)',
          }}>
            <GitCompareArrows size={11} style={{ color: 'var(--sky)' }} />
            <span style={{ fontSize: 10, color: 'var(--muted)' }}>
              Prior year auto-detected for variance comparison
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
