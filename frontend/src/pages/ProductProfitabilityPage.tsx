import { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, DollarSign, Package } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

function fmt(n: string | number | null | undefined): string {
  const v = typeof n === 'string' ? parseFloat(n) : n;
  if (v == null || isNaN(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e6) return `₾${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `₾${(v / 1e3).toFixed(0)}K`;
  return `₾${v.toFixed(0)}`;
}

export default function ProductProfitabilityPage() {
  const { dataset_id } = useStore();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [segment, setSegment] = useState('');
  const [sortBy, setSortBy] = useState('margin_pct');

  useEffect(() => {
    setLoading(true);
    setError('');
    api.profitability(dataset_id || undefined, segment || undefined, sortBy)
      .then((d: any) => setData(d))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [dataset_id, segment, sortBy]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Loading profitability data...</div>;
  if (error) return <div style={{ padding: 40, color: 'var(--rose)' }}>Error: {error}</div>;
  if (!data) return <div style={{ padding: 40, color: 'var(--muted)' }}>No data available. Upload a dataset first.</div>;

  const { products, summary } = data;
  const chartData = products.slice(0, 15).map((p: any) => ({
    name: (p.product_en || p.product || '').substring(0, 20),
    margin: parseFloat(p.margin_pct),
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 4px', animation: 'slide-up 0.4s ease both', position: 'relative', overflow: 'hidden' }}>
      <div className="scanline" />

      {/* Modern Industrial Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--b1)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 900, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, margin: 0, letterSpacing: -0.5 }}>
            <BarChart3 size={22} style={{ color: 'var(--sky)' }} /> PROFITABILITY_INTELLIGENCE
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
            TRACE::PRODUCT_MARGIN_V4 // STATE::REALTIME_CALCULATION
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15,20,34,0.4)', padding: 2, borderRadius: 2, border: '1px solid var(--b1)' }}>
            <select value={segment} onChange={e => setSegment(e.target.value)}
              style={{ padding: '4px 12px', border: 'none', background: 'transparent', color: 'var(--text)', fontSize: 10, fontWeight: 800, fontFamily: 'var(--mono)', outline: 'none' }}>
              <option value="">ALL_SEGMENTS</option>
              <option value="Wholesale">WHOLESALE</option>
              <option value="Retail">RETAIL</option>
            </select>
            <div style={{ width: 1, height: 16, background: 'var(--b1)' }} />
            <select value={sortBy} onChange={e => setSortBy(e.target.value)}
              style={{ padding: '4px 12px', border: 'none', background: 'transparent', color: 'var(--text)', fontSize: 10, fontWeight: 800, fontFamily: 'var(--mono)', outline: 'none' }}>
              <option value="margin_pct">SORT::MARGIN_%</option>
              <option value="revenue">SORT::REVENUE</option>
              <option value="gp">SORT::GROSS_PROFIT</option>
            </select>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {[
          { label: 'GROSS_REVENUE', value: fmt(summary.total_revenue), color: 'var(--sky)' },
          { label: 'OPERATING_COGS', value: fmt(summary.total_cogs), color: 'var(--rose)' },
          { label: 'GROSS_PROFIT_DELTA', value: fmt(summary.total_gross_profit), color: 'var(--emerald)' },
          { label: 'AVG_MARGIN_EFFICIENCY', value: `${summary.avg_margin_pct}%`, color: 'var(--violet)' },
          { label: 'SKU_COUNT', value: summary.product_count, color: 'var(--amber)' },
        ].map(({ label, value, color }) => (
          <div key={label} className="glass-interactive" style={{ padding: '16px 20px', borderLeft: `3px solid ${color}` }}>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--dim)', marginBottom: 8 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 900, color, fontFamily: 'var(--mono)', letterSpacing: -1 }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 0.8fr)', gap: 16 }}>
        {/* Product Table */}
        <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', background: 'rgba(15,20,34,0.4)', borderBottom: '1px solid var(--b1)', fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 1 }}>
            PRODUCT_LEDGER_DATA_STREAM
          </div>
          <div style={{ overflowX: 'auto', maxHeight: '50vh' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>DESCRIPTOR</th>
                  <th style={{ width: 100 }}>SEGMENT</th>
                  <th className="right" style={{ width: 100 }}>REVENUE</th>
                  <th className="right" style={{ width: 100 }}>GP</th>
                  <th className="right" style={{ width: 80 }}>MARGIN_%</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p: any, i: number) => {
                  const margin = parseFloat(p.margin_pct);
                  const isNeg = margin < 0;
                  return (
                    <tr key={i}>
                      <td style={{ padding: '8px 16px', fontWeight: 700, fontSize: 11 }}>{(p.product_en || p.product).toUpperCase()}</td>
                      <td style={{ padding: '8px 16px', color: 'var(--muted)', fontSize: 10, fontFamily: 'var(--mono)' }}>{p.segment.toUpperCase()}</td>
                      <td className="mono right" style={{ fontSize: 11 }}>{fmt(p.revenue_net)}</td>
                      <td className="mono right" style={{ fontSize: 11, color: isNeg ? 'var(--rose)' : 'var(--emerald)', fontWeight: 700 }}>{fmt(p.gross_profit)}</td>
                      <td className="mono right" style={{ fontSize: 11, fontWeight: 900, color: isNeg ? 'var(--rose)' : 'var(--emerald)' }}>{margin.toFixed(1)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Charts & Analytics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {chartData.length > 0 && (
            <div className="glass" style={{ padding: 24 }}>
              <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 800, marginBottom: 20, letterSpacing: 1 }}>MARGIN_DISTRIBUTION_CHART</div>
              <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 24)}>
                <BarChart data={chartData} layout="vertical" margin={{ left: -10, right: 20 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="var(--b1)" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 9, fill: 'var(--dim)', fontFamily: 'var(--mono)' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: 'var(--text)', fontWeight: 700 }} width={100} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 2, fontSize: 10, fontFamily: 'var(--mono)' }}
                    cursor={{ fill: 'rgba(255,255,255,0.03)' }}
                  />
                  <Bar dataKey="margin" radius={[0, 2, 2, 0]} barSize={12}>
                    {chartData.map((_: any, i: number) => (
                      <Cell key={i} fill={chartData[i].margin >= 0 ? 'var(--emerald)' : 'var(--rose)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="glass-interactive" style={{ padding: 24 }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 800, marginBottom: 12, letterSpacing: 1 }}>SYSTEM_ANALYSIS_BUFFER</div>
            <p style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.6, margin: 0, fontFamily: 'var(--mono)', opacity: 0.8 }}>
              IDENTIFIED:: LOW_MARGIN_CONCENTRATION_IN_RETAIL_SEGMENT. 
              ACTION_REQUIRED:: REVIEW_COGS_ALLOCATION_FOR_PRODUCT_FLIGHTS_WITH_NEGATIVE_MARGIN_DELTA.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
