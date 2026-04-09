import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, Loader2, Activity } from 'lucide-react';

/* ─── Styles ─── */
const label9: React.CSSProperties = { fontSize: 9, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: 'var(--muted)' };

interface TimeSeriesAnalysis {
  trend_direction?: string;     // "up" | "down" | "flat"
  trend_strength?: number;      // 0-1
  rolling_average?: number[];   // 3-period rolling avg
  pct_changes?: number[];       // period-over-period % change
  mean?: number;
  std_dev?: number;
  volatility?: number;
  error?: string;
}

interface Props {
  values: number[];
  labels: string[];
  title: string;
}

/* ─── Mini sparkline renderer ─── */
function Sparkline({ data, color, height = 32, width = 120 }: { data: number[]; color: string; height?: number; width?: number }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = width / (data.length - 1);

  const points = data.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function TimeSeriesPanel({ values, labels, title }: Props) {
  const [analysis, setAnalysis] = useState<TimeSeriesAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!values || values.length < 2) return;
    setLoading(true);
    setError('');

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch('/api/ts/analyze', {
      method: 'POST',
      headers,
      body: JSON.stringify({ values, labels }),
    })
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(data => setAnalysis(data))
      .catch(e => setError(e.message || 'Analysis failed'))
      .finally(() => setLoading(false));
  }, [values.join(','), labels.join(',')]);

  const TrendIcon = analysis?.trend_direction === 'up' ? TrendingUp
    : analysis?.trend_direction === 'down' ? TrendingDown : Minus;
  const trendColor = analysis?.trend_direction === 'up' ? 'var(--emerald)'
    : analysis?.trend_direction === 'down' ? 'var(--rose)' : 'var(--muted)';

  return (
    <div className="glass" style={{ padding: 14, minWidth: 220 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Activity size={13} style={{ color: 'var(--sky)' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>{title}</span>
        </div>
        {loading && <Loader2 size={12} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />}
      </div>

      {error && (
        <p style={{ fontSize: 10, color: 'var(--rose)' }}>TS analysis unavailable</p>
      )}

      {!loading && !error && analysis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Trend */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendIcon size={16} style={{ color: trendColor }} />
            <div>
              <span style={{ fontSize: 12, fontWeight: 600, color: trendColor, textTransform: 'capitalize' }}>
                {analysis.trend_direction || 'N/A'}
              </span>
              {analysis.trend_strength != null && (
                <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 6 }}>
                  ({(analysis.trend_strength * 100).toFixed(0)}% strength)
                </span>
              )}
            </div>
          </div>

          {/* Rolling average sparkline */}
          {analysis.rolling_average && analysis.rolling_average.length > 1 && (
            <div>
              <div style={label9}>ROLLING 3-PERIOD AVG</div>
              <div style={{ marginTop: 4 }}>
                <Sparkline data={analysis.rolling_average} color="var(--sky)" width={180} height={28} />
              </div>
            </div>
          )}

          {/* % Change sparkline */}
          {analysis.pct_changes && analysis.pct_changes.length > 0 && (
            <div>
              <div style={label9}>% CHANGE</div>
              <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                {analysis.pct_changes.map((pct, i) => (
                  <span key={i} style={{
                    fontSize: 9, padding: '2px 5px', borderRadius: 3,
                    background: pct > 0 ? 'rgba(52,211,153,.08)' : pct < 0 ? 'rgba(239,68,68,.08)' : 'rgba(255,255,255,.04)',
                    color: pct > 0 ? 'var(--emerald)' : pct < 0 ? 'var(--rose)' : 'var(--muted)',
                    fontFamily: 'var(--mono, monospace)',
                  }}>
                    {pct > 0 ? '+' : ''}{pct.toFixed(1)}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && !error && !analysis && values.length >= 2 && (
        <p style={{ fontSize: 10, color: 'var(--muted)' }}>Awaiting analysis...</p>
      )}
      {values.length < 2 && (
        <p style={{ fontSize: 10, color: 'var(--muted)' }}>Need at least 2 data points</p>
      )}
    </div>
  );
}
