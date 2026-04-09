import { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { FileText, RefreshCcw, AlertTriangle, TrendingUp, TrendingDown, DollarSign } from 'lucide-react';
import { api } from '../api/client';

/* ─── Types ─── */
interface AgingBuckets {
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  over_90: number;
}

interface AgingReport {
  as_of: string;
  buckets: AgingBuckets;
  items: Record<string, unknown[]>;
  total_outstanding: number;
  overdue_items: unknown[];
  total_entries: number;
  dso_estimate?: number;
  dpo_estimate?: number;
  payment_schedule?: unknown;
}

interface SummaryData {
  ar: { total_outstanding: number; buckets: AgingBuckets; entry_count: number; overdue_count: number };
  ap: { total_outstanding: number; buckets: AgingBuckets; entry_count: number; overdue_count: number };
  top_overdue_ar: OverdueEntry[];
  top_overdue_ap: OverdueEntry[];
  net_position: number;
}

interface OverdueEntry {
  invoice_id?: string;
  bill_id?: string;
  customer?: string;
  vendor?: string;
  amount: number;
  balance: number;
  due_date: string;
  status: string;
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
  gap: 4,
  minWidth: 180,
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

const tableSt: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse' as const,
  fontSize: 13,
};

const thSt: React.CSSProperties = {
  textAlign: 'left' as const,
  padding: '10px 12px',
  color: 'var(--text-secondary, #888)',
  borderBottom: '1px solid var(--border, #2a2a4a)',
  fontWeight: 500,
};

const tdSt: React.CSSProperties = {
  padding: '10px 12px',
  color: 'var(--heading, #e0e0e0)',
  borderBottom: '1px solid var(--border, #2a2a4a)',
};

/* ─── Helpers ─── */
function fmt(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

const BUCKET_LABELS = ['Current', '1-30 days', '31-60 days', '61-90 days', '90+ days'];
const BUCKET_KEYS: (keyof AgingBuckets)[] = ['current', '1_30', '31_60', '61_90', 'over_90'];
const BUCKET_COLORS = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444'];

export default function SubledgerPage() {
  const [arAging, setArAging] = useState<AgingReport | null>(null);
  const [apAging, setApAging] = useState<AgingReport | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState('');

  const fetchAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [ar, ap, sum] = await Promise.all([
        api.subledgerARaging() as Promise<AgingReport>,
        api.subledgerAPaging() as Promise<AgingReport>,
        api.subledgerSummary() as Promise<SummaryData>,
      ]);
      setArAging(ar);
      setApAging(ap);
      setSummary(sum);
    } catch (err: any) {
      console.error('Subledger fetch failed:', err);
      setError(err.message || 'Failed to load sub-ledger data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.subledgerSeed();
      await fetchAll();
    } catch (err: any) {
      setError(err.message || 'Seed failed');
    } finally {
      setSeeding(false);
    }
  };

  const isEmpty = summary && summary.ar.entry_count === 0 && summary.ap.entry_count === 0;

  /* ─── Aging Stacked Bar Chart ─── */
  const agingBarOption = (arBuckets: AgingBuckets, apBuckets: AgingBuckets) => ({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(20,20,40,0.95)',
      borderColor: '#333',
      textStyle: { color: '#e0e0e0', fontSize: 12 },
      formatter: (params: any[]) => {
        let html = `<b>${params[0]?.axisValue}</b><br/>`;
        params.forEach((p: any) => {
          html += `<span style="color:${p.color}">\u25CF</span> ${p.seriesName}: ${fmt(p.value)}<br/>`;
        });
        return html;
      },
    },
    legend: {
      data: ['AR', 'AP'],
      textStyle: { color: '#aaa', fontSize: 12 },
      top: 0,
    },
    grid: { left: 60, right: 20, top: 40, bottom: 30 },
    xAxis: {
      type: 'category',
      data: BUCKET_LABELS,
      axisLabel: { color: '#aaa', fontSize: 11 },
      axisLine: { lineStyle: { color: '#444' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: '#aaa',
        fontSize: 11,
        formatter: (v: number) => fmt(v),
      },
      splitLine: { lineStyle: { color: '#2a2a4a' } },
    },
    series: [
      {
        name: 'AR',
        type: 'bar',
        stack: 'aging',
        data: BUCKET_KEYS.map(k => arBuckets[k]),
        itemStyle: { color: '#6366f1', borderRadius: [0, 0, 0, 0] },
        barWidth: '50%',
      },
      {
        name: 'AP',
        type: 'bar',
        stack: 'aging',
        data: BUCKET_KEYS.map(k => apBuckets[k]),
        itemStyle: { color: '#f97316', borderRadius: [4, 4, 0, 0] },
      },
    ],
  });

  /* ─── Heatmap ─── */
  const heatmapOption = (arBuckets: AgingBuckets, apBuckets: AgingBuckets) => {
    const arTotal = Object.values(arBuckets).reduce((a, b) => a + b, 0) || 1;
    const apTotal = Object.values(apBuckets).reduce((a, b) => a + b, 0) || 1;

    const data: [number, number, number][] = [];
    BUCKET_KEYS.forEach((k, col) => {
      data.push([col, 0, Math.round((arBuckets[k] / arTotal) * 100)]);
      data.push([col, 1, Math.round((apBuckets[k] / apTotal) * 100)]);
    });

    return {
      tooltip: {
        formatter: (p: any) => {
          const label = BUCKET_LABELS[p.data[0]];
          const type = p.data[1] === 0 ? 'AR' : 'AP';
          return `${type} ${label}: ${p.data[2]}%`;
        },
        backgroundColor: 'rgba(20,20,40,0.95)',
        borderColor: '#333',
        textStyle: { color: '#e0e0e0' },
      },
      grid: { left: 60, right: 40, top: 10, bottom: 40 },
      xAxis: {
        type: 'category',
        data: BUCKET_LABELS,
        axisLabel: { color: '#aaa', fontSize: 11 },
        splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.04)'] } },
      },
      yAxis: {
        type: 'category',
        data: ['AR', 'AP'],
        axisLabel: { color: '#aaa', fontSize: 12 },
      },
      visualMap: {
        min: 0,
        max: 60,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: { color: ['#1a1a3e', '#3b82f6', '#f97316', '#ef4444'] },
        textStyle: { color: '#aaa', fontSize: 11 },
      },
      series: [{
        type: 'heatmap',
        data,
        label: { show: true, color: '#fff', fontSize: 12, formatter: (p: any) => `${p.data[2]}%` },
        itemStyle: { borderWidth: 2, borderColor: 'var(--bg0, #0d0d1a)' },
      }],
    };
  };

  /* ─── Render ─── */
  if (loading) {
    return (
      <div style={{ padding: 32, color: 'var(--heading, #e0e0e0)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <RefreshCcw size={20} style={{ animation: 'spin 1s linear infinite' }} />
          Loading sub-ledger data...
        </div>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <div style={{ ...card, maxWidth: 520, margin: '80px auto', padding: 48 }}>
          <FileText size={48} style={{ color: 'var(--accent, #6366f1)', marginBottom: 16 }} />
          <h2 style={{ ...heading, fontSize: 22, marginBottom: 8 }}>No Sub-Ledger Data</h2>
          <p style={{ ...subtext, marginBottom: 24 }}>
            Seed demo AR and AP entries to explore aging analysis, DSO/DPO metrics, and concentration risk.
          </p>
          <button style={btn} onClick={handleSeed} disabled={seeding}>
            {seeding ? <RefreshCcw size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <FileText size={16} />}
            {seeding ? 'Seeding...' : 'Seed Demo Data'}
          </button>
          {error && <p style={{ color: '#ef4444', marginTop: 12, fontSize: 13 }}>{error}</p>}
        </div>
      </div>
    );
  }

  const arBuckets = summary?.ar.buckets || { current: 0, '1_30': 0, '31_60': 0, '61_90': 0, over_90: 0 };
  const apBuckets = summary?.ap.buckets || { current: 0, '1_30': 0, '31_60': 0, '61_90': 0, over_90: 0 };

  return (
    <div style={{ padding: '0 0 32px 0', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ ...heading, fontSize: 22, display: 'flex', alignItems: 'center', gap: 10 }}>
            <FileText size={22} style={{ color: 'var(--accent, #6366f1)' }} /> Sub-Ledger Analysis
          </h1>
          <p style={subtext}>AR & AP aging, concentration risk, and working capital metrics</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={{ ...btn, background: 'var(--bg1, #1a1a2e)', color: 'var(--heading, #e0e0e0)', border: '1px solid var(--border, #2a2a4a)' }} onClick={fetchAll}>
            <RefreshCcw size={14} /> Refresh
          </button>
          <button style={btn} onClick={handleSeed} disabled={seeding}>
            {seeding ? 'Seeding...' : 'Seed Demo Data'}
          </button>
        </div>
      </div>

      {error && <div style={{ ...card, background: '#1c0a0a', borderColor: '#ef4444', padding: 12, color: '#ef4444', fontSize: 13 }}>{error}</div>}

      {/* Summary KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingUp size={18} style={{ color: '#6366f1' }} />
            <span style={subtext}>Total AR Outstanding</span>
          </div>
          <p style={metricValue}>{fmt(summary?.ar.total_outstanding || 0)}</p>
          <span style={{ ...subtext, fontSize: 12 }}>{summary?.ar.entry_count || 0} invoices ({summary?.ar.overdue_count || 0} overdue)</span>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TrendingDown size={18} style={{ color: '#f97316' }} />
            <span style={subtext}>Total AP Outstanding</span>
          </div>
          <p style={metricValue}>{fmt(summary?.ap.total_outstanding || 0)}</p>
          <span style={{ ...subtext, fontSize: 12 }}>{summary?.ap.entry_count || 0} bills ({summary?.ap.overdue_count || 0} overdue)</span>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={18} style={{ color: '#22c55e' }} />
            <span style={subtext}>DSO (Days Sales Outstanding)</span>
          </div>
          <p style={metricValue}>{arAging?.dso_estimate?.toFixed(0) || '0'}<span style={{ fontSize: 16, fontWeight: 400 }}> days</span></p>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={18} style={{ color: '#eab308' }} />
            <span style={subtext}>DPO (Days Payable Outstanding)</span>
          </div>
          <p style={metricValue}>{apAging?.dpo_estimate?.toFixed(0) || '0'}<span style={{ fontSize: 16, fontWeight: 400 }}> days</span></p>
        </div>
        <div style={metricCard}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={18} style={{ color: (summary?.net_position || 0) >= 0 ? '#22c55e' : '#ef4444' }} />
            <span style={subtext}>Net Position (AR - AP)</span>
          </div>
          <p style={{ ...metricValue, color: (summary?.net_position || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
            {(summary?.net_position || 0) >= 0 ? '+' : ''}{fmt(summary?.net_position || 0)}
          </p>
        </div>
      </div>

      {/* Charts Row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* AR Aging Bar */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16 }}>AR vs AP Aging Distribution</h3>
          <ReactECharts
            option={agingBarOption(arBuckets, apBuckets)}
            style={{ height: 320, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
        {/* Heatmap */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16 }}>Concentration Risk Heatmap</h3>
          <ReactECharts
            option={heatmapOption(arBuckets, apBuckets)}
            style={{ height: 320, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
        </div>
      </div>

      {/* AR and AP separate aging bars */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, color: '#6366f1' }}>Accounts Receivable Aging</h3>
          <ReactECharts
            option={{
              tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(20,20,40,0.95)',
                borderColor: '#333',
                textStyle: { color: '#e0e0e0' },
              },
              grid: { left: 60, right: 20, top: 10, bottom: 30 },
              xAxis: {
                type: 'category',
                data: BUCKET_LABELS,
                axisLabel: { color: '#aaa', fontSize: 11 },
                axisLine: { lineStyle: { color: '#444' } },
              },
              yAxis: {
                type: 'value',
                axisLabel: { color: '#aaa', formatter: (v: number) => fmt(v) },
                splitLine: { lineStyle: { color: '#2a2a4a' } },
              },
              series: [{
                type: 'bar',
                data: BUCKET_KEYS.map((k, i) => ({
                  value: arBuckets[k],
                  itemStyle: { color: BUCKET_COLORS[i], borderRadius: [6, 6, 0, 0] },
                })),
                barWidth: '55%',
              }],
            }}
            style={{ height: 250, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--text-secondary, #888)' }}>
            <span>Total: {fmt(summary?.ar.total_outstanding || 0)}</span>
            <span>Overdue: {fmt((arBuckets['1_30'] || 0) + (arBuckets['31_60'] || 0) + (arBuckets['61_90'] || 0) + (arBuckets.over_90 || 0))}</span>
          </div>
        </div>
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, color: '#f97316' }}>Accounts Payable Aging</h3>
          <ReactECharts
            option={{
              tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(20,20,40,0.95)',
                borderColor: '#333',
                textStyle: { color: '#e0e0e0' },
              },
              grid: { left: 60, right: 20, top: 10, bottom: 30 },
              xAxis: {
                type: 'category',
                data: BUCKET_LABELS,
                axisLabel: { color: '#aaa', fontSize: 11 },
                axisLine: { lineStyle: { color: '#444' } },
              },
              yAxis: {
                type: 'value',
                axisLabel: { color: '#aaa', formatter: (v: number) => fmt(v) },
                splitLine: { lineStyle: { color: '#2a2a4a' } },
              },
              series: [{
                type: 'bar',
                data: BUCKET_KEYS.map((k, i) => ({
                  value: apBuckets[k],
                  itemStyle: { color: BUCKET_COLORS[i], borderRadius: [6, 6, 0, 0] },
                })),
                barWidth: '55%',
              }],
            }}
            style={{ height: 250, width: '100%' }}
            opts={{ renderer: 'svg' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 12, color: 'var(--text-secondary, #888)' }}>
            <span>Total: {fmt(summary?.ap.total_outstanding || 0)}</span>
            <span>Overdue: {fmt((apBuckets['1_30'] || 0) + (apBuckets['31_60'] || 0) + (apBuckets['61_90'] || 0) + (apBuckets.over_90 || 0))}</span>
          </div>
        </div>
      </div>

      {/* Top Overdue Tables */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* AR Top Overdue */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={16} style={{ color: '#ef4444' }} /> Top Overdue AR Invoices
          </h3>
          {(summary?.top_overdue_ar?.length || 0) === 0 ? (
            <p style={subtext}>No overdue AR invoices</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableSt}>
                <thead>
                  <tr>
                    <th style={thSt}>Customer</th>
                    <th style={thSt}>Invoice</th>
                    <th style={{ ...thSt, textAlign: 'right' }}>Balance</th>
                    <th style={thSt}>Due Date</th>
                    <th style={{ ...thSt, textAlign: 'right' }}>Days Past</th>
                  </tr>
                </thead>
                <tbody>
                  {summary!.top_overdue_ar.map((e, i) => {
                    const daysPast = Math.max(0, Math.floor((Date.now() - new Date(e.due_date).getTime()) / 86400000));
                    return (
                      <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                        <td style={tdSt}>{e.customer || '-'}</td>
                        <td style={{ ...tdSt, fontFamily: 'monospace', fontSize: 12 }}>{e.invoice_id || '-'}</td>
                        <td style={{ ...tdSt, textAlign: 'right', fontWeight: 600, color: '#ef4444' }}>{fmt(e.balance)}</td>
                        <td style={tdSt}>{e.due_date}</td>
                        <td style={{ ...tdSt, textAlign: 'right', color: daysPast > 60 ? '#ef4444' : daysPast > 30 ? '#f97316' : '#eab308' }}>
                          {daysPast}d
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* AP Top Overdue */}
        <div style={card}>
          <h3 style={{ ...heading, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={16} style={{ color: '#f97316' }} /> Top Overdue AP Bills
          </h3>
          {(summary?.top_overdue_ap?.length || 0) === 0 ? (
            <p style={subtext}>No overdue AP bills</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={tableSt}>
                <thead>
                  <tr>
                    <th style={thSt}>Vendor</th>
                    <th style={thSt}>Bill</th>
                    <th style={{ ...thSt, textAlign: 'right' }}>Balance</th>
                    <th style={thSt}>Due Date</th>
                    <th style={{ ...thSt, textAlign: 'right' }}>Days Past</th>
                  </tr>
                </thead>
                <tbody>
                  {summary!.top_overdue_ap.map((e, i) => {
                    const daysPast = Math.max(0, Math.floor((Date.now() - new Date(e.due_date).getTime()) / 86400000));
                    return (
                      <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                        <td style={tdSt}>{e.vendor || '-'}</td>
                        <td style={{ ...tdSt, fontFamily: 'monospace', fontSize: 12 }}>{e.bill_id || '-'}</td>
                        <td style={{ ...tdSt, textAlign: 'right', fontWeight: 600, color: '#f97316' }}>{fmt(e.balance)}</td>
                        <td style={tdSt}>{e.due_date}</td>
                        <td style={{ ...tdSt, textAlign: 'right', color: daysPast > 60 ? '#ef4444' : daysPast > 30 ? '#f97316' : '#eab308' }}>
                          {daysPast}d
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
