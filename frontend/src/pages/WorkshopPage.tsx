import { useState, useEffect, useCallback, useRef } from 'react';
import {
  LayoutGrid, Plus, Save, Share2, Trash2, Settings, BarChart3, Activity,
  Table2, Hash, AlertTriangle, Loader2, GripVertical, Link2, Rows3,
  Search, Play, Clock, Database, Filter, ChevronDown, ChevronRight,
  Bookmark, Layers, TrendingUp, Grid3X3, Sliders, Zap, FileBarChart,
  GitCompare, Target, PieChart, ArrowRight,
} from 'lucide-react';
import WorkshopTour, { WatchDemoButton } from '../components/WorkshopTour';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';

const AnyGridLayout = GridLayout as any;

export interface GridItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  maxW?: number;
  minH?: number;
  maxH?: number;
  static?: boolean;
  isDraggable?: boolean;
  isResizable?: boolean;
}
import { useStore } from '../store/useStore';
import { t } from '../i18n/translations';
import MetricCardWidget from '../components/widgets/MetricCardWidget';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, Cell, LineChart, Line, PieChart as RePieChart, Pie,
} from 'recharts';

/* ─── Palette ─── */
const C = {
  sky: '#3B82F6', blue: '#2563EB', violet: '#8B5CF6',
  emerald: '#10B981', amber: '#F59E0B', rose: '#EF4444',
  teal: '#14B8A6', gold: '#EAB308', cerulean: '#06B6D4',
};

function fmt(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '\u2014';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e3).toFixed(0)}K`;
  return `\u20BE${n.toFixed(0)}`;
}

/* ─── Types ─── */
interface WidgetConfig {
  id: string;
  type: 'metric' | 'chart' | 'table' | 'kpi_list' | 'alert_feed' | 'pivot';
  dataSource: string;
  label: string;
  props: Record<string, unknown>;
}

interface DashboardLayout {
  id: string;
  name: string;
  slug: string;
  grid: GridItem[];
  widgets: WidgetConfig[];
  is_shared?: boolean;
}

interface SavedQuery {
  id: string;
  name: string;
  description: string;
  dataSource: string;
  metric: string;
  periods: string[];
  chartType: 'bar' | 'line' | 'table' | 'kpi';
  createdAt: string;
  lastRun: string;
  result?: any;
}

interface TemplateConfig {
  id: string;
  name: string;
  description: string;
  icon: any;
  color: string;
  category: string;
}

const WIDGET_TYPES = [
  { type: 'metric' as const, label: 'Metric Card', icon: Hash, defaultW: 3, defaultH: 4, desc: 'Single KPI value with sparkline' },
  { type: 'chart' as const, label: 'Chart', icon: BarChart3, defaultW: 6, defaultH: 5, desc: 'Bar/Line/Area chart' },
  { type: 'kpi_list' as const, label: 'KPI List', icon: Activity, defaultW: 4, defaultH: 6, desc: 'List of KPI status indicators' },
  { type: 'table' as const, label: 'Data Table', icon: Table2, defaultW: 6, defaultH: 6, desc: 'Tabular data from warehouse' },
  { type: 'pivot' as const, label: 'Pivot Table', icon: Rows3, defaultW: 8, defaultH: 7, desc: 'Cross-tab analysis with row/col dimensions' },
  { type: 'alert_feed' as const, label: 'Alert Feed', icon: AlertTriangle, defaultW: 4, defaultH: 5, desc: 'Live alert stream' },
];

const DATA_SOURCES = [
  { id: 'pnl', label: 'Profit & Loss', icon: FileBarChart },
  { id: 'revenue', label: 'Revenue', icon: TrendingUp },
  { id: 'cogs', label: 'Cost of Goods Sold', icon: Layers },
  { id: 'balance_sheet', label: 'Balance Sheet', icon: Grid3X3 },
  { id: 'knowledge_graph', label: 'Knowledge Graph', icon: Database },
];

const METRICS: Record<string, { id: string; label: string }[]> = {
  pnl: [
    { id: 'revenue', label: 'Revenue' },
    { id: 'cogs', label: 'COGS' },
    { id: 'gross_profit', label: 'Gross Profit' },
    { id: 'ebitda', label: 'EBITDA' },
    { id: 'net_profit', label: 'Net Profit' },
    { id: 'selling_expenses', label: 'Selling Expenses' },
    { id: 'admin_expenses', label: 'Admin Expenses' },
    { id: 'depreciation', label: 'Depreciation' },
  ],
  revenue: [
    { id: 'revenue', label: 'Total Revenue' },
    { id: 'revenue_wholesale', label: 'Wholesale Revenue' },
    { id: 'revenue_retail', label: 'Retail Revenue' },
    { id: 'revenue_other', label: 'Other Revenue' },
  ],
  cogs: [
    { id: 'cogs', label: 'Total COGS' },
    { id: 'cogs_wholesale', label: 'Wholesale COGS' },
    { id: 'cogs_retail', label: 'Retail COGS' },
  ],
  balance_sheet: [
    { id: 'total_assets', label: 'Total Assets' },
    { id: 'total_liabilities', label: 'Total Liabilities' },
    { id: 'total_equity', label: 'Total Equity' },
    { id: 'cash', label: 'Cash & Equivalents' },
  ],
  knowledge_graph: [
    { id: 'entity_count', label: 'Entity Count' },
    { id: 'ratios', label: 'Financial Ratios' },
    { id: 'risks', label: 'Risk Signals' },
  ],
};

const TEMPLATES: TemplateConfig[] = [
  { id: 'revenue_waterfall', name: 'Revenue Waterfall', description: 'Revenue breakdown as a waterfall chart showing contribution of each segment', icon: BarChart3, color: C.sky, category: 'Revenue' },
  { id: 'profitability_matrix', name: 'Profitability Matrix', description: 'Products vs margins heatmap highlighting high and low performers', icon: Grid3X3, color: C.emerald, category: 'Profitability' },
  { id: 'period_comparison', name: 'Period Comparison', description: 'Side-by-side P&L for two periods with variance analysis', icon: GitCompare, color: C.violet, category: 'Comparison' },
  { id: 'kpi_dashboard', name: 'KPI Dashboard', description: 'Custom KPI cards with configurable thresholds and targets', icon: Target, color: C.amber, category: 'Monitoring' },
];

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
const glass: React.CSSProperties = { background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 10, padding: 20 };

/* ─── localStorage helpers ─── */
function loadSavedQueries(): SavedQuery[] {
  try { return JSON.parse(localStorage.getItem('workshop_queries') || '[]'); } catch { return []; }
}
function saveSavedQueries(queries: SavedQuery[]) {
  localStorage.setItem('workshop_queries', JSON.stringify(queries));
}

/* ═══════════════════════════════════════════════════════════════════
   WORKSHOP PAGE
   ═══════════════════════════════════════════════════════════════════ */
export default function WorkshopPage() {
  const { pnl, balance_sheet, company, period } = useStore();
  const [activeTab, setActiveTab] = useState<'builder' | 'query' | 'saved' | 'templates'>('builder');

  /* ─── Dashboard Builder state (existing) ─── */
  const [layout, setLayout] = useState<GridItem[]>([]);
  const [widgets, setWidgets] = useState<WidgetConfig[]>([]);
  const [dashName, setDashName] = useState('My Dashboard');
  const [dashId, setDashId] = useState<string | null>(null);
  const [selectedWidget, setSelectedWidget] = useState<string | null>(null);
  const [dataSources, setDataSources] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [widgetData, setWidgetData] = useState<Record<string, any>>({});
  const [savedLayouts, setSavedLayouts] = useState<DashboardLayout[]>([]);
  const [draggingType, setDraggingType] = useState<string | null>(null);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  /* ─── Query Builder state ─── */
  const [qDataSource, setQDataSource] = useState('pnl');
  const [qMetric, setQMetric] = useState('revenue');
  const [qChartType, setQChartType] = useState<'bar' | 'line' | 'table' | 'kpi'>('bar');
  const [qName, setQName] = useState('');
  const [qResult, setQResult] = useState<any>(null);
  const [qBuilding, setQBuilding] = useState(false);

  /* ─── Saved Queries state ─── */
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>(loadSavedQueries());

  /* ─── Template state ─── */
  const [activeTemplate, setActiveTemplate] = useState<string | null>(null);
  const [templateData, setTemplateData] = useState<any>(null);

  /* ─── Tour state ─── */
  const [tourActive, setTourActive] = useState(false);

  // Fetch data sources for builder
  useEffect(() => {
    fetch('/api/workshop/datasources')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.datasources) setDataSources(d.datasources); })
      .catch(() => {});
    fetch('/api/workshop/layouts')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.layouts) setSavedLayouts(d.layouts); })
      .catch(() => {});
  }, []);

  // Fetch widget data when widgets change
  useEffect(() => {
    widgets.forEach(w => {
      if (!w.dataSource) return;
      const [type, metric] = w.dataSource.split(':');
      if (type === 'metric' && pnl) {
        const val = (pnl as any)[metric] ?? 0;
        const rev = (pnl as any).revenue ?? 1;
        let value = val;
        if (metric === 'gross_margin') value = ((pnl as any).gross_profit ?? 0) / rev * 100;
        else if (metric === 'net_margin') value = ((pnl as any).net_profit ?? 0) / rev * 100;
        setWidgetData(prev => ({ ...prev, [w.id]: { value, type: 'single_value' } }));
      } else if (type === 'ontology' || type === 'warehouse' || type === 'objectset') {
        fetch('/api/workshop/datasources/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_id: w.dataSource, type }),
        })
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) setWidgetData(prev => ({ ...prev, [w.id]: d })); })
          .catch(() => {});
      }
    });
  }, [widgets, pnl]);

  const addWidget = (widgetType: typeof WIDGET_TYPES[0]) => {
    const id = `w-${Date.now()}`;
    const newWidget: WidgetConfig = {
      id,
      type: widgetType.type,
      dataSource: widgetType.type === 'metric' ? 'metric:revenue' : '',
      label: widgetType.label,
      props: {},
    };
    const newLayoutItem: GridItem = {
      i: id,
      x: (layout.length * 3) % 12,
      y: Infinity,
      w: widgetType.defaultW,
      h: widgetType.defaultH,
    };
    setWidgets(prev => [...prev, newWidget]);
    setLayout(prev => [...prev, newLayoutItem]);
    setSelectedWidget(id);
  };

  const removeWidget = (id: string) => {
    setWidgets(prev => prev.filter(w => w.id !== id));
    setLayout(prev => prev.filter(l => l.i !== id));
    if (selectedWidget === id) setSelectedWidget(null);
  };

  const updateWidgetConfig = (id: string, patch: Partial<WidgetConfig>) => {
    setWidgets(prev => prev.map(w => w.id === id ? { ...w, ...patch } : w));
  };

  const saveDashboard = async () => {
    setSaving(true);
    try {
      const method = dashId ? 'PUT' : 'POST';
      const url = dashId ? `/api/workshop/layouts/${dashId}` : '/api/workshop/layouts';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: dashName, grid: layout, widgets }),
      });
      const data = await res.json();
      if (data.id) setDashId(data.id);
      fetch('/api/workshop/layouts')
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.layouts) setSavedLayouts(d.layouts); });
    } catch {}
    setSaving(false);
  };

  const loadDashboard = async (l: DashboardLayout) => {
    setDashId(l.id);
    setDashName(l.name);
    setLayout(l.grid || []);
    setWidgets(l.widgets || []);
    setSelectedWidget(null);
    setShareUrl(null);
  };

  const shareDashboard = async () => {
    if (!dashId) { await saveDashboard(); }
    const id = dashId;
    if (!id) return;
    try {
      await fetch(`/api/workshop/layouts/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_shared: true }),
      });
      const url = `${window.location.origin}/workshop?layout=${id}`;
      setShareUrl(url);
      navigator.clipboard?.writeText(url);
    } catch {}
  };

  // Load shared layout from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const layoutId = params.get('layout');
    if (layoutId) {
      fetch(`/api/workshop/layouts/${layoutId}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.id) loadDashboard(d); })
        .catch(() => {});
    }
  }, []);

  // Handle drag from palette
  const handlePaletteDragStart = (e: React.DragEvent, widgetType: typeof WIDGET_TYPES[0]) => {
    e.dataTransfer.setData('widget-type', JSON.stringify(widgetType));
    e.dataTransfer.effectAllowed = 'copy';
    setDraggingType(widgetType.type);
  };

  const handleCanvasDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const data = e.dataTransfer.getData('widget-type');
    if (!data) return;
    try {
      const widgetType = JSON.parse(data);
      addWidget(widgetType);
    } catch {}
    setDraggingType(null);
  };

  const handleCanvasDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const selectedW = widgets.find(w => w.id === selectedWidget);
  const selectedDs = dataSources.find(d => d.id === selectedW?.dataSource);

  /* ─── Query Builder logic ─── */
  const buildQuery = () => {
    setQBuilding(true);
    const p = pnl || {} as any;
    const bs = balance_sheet || {} as any;

    // Extract the metric value
    let value: number | null = null;
    if (qDataSource === 'pnl' || qDataSource === 'revenue' || qDataSource === 'cogs') {
      value = (p as any)[qMetric] ?? null;
    } else if (qDataSource === 'balance_sheet') {
      value = (bs as any)[qMetric] ?? null;
    }

    // Build result data
    const rev = p.revenue || 1;
    const result: any = {
      metric: qMetric,
      value: value ?? 0,
      formatted: fmt(value),
      period: period || 'current',
      dataSource: qDataSource,
      pctOfRevenue: rev > 0 && value != null ? ((Math.abs(value) / rev) * 100).toFixed(1) + '%' : null,
      timestamp: new Date().toISOString(),
    };

    // Generate chart data for bar/line
    if (qChartType === 'bar' || qChartType === 'line') {
      const metrics = METRICS[qDataSource] || [];
      result.chartData = metrics.map(m => {
        const val = qDataSource === 'balance_sheet' ? ((bs as any)[m.id] ?? 0) : ((p as any)[m.id] ?? 0);
        return { name: m.label, value: Math.abs(val), raw: val, fill: val >= 0 ? C.sky : C.rose };
      }).filter((d: any) => d.value > 0);
    }

    // Generate table data
    if (qChartType === 'table') {
      const metrics = METRICS[qDataSource] || [];
      result.tableData = metrics.map(m => {
        const val = qDataSource === 'balance_sheet' ? ((bs as any)[m.id] ?? 0) : ((p as any)[m.id] ?? 0);
        return { metric: m.label, value: val, formatted: fmt(val), pctOfRevenue: rev > 0 ? ((Math.abs(val) / rev) * 100).toFixed(1) + '%' : '-' };
      });
    }

    setTimeout(() => {
      setQResult(result);
      setQBuilding(false);
    }, 300);
  };

  const saveQuery = () => {
    if (!qName.trim()) return;
    const query: SavedQuery = {
      id: `q-${Date.now()}`,
      name: qName,
      description: `${qDataSource} / ${qMetric} / ${qChartType}`,
      dataSource: qDataSource,
      metric: qMetric,
      periods: [period || 'current'],
      chartType: qChartType,
      createdAt: new Date().toISOString(),
      lastRun: new Date().toISOString(),
      result: qResult,
    };
    const updated = [...savedQueries, query];
    setSavedQueries(updated);
    saveSavedQueries(updated);
    setQName('');
  };

  const runSavedQuery = (q: SavedQuery) => {
    setQDataSource(q.dataSource);
    setQMetric(q.metric);
    setQChartType(q.chartType);
    setActiveTab('query');
    setTimeout(() => buildQuery(), 100);
    // Update lastRun
    const updated = savedQueries.map(sq => sq.id === q.id ? { ...sq, lastRun: new Date().toISOString() } : sq);
    setSavedQueries(updated);
    saveSavedQueries(updated);
  };

  const deleteSavedQuery = (id: string) => {
    const updated = savedQueries.filter(q => q.id !== id);
    setSavedQueries(updated);
    saveSavedQueries(updated);
  };

  /* ─── Template logic ─── */
  const runTemplate = (templateId: string) => {
    setActiveTemplate(templateId);
    const p = pnl || {} as any;
    const bs = balance_sheet || {} as any;
    const rev = p.revenue || 0;
    const cogs = Math.abs(p.cogs || 0);
    const gp = p.gross_profit || (rev - cogs);
    const selling = Math.abs(p.selling_expenses || 0);
    const admin = Math.abs(p.admin_expenses || p.ga_expenses || 0);
    const totalOpex = selling + admin;
    const ebitda = totalOpex > 0 ? (gp - totalOpex) : (p.ebitda ?? gp);
    const depr = Math.abs(p.depreciation || 0);
    const netProfit = p.net_profit ?? (ebitda - depr);

    if (templateId === 'revenue_waterfall') {
      const wholesale = p.revenue_wholesale || 0;
      const retail = p.revenue_retail || 0;
      const other = p.revenue_other || (rev - wholesale - retail);
      setTemplateData({
        type: 'waterfall',
        data: [
          { name: 'Wholesale', value: wholesale, fill: C.sky },
          { name: 'Retail', value: retail, fill: C.cerulean },
          { name: 'Other', value: other > 0 ? other : 0, fill: C.teal },
          { name: 'Total Revenue', value: rev, fill: C.emerald },
        ].filter(d => d.value > 0),
      });
    } else if (templateId === 'profitability_matrix') {
      const segments = [
        { name: 'Wholesale', revenue: p.revenue_wholesale || 0, cogs: Math.abs(p.cogs_wholesale || 0) },
        { name: 'Retail', revenue: p.revenue_retail || 0, cogs: Math.abs(p.cogs_retail || 0) },
      ].filter(s => s.revenue > 0);
      setTemplateData({
        type: 'matrix',
        data: segments.map(s => ({
          name: s.name,
          revenue: s.revenue,
          cogs: s.cogs,
          grossProfit: s.revenue - s.cogs,
          margin: s.revenue > 0 ? ((s.revenue - s.cogs) / s.revenue * 100) : 0,
        })),
      });
    } else if (templateId === 'period_comparison') {
      setTemplateData({
        type: 'comparison',
        current: { period: period || 'Current', revenue: rev, cogs, gp, ebitda, netProfit },
        prior: {
          period: 'Prior',
          revenue: p.prior_revenue || p.revenue_prior || 0,
          cogs: Math.abs(p.prior_cogs || 0),
          gp: p.prior_gross_profit || 0,
          ebitda: p.prior_ebitda || 0,
          netProfit: p.prior_net_profit || 0,
        },
      });
    } else if (templateId === 'kpi_dashboard') {
      const gpMargin = rev > 0 ? (gp / rev * 100) : 0;
      const netMargin = rev > 0 ? (netProfit / rev * 100) : 0;
      const ebitdaMargin = rev > 0 ? (ebitda / rev * 100) : 0;
      const currentRatio = (bs.total_assets && bs.total_liabilities) ? (bs.total_assets / bs.total_liabilities) : null;
      setTemplateData({
        type: 'kpi',
        kpis: [
          { label: 'Revenue', value: rev, format: 'currency', target: null, status: 'info' },
          { label: 'Gross Margin', value: gpMargin, format: 'pct', target: 20, status: gpMargin >= 20 ? 'good' : gpMargin >= 10 ? 'warn' : 'bad' },
          { label: 'EBITDA Margin', value: ebitdaMargin, format: 'pct', target: 10, status: ebitdaMargin >= 10 ? 'good' : ebitdaMargin >= 0 ? 'warn' : 'bad' },
          { label: 'Net Margin', value: netMargin, format: 'pct', target: 5, status: netMargin >= 5 ? 'good' : netMargin >= 0 ? 'warn' : 'bad' },
          { label: 'Current Ratio', value: currentRatio, format: 'ratio', target: 1.5, status: currentRatio == null ? 'info' : currentRatio >= 1.5 ? 'good' : currentRatio >= 1 ? 'warn' : 'bad' },
          { label: 'Net Profit', value: netProfit, format: 'currency', target: null, status: netProfit >= 0 ? 'good' : 'bad' },
        ],
      });
    }
  };

  /* ─── Tab navigation ─── */
  const tabs = [
    { id: 'builder' as const, label: 'Dashboard Builder', icon: LayoutGrid },
    { id: 'query' as const, label: 'Query Builder', icon: Search },
    { id: 'saved' as const, label: 'Saved Tools', icon: Bookmark },
    { id: 'templates' as const, label: 'Templates', icon: Layers },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)' }}>
      {/* ─── Tab Bar ─── */}
      <div data-tour="tab-bar" style={{
        display: 'flex', alignItems: 'center', gap: 0,
        borderBottom: '1px solid var(--b1)', padding: '0 16px',
        background: 'var(--bg1)', flexShrink: 0,
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            data-tour={`tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '12px 18px', fontSize: 11, fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? 'var(--heading)' : 'var(--muted)',
              background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: activeTab === tab.id ? '2px solid var(--sky)' : '2px solid transparent',
              fontFamily: 'var(--font)', transition: 'all .15s',
            }}
          >
            <tab.icon size={13} />
            {tab.label}
            {tab.id === 'saved' && savedQueries.length > 0 && (
              <span style={{
                fontSize: 9, padding: '1px 6px', borderRadius: 8,
                background: 'rgba(56,189,248,.1)', color: 'var(--sky)',
                fontFamily: 'var(--mono)', fontWeight: 700,
              }}>
                {savedQueries.length}
              </span>
            )}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', padding: '6px 0' }}>
          <WatchDemoButton onClick={() => setTourActive(true)} />
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
          TAB 1: DASHBOARD BUILDER (existing)
          ═══════════════════════════════════════════════════════ */}
      {activeTab === 'builder' && (
        <div style={{ display: 'flex', gap: 0, flex: 1, overflow: 'hidden' }}>
          {/* Left Panel: Widget Palette */}
          <div data-tour="widget-palette" style={{ width: 220, borderRight: '1px solid var(--b1)', padding: 12, overflowY: 'auto', flexShrink: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
              Widgets
            </div>
            {WIDGET_TYPES.map(wt => (
              <div
                key={wt.type}
                draggable
                onDragStart={e => handlePaletteDragStart(e, wt)}
                onDragEnd={() => setDraggingType(null)}
                onClick={() => addWidget(wt)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                  padding: '10px 12px', marginBottom: 6, borderRadius: 8,
                  background: draggingType === wt.type ? 'rgba(56,189,248,.1)' : 'var(--bg3)',
                  border: `1px solid ${draggingType === wt.type ? 'var(--sky)' : 'var(--b1)'}`,
                  color: 'var(--text)', cursor: 'grab', fontSize: 11, textAlign: 'left' as const,
                  transition: 'all .15s',
                }}
              >
                <wt.icon size={14} style={{ color: 'var(--sky)', flexShrink: 0 }} />
                <div>
                  <div style={{ fontWeight: 600 }}>{wt.label}</div>
                  <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>{wt.desc}</div>
                </div>
              </div>
            ))}

            {savedLayouts.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, margin: '20px 0 8px' }}>
                  Saved
                </div>
                {savedLayouts.map(l => (
                  <button
                    key={l.id}
                    onClick={() => loadDashboard(l)}
                    style={{
                      display: 'block', width: '100%', padding: '8px 10px', marginBottom: 4,
                      borderRadius: 6, background: dashId === l.id ? 'rgba(56,189,248,.08)' : 'transparent',
                      border: `1px solid ${dashId === l.id ? 'rgba(56,189,248,.2)' : 'var(--b1)'}`,
                      color: dashId === l.id ? 'var(--sky)' : 'var(--text)',
                      cursor: 'pointer', fontSize: 10, textAlign: 'left',
                    }}
                  >
                    {l.name}
                    <span style={{ fontSize: 8, color: 'var(--muted)', marginLeft: 4 }}>
                      ({l.widgets?.length || 0})
                    </span>
                  </button>
                ))}
              </>
            )}
          </div>

          {/* Center: Grid Canvas */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <LayoutGrid size={18} style={{ color: 'var(--sky)' }} />
              <input
                value={dashName}
                onChange={e => setDashName(e.target.value)}
                style={{
                  background: 'transparent', border: 'none', color: 'var(--heading)',
                  fontSize: 16, fontWeight: 700, outline: 'none', flex: 1,
                }}
                placeholder="Dashboard name..."
              />
              <button onClick={shareDashboard} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px',
                borderRadius: 8, background: 'var(--bg3)', border: '1px solid var(--b1)',
                color: 'var(--text)', cursor: 'pointer', fontSize: 11,
              }}>
                <Link2 size={12} /> Share
              </button>
              <button onClick={saveDashboard} disabled={saving} style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '7px 16px',
                borderRadius: 8, background: 'linear-gradient(135deg, var(--sky), var(--blue))',
                color: '#fff', border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600,
              }}>
                {saving ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Save size={12} />}
                Save
              </button>
            </div>
            {shareUrl && (
              <div style={{ fontSize: 10, color: 'var(--emerald)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Link2 size={10} /> Link copied: <span style={{ fontFamily: 'var(--mono)', color: 'var(--sky)' }}>{shareUrl.substring(0, 60)}...</span>
              </div>
            )}

            {widgets.length === 0 ? (
              <div
                onDrop={handleCanvasDrop}
                onDragOver={handleCanvasDragOver}
                style={{
                  textAlign: 'center', padding: '80px 20px', color: 'var(--muted)',
                  border: draggingType ? '2px dashed var(--sky)' : '2px dashed transparent',
                  borderRadius: 12, transition: 'border .2s',
                  background: draggingType ? 'rgba(56,189,248,.03)' : 'transparent',
                  minHeight: 300,
                }}
              >
                <LayoutGrid size={40} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
                  {draggingType ? 'Drop widget here' : 'Empty Canvas'}
                </p>
                <p style={{ fontSize: 11 }}>
                  {draggingType ? 'Release to add widget' : 'Drag a widget from the left panel or click to add'}
                </p>
              </div>
            ) : (
              <div onDrop={handleCanvasDrop} onDragOver={handleCanvasDragOver}>
              <AnyGridLayout
                className="layout"
                layout={layout}
                cols={12}
                rowHeight={40}
                width={Math.max(800, (typeof window !== 'undefined' ? window.innerWidth : 1200) - 560)}
                onLayoutChange={setLayout}
                draggableHandle=".drag-handle"
                isResizable
              >
                {widgets.map(w => {
                  const data = widgetData[w.id];
                  const isSelected = selectedWidget === w.id;
                  return (
                    <div
                      key={w.id}
                      style={{
                        ...card,
                        borderColor: isSelected ? 'var(--sky)' : 'var(--b1)',
                        display: 'flex', flexDirection: 'column', overflow: 'hidden',
                      }}
                      onClick={() => setSelectedWidget(w.id)}
                    >
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px',
                        borderBottom: '1px solid var(--b1)', fontSize: 10, color: 'var(--muted)',
                      }}>
                        <GripVertical size={10} className="drag-handle" style={{ cursor: 'grab' }} />
                        <span style={{ flex: 1, fontWeight: 600 }}>{w.label}</span>
                        <button onClick={e => { e.stopPropagation(); removeWidget(w.id); }} style={{
                          background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 2,
                        }}>
                          <Trash2 size={10} />
                        </button>
                      </div>

                      <div style={{ flex: 1, padding: 10, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {w.type === 'metric' && data?.value !== undefined ? (
                          <MetricCardWidget
                            label={w.label}
                            value={data.value}
                            format={(w.props.format as 'currency' | 'percentage' | 'number') || 'currency'}
                            size="compact"
                            conditionalRules={[
                              { condition: 'lt', threshold: 0, color: 'var(--rose)' },
                              { condition: 'gt', threshold: 0, color: 'var(--sky)' },
                            ]}
                          />
                        ) : w.type === 'kpi_list' && data?.data ? (
                          <div style={{ fontSize: 10, width: '100%', overflowY: 'auto' }}>
                            {data.data.slice(0, 8).map((item: any, i: number) => (
                              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--b1)' }}>
                                <span style={{ color: 'var(--text)' }}>{item.properties?.metric || item.id?.substring(0, 20)}</span>
                                <span style={{ fontFamily: 'var(--mono)', color: 'var(--sky)' }}>{item.properties?.value?.toFixed?.(2) ?? '\u2014'}</span>
                              </div>
                            ))}
                          </div>
                        ) : w.type === 'table' && data?.data ? (
                          <div style={{ fontSize: 9, width: '100%', overflowY: 'auto' }}>
                            {data.data.slice(0, 10).map((row: any, i: number) => (
                              <div key={i} style={{ display: 'flex', gap: 8, padding: '2px 0', borderBottom: '1px solid var(--b1)' }}>
                                {Object.entries(row).map(([k, v]) => (
                                  <span key={k} style={{ flex: 1, color: 'var(--text)' }}>{String(v).substring(0, 20)}</span>
                                ))}
                              </div>
                            ))}
                          </div>
                        ) : w.type === 'pivot' && data?.data ? (
                          <div style={{ fontSize: 9, width: '100%', overflowY: 'auto', overflowX: 'auto' }}>
                            {(() => {
                              const rows = data.data as Record<string, any>[];
                              if (!rows.length) return <span style={{ color: 'var(--muted)' }}>No data</span>;
                              const cols = Object.keys(rows[0]);
                              const groupCol = cols[0];
                              const valueCol = cols.find(c => typeof rows[0][c] === 'number') || cols[1];
                              const groups: Record<string, number> = {};
                              rows.forEach(r => {
                                const key = String(r[groupCol] || 'Other');
                                groups[key] = (groups[key] || 0) + (Number(r[valueCol]) || 0);
                              });
                              const sorted = Object.entries(groups).sort((a, b) => b[1] - a[1]);
                              return (
                                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                                  <thead>
                                    <tr style={{ borderBottom: '1px solid var(--b2)' }}>
                                      <th style={{ padding: '3px 6px', textAlign: 'left', color: 'var(--muted)', fontSize: 8, textTransform: 'uppercase' }}>{groupCol}</th>
                                      <th style={{ padding: '3px 6px', textAlign: 'right', color: 'var(--muted)', fontSize: 8, textTransform: 'uppercase' }}>{valueCol}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {sorted.slice(0, 15).map(([k, v]) => (
                                      <tr key={k} style={{ borderBottom: '1px solid var(--b1)' }}>
                                        <td style={{ padding: '2px 6px', color: 'var(--text)' }}>{k.substring(0, 25)}</td>
                                        <td style={{ padding: '2px 6px', textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--sky)' }}>{v.toLocaleString()}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              );
                            })()}
                          </div>
                        ) : (
                          <div style={{ fontSize: 10, color: 'var(--muted)', textAlign: 'center' }}>
                            <Settings size={16} style={{ margin: '0 auto 4px', opacity: 0.4 }} />
                            <div>Configure data source</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </AnyGridLayout>
              </div>
            )}
          </div>

          {/* Right Panel: Widget Config */}
          <div data-tour="config-panel" style={{ width: 260, borderLeft: '1px solid var(--b1)', padding: 12, overflowY: 'auto', flexShrink: 0 }}>
            {selectedW ? (
              <>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 12 }}>
                  Configure: {selectedW.label}
                </div>

                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Label</label>
                  <input
                    value={selectedW.label}
                    onChange={e => updateWidgetConfig(selectedW.id, { label: e.target.value })}
                    style={{
                      width: '100%', marginTop: 4, padding: '6px 10px', borderRadius: 6,
                      border: '1px solid var(--b2)', background: 'var(--bg3)',
                      color: 'var(--text)', fontSize: 11, outline: 'none',
                    }}
                  />
                </div>

                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Data Source</label>
                  <select
                    value={selectedW.dataSource}
                    onChange={e => updateWidgetConfig(selectedW.id, { dataSource: e.target.value })}
                    style={{
                      width: '100%', marginTop: 4, padding: '6px 10px', borderRadius: 6,
                      border: '1px solid var(--b2)', background: 'var(--bg3)',
                      color: 'var(--text)', fontSize: 11, outline: 'none', cursor: 'pointer',
                    }}
                  >
                    <option value="">Select data source...</option>
                    {dataSources.map(ds => (
                      <option key={ds.id} value={ds.id}>{ds.label} ({ds.type})</option>
                    ))}
                  </select>
                </div>

                {selectedW.type === 'metric' && (
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Format</label>
                    <select
                      value={(selectedW.props.format as string) || 'currency'}
                      onChange={e => updateWidgetConfig(selectedW.id, { props: { ...selectedW.props, format: e.target.value } })}
                      style={{
                        width: '100%', marginTop: 4, padding: '6px 10px', borderRadius: 6,
                        border: '1px solid var(--b2)', background: 'var(--bg3)',
                        color: 'var(--text)', fontSize: 11, outline: 'none', cursor: 'pointer',
                      }}
                    >
                      <option value="currency">Currency (GEL)</option>
                      <option value="percentage">Percentage (%)</option>
                      <option value="number">Number</option>
                    </select>
                  </div>
                )}

                {selectedDs && (
                  <div style={{ ...card, padding: 10, marginTop: 16 }}>
                    <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Data Preview</div>
                    <div style={{ fontSize: 11, color: 'var(--text)' }}>
                      Type: <span style={{ color: 'var(--sky)' }}>{selectedDs.type}</span>
                    </div>
                    {widgetData[selectedW.id]?.value !== undefined && (
                      <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--heading)', marginTop: 6 }}>
                        {typeof widgetData[selectedW.id].value === 'number'
                          ? widgetData[selectedW.id].value.toLocaleString()
                          : String(widgetData[selectedW.id].value)}
                      </div>
                    )}
                    {widgetData[selectedW.id]?.count !== undefined && (
                      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4 }}>
                        {widgetData[selectedW.id].count} rows
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 10px', color: 'var(--muted)' }}>
                <Settings size={24} style={{ margin: '0 auto 8px', opacity: 0.3 }} />
                <p style={{ fontSize: 11 }}>Click a widget to configure</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          TAB 2: CUSTOM QUERY BUILDER
          ═══════════════════════════════════════════════════════ */}
      {activeTab === 'query' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          <div style={{ maxWidth: 1100, margin: '0 auto' }}>
            {/* Header */}
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', margin: 0, fontFamily: 'var(--font)' }}>
                Custom Query Builder
              </h2>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                Select a data source, metric, and visualization to build custom analytics
              </p>
            </div>

            {/* Builder controls */}
            <div data-tour="query-controls" style={{ ...glass, marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 16, alignItems: 'end' }}>
                {/* Data source */}
                <div>
                  <label style={{ fontSize: 9, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6, display: 'block' }}>
                    Data Source
                  </label>
                  <select
                    value={qDataSource}
                    onChange={e => { setQDataSource(e.target.value); setQMetric(METRICS[e.target.value]?.[0]?.id || ''); setQResult(null); }}
                    style={{
                      width: '100%', padding: '10px 14px', borderRadius: 8,
                      border: '1px solid var(--b2)', background: 'var(--bg2)',
                      color: 'var(--text)', fontSize: 12, outline: 'none', cursor: 'pointer',
                    }}
                  >
                    {DATA_SOURCES.map(ds => (
                      <option key={ds.id} value={ds.id}>{ds.label}</option>
                    ))}
                  </select>
                </div>

                {/* Metric */}
                <div>
                  <label style={{ fontSize: 9, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6, display: 'block' }}>
                    Metric
                  </label>
                  <select
                    value={qMetric}
                    onChange={e => { setQMetric(e.target.value); setQResult(null); }}
                    style={{
                      width: '100%', padding: '10px 14px', borderRadius: 8,
                      border: '1px solid var(--b2)', background: 'var(--bg2)',
                      color: 'var(--text)', fontSize: 12, outline: 'none', cursor: 'pointer',
                    }}
                  >
                    {(METRICS[qDataSource] || []).map(m => (
                      <option key={m.id} value={m.id}>{m.label}</option>
                    ))}
                  </select>
                </div>

                {/* Chart type */}
                <div>
                  <label style={{ fontSize: 9, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6, display: 'block' }}>
                    Visualization
                  </label>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {(['bar', 'line', 'table', 'kpi'] as const).map(ct => (
                      <button
                        key={ct}
                        onClick={() => { setQChartType(ct); setQResult(null); }}
                        style={{
                          flex: 1, padding: '10px 8px', borderRadius: 8, fontSize: 10, fontWeight: 600,
                          background: qChartType === ct ? 'rgba(56,189,248,.12)' : 'var(--bg2)',
                          border: `1px solid ${qChartType === ct ? 'var(--sky)' : 'var(--b2)'}`,
                          color: qChartType === ct ? 'var(--sky)' : 'var(--muted)',
                          cursor: 'pointer', textTransform: 'uppercase', letterSpacing: 0.5,
                        }}
                      >
                        {ct}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Build button */}
                <button
                  onClick={buildQuery}
                  disabled={qBuilding}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 24px', borderRadius: 8,
                    background: 'linear-gradient(135deg, var(--sky), var(--blue))',
                    color: '#fff', border: 'none', cursor: 'pointer',
                    fontSize: 12, fontWeight: 700, whiteSpace: 'nowrap',
                  }}
                >
                  {qBuilding ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Zap size={14} />}
                  Build
                </button>
              </div>

              {/* Save row */}
              {qResult && (
                <div data-tour="query-save" style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--b1)' }}>
                  <input
                    value={qName}
                    onChange={e => setQName(e.target.value)}
                    placeholder="Name this query to save..."
                    style={{
                      flex: 1, padding: '8px 14px', borderRadius: 8,
                      border: '1px solid var(--b2)', background: 'var(--bg2)',
                      color: 'var(--text)', fontSize: 11, outline: 'none',
                    }}
                  />
                  <button
                    onClick={saveQuery}
                    disabled={!qName.trim()}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '8px 16px', borderRadius: 8,
                      background: qName.trim() ? 'var(--bg3)' : 'var(--bg2)',
                      border: '1px solid var(--b2)', color: qName.trim() ? 'var(--text)' : 'var(--muted)',
                      cursor: qName.trim() ? 'pointer' : 'default', fontSize: 11, fontWeight: 600,
                    }}
                  >
                    <Bookmark size={12} /> Save
                  </button>
                </div>
              )}
            </div>

            {/* Result */}
            {qResult && (
              <div style={{ ...glass }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                  <BarChart3 size={14} style={{ color: C.sky }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>
                    {(METRICS[qDataSource] || []).find(m => m.id === qMetric)?.label || qMetric} &mdash; {period || 'Current'}
                  </span>
                  <span style={{ fontSize: 10, color: 'var(--dim)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                    {new Date(qResult.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                {/* KPI view */}
                {qChartType === 'kpi' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                    <div style={{ fontSize: 36, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--heading)' }}>
                      {qResult.formatted}
                    </div>
                    {qResult.pctOfRevenue && (
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                        <span style={{ fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 600 }}>{qResult.pctOfRevenue}</span> of revenue
                      </div>
                    )}
                  </div>
                )}

                {/* Bar chart */}
                {qChartType === 'bar' && qResult.chartData && (
                  <ResponsiveContainer width="100%" height={320}>
                    <BarChart data={qResult.chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" />
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} tickFormatter={(v: number) => fmt(v)} width={55} />
                      <Tooltip contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b2)', borderRadius: 8, fontSize: 12 }} formatter={(v: any) => fmt(Number(v || 0))} />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {qResult.chartData.map((e: any, i: number) => <Cell key={i} fill={e.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}

                {/* Line chart */}
                {qChartType === 'line' && qResult.chartData && (
                  <ResponsiveContainer width="100%" height={320}>
                    <LineChart data={qResult.chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" />
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'var(--muted)' }} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} tickFormatter={(v: number) => fmt(v)} width={55} />
                      <Tooltip contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b2)', borderRadius: 8, fontSize: 12 }} formatter={(v: any) => fmt(Number(v || 0))} />
                      <Line type="monotone" dataKey="value" stroke={C.sky} strokeWidth={2} dot={{ fill: C.sky, r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                )}

                {/* Table */}
                {qChartType === 'table' && qResult.tableData && (
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--b2)' }}>
                        <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Metric</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Value</th>
                        <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>% of Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {qResult.tableData.map((row: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                          <td style={{ padding: '8px 12px', fontSize: 12, color: 'var(--text)' }}>{row.metric}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontSize: 13, fontFamily: 'var(--mono)', fontWeight: 600, color: row.value < 0 ? C.rose : 'var(--heading)' }}>{row.formatted}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>{row.pctOfRevenue}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {/* Empty state */}
            {!qResult && !qBuilding && (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--muted)' }}>
                <Search size={36} style={{ margin: '0 auto 12px', opacity: 0.2 }} />
                <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Select options and click Build</p>
                <p style={{ fontSize: 11 }}>Choose a data source, metric, and visualization type above</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          TAB 3: SAVED TOOLS
          ═══════════════════════════════════════════════════════ */}
      {activeTab === 'saved' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          <div style={{ maxWidth: 900, margin: '0 auto' }}>
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', margin: 0, fontFamily: 'var(--font)' }}>
                Saved Tools
              </h2>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                Your saved queries and custom views. Build new ones in the Query Builder tab.
              </p>
            </div>

            {savedQueries.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--muted)' }}>
                <Bookmark size={36} style={{ margin: '0 auto 12px', opacity: 0.2 }} />
                <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>No saved tools yet</p>
                <p style={{ fontSize: 11, marginBottom: 16 }}>Build a query and save it to see it here</p>
                <button
                  onClick={() => setActiveTab('query')}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '10px 20px', borderRadius: 8,
                    background: 'linear-gradient(135deg, var(--sky), var(--blue))',
                    color: '#fff', border: 'none', cursor: 'pointer',
                    fontSize: 12, fontWeight: 600,
                  }}
                >
                  <Plus size={14} /> Create Query
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {savedQueries.map(q => (
                  <div key={q.id} style={{
                    ...glass, display: 'flex', alignItems: 'center', gap: 16,
                    padding: '14px 18px',
                  }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                      background: 'rgba(56,189,248,.08)', border: '1px solid rgba(56,189,248,.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {q.chartType === 'bar' ? <BarChart3 size={16} style={{ color: C.sky }} /> :
                       q.chartType === 'line' ? <TrendingUp size={16} style={{ color: C.sky }} /> :
                       q.chartType === 'table' ? <Table2 size={16} style={{ color: C.sky }} /> :
                       <Hash size={16} style={{ color: C.sky }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{q.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2, display: 'flex', gap: 12 }}>
                        <span>{DATA_SOURCES.find(ds => ds.id === q.dataSource)?.label || q.dataSource}</span>
                        <span style={{ color: 'var(--dim)' }}>|</span>
                        <span>{q.chartType.toUpperCase()}</span>
                        <span style={{ color: 'var(--dim)' }}>|</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Clock size={9} /> {new Date(q.lastRun).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button
                        onClick={() => runSavedQuery(q)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          padding: '7px 14px', borderRadius: 6,
                          background: 'rgba(56,189,248,.08)', border: '1px solid rgba(56,189,248,.15)',
                          color: 'var(--sky)', cursor: 'pointer', fontSize: 10, fontWeight: 600,
                        }}
                      >
                        <Play size={10} /> Run
                      </button>
                      <button
                        onClick={() => deleteSavedQuery(q.id)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 4,
                          padding: '7px 10px', borderRadius: 6,
                          background: 'transparent', border: '1px solid var(--b1)',
                          color: 'var(--muted)', cursor: 'pointer', fontSize: 10,
                        }}
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          TAB 4: PRE-BUILT TEMPLATES
          ═══════════════════════════════════════════════════════ */}
      {activeTab === 'templates' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          <div style={{ maxWidth: 1100, margin: '0 auto' }}>
            <div style={{ marginBottom: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', margin: 0, fontFamily: 'var(--font)' }}>
                Pre-built Templates
              </h2>
              <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                Ready-to-use financial analysis tools. Click to generate from your data.
              </p>
            </div>

            {/* Template cards */}
            <div data-tour="template-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12, marginBottom: 24 }}>
              {TEMPLATES.map(tmpl => (
                <button
                  key={tmpl.id}
                  onClick={() => runTemplate(tmpl.id)}
                  style={{
                    ...glass, cursor: 'pointer', textAlign: 'left',
                    padding: '18px 20px',
                    borderColor: activeTemplate === tmpl.id ? tmpl.color : 'var(--b1)',
                    transition: 'all .15s',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 8,
                      background: `color-mix(in srgb, ${tmpl.color} 10%, transparent)`,
                      border: `1px solid color-mix(in srgb, ${tmpl.color} 20%, transparent)`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <tmpl.icon size={16} style={{ color: tmpl.color }} />
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{tmpl.name}</div>
                      <div style={{ fontSize: 9, color: tmpl.color, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1 }}>{tmpl.category}</div>
                    </div>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5, margin: 0 }}>{tmpl.description}</p>
                </button>
              ))}
            </div>

            {/* Template output */}
            {activeTemplate && templateData && (
              <div style={{ ...glass }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                  {(() => {
                    const tmpl = TEMPLATES.find(t => t.id === activeTemplate);
                    return tmpl ? (
                      <>
                        <tmpl.icon size={16} style={{ color: tmpl.color }} />
                        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--heading)' }}>{tmpl.name}</span>
                        <span style={{ fontSize: 10, color: 'var(--dim)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>{period || 'Current period'}</span>
                      </>
                    ) : null;
                  })()}
                </div>

                {/* Revenue Waterfall */}
                {templateData.type === 'waterfall' && (
                  <ResponsiveContainer width="100%" height={350}>
                    <BarChart data={templateData.data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
                      <YAxis tick={{ fontSize: 10, fill: 'var(--muted)' }} tickFormatter={(v: number) => fmt(v)} width={55} />
                      <Tooltip contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b2)', borderRadius: 8, fontSize: 12 }} formatter={(v: any) => fmt(Number(v || 0))} />
                      <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                        {templateData.data.map((e: any, i: number) => <Cell key={i} fill={e.fill} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}

                {/* Profitability Matrix */}
                {templateData.type === 'matrix' && (
                  <div>
                    {templateData.data.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--muted)', fontSize: 12 }}>
                        No segment breakdown available. Upload data with product-level detail.
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(templateData.data.length, 4)}, 1fr)`, gap: 12 }}>
                        {templateData.data.map((seg: any, i: number) => {
                          const marginColor = seg.margin >= 20 ? C.emerald : seg.margin >= 10 ? C.amber : C.rose;
                          return (
                            <div key={i} style={{
                              background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8, padding: 16,
                            }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 12 }}>{seg.name}</div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>Revenue</span>
                                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text)' }}>{fmt(seg.revenue)}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                  <span style={{ fontSize: 10, color: 'var(--muted)' }}>COGS</span>
                                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: C.rose }}>{fmt(-seg.cogs)}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--b1)', paddingTop: 6 }}>
                                  <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)' }}>Gross Profit</span>
                                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700, color: seg.grossProfit >= 0 ? C.emerald : C.rose }}>{fmt(seg.grossProfit)}</span>
                                </div>
                                {/* Margin bar */}
                                <div style={{ marginTop: 8 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                    <span style={{ fontSize: 9, color: 'var(--muted)' }}>Margin</span>
                                    <span style={{ fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 700, color: marginColor }}>{seg.margin.toFixed(1)}%</span>
                                  </div>
                                  <div style={{ width: '100%', height: 6, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
                                    <div style={{ width: `${Math.min(Math.max(seg.margin, 0), 100)}%`, height: '100%', background: marginColor, borderRadius: 3, transition: 'width .4s ease' }} />
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Period Comparison */}
                {templateData.type === 'comparison' && (
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--b2)' }}>
                        <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>Line Item</th>
                        <th style={{ padding: '10px 14px', textAlign: 'right', fontSize: 11, color: 'var(--sky)', textTransform: 'uppercase' }}>{templateData.current.period}</th>
                        <th style={{ padding: '10px 14px', textAlign: 'right', fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>{templateData.prior.period}</th>
                        <th style={{ padding: '10px 14px', textAlign: 'right', fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>Variance</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { label: 'Revenue', curr: templateData.current.revenue, prior: templateData.prior.revenue },
                        { label: 'COGS', curr: -templateData.current.cogs, prior: -templateData.prior.cogs },
                        { label: 'Gross Profit', curr: templateData.current.gp, prior: templateData.prior.gp, bold: true },
                        { label: 'EBITDA', curr: templateData.current.ebitda, prior: templateData.prior.ebitda, bold: true },
                        { label: 'Net Profit', curr: templateData.current.netProfit, prior: templateData.prior.netProfit, bold: true },
                      ].map((row, i) => {
                        const variance = row.prior ? ((row.curr - row.prior) / Math.abs(row.prior) * 100) : null;
                        return (
                          <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                            <td style={{ padding: '10px 14px', fontSize: 12, fontWeight: row.bold ? 600 : 400, color: row.bold ? 'var(--heading)' : 'var(--text)' }}>{row.label}</td>
                            <td style={{ padding: '10px 14px', textAlign: 'right', fontSize: 13, fontFamily: 'var(--mono)', fontWeight: row.bold ? 700 : 400, color: row.curr < 0 ? C.rose : 'var(--heading)' }}>{fmt(row.curr)}</td>
                            <td style={{ padding: '10px 14px', textAlign: 'right', fontSize: 13, fontFamily: 'var(--mono)', color: row.prior && row.prior < 0 ? C.rose : 'var(--muted)' }}>{row.prior ? fmt(row.prior) : '\u2014'}</td>
                            <td style={{ padding: '10px 14px', textAlign: 'right', fontSize: 11, fontFamily: 'var(--mono)', fontWeight: 600, color: variance == null ? 'var(--dim)' : variance >= 0 ? C.emerald : C.rose }}>
                              {variance != null ? `${variance >= 0 ? '+' : ''}${variance.toFixed(1)}%` : '\u2014'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}

                {/* KPI Dashboard */}
                {templateData.type === 'kpi' && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                    {templateData.kpis.map((kpi: any, i: number) => {
                      const statusColor = kpi.status === 'good' ? C.emerald : kpi.status === 'warn' ? C.amber : kpi.status === 'bad' ? C.rose : C.sky;
                      const displayValue = kpi.format === 'currency' ? fmt(kpi.value) :
                                           kpi.format === 'pct' ? `${kpi.value?.toFixed(1)}%` :
                                           kpi.format === 'ratio' ? (kpi.value?.toFixed(2) || '\u2014') :
                                           String(kpi.value ?? '\u2014');
                      return (
                        <div key={i} style={{
                          background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8,
                          padding: 16, borderLeft: `3px solid ${statusColor}`,
                        }}>
                          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
                            {kpi.label}
                          </div>
                          <div style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--heading)', lineHeight: 1 }}>
                            {displayValue}
                          </div>
                          {kpi.target != null && (
                            <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 8 }}>
                              Target: <span style={{ fontFamily: 'var(--mono)', color: statusColor }}>
                                {kpi.format === 'pct' ? `${kpi.target}%` : kpi.format === 'ratio' ? kpi.target.toFixed(1) : fmt(kpi.target)}
                              </span>
                              <span style={{
                                marginLeft: 8, fontSize: 9, padding: '2px 6px', borderRadius: 4,
                                background: `color-mix(in srgb, ${statusColor} 10%, transparent)`,
                                color: statusColor, fontWeight: 600,
                              }}>
                                {kpi.status === 'good' ? 'ON TRACK' : kpi.status === 'warn' ? 'WATCH' : kpi.status === 'bad' ? 'BELOW' : 'INFO'}
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Empty state for templates */}
            {!activeTemplate && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--muted)' }}>
                <Layers size={36} style={{ margin: '0 auto 12px', opacity: 0.2 }} />
                <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Select a template above</p>
                <p style={{ fontSize: 11 }}>Click any template card to generate analysis from your financial data</p>
              </div>
            )}
          </div>
        </div>
      )}
      {/* ═══════════════════════════════════════════════════════
          WORKSHOP TOUR
          ═══════════════════════════════════════════════════════ */}
      <WorkshopTour
        active={tourActive}
        onEnd={() => setTourActive(false)}
        onSwitchTab={(tab) => setActiveTab(tab)}
        onAddWidget={() => addWidget(WIDGET_TYPES[0])}
        onBuildQuery={buildQuery}
        onRunTemplate={runTemplate}
        onSelectDataSource={(ds) => { setQDataSource(ds); setQResult(null); }}
        onSelectMetric={(m) => { setQMetric(m); setQResult(null); }}
        onSelectChartType={(ct) => { setQChartType(ct); setQResult(null); }}
      />
    </div>
  );
}
