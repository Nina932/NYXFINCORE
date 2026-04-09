import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, Loader2, Activity } from 'lucide-react';

/* ── Types ── */
interface PeriodData {
  period: string;
  revenue: number;
  cogs: number;
  gross_profit: number;
  ebitda: number;
  net_profit: number;
}

interface TrendResponse {
  periods: PeriodData[];
}

/* ── Sparkline SVG ── */
function Sparkline({ data, width = 100, height = 28 }: { data: number[]; width?: number; height?: number }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);
  const last = data[data.length - 1];
  const prev = data[data.length - 2];
  const isPositive = last >= prev;
  const color = isPositive ? 'var(--emerald)' : 'var(--rose)';

  const points = data.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* ── Format helpers ── */
function fmt(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '\u2014';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e3).toFixed(0)}K`;
  return `\u20BE${n.toFixed(0)}`;
}

function pctChange(current: number, prior: number): number | null {
  if (!prior) return null;
  return ((current - prior) / Math.abs(prior)) * 100;
}

/* ── Metric card ── */
interface MetricTrendCardProps {
  label: string;
  values: number[];
  suffix?: string;
}

function MetricTrendCard({ label, values, suffix }: MetricTrendCardProps) {
  if (!values || values.length === 0) return null;
  const current = values[values.length - 1];
  const prior = values.length >= 2 ? values[values.length - 2] : null;
  const change = prior !== null ? pctChange(current, prior) : null;
  const absChange = prior !== null ? current - prior : null;
  const isPositive = change !== null && change >= 0;

  return (
    <div className="glass" style={{ padding: '14px 16px', minWidth: 0 }}>
      <div style={{
        fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
        color: 'var(--muted)', marginBottom: 6,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 22, fontWeight: 800, fontFamily: 'var(--mono)',
        color: current >= 0 ? 'var(--heading)' : 'var(--rose)',
      }}>
        {suffix ? `${current.toFixed(1)}${suffix}` : fmt(current)}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8, gap: 8 }}>
        {/* Change badge */}
        {change !== null ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 3,
              fontSize: 10, fontWeight: 600, fontFamily: 'var(--mono)',
              color: isPositive ? 'var(--emerald)' : 'var(--rose)',
            }}>
              {isPositive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
              {change > 0 ? '+' : ''}{change.toFixed(1)}%
              {absChange !== null && !suffix && (
                <span style={{ fontSize: 9, fontWeight: 500, color: 'var(--muted)', marginLeft: 2 }}>
                  ({absChange >= 0 ? '+' : ''}{fmt(absChange)})
                </span>
              )}
            </div>
            <span style={{ fontSize: 8, color: 'var(--dim)', fontFamily: 'var(--font)', letterSpacing: '0.02em' }}>
              vs prior period
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: 'var(--muted)' }}>
            <Minus size={11} /> N/A
          </div>
        )}
        {/* Sparkline */}
        <Sparkline data={values} width={80} height={24} />
      </div>
    </div>
  );
}

/* ── Main component ── */
export default function TrendSection() {
  const [data, setData] = useState<PeriodData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');

    const headers: Record<string, string> = {};
    const token = localStorage.getItem('token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch('/api/analytics/pl-trend', { headers })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((res: TrendResponse) => {
        setData(res.periods || []);
      })
      .catch(e => setError(e.message || 'Failed to load trends'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 0', color: 'var(--muted)', fontSize: 11 }}>
        <Loader2 size={14} style={{ animation: 'spin 1s linear infinite', color: 'var(--sky)' }} />
        Loading trends...
      </div>
    );
  }

  if (error || data.length < 2) return null; // silently hide if no trend data

  const revenues = data.map(d => d.revenue);
  const netProfits = data.map(d => d.net_profit);
  const grossMargins = data.map(d => d.revenue ? (d.gross_profit / d.revenue) * 100 : 0);
  const ebitdas = data.map(d => d.ebitda);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <Activity size={13} style={{ color: 'var(--sky)' }} />
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>
          Month-over-Month Trends
        </span>
        <div style={{ flex: 1, height: 1, background: 'var(--b1)' }} />
        <span style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>
          {data.length} periods
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        <MetricTrendCard label="Revenue" values={revenues} />
        <MetricTrendCard label="Net Profit" values={netProfits} />
        <MetricTrendCard label="Gross Margin %" values={grossMargins} suffix="%" />
        <MetricTrendCard label="EBITDA" values={ebitdas} />
      </div>
    </div>
  );
}
