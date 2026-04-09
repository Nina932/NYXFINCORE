import { useState, useEffect, useMemo, useCallback } from 'react';
import { TrendingUp, Download, Loader2, Mail } from 'lucide-react';
import TrendSection from '../components/TrendSection';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import EmailReportModal from '../components/EmailReportModal';
import { RevenueWaterfallChart } from '../components/FinancialCharts';
import { TechnicalStatsGrid, TechnicalStat } from '../components/PalantirWidgets';
import { fmtCompact, fmtFull, fmtPct } from '../utils/formatters';
import IndustrialPivot from '../components/IndustrialPivot';

export default function PnLPage() {
  const { dataset_id, period, company } = useStore();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError('');
    (api as any).plComparison(dataset_id || undefined)
      .then((d: any) => {
        setData(d);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [dataset_id, period]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await (api as any).plExportExcel(dataset_id || undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `PL_Statement_${data?.period || 'report'}.xlsx`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e: any) { alert(`Export failed: ${e.message}`); }
    finally { setExporting(false); }
  };

  const rows = useMemo(() => data?.rows || [], [data]);
  const hasPrior = useMemo(() => rows.some((r: any) => r.pr !== 0), [rows]);
  const revenue = data?.summary?.revenue || 0;

  const columns = useMemo(() => [
    { key: 'c', label: 'CODE', width: 80 },
    { key: 'l', label: 'LINE_ITEM_SPECIFICATION', width: '35%' },
    ...(hasPrior ? [{ key: 'pr', label: 'PY_ACTUAL', align: 'right' as const, format: (v: number) => fmtFull(v) }] : []),
    { key: 'ac', label: 'CY_ACTUAL', align: 'right' as const, format: (v: number) => <span className={v < 0 ? 'text-rose' : 'text-sky'}>{fmtFull(v)}</span> },
    { key: 'rev_pct', label: '%_REV', align: 'right' as const, format: (_: any, row: any) => revenue ? `${(row.ac / revenue * 100).toFixed(1)}%` : '-' },
    ...(hasPrior ? [
        { key: 'var', label: 'ABS_VAR', align: 'right' as const, format: (v: number) => <span style={{ color: v > 0 ? 'var(--emerald)' : v < 0 ? 'var(--rose)' : 'var(--dim)' }}>{fmtFull(v)}</span> },
        { key: 'var_pct', label: 'VAR_%', align: 'right' as const, format: (v: number) => <span style={{ color: v > 0 ? 'var(--emerald)' : v < 0 ? 'var(--rose)' : 'var(--dim)' }}>{fmtPct(v)}</span> },
    ] : [])
  ], [hasPrior, revenue]);

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 text-dim">
      <Loader2 size={32} className="animate-spin text-sky" />
      <span className="text-[10px] font-black tracking-widest uppercase">Initializing Financial Matrix...</span>
    </div>
  );
  if (error && !data) return <div style={{ padding: 40, color: 'var(--muted)' }}>No P&L data available. Upload a financial file to see the Income Statement.</div>;
  if (!data) return <div style={{ padding: 40, color: 'var(--muted)' }}>No P&L data available.</div>;

  return (
    <div className="max-w-[1600px] mx-auto space-y-10 pb-12">
      
      {/* HEADER - Synchronized Command UI */}
      <div className="flex items-center justify-between py-6 border-b border-b1">
        <div>
          <h1 className="text-xl font-black text-heading flex items-center gap-3 tracking-tighter">
            <TrendingUp size={24} className="text-sky shimmer-active" /> 
            <span>INCOME_STATEMENT_ANALYTICS</span>
          </h1>
          <div className="mt-2 flex items-center gap-2 text-[10px] font-bold font-mono text-muted uppercase tracking-widest opacity-60">
            <span>{data.company || company || 'NYX Core Thinker LLC'}</span>
            <span className="text-b4">/</span>
            <span>{data.period || period}</span>
            {data.prior_period && (
              <>
                <span className="text-b4">/</span>
                <span className="text-sky">VS: {data.prior_period}</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={() => setEmailOpen(true)} className="btn-minimal !px-4 !py-2 text-[11px]">
            <Mail size={14} className="mr-2" /> SEND_REPORT
          </button>
          <button onClick={handleExport} disabled={exporting} className="btn btn-primary !px-6 !py-2.5">
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} className="mr-2" />}
            EXPORT_EXCEL
          </button>
        </div>
      </div>

      {/* KEY METRICS */}
      <TechnicalStatsGrid>
        <TechnicalStat 
          label="REVENUE" 
          value={fmtCompact(data.summary?.revenue)} 
          subValue="TOP_LINE_PERF"
          trend={{ val: 'VERIFIED', pos: true }}
          progress={100}
          status="NOMINAL"
        />
        <TechnicalStat 
          label="GROSS_PROFIT" 
          value={fmtCompact(data.summary?.gross_profit)} 
          subValue="COGS_EFFICIENCY"
          trend={{ val: (data.summary?.gross_profit || 0) >= 0 ? 'POSITIVE' : 'NEGATIVE', pos: (data.summary?.gross_profit || 0) >= 0 }}
          progress={70}
          color={(data.summary?.gross_profit || 0) >= 0 ? 'var(--emerald)' : 'var(--rose)'}
          status={(data.summary?.gross_profit || 0) >= 0 ? 'OPTIMAL' : 'CRITICAL'}
        />
        <TechnicalStat 
          label="EBITDA" 
          value={fmtCompact(data.summary?.ebitda)} 
          subValue="OPERATIONAL_CASH"
          trend={{ val: (data.summary?.ebitda || 0) >= 0 ? 'STABLE' : 'LEAKAGE', pos: (data.summary?.ebitda || 0) >= 0 }}
          progress={60}
          color={(data.summary?.ebitda || 0) >= 0 ? 'var(--sky)' : 'var(--rose)'}
          status="VERIFIED"
        />
        <TechnicalStat 
          label="NET_PROFIT" 
          value={fmtCompact(data.summary?.net_profit)} 
          subValue="BOTTOM_LINE"
          trend={{ val: (data.summary?.net_profit || 0) >= 0 ? 'PROFIT' : 'LOSS', pos: (data.summary?.net_profit || 0) >= 0 }}
          progress={Math.abs((data.summary?.net_profit || 0) / (data.summary?.revenue || 1)) * 100}
          color={(data.summary?.net_profit || 0) >= 0 ? 'var(--emerald)' : 'var(--rose)'}
          status="FINAL"
        />
      </TechnicalStatsGrid>

      {/* P&L Waterfall Bridge (The Correct Layer) */}
      {data.summary && (
        <div className="surface-industrial p-8 relative overflow-hidden group">
          <div className="telemetry-token">RECON_BRIDGE_v4.2</div>
          <div className="mb-8 pl-1 border-l-2 border-sky/30">
            <div className="text-[10px] font-black text-sky uppercase tracking-[0.3em]">Financial Waterfall</div>
            <div className="text-xs text-muted mt-1">Cross-period reconciliation of profit drivers</div>
          </div>
          <RevenueWaterfallChart data={[
            { label: 'Revenue', value: data.summary.revenue || 0 },
            { label: 'COGS', value: -(data.summary.cogs || (data.summary.revenue || 0) - (data.summary.gross_profit || 0)) },
            { label: 'Gross Profit', value: data.summary.gross_profit || 0 },
            ...(data.summary.selling_expenses ? [{ label: 'Selling', value: -Math.abs(data.summary.selling_expenses) }] : []),
            ...(data.summary.admin_expenses || data.summary.ga_expenses ? [{ label: 'Admin', value: -Math.abs(data.summary.admin_expenses || data.summary.ga_expenses) }] : []),
            ...(data.summary.ebitda != null ? [{ label: 'EBITDA', value: data.summary.ebitda }] : []),
            ...(data.summary.depreciation ? [{ label: 'D&A', value: -Math.abs(data.summary.depreciation) }] : []),
            { label: 'Net Profit', value: data.summary.net_profit || 0 },
          ]} />
        </div>
      )}

      {/* Trend Section */}
      <TrendSection />

      {/* P&L MATRIX (Industrial Pivot) */}
      <IndustrialPivot 
        data={rows} 
        columns={columns} 
        rowKey="c" 
        indentKey="lvl" 
        title="Income Statement Matrix"
      />

      <EmailReportModal
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        reportType="pl_comparison"
        reportLabel="Income Statement"
      />
    </div>
  );
}
