import { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { Target, RefreshCcw, TrendingUp, TrendingDown, AlertTriangle, Shield, Zap, DollarSign } from 'lucide-react';
import { api } from '../api/client';

/* ─── Types ─── */
interface HealthData {
  score: number;
  grade: string;
  bullets: string[];
}

interface OverviewData {
  company: { name: string; industry: string; currency: string };
  period: string;
  health: HealthData;
  financials: Record<string, number>;
  ratios: Record<string, number>;
  risks: { severity: string; title: string; detail: string; metric: string }[];
  opportunities: { title: string; detail: string; estimated_impact: number; category: string }[];
  recommendations: any[];
  kpi_status: any[];
  subledgers: Record<string, number>;
  trends: { revenue: { period: string; value: number }[]; net_profit: { period: string; value: number }[] };
  recent_activity: any[];
  ai_narrative: string;
  causal_drivers: { metric: string; current: number; previous: number; change_pct: number; direction: string; impact: string }[];
}

/* ─── Styles ─── */
const card: React.CSSProperties = {
  background: 'var(--bg1, #1a1a2e)',
  borderRadius: 12,
  padding: 24,
  border: '1px solid var(--border, #2a2a4a)',
};

const metricCard: React.CSSProperties = {
  ...card,
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
  position: 'relative',
  overflow: 'hidden',
};

const heading: React.CSSProperties = {
  color: 'var(--heading, #e0e0e0)',
  fontSize: 16,
  fontWeight: 600,
  margin: 0,
};

const subtext: React.CSSProperties = {
  color: 'var(--text-secondary, #888)',
  fontSize: 13,
};

const metricValue: React.CSSProperties = {
  color: 'var(--heading, #e0e0e0)',
  fontSize: 28,
  fontWeight: 700,
  margin: 0,
};

const btn: React.CSSProperties = {
  background: 'var(--accent, #6366f1)',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  padding: '10px 20px',
  cursor: 'pointer',
  fontWeight: 600,
  fontSize: 14,
  display: 'flex',
  alignItems: 'center',
  gap: 8,
};

const tableSt: React.CSSProperties = { width: '100%', borderCollapse: 'collapse' as const, fontSize: 13 };
const thSt: React.CSSProperties = { textAlign: 'left' as const, padding: '10px 12px', color: 'var(--text-secondary, #888)', borderBottom: '1px solid var(--border, #2a2a4a)', fontWeight: 500 };
const tdSt: React.CSSProperties = { padding: '10px 12px', color: 'var(--heading, #e0e0e0)', borderBottom: '1px solid var(--border, #2a2a4a)' };

/* ─── Helpers ─── */
function fmt(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function gradeColor(grade: string): string {
  const g = grade?.charAt(0)?.toUpperCase() || 'C';
  if (g === 'A') return '#22c55e';
  if (g === 'B') return '#84cc16';
  if (g === 'C') return '#eab308';
  if (g === 'D') return '#f97316';
  return '#ef4444';
}

function severityColor(sev: string): string {
  if (sev === 'critical') return '#ef4444';
  if (sev === 'warning') return '#f97316';
  return '#eab308';
}

/* ─── Health Gauge ─── */
function gaugeOption(score: number, grade: string) {
  return {
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 10,
      center: ['50%', '60%'],
      radius: '90%',
      progress: { show: true, width: 18, itemStyle: { color: gradeColor(grade) } },
      pointer: { show: true, length: '60%', width: 5, itemStyle: { color: '#aaa' } },
      axisLine: { lineStyle: { width: 18, color: [[1, 'rgba(255,255,255,0.08)']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: true, offsetCenter: [0, '70%'], fontSize: 14, color: '#aaa' },
      detail: {
        valueAnimation: true,
        fontSize: 36,
        fontWeight: 700,
        offsetCenter: [0, '20%'],
        formatter: `{value}`,
        color: gradeColor(grade),
      },
      data: [{ value: Math.round(score), name: `Grade ${grade}` }],
    }],
  };
}

/* ─── Radar Chart ─── */
function radarOption(ratios: Record<string, number>) {
  const dims = [
    { key: 'gross_margin', label: 'Profitability', max: 50 },
    { key: 'current_ratio', label: 'Liquidity', max: 3 },
    { key: 'debt_to_equity', label: 'Solvency', max: 5, invert: true },
    { key: 'asset_turnover', label: 'Efficiency', max: 3 },
    { key: 'ebitda_margin', label: 'Growth', max: 30 },
    { key: 'net_margin', label: 'Risk Mgmt', max: 20 },
  ];

  const values = dims.map(d => {
    let v = ratios[d.key] || 0;
    if (d.invert) v = Math.max(0, d.max - v); // Lower D/E is better
    return Math.max(0, Math.min(v, d.max));
  });

  return {
    tooltip: {
      backgroundColor: 'rgba(20,20,40,0.95)',
      borderColor: '#333',
      textStyle: { color: '#e0e0e0' },
    },
    radar: {
      indicator: dims.map(d => ({ name: d.label, max: d.max })),
      shape: 'polygon',
      axisName: { color: '#aaa', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      splitArea: { areaStyle: { color: ['rgba(99,102,241,0.05)', 'rgba(99,102,241,0.02)'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: 'Financial Health',
        areaStyle: { color: 'rgba(99,102,241,0.25)' },
        lineStyle: { color: '#6366f1', width: 2 },
        itemStyle: { color: '#6366f1' },
      }],
    }],
  };
}

export default function Company360Page() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.company360Overview() as unknown as OverviewData;
      setOverview(data);
    } catch (err: any) {
      console.error('Company 360 fetch failed:', err);
      setError(err.message || 'Failed to load company data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.company360Seed();
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Seed failed');
    } finally {
      setSeeding(false);
    }
  };

  const isEmpty = overview && !overview.financials?.revenue && !overview.health?.score;

  if (loading) {
    return (
      <div style={{ padding: 32, color: 'var(--heading, #e0e0e0)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <RefreshCcw size={20} style={{ animation: 'spin 1s linear infinite' }} />
          Loading company 360 view...
        </div>
      </div>
    );
  }

  if (isEmpty || !overview) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <div style={{ ...card, maxWidth: 520, margin: '80px auto', padding: 48 }}>
          <Target size={48} style={{ color: 'var(--accent, #6366f1)', marginBottom: 16 }} />
          <h2 style={{ ...heading, fontSize: 22, marginBottom: 8 }}>No Financial Data</h2>
          <p style={{ ...subtext, marginBottom: 24 }}>
            Seed demo financial data to explore the Company 360 view with health scores, KPIs, risk analysis, and recommendations.
          </p>
          <button style={btn} onClick={handleSeed} disabled={seeding}>
            {seeding ? <RefreshCcw size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Target size={16} />}
            {seeding ? 'Seeding...' : 'Seed Demo Data'}
          </button>
          {error && <p style={{ color: '#ef4444', marginTop: 12, fontSize: 13 }}>{error}</p>}
        </div>
      </div>
    );
  }

  const { company, period, health, financials, ratios, risks, opportunities, recommendations, kpi_status, ai_narrative, causal_drivers } = overview;

  return (
    <div style={{ padding: '0 0 32px 0', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ ...heading, fontSize: 22, display: 'flex', alignItems: 'center', gap: 10 }}>
            <Target size={22} style={{ color: 'var(--accent, #6366f1)' }} /> Company 360{'\u00B0'}
          </h1>
          <p style={subtext}>{company?.name || 'Company'} &middot; {company?.industry?.replace(/_/g, ' ')} &middot; Period: {period || 'N/A'}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ ...btn, background: 'var(--bg1, #1a1a2e)', color: 'var(--heading, #e0e0e0)', border: '1px solid var(--border, #2a2a4a)' }} onClick={fetchData}>
            <RefreshCcw size={14} /> Refresh
          </button>
          <button style={btn} onClick={handleSeed} disabled={seeding}>
            {seeding ? 'Seeding...' : 'Seed Demo Data'}
          </button>
        </div>
      </div>

      {error && <div style={{ ...card, background: '#1c0a0a', borderColor: '#ef4444', padding: 12, color: '#ef4444', fontSize: 13 }}>{error}</div>}

      {/* AI Narrative */}
      {ai_narrative && (
        <div style={{ ...card, background: 'linear-gradient(135deg, rgba(99,102,241,0.08), rgba(99,102,241,0.03))', borderColor: 'rgba(99,102,241,0.3)' }}>
          <p style={{ color: 'var(--heading, #e0e0e0)', fontSize: 14, lineHeight: 1.6, margin: 0 }}>
            {ai_narrative}
          </p>
        </div>
      )}

      {/* Executive Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={18} style={{ color: '#6366f1' }} />
            <span style={subtext}>Revenue</span>
          </div>
          <p style={metricValue}>{fmt(financials.revenue || 0)}</p>
          <span style={{ ...subtext, fontSize: 12 }}>{company?.currency || 'GEL'}</span>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={18} style={{ color: (financials.net_profit || 0) >= 0 ? '#22c55e' : '#ef4444' }} />
            <span style={subtext}>Net Income</span>
          </div>
          <p style={{ ...metricValue, color: (financials.net_profit || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
            {fmt(financials.net_profit || 0)}
          </p>
          <span style={{ ...subtext, fontSize: 12 }}>
            {ratios.net_margin != null ? `${ratios.net_margin}% margin` : ''}
          </span>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Shield size={18} style={{ color: '#3b82f6' }} />
            <span style={subtext}>Total Assets</span>
          </div>
          <p style={metricValue}>{fmt(financials.total_assets || 0)}</p>
          <span style={{ ...subtext, fontSize: 12 }}>Equity: {fmt(financials.total_equity || 0)}</span>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Target size={18} style={{ color: gradeColor(health?.grade || 'C') }} />
            <span style={subtext}>Health Score</span>
          </div>
          <p style={{ ...metricValue, color: gradeColor(health?.grade || 'C') }}>
            {health?.score?.toFixed(0) || 0}<span style={{ fontSize: 16, fontWeight: 400 }}>/100</span>
          </p>
          <span style={{ ...subtext, fontSize: 12, color: gradeColor(health?.grade || 'C') }}>
            Grade {health?.grade || '?'}
          </span>
        </div>
      </div>

      {/* Health Gauge + Radar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 8 }}>Company Health Gauge</h3>
          <ReactECharts
            option={gaugeOption(health?.score || 0, health?.grade || 'C')}
            style={{ height: 280, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
          {health?.bullets?.length > 0 && (
            <ul style={{ margin: '8px 0 0 0', padding: '0 0 0 16px' }}>
              {health.bullets.map((b, i) => (
                <li key={i} style={{ color: 'var(--text-secondary, #888)', fontSize: 13, marginBottom: 4 }}>{b}</li>
              ))}
            </ul>
          )}
        </div>
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 8 }}>Financial Health Radar</h3>
          <p style={{ ...subtext, marginBottom: 8 }}>6 dimensions: Profitability, Liquidity, Solvency, Efficiency, Growth, Risk</p>
          <ReactECharts
            option={radarOption(ratios || {})}
            style={{ height: 300, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      </div>

      {/* KPI Performance Table */}
      <div style={card}>
        <h3 style={{ ...heading, marginBottom: 16 }}>Key Financial Ratios</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
          {[
            { label: 'Gross Margin', value: ratios.gross_margin, suffix: '%', good: (v: number) => v > 20 },
            { label: 'Net Margin', value: ratios.net_margin, suffix: '%', good: (v: number) => v > 5 },
            { label: 'EBITDA Margin', value: ratios.ebitda_margin, suffix: '%', good: (v: number) => v > 10 },
            { label: 'Current Ratio', value: ratios.current_ratio, suffix: 'x', good: (v: number) => v >= 1.5 },
            { label: 'Debt/Equity', value: ratios.debt_to_equity, suffix: 'x', good: (v: number) => v < 2 },
            { label: 'Asset Turnover', value: ratios.asset_turnover, suffix: 'x', good: (v: number) => v > 0.5 },
          ].map((r, i) => {
            const v = r.value ?? 0;
            const isGood = r.good(v);
            const barPct = Math.min(100, Math.max(0, r.label.includes('Debt') ? Math.max(0, (1 - v / 5) * 100) : (v / (r.suffix === 'x' ? 3 : 50)) * 100));
            return (
              <div key={i} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ ...subtext, fontSize: 12 }}>{r.label}</span>
                  {isGood
                    ? <TrendingUp size={14} style={{ color: '#22c55e' }} />
                    : <TrendingDown size={14} style={{ color: '#ef4444' }} />
                  }
                </div>
                <p style={{ ...metricValue, fontSize: 22, color: isGood ? '#22c55e' : v < 0 ? '#ef4444' : '#eab308' }}>
                  {typeof v === 'number' ? v.toFixed(1) : v}{r.suffix}
                </p>
                <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2, marginTop: 8 }}>
                  <div style={{
                    height: '100%',
                    width: `${barPct}%`,
                    background: isGood ? '#22c55e' : '#ef4444',
                    borderRadius: 2,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Causal Drivers + KPI Status */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Causal Drivers */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Zap size={16} style={{ color: '#eab308' }} /> Causal Drivers
          </h3>
          {(!causal_drivers || causal_drivers.length === 0) ? (
            <p style={subtext}>No causal driver data available (needs multiple periods)</p>
          ) : (
            <table style={tableSt}>
              <thead>
                <tr>
                  <th style={thSt}>Metric</th>
                  <th style={{ ...thSt, textAlign: 'right' }}>Current</th>
                  <th style={{ ...thSt, textAlign: 'right' }}>Previous</th>
                  <th style={{ ...thSt, textAlign: 'right' }}>Change</th>
                </tr>
              </thead>
              <tbody>
                {causal_drivers.map((d, i) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                    <td style={tdSt}>{d.metric}</td>
                    <td style={{ ...tdSt, textAlign: 'right' }}>{fmt(d.current)}</td>
                    <td style={{ ...tdSt, textAlign: 'right', color: '#888' }}>{fmt(d.previous)}</td>
                    <td style={{
                      ...tdSt,
                      textAlign: 'right',
                      fontWeight: 600,
                      color: d.impact === 'positive' ? '#22c55e' : '#ef4444',
                    }}>
                      {d.direction === 'up' ? '\u25B2' : '\u25BC'} {d.change_pct > 0 ? '+' : ''}{d.change_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* KPI Status */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Target size={16} style={{ color: '#6366f1' }} /> KPI Status
          </h3>
          {(!kpi_status || kpi_status.length === 0) ? (
            <p style={subtext}>No KPI status data available</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {kpi_status.slice(0, 8).map((kpi: any, i: number) => {
                const met = kpi.status === 'met' || kpi.on_target;
                return (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', borderRadius: 8,
                    background: met ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                    border: `1px solid ${met ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
                  }}>
                    <span style={{ color: 'var(--heading, #e0e0e0)', fontSize: 13 }}>
                      {kpi.metric || kpi.name || kpi.kpi || JSON.stringify(kpi).slice(0, 40)}
                    </span>
                    <span style={{
                      fontSize: 12, fontWeight: 600,
                      color: met ? '#22c55e' : '#ef4444',
                      padding: '2px 8px', borderRadius: 4,
                      background: met ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                    }}>
                      {met ? 'On Target' : 'Below Target'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Risks + Opportunities */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={16} style={{ color: '#ef4444' }} /> Risk Assessment
          </h3>
          {(!risks || risks.length === 0) ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#22c55e' }}>
              <Shield size={16} /> No significant risks detected
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {risks.map((r, i) => (
                <div key={i} style={{
                  padding: '12px 16px', borderRadius: 8,
                  background: r.severity === 'critical' ? 'rgba(239,68,68,0.08)' : 'rgba(249,115,22,0.08)',
                  borderLeft: `3px solid ${severityColor(r.severity)}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ color: 'var(--heading, #e0e0e0)', fontWeight: 600, fontSize: 14 }}>{r.title}</span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const,
                      color: severityColor(r.severity),
                      padding: '2px 6px', borderRadius: 4,
                      background: r.severity === 'critical' ? 'rgba(239,68,68,0.15)' : 'rgba(249,115,22,0.15)',
                    }}>
                      {r.severity}
                    </span>
                  </div>
                  <p style={{ ...subtext, margin: 0 }}>{r.detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Zap size={16} style={{ color: '#22c55e' }} /> Opportunities
          </h3>
          {(!opportunities || opportunities.length === 0) ? (
            <p style={subtext}>No opportunities identified yet</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {opportunities.map((o, i) => (
                <div key={i} style={{
                  padding: '12px 16px', borderRadius: 8,
                  background: 'rgba(34,197,94,0.06)',
                  borderLeft: '3px solid #22c55e',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ color: 'var(--heading, #e0e0e0)', fontWeight: 600, fontSize: 14 }}>{o.title}</span>
                    {o.estimated_impact > 0 && (
                      <span style={{ color: '#22c55e', fontWeight: 600, fontSize: 13 }}>
                        +{fmt(o.estimated_impact)}
                      </span>
                    )}
                  </div>
                  <p style={{ ...subtext, margin: 0 }}>{o.detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16 }}>Recommendations</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12 }}>
            {recommendations.slice(0, 6).map((rec: any, i: number) => (
              <div key={i} style={{
                padding: 16, borderRadius: 8,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border, #2a2a4a)',
              }}>
                <p style={{ color: 'var(--heading, #e0e0e0)', fontSize: 14, fontWeight: 500, margin: '0 0 4px 0' }}>
                  {rec.action || rec.title || rec.recommendation || JSON.stringify(rec).slice(0, 60)}
                </p>
                {rec.rationale && <p style={{ ...subtext, margin: 0 }}>{rec.rationale}</p>}
                {rec.expected_impact && <p style={{ color: '#22c55e', fontSize: 12, margin: '4px 0 0 0' }}>Impact: {rec.expected_impact}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
