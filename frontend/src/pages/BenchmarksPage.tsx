import { useState, useEffect } from 'react';
import { BarChart3, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { api } from '../api/client';

export default function BenchmarksPage() {
  const [industries, setIndustries] = useState<any[]>([]);
  const [selected, setSelected] = useState('fuel_distribution');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.benchmarkIndustries?.()
      .then((d: any) => setIndustries(d?.industries || d || []))
      .catch(() => {});
  }, []);

  const runCompare = async () => {
    setLoading(true);
    try {
      const r = await (api as any).benchmarkCompare?.({ industry_id: selected });
      setResult(r);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--heading)' }}>
          <BarChart3 size={22} style={{ color: 'var(--sky)' }} /> Industry Benchmarks
        </h1>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <select value={selected} onChange={e => setSelected(e.target.value)} style={{
          padding: '8px 12px', borderRadius: 8, background: 'var(--bg2)', color: 'var(--text)',
          border: '1px solid var(--b1)', fontSize: 13,
        }}>
          {(Array.isArray(industries) ? industries : []).map((ind: any) => (
            <option key={ind.industry_id} value={ind.industry_id}>{ind.industry_name}</option>
          ))}
        </select>
        <button onClick={runCompare} disabled={loading} style={{
          padding: '8px 18px', borderRadius: 8, background: 'var(--sky)', color: '#fff',
          border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer',
        }}>
          {loading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : 'Compare'}
        </button>
      </div>

      {result && (
        <div className="glass" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--b2)', background: 'rgba(56,189,248,0.04)' }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>Metric</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>Your Value</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>Industry Avg</th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {(result.comparisons || result.results || []).map((c: any, i: number) => {
                const status = c.status || (c.value > c.benchmark ? 'above' : 'below');
                const color = status === 'healthy' || status === 'above' ? 'var(--emerald)' : status === 'critical' ? 'var(--rose)' : 'var(--muted)';
                return (
                  <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 600 }}>{c.metric || c.name}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{typeof c.value === 'number' ? c.value.toFixed(2) : c.value}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--dim)' }}>{typeof c.benchmark === 'number' ? c.benchmark.toFixed(2) : c.benchmark || c.industry_avg}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600, color }}>{status}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!result && !loading && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
          Select an industry and click Compare to see how your financials stack up against benchmarks.
        </div>
      )}
    </div>
  );
}
