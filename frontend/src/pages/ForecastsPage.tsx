import { useState, useEffect } from 'react';
import { Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, ComposedChart } from 'recharts';
import { LineChart, Play, Loader2 } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { formatCurrency } from '../utils/format';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };

export default function ForecastsPage() {
  const { pnl } = useStore();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    if (!pnl) return;
    const revenue = pnl.revenue ?? pnl.total_revenue ?? 0;
    const gp = pnl.gross_profit ?? 0;
    const ebitda = pnl.ebitda ?? 0;
    // Use available financial metrics as a time series proxy
    const values = [revenue, gp, ebitda].filter(v => v !== 0);
    setLoading(true); setError('');
    try {
      const data = await api.forecast(values, values.length, 6) as Record<string, unknown>;
      setResult(data);
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setLoading(false); }
  };

  // Auto-run on mount
  useEffect(() => { if (pnl && !result) run(); }, [pnl]);

  const forecasts = (result?.forecasts as { period: number; value: number; lower?: number; upper?: number }[]) || [];
  const methods = (result?.methods as { name: string; mape?: number; weight?: number }[]) || [];

  // Build chart data
  const chartData = forecasts.map((f, i) => ({
    name: `+${i + 1}`,
    forecast: f.value,
    lower: f.lower ?? f.value * 0.9,
    upper: f.upper ?? f.value * 1.1,
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <LineChart size={20} style={{ color: 'var(--sky)' }} /> Forecasts
          </h1>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>Ensemble forecast with confidence intervals</p>
        </div>
        <button onClick={run} disabled={loading || !pnl} style={{ display: 'flex', alignItems: 'center', gap: 6, background: (!pnl || loading) ? 'var(--bg3)' : 'linear-gradient(135deg, var(--sky), var(--blue))', color: (!pnl || loading) ? 'var(--muted)' : '#000', fontWeight: 600, padding: '8px 18px', borderRadius: 8, border: 'none', cursor: (!pnl || loading) ? 'default' : 'pointer', fontSize: 12 }}>
          {loading ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Forecasting...</> : <><Play size={14} /> Run Forecast</>}
        </button>
      </div>
      {error && <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px' }}>{error}</div>}
      {!pnl && <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>Upload financial data first.</p></div>}

      {chartData.length > 0 && (
        <div style={{ ...card, padding: 18 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 14 }}>Forecast with Confidence Bands</h3>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData}>
              <defs>
                <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" stroke="var(--muted)" fontSize={10} />
              <YAxis stroke="var(--muted)" fontSize={9} tickFormatter={(v: number) => `${(v / 1_000_000).toFixed(0)}M`} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8, fontSize: 11 }} formatter={(v) => [formatCurrency(Number(v)), '']} />
              <Area type="monotone" dataKey="upper" stroke="transparent" fill="url(#confGrad)" />
              <Area type="monotone" dataKey="lower" stroke="transparent" fill="transparent" />
              <Line type="monotone" dataKey="forecast" stroke="#38bdf8" strokeWidth={2} dot={{ fill: '#38bdf8', r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {methods.length > 0 && (
        <div style={{ ...card, padding: 18 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 10 }}>Forecast Methods</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
            {methods.map((m, i) => (
              <div key={i} style={{ background: 'var(--bg3)', borderRadius: 6, padding: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>{m.name}</div>
                {m.mape !== undefined && <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>MAPE: {m.mape.toFixed(1)}%</div>}
                {m.weight !== undefined && <div style={{ fontSize: 10, color: 'var(--sky)', marginTop: 1 }}>Weight: {(m.weight * 100).toFixed(0)}%</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
