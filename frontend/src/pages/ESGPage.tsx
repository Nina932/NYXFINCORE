import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  Leaf, Droplets, Recycle, Users, Shield, TrendingUp,
  Factory, Zap, RefreshCcw, CheckCircle2, AlertTriangle,
  ArrowDown, ArrowUp, Minus, Target, BarChart3, Award,
} from 'lucide-react';
import { api } from '../api/client';

/* ─── Types ─── */

interface ESGScore {
  environmental: number;
  social: number;
  governance: number;
  composite: number;
  rating: string;
  methodology: string;
  sub_ratings: Record<string, string>;
}

interface CarbonFootprint {
  scope1: number;
  scope2: number;
  scope3: number;
  total: number;
  unit: string;
  intensity: number;
  yoy_change_pct: number;
  reduction_target: number;
  target_year: number;
  scope_breakdown: { scope1_pct: number; scope2_pct: number; scope3_pct: number };
}

interface KPI {
  kpi_id: string;
  name: string;
  category: string;
  value: number;
  target: number;
  unit: string;
  progress_pct: number;
  trend: string;
  description: string;
  framework: string;
  framework_ref: string;
  on_track: boolean;
}

interface Framework {
  framework: string;
  total_indicators: number;
  aligned: number;
  partial: number;
  not_aligned: number;
  coverage_pct: number;
  key_gaps: string[];
}

interface Recommendation {
  priority: string;
  category: string;
  title: string;
  description: string;
  impact: string;
  estimated_cost: string;
  timeline: string;
  framework_ref: string;
}

interface DashboardData {
  seeded: boolean;
  score: ESGScore;
  carbon: CarbonFootprint;
  kpis: KPI[];
  frameworks: Framework[];
  recommendations: Recommendation[];
  generated_at: string;
}

/* ─── Helpers ─── */

const ratingColor = (rating: string): string => {
  if (rating.startsWith('A')) return 'var(--emerald, #34d399)';
  if (rating.startsWith('B')) return 'var(--sky, #38bdf8)';
  if (rating.startsWith('C')) return 'var(--amber, #fbbf24)';
  return 'var(--rose, #fb7185)';
};

const priorityStyle = (p: string) => {
  switch (p) {
    case 'critical': return { bg: 'rgba(251,113,133,0.15)', text: '#fb7185', border: 'rgba(251,113,133,0.4)' };
    case 'high': return { bg: 'rgba(251,191,36,0.15)', text: '#fbbf24', border: 'rgba(251,191,36,0.4)' };
    case 'medium': return { bg: 'rgba(56,189,248,0.12)', text: '#38bdf8', border: 'rgba(56,189,248,0.3)' };
    default: return { bg: 'rgba(148,163,184,0.1)', text: '#94a3b8', border: 'rgba(148,163,184,0.3)' };
  }
};

const categoryIcon = (cat: string) => {
  switch (cat) {
    case 'environmental': return <Leaf size={14} style={{ color: 'var(--emerald, #34d399)' }} />;
    case 'social': return <Users size={14} style={{ color: 'var(--sky, #38bdf8)' }} />;
    case 'governance': return <Shield size={14} style={{ color: 'var(--amber, #fbbf24)' }} />;
    default: return <Target size={14} />;
  }
};

const trendIcon = (trend: string) => {
  if (trend === 'improving') return <ArrowUp size={12} style={{ color: 'var(--emerald, #34d399)' }} />;
  if (trend === 'declining') return <ArrowDown size={12} style={{ color: 'var(--rose, #fb7185)' }} />;
  return <Minus size={12} style={{ color: 'var(--dim, #64748b)' }} />;
};

/* ─── Component ─── */

export default function ESGPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'kpis' | 'carbon' | 'recommendations'>('overview');

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.esgDashboard() as any;
      if (res && res.score) {
        setData(res as DashboardData);
      } else {
        setData(null);
      }
    } catch (err) {
      console.error('ESG fetch failed:', err);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const seedData = async () => {
    setSeeding(true);
    try {
      await api.esgSeed();
      await fetchData();
    } catch (err) {
      console.error('ESG seed failed:', err);
    } finally {
      setSeeding(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  /* ─── Gauge chart option builder ─── */
  const gaugeOption = useMemo(() => {
    if (!data?.score) return {};
    const { composite, rating } = data.score;
    const color = ratingColor(rating);
    return {
      series: [{
        type: 'gauge',
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: 100,
        splitNumber: 10,
        center: ['50%', '55%'],
        radius: '90%',
        itemStyle: { color },
        progress: { show: true, width: 18, roundCap: true },
        pointer: { show: true, length: '55%', width: 4, itemStyle: { color: 'var(--heading, #e2e8f0)' } },
        axisLine: { lineStyle: { width: 18, color: [[1, 'rgba(148,163,184,0.12)']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '70%'], fontSize: 13, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '40%'],
          fontSize: 36,
          fontWeight: 700,
          color,
          formatter: '{value}',
          fontFamily: 'JetBrains Mono, monospace',
        },
        data: [{ value: Math.round(composite), name: `Rating: ${rating}` }],
      }],
    };
  }, [data?.score]);

  /* ─── Mini gauge for sub-scores ─── */
  const miniGauge = (value: number, label: string, subRating: string) => {
    const color = ratingColor(subRating);
    return {
      series: [{
        type: 'gauge',
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: 100,
        center: ['50%', '58%'],
        radius: '88%',
        itemStyle: { color },
        progress: { show: true, width: 10, roundCap: true },
        pointer: { show: false },
        axisLine: { lineStyle: { width: 10, color: [[1, 'rgba(148,163,184,0.1)']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: true, offsetCenter: [0, '68%'], fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' },
        detail: {
          valueAnimation: true,
          offsetCenter: [0, '30%'],
          fontSize: 22,
          fontWeight: 700,
          color,
          formatter: '{value}',
          fontFamily: 'JetBrains Mono, monospace',
        },
        data: [{ value: Math.round(value), name: subRating }],
      }],
    };
  };

  /* ─── Carbon stacked bar ─── */
  const carbonBarOption = useMemo(() => {
    if (!data?.carbon) return {};
    const { scope1, scope2, scope3 } = data.carbon;
    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15,23,42,0.95)',
        borderColor: 'rgba(56,189,248,0.2)',
        textStyle: { color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          let s = `<div style="font-weight:600;margin-bottom:4px">${params[0]?.axisValue}</div>`;
          params.forEach((p: any) => {
            s += `<div style="display:flex;gap:8px;align-items:center"><span style="width:8px;height:8px;border-radius:50%;background:${p.color};display:inline-block"></span>${p.seriesName}: <b>${p.value.toLocaleString()} tCO2e</b></div>`;
          });
          return s;
        },
      },
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: 'category',
        data: ['Current Year'],
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
        axisLabel: { color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        name: 'tCO2e',
        nameTextStyle: { color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.08)' } },
        axisLabel: { color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, formatter: (v: number) => v.toLocaleString() },
      },
      series: [
        {
          name: 'Scope 1 (Direct)',
          type: 'bar',
          stack: 'total',
          data: [scope1],
          itemStyle: { color: '#f97316', borderRadius: [0, 0, 0, 0] },
          barWidth: 80,
        },
        {
          name: 'Scope 2 (Energy)',
          type: 'bar',
          stack: 'total',
          data: [scope2],
          itemStyle: { color: '#38bdf8' },
          barWidth: 80,
        },
        {
          name: 'Scope 3 (Value Chain)',
          type: 'bar',
          stack: 'total',
          data: [scope3],
          itemStyle: { color: '#a78bfa', borderRadius: [6, 6, 0, 0] },
          barWidth: 80,
        },
      ],
    };
  }, [data?.carbon]);

  /* ─── Scope donut ─── */
  const scopeDonutOption = useMemo(() => {
    if (!data?.carbon) return {};
    const { scope1, scope2, scope3 } = data.carbon;
    return {
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15,23,42,0.95)',
        borderColor: 'rgba(56,189,248,0.2)',
        textStyle: { color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
        formatter: (p: any) => `${p.name}: <b>${p.value.toLocaleString()} tCO2e</b> (${p.percent}%)`,
      },
      series: [{
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        label: { show: true, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, formatter: '{b}\n{d}%' },
        labelLine: { lineStyle: { color: 'rgba(148,163,184,0.3)' } },
        itemStyle: { borderRadius: 4, borderColor: 'rgba(15,23,42,0.8)', borderWidth: 2 },
        data: [
          { value: Math.round(scope1), name: 'Scope 1', itemStyle: { color: '#f97316' } },
          { value: Math.round(scope2), name: 'Scope 2', itemStyle: { color: '#38bdf8' } },
          { value: Math.round(scope3), name: 'Scope 3', itemStyle: { color: '#a78bfa' } },
        ],
      }],
    };
  }, [data?.carbon]);

  /* ─── Framework coverage radar ─── */
  const frameworkRadarOption = useMemo(() => {
    if (!data?.frameworks?.length) return {};
    return {
      radar: {
        indicator: data.frameworks.map(f => ({ name: f.framework, max: 100 })),
        axisLine: { lineStyle: { color: 'rgba(148,163,184,0.15)' } },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
        splitArea: { show: false },
        axisName: { color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      },
      series: [{
        type: 'radar',
        data: [{
          value: data.frameworks.map(f => Math.round(f.coverage_pct)),
          name: 'Coverage',
          areaStyle: { color: 'rgba(56,189,248,0.15)' },
          lineStyle: { color: '#38bdf8', width: 2 },
          itemStyle: { color: '#38bdf8' },
        }],
      }],
      tooltip: {
        backgroundColor: 'rgba(15,23,42,0.95)',
        borderColor: 'rgba(56,189,248,0.2)',
        textStyle: { color: '#e2e8f0', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      },
    };
  }, [data?.frameworks]);

  /* ─── Empty state ─── */
  if (!loading && !data) {
    return (
      <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 24 }}>
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: 'linear-gradient(135deg, rgba(52,211,153,0.15), rgba(56,189,248,0.15))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Leaf size={36} style={{ color: 'var(--emerald, #34d399)' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--heading, #e2e8f0)', margin: 0 }}>ESG & Sustainability</h2>
          <p style={{ color: 'var(--dim, #64748b)', fontSize: 13, marginTop: 8, maxWidth: 420 }}>
            No ESG data available yet. Seed demo data to explore environmental, social, and governance scoring for a fuel distribution company.
          </p>
        </div>
        <button
          onClick={seedData}
          disabled={seeding}
          className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        >
          {seeding ? <RefreshCcw size={14} className="animate-spin" /> : <Zap size={14} />}
          {seeding ? 'Seeding...' : 'Seed Demo Data'}
        </button>
      </div>
    );
  }

  /* ─── Loading state ─── */
  if (loading && !data) {
    return (
      <div className="empty-state">
        <Leaf className="animate-pulse" size={32} style={{ color: 'var(--emerald, #34d399)' }} />
        <p className="font-mono text-xs uppercase tracking-widest mt-4" style={{ color: 'var(--dim, #64748b)' }}>
          Loading ESG Data...
        </p>
      </div>
    );
  }

  if (!data) return null;

  const { score, carbon, kpis, frameworks, recommendations } = data;

  const envKpis = kpis.filter(k => k.category === 'environmental');
  const socKpis = kpis.filter(k => k.category === 'social');
  const govKpis = kpis.filter(k => k.category === 'governance');

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 24, paddingBottom: 48 }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--heading, #e2e8f0)', display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
            <Leaf size={22} style={{ color: 'var(--emerald, #34d399)' }} />
            ESG & Sustainability
          </h1>
          <p style={{ fontSize: 11, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 4 }}>
            Environmental, Social & Governance Scoring Framework
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={fetchData} className="btn btn-ghost" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCcw size={14} /> Refresh
          </button>
          <button onClick={seedData} disabled={seeding} className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {seeding ? <RefreshCcw size={14} className="animate-spin" /> : <Zap size={14} />}
            Re-seed Data
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--b1, rgba(148,163,184,0.1))', paddingBottom: 0 }}>
        {(['overview', 'kpis', 'carbon', 'recommendations'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px',
              fontSize: 12,
              fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? 'var(--sky, #38bdf8)' : 'var(--dim, #64748b)',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--sky, #38bdf8)' : '2px solid transparent',
              cursor: 'pointer',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              fontFamily: 'JetBrains Mono, monospace',
              transition: 'all 0.15s',
            }}
          >
            {tab === 'overview' && 'Overview'}
            {tab === 'kpis' && 'Sustainability KPIs'}
            {tab === 'carbon' && 'Carbon Footprint'}
            {tab === 'recommendations' && 'Recommendations'}
          </button>
        ))}
      </div>

      {/* ─── OVERVIEW TAB ─── */}
      {activeTab === 'overview' && (
        <>
          {/* Main Score + Sub-scores */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16 }}>
            {/* Composite Gauge */}
            <div className="glass" style={{ padding: 16, gridColumn: 'span 1' }}>
              <div style={{ fontSize: 11, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
                ESG Composite Score
              </div>
              <ReactECharts option={gaugeOption} style={{ height: 200 }} opts={{ renderer: 'svg' }} />
            </div>

            {/* Environmental */}
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Leaf size={14} style={{ color: 'var(--emerald, #34d399)' }} />
                <span style={{ fontSize: 11, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Environmental</span>
              </div>
              <ReactECharts
                option={miniGauge(score.environmental, 'Environmental', score.sub_ratings?.environmental || 'N/A')}
                style={{ height: 170 }}
                opts={{ renderer: 'svg' }}
              />
              <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>
                {envKpis.filter(k => k.on_track).length}/{envKpis.length} KPIs on track
              </div>
            </div>

            {/* Social */}
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Users size={14} style={{ color: 'var(--sky, #38bdf8)' }} />
                <span style={{ fontSize: 11, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Social</span>
              </div>
              <ReactECharts
                option={miniGauge(score.social, 'Social', score.sub_ratings?.social || 'N/A')}
                style={{ height: 170 }}
                opts={{ renderer: 'svg' }}
              />
              <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>
                {socKpis.filter(k => k.on_track).length}/{socKpis.length} KPIs on track
              </div>
            </div>

            {/* Governance */}
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <Shield size={14} style={{ color: 'var(--amber, #fbbf24)' }} />
                <span style={{ fontSize: 11, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Governance</span>
              </div>
              <ReactECharts
                option={miniGauge(score.governance, 'Governance', score.sub_ratings?.governance || 'N/A')}
                style={{ height: 170 }}
                opts={{ renderer: 'svg' }}
              />
              <div style={{ textAlign: 'center', fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>
                {govKpis.filter(k => k.on_track).length}/{govKpis.length} KPIs on track
              </div>
            </div>
          </div>

          {/* Carbon + Frameworks row */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
            {/* Carbon Summary */}
            <div className="glass" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <Factory size={16} style={{ color: 'var(--dim, #64748b)' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>Carbon Footprint</span>
                <span style={{
                  marginLeft: 'auto', fontSize: 11, fontFamily: 'JetBrains Mono, monospace',
                  color: carbon.yoy_change_pct < 0 ? 'var(--emerald, #34d399)' : 'var(--rose, #fb7185)',
                }}>
                  {carbon.yoy_change_pct < 0 ? '' : '+'}{carbon.yoy_change_pct.toFixed(1)}% YoY
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <ReactECharts option={carbonBarOption} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
                <ReactECharts option={scopeDonutOption} style={{ height: 220 }} opts={{ renderer: 'svg' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 16 }}>
                <StatBox label="Total Emissions" value={`${carbon.total.toLocaleString()}`} unit={carbon.unit} />
                <StatBox label="Scope 1 (Direct)" value={`${carbon.scope1.toLocaleString()}`} unit={carbon.unit} color="#f97316" />
                <StatBox label="Scope 2 (Energy)" value={`${carbon.scope2.toLocaleString()}`} unit={carbon.unit} color="#38bdf8" />
                <StatBox label="Scope 3 (Value Chain)" value={`${carbon.scope3.toLocaleString()}`} unit={carbon.unit} color="#a78bfa" />
              </div>
            </div>

            {/* Framework Alignment */}
            <div className="glass" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <Award size={16} style={{ color: 'var(--sky, #38bdf8)' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>Framework Compliance</span>
              </div>
              {frameworks.length > 1 && (
                <ReactECharts option={frameworkRadarOption} style={{ height: 160 }} opts={{ renderer: 'svg' }} />
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
                {frameworks.map(fw => (
                  <div key={fw.framework} style={{
                    padding: 12, borderRadius: 8,
                    background: 'rgba(148,163,184,0.04)',
                    border: '1px solid rgba(148,163,184,0.08)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>{fw.framework}</span>
                      <span style={{
                        fontSize: 11, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600,
                        color: fw.coverage_pct >= 70 ? 'var(--emerald, #34d399)' : fw.coverage_pct >= 50 ? 'var(--amber, #fbbf24)' : 'var(--rose, #fb7185)',
                      }}>{fw.coverage_pct.toFixed(0)}%</span>
                    </div>
                    {/* Progress bar */}
                    <div style={{ height: 6, borderRadius: 3, background: 'rgba(148,163,184,0.1)', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: 3, transition: 'width 0.8s ease',
                        width: `${fw.coverage_pct}%`,
                        background: fw.coverage_pct >= 70 ? 'var(--emerald, #34d399)' : fw.coverage_pct >= 50 ? 'var(--amber, #fbbf24)' : 'var(--rose, #fb7185)',
                      }} />
                    </div>
                    <div style={{ display: 'flex', gap: 12, marginTop: 8, fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: 'var(--dim, #64748b)' }}>
                      <span style={{ color: 'var(--emerald, #34d399)' }}>{fw.aligned} aligned</span>
                      <span style={{ color: 'var(--amber, #fbbf24)' }}>{fw.partial} partial</span>
                      <span style={{ color: 'var(--rose, #fb7185)' }}>{fw.not_aligned} gaps</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Recommendations */}
          <div className="glass" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <TrendingUp size={16} style={{ color: 'var(--amber, #fbbf24)' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>Top Recommendations</span>
              <span style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginLeft: 'auto' }}>
                {recommendations.length} actions identified
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {recommendations.slice(0, 3).map((rec, i) => {
                const ps = priorityStyle(rec.priority);
                return (
                  <div key={i} style={{
                    padding: 14, borderRadius: 8,
                    background: ps.bg,
                    border: `1px solid ${ps.border}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                      {categoryIcon(rec.category)}
                      <span style={{
                        fontSize: 9, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase',
                        letterSpacing: '0.08em', color: ps.text, fontWeight: 700,
                      }}>{rec.priority}</span>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)', marginBottom: 4 }}>{rec.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--dim, #64748b)', lineHeight: 1.5 }}>{rec.impact}</div>
                    <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginTop: 8, display: 'flex', gap: 12 }}>
                      <span>{rec.timeline}</span>
                      <span>{rec.estimated_cost}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* ─── KPIs TAB ─── */}
      {activeTab === 'kpis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* KPI Summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <SummaryCard icon={<Target size={16} />} label="Total KPIs" value={kpis.length} color="var(--sky, #38bdf8)" />
            <SummaryCard icon={<CheckCircle2 size={16} />} label="On Track" value={kpis.filter(k => k.on_track).length} color="var(--emerald, #34d399)" />
            <SummaryCard icon={<AlertTriangle size={16} />} label="Needs Attention" value={kpis.filter(k => !k.on_track).length} color="var(--amber, #fbbf24)" />
            <SummaryCard icon={<TrendingUp size={16} />} label="Improving" value={kpis.filter(k => k.trend === 'improving').length} color="var(--emerald, #34d399)" />
          </div>

          {/* KPI Categories */}
          {[
            { title: 'Environmental', icon: <Leaf size={16} style={{ color: 'var(--emerald, #34d399)' }} />, items: envKpis },
            { title: 'Social', icon: <Users size={16} style={{ color: 'var(--sky, #38bdf8)' }} />, items: socKpis },
            { title: 'Governance', icon: <Shield size={16} style={{ color: 'var(--amber, #fbbf24)' }} />, items: govKpis },
          ].map(cat => (
            <div key={cat.title} className="glass" style={{ padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                {cat.icon}
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>{cat.title} KPIs</span>
                <span style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginLeft: 'auto' }}>
                  {cat.items.filter(k => k.on_track).length}/{cat.items.length} on track
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {cat.items.map(kpi => (
                  <KPIRow key={kpi.kpi_id} kpi={kpi} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ─── CARBON TAB ─── */}
      {activeTab === 'carbon' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Carbon Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
            <StatCard label="Total Emissions" value={carbon.total.toLocaleString()} unit={carbon.unit} icon={<Factory size={16} />} />
            <StatCard label="Scope 1" value={carbon.scope1.toLocaleString()} unit={carbon.unit} icon={<Zap size={16} />} color="#f97316" />
            <StatCard label="Scope 2" value={carbon.scope2.toLocaleString()} unit={carbon.unit} icon={<Zap size={16} />} color="#38bdf8" />
            <StatCard label="Scope 3" value={carbon.scope3.toLocaleString()} unit={carbon.unit} icon={<Zap size={16} />} color="#a78bfa" />
            <StatCard label="Intensity" value={carbon.intensity.toFixed(1)} unit="tCO2e/M" icon={<BarChart3 size={16} />} />
          </div>

          {/* Charts */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="glass" style={{ padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)', marginBottom: 12 }}>Emissions by Scope</div>
              <ReactECharts option={carbonBarOption} style={{ height: 300 }} opts={{ renderer: 'svg' }} />
            </div>
            <div className="glass" style={{ padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)', marginBottom: 12 }}>Scope Distribution</div>
              <ReactECharts option={scopeDonutOption} style={{ height: 300 }} opts={{ renderer: 'svg' }} />
            </div>
          </div>

          {/* Reduction Target */}
          <div className="glass" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <Target size={16} style={{ color: 'var(--emerald, #34d399)' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>Reduction Target</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <div style={{ padding: 16, borderRadius: 8, background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.2)' }}>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase' }}>Current Emissions</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--heading, #e2e8f0)', fontFamily: 'JetBrains Mono, monospace', marginTop: 4 }}>
                  {carbon.total.toLocaleString()}
                </div>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>{carbon.unit}</div>
              </div>
              <div style={{ padding: 16, borderRadius: 8, background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.2)' }}>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase' }}>Target ({carbon.target_year})</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--sky, #38bdf8)', fontFamily: 'JetBrains Mono, monospace', marginTop: 4 }}>
                  {carbon.reduction_target.toLocaleString()}
                </div>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>{carbon.unit} (45% reduction)</div>
              </div>
              <div style={{ padding: 16, borderRadius: 8, background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.2)' }}>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase' }}>Gap to Close</div>
                <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--amber, #fbbf24)', fontFamily: 'JetBrains Mono, monospace', marginTop: 4 }}>
                  {(carbon.total - carbon.reduction_target).toLocaleString()}
                </div>
                <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>{carbon.unit} remaining reduction</div>
              </div>
            </div>
            {/* Gap progress bar */}
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginBottom: 6 }}>
                <span>Progress toward {carbon.target_year} target</span>
                <span>{((1 - carbon.total / (carbon.total * 1.05 || 1)) * 100 / 45 * 100).toFixed(0)}% achieved</span>
              </div>
              <div style={{ height: 8, borderRadius: 4, background: 'rgba(148,163,184,0.1)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 4,
                  width: `${Math.min((carbon.yoy_change_pct < 0 ? Math.abs(carbon.yoy_change_pct) / 45 * 100 : 2), 100)}%`,
                  background: 'linear-gradient(90deg, var(--emerald, #34d399), var(--sky, #38bdf8))',
                  transition: 'width 1s ease',
                }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── RECOMMENDATIONS TAB ─── */}
      {activeTab === 'recommendations' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <SummaryCard icon={<AlertTriangle size={16} />} label="Critical" value={recommendations.filter(r => r.priority === 'critical').length} color="var(--rose, #fb7185)" />
            <SummaryCard icon={<TrendingUp size={16} />} label="High Priority" value={recommendations.filter(r => r.priority === 'high').length} color="var(--amber, #fbbf24)" />
            <SummaryCard icon={<Target size={16} />} label="Medium" value={recommendations.filter(r => r.priority === 'medium').length} color="var(--sky, #38bdf8)" />
            <SummaryCard icon={<Leaf size={16} />} label="Total Actions" value={recommendations.length} color="var(--emerald, #34d399)" />
          </div>

          {recommendations.map((rec, i) => {
            const ps = priorityStyle(rec.priority);
            return (
              <div key={i} className="glass" style={{
                padding: 20,
                borderLeft: `3px solid ${ps.text}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  {categoryIcon(rec.category)}
                  <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>{rec.title}</span>
                  <span style={{
                    padding: '2px 8px', borderRadius: 4, fontSize: 9,
                    fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase',
                    fontWeight: 700, letterSpacing: '0.08em',
                    background: ps.bg, color: ps.text, border: `1px solid ${ps.border}`,
                  }}>{rec.priority}</span>
                  <span style={{
                    marginLeft: 'auto', fontSize: 10, color: 'var(--dim, #64748b)',
                    fontFamily: 'JetBrains Mono, monospace',
                  }}>{rec.framework_ref}</span>
                </div>
                <p style={{ fontSize: 12, color: 'var(--text, #cbd5e1)', lineHeight: 1.6, margin: 0, marginBottom: 10 }}>
                  {rec.description}
                </p>
                <div style={{ fontSize: 12, color: 'var(--emerald, #34d399)', fontStyle: 'italic', marginBottom: 10 }}>
                  {rec.impact}
                </div>
                <div style={{ display: 'flex', gap: 24, fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: 'var(--dim, #64748b)' }}>
                  <span>Timeline: <b style={{ color: 'var(--heading, #e2e8f0)' }}>{rec.timeline}</b></span>
                  <span>Est. Cost: <b style={{ color: 'var(--heading, #e2e8f0)' }}>{rec.estimated_cost}</b></span>
                  <span style={{ textTransform: 'capitalize' }}>Category: <b style={{ color: 'var(--heading, #e2e8f0)' }}>{rec.category}</b></span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Reusable sub-components ─── */

function StatBox({ label, value, unit, color }: { label: string; value: string; unit: string; color?: string }) {
  return (
    <div style={{
      padding: 10, borderRadius: 6,
      background: 'rgba(148,163,184,0.04)',
      border: '1px solid rgba(148,163,184,0.08)',
    }}>
      <div style={{ fontSize: 9, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: color || 'var(--heading, #e2e8f0)', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>
        {value}
      </div>
      <div style={{ fontSize: 9, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>{unit}</div>
    </div>
  );
}

function StatCard({ label, value, unit, icon, color }: { label: string; value: string; unit: string; icon: React.ReactNode; color?: string }) {
  return (
    <div className="glass" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ color: color || 'var(--dim, #64748b)' }}>{icon}</span>
        <span style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--heading, #e2e8f0)', fontFamily: 'JetBrains Mono, monospace' }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>{unit}</div>
    </div>
  );
}

function SummaryCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="glass" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{ color }}>{icon}</span>
        <span style={{ fontSize: 10, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace' }}>{value}</div>
    </div>
  );
}

function KPIRow({ kpi }: { kpi: KPI }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 3fr 80px',
      gap: 12, alignItems: 'center',
      padding: '10px 12px', borderRadius: 6,
      background: 'rgba(148,163,184,0.03)',
      border: '1px solid rgba(148,163,184,0.06)',
    }}>
      {/* Name + framework */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--heading, #e2e8f0)' }}>{kpi.name}</div>
        <div style={{ fontSize: 9, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace' }}>{kpi.framework_ref}</div>
      </div>

      {/* Value */}
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, fontWeight: 600, color: 'var(--heading, #e2e8f0)' }}>
        {kpi.value} <span style={{ fontSize: 9, fontWeight: 400, color: 'var(--dim, #64748b)' }}>{kpi.unit}</span>
      </div>

      {/* Target */}
      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: 'var(--dim, #64748b)' }}>
        Target: {kpi.target}
      </div>

      {/* Progress bar */}
      <div>
        <div style={{ height: 6, borderRadius: 3, background: 'rgba(148,163,184,0.1)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 3,
            width: `${Math.min(kpi.progress_pct, 100)}%`,
            background: kpi.on_track ? 'var(--emerald, #34d399)' : kpi.progress_pct > 50 ? 'var(--amber, #fbbf24)' : 'var(--rose, #fb7185)',
            transition: 'width 0.8s ease',
          }} />
        </div>
        <div style={{ fontSize: 9, color: 'var(--dim, #64748b)', fontFamily: 'JetBrains Mono, monospace', marginTop: 2 }}>
          {kpi.progress_pct.toFixed(0)}%
        </div>
      </div>

      {/* Trend + status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
        {trendIcon(kpi.trend)}
        {kpi.on_track
          ? <CheckCircle2 size={14} style={{ color: 'var(--emerald, #34d399)' }} />
          : <AlertTriangle size={14} style={{ color: 'var(--amber, #fbbf24)' }} />}
      </div>
    </div>
  );
}
