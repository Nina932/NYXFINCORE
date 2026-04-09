/**
 * SensitivityPage — Monte Carlo simulations, tornado charts, scenario analysis
 * Connects to backend /api/agent/agents/sensitivity/* endpoints
 */
import { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  Activity, Zap, BarChart3, RefreshCcw, TrendingUp, TrendingDown,
  Target, AlertTriangle, Play, Settings,
} from 'lucide-react';
import { api } from '../api/client';

interface SensitivityResult {
  metric: string;
  base_value: number;
  low_value: number;
  high_value: number;
  sensitivity_pct: number;
}

interface MonteCarloResult {
  metric: string;
  mean: number;
  p10: number;
  p50: number;
  p90: number;
  std_dev: number;
  var_95: number;
  distribution?: number[];
}

export default function SensitivityPage() {
  const [loading, setLoading] = useState(false);
  const [sensData, setSensData] = useState<SensitivityResult[]>([]);
  const [mcData, setMcData] = useState<MonteCarloResult | null>(null);
  const [iterations, setIterations] = useState(1000);
  const [activeTab, setActiveTab] = useState<'tornado' | 'montecarlo' | 'scenarios'>('tornado');

  // Demo data for when backend isn't loaded
  const demoSensitivity: SensitivityResult[] = [
    { metric: 'Revenue Growth', base_value: 69_000_000, low_value: 55_200_000, high_value: 82_800_000, sensitivity_pct: 40 },
    { metric: 'COGS Ratio', base_value: 69_000_000, low_value: 58_650_000, high_value: 79_350_000, sensitivity_pct: 30 },
    { metric: 'Fuel Price', base_value: 69_000_000, low_value: 60_720_000, high_value: 77_280_000, sensitivity_pct: 24 },
    { metric: 'FX Rate (USD/GEL)', base_value: 69_000_000, low_value: 62_100_000, high_value: 75_900_000, sensitivity_pct: 20 },
    { metric: 'Operating Leverage', base_value: 69_000_000, low_value: 63_480_000, high_value: 74_520_000, sensitivity_pct: 16 },
    { metric: 'Interest Rate', base_value: 69_000_000, low_value: 65_550_000, high_value: 72_450_000, sensitivity_pct: 10 },
    { metric: 'Tax Rate', base_value: 69_000_000, low_value: 66_240_000, high_value: 71_760_000, sensitivity_pct: 8 },
    { metric: 'Headcount', base_value: 69_000_000, low_value: 67_620_000, high_value: 70_380_000, sensitivity_pct: 4 },
  ];

  const demoMC: MonteCarloResult = {
    metric: 'Net Income',
    mean: 7_200_000,
    p10: 3_800_000,
    p50: 7_100_000,
    p90: 10_600_000,
    std_dev: 2_100_000,
    var_95: 2_900_000,
    distribution: Array.from({ length: 50 }, (_, i) => {
      const x = 1_000_000 + i * 250_000;
      const mu = 7_200_000;
      const sigma = 2_100_000;
      return Math.round(1000 * Math.exp(-0.5 * Math.pow((x - mu) / sigma, 2)));
    }),
  };

  useEffect(() => {
    setSensData(demoSensitivity);
    setMcData(demoMC);
  }, []);

  const runSensitivity = async () => {
    setLoading(true);
    try {
      const financials = { revenue: 69_000_000, cogs: 38_000_000, opex: 15_700_000, net_income: 7_200_000 };
      const resp: any = await api.sensitivity(financials);
      if (resp?.bands) {
        // Map backend bands → our SensitivityResult format
        const baseNP = parseFloat(resp.base_net_profit || '0');
        const mapped: SensitivityResult[] = resp.bands.map((b: any) => {
          const outcomes = (b.net_profit_outcomes || []).map(Number);
          const low = Math.min(...outcomes);
          const high = Math.max(...outcomes);
          const range = high - low;
          const sensPct = baseNP > 0 ? Math.round((range / baseNP) * 100) : 0;
          return {
            metric: (b.variable || '').replace(/_pct$/, '').replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
            base_value: baseNP,
            low_value: low,
            high_value: high,
            sensitivity_pct: sensPct,
          };
        });
        mapped.sort((a: SensitivityResult, b: SensitivityResult) => b.sensitivity_pct - a.sensitivity_pct);
        setSensData(mapped);
      }
    } catch (err) {
      console.error('Sensitivity analysis failed:', err);
      setSensData(demoSensitivity);
    } finally {
      setLoading(false);
    }
  };

  const runMonteCarlo = async () => {
    setLoading(true);
    try {
      const financials = { revenue: 69_000_000, cogs: 38_000_000, opex: 15_700_000, net_income: 7_200_000 };
      const resp: any = await api.monteCarlo(financials, iterations);
      if (resp?.mean_net_profit) {
        const mean = parseFloat(resp.mean_net_profit);
        const p5 = parseFloat(resp.p5_net_profit || '0');
        const median = parseFloat(resp.median_net_profit || '0');
        const p95 = parseFloat(resp.p95_net_profit || '0');
        const std = parseFloat(resp.std_dev || '0');
        const var95 = parseFloat(resp.value_at_risk_95 || '0');
        // Build a synthetic gaussian distribution for the histogram
        const dist = Array.from({ length: 50 }, (_, i) => {
          const x = (p5 - std) + i * ((p95 + std - p5 + std) / 50);
          return Math.round(iterations * Math.exp(-0.5 * Math.pow((x - mean) / std, 2)));
        });
        setMcData({
          metric: 'Net Profit',
          mean,
          p10: p5,  // using p5 as conservative P10
          p50: median,
          p90: p95, // using p95 as conservative P90
          std_dev: std,
          var_95: Math.abs(var95),
          distribution: dist,
        });
      }
    } catch (err) {
      console.error('Monte Carlo failed:', err);
      setMcData(demoMC);
    } finally {
      setLoading(false);
    }
  };

  const fmt = (v: number) => {
    if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (Math.abs(v) >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  };

  // Tornado chart option
  const tornadoOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 130, right: 80, top: 20, bottom: 30 },
    xAxis: {
      type: 'value',
      axisLabel: { fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#718096', formatter: (v: number) => fmt(v) },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    yAxis: {
      type: 'category',
      data: sensData.map(s => s.metric).reverse(),
      axisLabel: { fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#A0AEC0' },
    },
    series: [
      {
        name: 'Downside',
        type: 'bar',
        stack: 'total',
        data: sensData.map(s => s.low_value).reverse(),
        itemStyle: { color: '#F56565', borderRadius: [4, 0, 0, 4] },
        label: { show: false },
      },
      {
        name: 'Upside',
        type: 'bar',
        stack: 'total',
        data: sensData.map(s => s.high_value - s.low_value).reverse(),
        itemStyle: { color: '#48BB78', borderRadius: [0, 4, 4, 0] },
        label: { show: false },
      },
    ],
    markLine: {
      data: [{ xAxis: sensData[0]?.base_value || 0 }],
      lineStyle: { color: '#00D8FF', type: 'dashed', width: 2 },
      label: { formatter: 'Base', color: '#00D8FF', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
    },
  };

  // Monte Carlo histogram
  const mcHistogramOption = mcData ? {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 40, top: 30, bottom: 50 },
    xAxis: {
      type: 'category',
      data: (mcData.distribution || []).map((_, i) => fmt(1_000_000 + i * 250_000)),
      axisLabel: { fontFamily: "'JetBrains Mono', monospace", fontSize: 8, color: '#718096', rotate: 45, interval: 4 },
    },
    yAxis: {
      type: 'value',
      name: 'Frequency',
      nameTextStyle: { color: '#718096', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
      axisLabel: { fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: '#718096' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    series: [{
      type: 'bar',
      data: (mcData.distribution || []).map((v, i) => {
        const x = 1_000_000 + i * 250_000;
        let color = '#48BB78';
        if (x < mcData.p10) color = '#F56565';
        else if (x < mcData.p50) color = '#ED8936';
        else if (x > mcData.p90) color = '#00D8FF';
        return { value: v, itemStyle: { color } };
      }),
      barWidth: '90%',
    }],
    graphic: [
      { type: 'line', shape: { x1: 0, y1: 0, x2: 0, y2: 300 }, style: { stroke: '#F56565', lineWidth: 2, lineDash: [4, 4] }, left: '20%', top: 30 },
    ],
  } : {};

  // Scenario cards
  const scenarios = [
    { name: 'Base Case', revenue: 69_000_000, ni: 7_200_000, prob: '50%', color: 'var(--sky)' },
    { name: 'Bull Case', revenue: 82_800_000, ni: 12_400_000, prob: '25%', color: 'var(--emerald)' },
    { name: 'Bear Case', revenue: 55_200_000, ni: 2_100_000, prob: '20%', color: 'var(--rose)' },
    { name: 'Stress Test', revenue: 41_400_000, ni: -3_600_000, prob: '5%', color: 'var(--amber)' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Activity size={20} style={{ color: 'var(--sky)' }} />
            Sensitivity & Simulations
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
            Tornado analysis, Monte Carlo simulations, scenario modeling
          </p>
        </div>
        <button
          onClick={activeTab === 'montecarlo' ? runMonteCarlo : runSensitivity}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', fontSize: 11,
            background: 'rgba(0,216,255,0.1)', border: '1px solid rgba(0,216,255,0.3)',
            borderRadius: 6, color: 'var(--sky)', cursor: 'pointer', fontWeight: 600,
          }}
        >
          {loading ? <RefreshCcw size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={14} />}
          Run {activeTab === 'montecarlo' ? 'Monte Carlo' : 'Analysis'}
        </button>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 2, background: 'var(--bg2)', borderRadius: 8, padding: 3, border: '1px solid var(--b1)' }}>
        {[
          { id: 'tornado' as const, label: 'Tornado Analysis', icon: BarChart3 },
          { id: 'montecarlo' as const, label: 'Monte Carlo', icon: Zap },
          { id: 'scenarios' as const, label: 'Scenario Modeling', icon: Target },
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px',
                fontSize: 11, fontWeight: isActive ? 600 : 400, fontFamily: "var(--mono)",
                color: isActive ? 'var(--sky)' : 'var(--muted)',
                background: isActive ? 'rgba(0,216,255,0.08)' : 'transparent',
                border: isActive ? '1px solid rgba(0,216,255,0.2)' : '1px solid transparent',
                borderRadius: 6, cursor: 'pointer',
              }}
            >
              <Icon size={13} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tornado */}
      {activeTab === 'tornado' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Tornado Chart — Revenue Sensitivity</div>
              <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Impact of each variable on revenue, sorted by magnitude</div>
            </div>
            <ReactECharts option={tornadoOption} style={{ height: '400px' }} theme="dark" />
          </div>
          {/* Sensitivity table */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 12 }}>Variable Impact Analysis</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--b2)' }}>
                  {['Variable', 'Low Case', 'Base', 'High Case', 'Sensitivity'].map(h => (
                    <th key={h} style={{ padding: '6px 12px', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontFamily: "var(--mono)", textAlign: h === 'Variable' ? 'left' : 'right' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sensData.map((s, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 500, color: 'var(--heading)' }}>{s.metric}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: "var(--mono)", color: 'var(--rose)' }}>{fmt(s.low_value)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: "var(--mono)", color: 'var(--text)' }}>{fmt(s.base_value)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: "var(--mono)", color: 'var(--emerald)' }}>{fmt(s.high_value)}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                      <span style={{
                        fontSize: 10, padding: '2px 8px', borderRadius: 10, fontWeight: 600, fontFamily: "var(--mono)",
                        background: s.sensitivity_pct > 20 ? 'rgba(245,101,101,0.1)' : s.sensitivity_pct > 10 ? 'rgba(237,137,54,0.1)' : 'rgba(72,187,120,0.1)',
                        color: s.sensitivity_pct > 20 ? 'var(--rose)' : s.sensitivity_pct > 10 ? 'var(--amber)' : 'var(--emerald)',
                      }}>
                        {s.sensitivity_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Monte Carlo */}
      {activeTab === 'montecarlo' && mcData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* KPI Row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
            {[
              { label: 'Mean', value: fmt(mcData.mean), color: 'var(--sky)' },
              { label: 'P10 (Downside)', value: fmt(mcData.p10), color: 'var(--rose)' },
              { label: 'P50 (Median)', value: fmt(mcData.p50), color: 'var(--text)' },
              { label: 'P90 (Upside)', value: fmt(mcData.p90), color: 'var(--emerald)' },
              { label: 'VaR (95%)', value: fmt(mcData.var_95), color: 'var(--amber)' },
            ].map(kpi => (
              <div key={kpi.label} className="glass" style={{ padding: 14, textAlign: 'center' }}>
                <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)', fontFamily: "var(--mono)" }}>{kpi.label}</div>
                <div style={{ fontSize: 20, fontWeight: 800, color: kpi.color, fontFamily: "var(--mono)", marginTop: 4 }}>{kpi.value}</div>
              </div>
            ))}
          </div>

          {/* Histogram */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Monte Carlo Distribution — {mcData.metric}</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>{iterations.toLocaleString()} iterations, normal distribution assumption</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Settings size={12} style={{ color: 'var(--dim)' }} />
                <select
                  value={iterations}
                  onChange={e => setIterations(Number(e.target.value))}
                  style={{
                    padding: '4px 8px', fontSize: 10, fontFamily: "var(--mono)",
                    background: 'var(--bg3)', border: '1px solid var(--b2)', borderRadius: 4,
                    color: 'var(--text)',
                  }}
                >
                  <option value={500}>500 iter</option>
                  <option value={1000}>1,000 iter</option>
                  <option value={5000}>5,000 iter</option>
                  <option value={10000}>10,000 iter</option>
                </select>
              </div>
            </div>
            <ReactECharts option={mcHistogramOption} style={{ height: '350px' }} theme="dark" />
            {/* Legend */}
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginTop: 8 }}>
              {[
                { label: 'Below P10', color: '#F56565' },
                { label: 'P10–P50', color: '#ED8936' },
                { label: 'P50–P90', color: '#48BB78' },
                { label: 'Above P90', color: '#00D8FF' },
              ].map(l => (
                <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: l.color }} />
                  <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: "var(--mono)" }}>{l.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Scenarios */}
      {activeTab === 'scenarios' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            {scenarios.map(s => (
              <div key={s.name} className="glass" style={{ padding: 16, borderLeft: `3px solid ${s.color}` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{s.name}</span>
                  <span style={{
                    fontSize: 9, padding: '2px 8px', borderRadius: 10, fontWeight: 600, fontFamily: "var(--mono)",
                    background: `${s.color}15`, color: s.color,
                  }}>
                    {s.prob}
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--muted)', fontFamily: "var(--mono)", marginBottom: 2 }}>REVENUE</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: "var(--mono)" }}>{fmt(s.revenue)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--muted)', fontFamily: "var(--mono)", marginBottom: 2 }}>NET INCOME</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {s.ni >= 0
                        ? <TrendingUp size={14} style={{ color: 'var(--emerald)' }} />
                        : <TrendingDown size={14} style={{ color: 'var(--rose)' }} />
                      }
                      <span style={{
                        fontSize: 18, fontWeight: 700, fontFamily: "var(--mono)",
                        color: s.ni >= 0 ? 'var(--emerald)' : 'var(--rose)',
                      }}>
                        {fmt(s.ni)}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 4, lineHeight: 1.5 }}>
                    {s.name === 'Base Case' && 'Current trajectory with stable market conditions and normal operations.'}
                    {s.name === 'Bull Case' && 'Favorable fuel prices, increased demand, FX tailwinds, expansion gains.'}
                    {s.name === 'Bear Case' && 'Commodity shock, demand decline, regulatory headwinds, margin compression.'}
                    {s.name === 'Stress Test' && 'Severe recession + supply disruption + FX collapse. Liquidity crisis scenario.'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Risk matrix */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 12 }}>Key Risk Factors</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {[
                { risk: 'Commodity Price Volatility', impact: 'HIGH', likelihood: 'MEDIUM', icon: AlertTriangle, color: 'var(--amber)' },
                { risk: 'FX Rate Fluctuation', impact: 'MEDIUM', likelihood: 'HIGH', icon: TrendingDown, color: 'var(--rose)' },
                { risk: 'Regulatory Changes', impact: 'MEDIUM', likelihood: 'LOW', icon: Target, color: 'var(--violet)' },
                { risk: 'Supply Chain Disruption', impact: 'HIGH', likelihood: 'LOW', icon: AlertTriangle, color: 'var(--amber)' },
                { risk: 'Interest Rate Movement', impact: 'LOW', likelihood: 'HIGH', icon: TrendingUp, color: 'var(--emerald)' },
                { risk: 'Market Share Loss', impact: 'HIGH', likelihood: 'MEDIUM', icon: TrendingDown, color: 'var(--rose)' },
              ].map(r => {
                const Icon = r.icon;
                return (
                  <div key={r.risk} style={{ display: 'flex', gap: 10, padding: 10, background: 'var(--bg3)', borderRadius: 6 }}>
                    <Icon size={16} style={{ color: r.color, marginTop: 2, flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--heading)', marginBottom: 4 }}>{r.risk}</div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <span style={{ fontSize: 9, fontFamily: "var(--mono)", color: 'var(--muted)' }}>Impact: <span style={{ color: r.color, fontWeight: 600 }}>{r.impact}</span></span>
                        <span style={{ fontSize: 9, fontFamily: "var(--mono)", color: 'var(--muted)' }}>Prob: <span style={{ fontWeight: 600 }}>{r.likelihood}</span></span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
