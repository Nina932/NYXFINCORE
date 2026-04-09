/**
 * AnalyticsCenterPage — Enterprise analytics showcase with all advanced visualizations
 * Treemap, Sunburst, Heatmap, Waterfall, Sankey, Pivot Table, Radar, Funnel, DrilldownBar
 */
import { useState, useMemo } from 'react';
import {
  BarChart3, PieChart, Grid3X3, Droplets, GitBranch as FlowIcon,
  TrendingUp, Filter, Layers, Activity, Target,
} from 'lucide-react';
import {
  TreemapChart, SunburstChart, HeatmapChart, WaterfallChart,
  SankeyChart, RadarChart, FunnelChart, DrilldownBarChart, GaugeChart,
} from '../components/EnterpriseCharts';
import { PivotTable } from '../components/PivotTable';
import type { PivotConfig } from '../components/PivotTable';

/* ─── Tab Definitions ─── */
const TABS = [
  { id: 'treemap', label: 'Treemap', icon: Grid3X3 },
  { id: 'sunburst', label: 'Sunburst', icon: PieChart },
  { id: 'heatmap', label: 'Heatmap', icon: Droplets },
  { id: 'waterfall', label: 'Waterfall', icon: BarChart3 },
  { id: 'sankey', label: 'Flow', icon: FlowIcon },
  { id: 'radar', label: 'Radar', icon: Target },
  { id: 'pivot', label: 'Pivot', icon: Layers },
  { id: 'funnel', label: 'Funnel', icon: Filter },
] as const;

type TabId = typeof TABS[number]['id'];

/* ─── Demo Data ─── */
const TREEMAP_DATA = [
  {
    name: 'Revenue',
    value: 69_000_000,
    children: [
      { name: 'Fuel Distribution', value: 42_500_000, children: [
        { name: 'Diesel', value: 22_000_000 },
        { name: 'Gasoline', value: 15_500_000 },
        { name: 'LPG', value: 5_000_000 },
      ]},
      { name: 'Trading', value: 18_200_000, children: [
        { name: 'Crude Oil', value: 12_000_000 },
        { name: 'Refined Products', value: 6_200_000 },
      ]},
      { name: 'Logistics', value: 8_300_000, children: [
        { name: 'Domestic Transport', value: 5_100_000 },
        { name: 'Cross-border', value: 3_200_000 },
      ]},
    ]
  },
  {
    name: 'Operating Costs',
    value: 50_500_000,
    children: [
      { name: 'COGS', value: 38_000_000, children: [
        { name: 'Fuel Purchase', value: 30_000_000 },
        { name: 'Storage', value: 5_000_000 },
        { name: 'Insurance', value: 3_000_000 },
      ]},
      { name: 'SG&A', value: 12_500_000, children: [
        { name: 'Salaries', value: 7_000_000 },
        { name: 'Marketing', value: 2_500_000 },
        { name: 'Admin', value: 3_000_000 },
      ]},
    ]
  }
];

const SUNBURST_DATA = [
  { name: 'Assets', value: 85_800_000, children: [
    { name: 'Current', value: 38_000_000, children: [
      { name: 'Cash', value: 8_400_000 },
      { name: 'Receivables', value: 12_600_000 },
      { name: 'Inventory', value: 15_200_000 },
      { name: 'Prepaid', value: 1_800_000 },
    ]},
    { name: 'Non-Current', value: 47_800_000, children: [
      { name: 'PP&E', value: 34_000_000 },
      { name: 'Intangibles', value: 5_600_000 },
      { name: 'Investments', value: 8_200_000 },
    ]},
  ]},
  { name: 'Liabilities', value: 46_000_000, children: [
    { name: 'Current', value: 19_400_000, children: [
      { name: 'Payables', value: 9_800_000 },
      { name: 'Short Debt', value: 6_200_000 },
      { name: 'Accrued', value: 3_400_000 },
    ]},
    { name: 'Non-Current', value: 26_600_000, children: [
      { name: 'Long Debt', value: 22_000_000 },
      { name: 'Deferred Tax', value: 4_600_000 },
    ]},
  ]},
  { name: 'Equity', value: 40_000_000, children: [
    { name: 'Share Capital', value: 15_000_000 },
    { name: 'Retained', value: 20_800_000 },
    { name: 'Reserves', value: 4_200_000 },
  ]}
];

const HEATMAP_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const HEATMAP_METRICS = ['Revenue', 'COGS', 'Gross Profit', 'OPEX', 'EBITDA', 'Net Income'];
const HEATMAP_DATA: [number, number, number][] = [];
HEATMAP_MONTHS.forEach((_, mi) => {
  HEATMAP_METRICS.forEach((_, ri) => {
    const base = [85, 70, 60, 45, 55, 40][ri];
    const seasonal = Math.sin((mi / 12) * Math.PI * 2) * 15;
    HEATMAP_DATA.push([mi, ri, Math.round(base + seasonal + (Math.random() - 0.5) * 20)]);
  });
});

const WATERFALL_DATA = [
  { name: 'Revenue', value: 69_000_000, isTotal: false },
  { name: 'COGS', value: -38_000_000 },
  { name: 'Gross Profit', value: 31_000_000, isTotal: true },
  { name: 'SG&A', value: -12_500_000 },
  { name: 'R&D', value: -3_200_000 },
  { name: 'Depreciation', value: -4_800_000 },
  { name: 'Other Income', value: 1_200_000 },
  { name: 'EBIT', value: 11_700_000, isTotal: true },
  { name: 'Interest', value: -2_400_000 },
  { name: 'Tax', value: -2_100_000 },
  { name: 'Net Income', value: 7_200_000, isTotal: true },
];

const SANKEY_NODES = [
  { name: 'Fuel Sales' }, { name: 'Trading Revenue' }, { name: 'Logistics' },
  { name: 'Total Revenue' }, { name: 'COGS' }, { name: 'Gross Profit' },
  { name: 'Operating Expenses' }, { name: 'EBITDA' }, { name: 'D&A' },
  { name: 'Interest' }, { name: 'Tax' }, { name: 'Net Income' },
];
const SANKEY_LINKS = [
  { source: 'Fuel Sales', target: 'Total Revenue', value: 42_500 },
  { source: 'Trading Revenue', target: 'Total Revenue', value: 18_200 },
  { source: 'Logistics', target: 'Total Revenue', value: 8_300 },
  { source: 'Total Revenue', target: 'COGS', value: 38_000 },
  { source: 'Total Revenue', target: 'Gross Profit', value: 31_000 },
  { source: 'Gross Profit', target: 'Operating Expenses', value: 15_700 },
  { source: 'Gross Profit', target: 'EBITDA', value: 15_300 },
  { source: 'EBITDA', target: 'D&A', value: 4_800 },
  { source: 'EBITDA', target: 'Interest', value: 2_400 },
  { source: 'EBITDA', target: 'Tax', value: 2_100 },
  { source: 'EBITDA', target: 'Net Income', value: 6_000 },
];

const RADAR_INDICATORS = [
  { name: 'Profitability', max: 100 },
  { name: 'Liquidity', max: 100 },
  { name: 'Solvency', max: 100 },
  { name: 'Efficiency', max: 100 },
  { name: 'Growth', max: 100 },
  { name: 'Risk Mgmt', max: 100 },
];
const RADAR_SERIES = [
  { name: 'Current Period', values: [72, 68, 55, 80, 64, 71], color: '#00D8FF' },
  { name: 'Prior Period', values: [65, 72, 60, 73, 58, 68], color: '#9F7AEA' },
  { name: 'Industry Avg', values: [60, 65, 58, 62, 50, 55], color: '#48BB78' },
];

const FUNNEL_DATA = [
  { name: 'Gross Revenue', value: 69_000_000 },
  { name: 'Net Revenue', value: 65_500_000 },
  { name: 'Gross Profit', value: 31_000_000 },
  { name: 'Operating Income', value: 15_300_000 },
  { name: 'EBIT', value: 11_700_000 },
  { name: 'Net Income', value: 7_200_000 },
];

/* ─── Pivot data: Monthly P&L by segment ─── */
const SEGMENTS = ['Fuel Distribution', 'Trading', 'Logistics'];
const PIVOT_DATA: Record<string, any>[] = [];
HEATMAP_MONTHS.forEach(month => {
  SEGMENTS.forEach(segment => {
    const baseRev = segment === 'Fuel Distribution' ? 3_500_000 : segment === 'Trading' ? 1_500_000 : 700_000;
    const baseCost = baseRev * (0.55 + Math.random() * 0.1);
    PIVOT_DATA.push({
      Month: month,
      Segment: segment,
      Revenue: Math.round(baseRev * (0.9 + Math.random() * 0.2)),
      COGS: Math.round(baseCost),
      'Gross Profit': Math.round(baseRev - baseCost),
    });
  });
});

const PIVOT_CONFIG: PivotConfig = {
  rows: ['Segment'],
  columns: ['Month'],
  values: ['Revenue'],
  aggregation: 'sum',
};

/* ═══════════════════════════════════════════════ */

export default function AnalyticsCenterPage() {
  const [activeTab, setActiveTab] = useState<TabId>('treemap');
  const [pivotMetric, setPivotMetric] = useState<string>('Revenue');

  const currentPivotConfig = useMemo(() => ({
    ...PIVOT_CONFIG,
    values: [pivotMetric],
  }), [pivotMetric]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={20} style={{ color: 'var(--sky)' }} />
          Enterprise Analytics Center
        </h1>
        <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
          Advanced visualization suite — Treemaps, Sunbursts, Heatmaps, Waterfalls, Sankey, Pivot Tables
        </p>
      </div>

      {/* Tab Bar */}
      <div style={{
        display: 'flex', gap: 2, background: 'var(--bg2)', borderRadius: 8, padding: 3,
        border: '1px solid var(--b1)', overflow: 'auto',
      }}>
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px',
                fontSize: 11, fontWeight: isActive ? 600 : 400, fontFamily: "var(--mono)",
                color: isActive ? 'var(--sky)' : 'var(--muted)',
                background: isActive ? 'rgba(0,216,255,0.08)' : 'transparent',
                border: isActive ? '1px solid rgba(0,216,255,0.2)' : '1px solid transparent',
                borderRadius: 6, cursor: 'pointer', whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ minHeight: 500 }}>
        {activeTab === 'treemap' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Revenue & Cost Treemap</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Click to drill down into segments. Breadcrumb navigation at top.</div>
              </div>
              <TreemapChart data={TREEMAP_DATA} height="420px" />
            </div>
          </div>
        )}

        {activeTab === 'sunburst' && (
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Balance Sheet Composition</div>
              <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Radial hierarchy: Assets, Liabilities, Equity with sub-categories</div>
            </div>
            <SunburstChart data={SUNBURST_DATA} height="480px" />
          </div>
        )}

        {activeTab === 'heatmap' && (
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Monthly Performance Heatmap</div>
              <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Performance index (0-100) across metrics and months. Bright = strong.</div>
            </div>
            <HeatmapChart
              data={HEATMAP_DATA}
              xLabels={HEATMAP_MONTHS}
              yLabels={HEATMAP_METRICS}
              height="380px"
              min={20}
              max={100}
              colorRange={['#1A0E2E', '#00D8FF']}
            />
          </div>
        )}

        {activeTab === 'waterfall' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Income Statement Waterfall (Bridge)</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Revenue-to-Net-Income bridge showing each P&L component</div>
              </div>
              <WaterfallChart data={WATERFALL_DATA} height="380px" />
            </div>
            {/* KPI Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              {[
                { label: 'Gross Margin', value: '44.9%', color: 'var(--emerald)' },
                { label: 'Operating Margin', value: '22.2%', color: 'var(--sky)' },
                { label: 'EBIT Margin', value: '17.0%', color: 'var(--violet)' },
                { label: 'Net Margin', value: '10.4%', color: 'var(--gold)' },
              ].map(kpi => (
                <div key={kpi.label} className="glass" style={{ padding: 14, textAlign: 'center' }}>
                  <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)', fontFamily: "var(--mono)" }}>{kpi.label}</div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: kpi.color, fontFamily: "var(--mono)", marginTop: 4 }}>{kpi.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'sankey' && (
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Revenue Flow — Sankey Diagram</div>
              <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Revenue sources through cost allocations to net income (values in thousands)</div>
            </div>
            <SankeyChart nodes={SANKEY_NODES} links={SANKEY_LINKS} height="450px" />
          </div>
        )}

        {activeTab === 'radar' && (
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Financial Health Radar</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>6-dimension analysis: Current vs Prior vs Industry</div>
              </div>
              <RadarChart indicators={RADAR_INDICATORS} series={RADAR_SERIES} height="400px" />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div className="glass" style={{ padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 8 }}>Overall Health</div>
                <GaugeChart value={72} title="Score" height="180px" />
              </div>
              <div className="glass" style={{ padding: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 12 }}>Dimension Scores</div>
                {RADAR_INDICATORS.map((ind, i) => {
                  const val = RADAR_SERIES[0].values[i];
                  return (
                    <div key={ind.name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)', width: 80, fontFamily: "var(--mono)" }}>{ind.name}</span>
                      <div style={{ flex: 1, height: 6, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${val}%`, height: '100%', background: val >= 70 ? '#48BB78' : val >= 50 ? '#ED8936' : '#F56565', borderRadius: 3, transition: 'width 0.8s ease' }} />
                      </div>
                      <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text)', fontFamily: "var(--mono)", width: 28, textAlign: 'right' }}>{val}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'pivot' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* Pivot metric selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: "var(--mono)" }}>METRIC:</span>
              {['Revenue', 'COGS', 'Gross Profit'].map(m => (
                <button
                  key={m}
                  onClick={() => setPivotMetric(m)}
                  style={{
                    padding: '4px 12px', fontSize: 10, fontFamily: "var(--mono)",
                    background: pivotMetric === m ? 'rgba(0,216,255,0.12)' : 'var(--bg3)',
                    border: `1px solid ${pivotMetric === m ? 'rgba(0,216,255,0.3)' : 'var(--b1)'}`,
                    borderRadius: 4, color: pivotMetric === m ? 'var(--sky)' : 'var(--muted)',
                    cursor: 'pointer',
                  }}
                >
                  {m}
                </button>
              ))}
            </div>
            <PivotTable
              data={PIVOT_DATA}
              config={currentPivotConfig}
              title={`${pivotMetric} by Segment × Month`}
            />
          </div>
        )}

        {activeTab === 'funnel' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>P&L Funnel — Revenue to Net Income</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Conversion efficiency at each P&L stage</div>
              </div>
              <FunnelChart data={FUNNEL_DATA} height="380px" />
            </div>
            <div className="glass" style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Segment Revenue Breakdown</div>
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>Revenue contribution by business segment</div>
              </div>
              <DrilldownBarChart
                data={[
                  { name: 'Fuel Distribution', value: 42_500_000 },
                  { name: 'Trading', value: 18_200_000 },
                  { name: 'Logistics', value: 8_300_000 },
                ]}
                height="380px"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
