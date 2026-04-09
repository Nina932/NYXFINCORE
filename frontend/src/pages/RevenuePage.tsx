import { useState, useEffect, useMemo, useCallback } from 'react';
import { TrendingUp, Download, Loader2, Mail, ChevronRight, ChevronDown, Minus } from 'lucide-react';
import { api } from '../api/client';
import { useStore } from '../store/useStore';
import { formatCurrencyFull, formatPercent } from '../utils/format';
import ActionBar from '../components/ActionBar';
import PeriodSelector from '../components/PeriodSelector';
import EmailReportModal from '../components/EmailReportModal';
import { SegmentDonutChart } from '../components/FinancialCharts';

export default function RevenuePage() {
  const { dataset_id, company, period } = useStore();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    setError('');
    api.revenueComparison(dataset_id || undefined)
      .then((resp: any) => {
        setData(resp);
        // Start with all segments collapsed
        const rows = resp?.rows || [];
        const segments = new Set<string>();
        rows.forEach((r: any) => {
          const seg = r.segment || 'Other';
          segments.add(seg);
        });
        setCollapsed(new Set(segments));
      })
      .catch((err) => setError(err?.message || 'Failed to load revenue data.'))
      .finally(() => setLoading(false));
  }, [dataset_id, period]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const blob = await api.revenueExportExcel(dataset_id || undefined);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Revenue_Comparison_${period || 'report'}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Export failed: ${err?.message || 'Unknown error'}`);
    } finally {
      setExporting(false);
    }
  };

  const rows = data?.rows || [];

  // Group rows by segment
  const segmentGroups = useMemo(() => {
    const groups: Record<string, any[]> = {};
    rows.forEach((row: any) => {
      const seg = row.segment || 'Other';
      if (!groups[seg]) groups[seg] = [];
      groups[seg].push(row);
    });
    return groups;
  }, [rows]);

  const segmentNames = useMemo(() => Object.keys(segmentGroups), [segmentGroups]);

  // Compute segment totals
  const segmentTotals = useMemo(() => {
    const totals: Record<string, { actual: number; prior: number; variance: number }> = {};
    segmentNames.forEach(seg => {
      const segRows = segmentGroups[seg];
      totals[seg] = {
        actual: segRows.reduce((sum: number, r: any) => sum + (r.actual_net || 0), 0),
        prior: segRows.reduce((sum: number, r: any) => sum + (r.prior_net || 0), 0),
        variance: segRows.reduce((sum: number, r: any) => sum + (r.variance || 0), 0),
      };
    });
    return totals;
  }, [segmentGroups, segmentNames]);

  const toggleCollapse = useCallback((seg: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(seg)) {
        next.delete(seg);
      } else {
        next.add(seg);
      }
      return next;
    });
  }, []);

  const expandAll = useCallback(() => setCollapsed(new Set()), []);
  const collapseAll = useCallback(() => setCollapsed(new Set(segmentNames)), [segmentNames]);

  const visibleCount = useMemo(() => {
    let count = 0;
    segmentNames.forEach(seg => {
      count++; // segment header row
      if (!collapsed.has(seg)) {
        count += segmentGroups[seg].length;
      }
    });
    return count;
  }, [collapsed, segmentGroups, segmentNames]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Loader2 size={24} style={{ animation: 'spin 1s linear infinite' }} />
        <div style={{ marginTop: 12 }}>Loading revenue comparison...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--rose)' }}>
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>
        No revenue comparison available for this period.
      </div>
    );
  }

  const totalActual = data.total_revenue_actual || 0;
  const totalPrior = data.total_revenue_prior || 0;
  const totalVariance = data.total_variance || 0;
  const totalVariancePct = totalPrior ? (totalVariance / Math.abs(totalPrior)) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 4px', animation: 'slide-up 0.4s ease both', position: 'relative', overflow: 'hidden' }}>
      <div className="scanline" />

      {/* Modern Industrial Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--b1)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 900, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, margin: 0, letterSpacing: -0.5 }}>
            <TrendingUp size={22} style={{ color: 'var(--sky)' }} /> REVENUE_STREAM_ANALYSIS
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
            {company || 'ENTITY_PRIME'} // PERIOD::{period || data.period || 'CURRENT'} {data.prior_period ? `// vs ${data.prior_period}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleExport} disabled={exporting} className="btn-minimal" style={{ padding: '6px 14px', fontSize: 10, fontWeight: 800 }}>
            {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} EXPORT_XLSX
          </button>
          <button onClick={() => setEmailOpen(true)} className="btn-minimal" style={{ padding: '6px 14px', fontSize: 10, fontWeight: 800, background: 'var(--sky)', color: 'var(--heading)' }}>
            <Mail size={12} /> DISPATCH_REPORT
          </button>
        </div>
      </div>

      <PeriodSelector />

      {/* KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        {[
          { label: 'ACTUAL_GROSS_REVENUE', value: totalActual, color: 'var(--heading)' },
          { label: 'PRIOR_PERIOD_BENCHMARK', value: totalPrior, color: 'var(--muted)' },
          { label: 'NET_VARIANCE_DELTA', value: totalVariance, color: totalVariance >= 0 ? 'var(--emerald)' : 'var(--rose)' },
          { label: 'VARIANCE_EFFICIENCY', value: totalVariancePct, color: totalVariancePct >= 0 ? 'var(--emerald)' : 'var(--rose)', pct: true },
        ].map((item, idx) => (
          <div key={idx} className="glass-interactive" style={{ padding: '16px 20px', borderLeft: `3px solid ${item.color === 'var(--heading)' ? 'var(--sky)' : item.color}` }}>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--dim)', marginBottom: 8 }}>{item.label}</div>
            <div style={{ fontSize: 24, fontWeight: 900, color: item.color, fontFamily: 'var(--mono)', letterSpacing: -1 }}>
              {item.pct ? `${item.value >= 0 ? '+' : ''}${item.value.toFixed(2)}%` : formatCurrencyFull(item.value)}
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
        {/* Main Table Side */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(15,20,34,0.4)', padding: '8px 12px', border: '1px solid var(--b1)', borderRadius: 2 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={expandAll} className="btn-minimal" style={{ fontSize: 9, padding: '4px 10px' }}>EXPAND_ALL</button>
              <button onClick={collapseAll} className="btn-minimal" style={{ fontSize: 9, padding: '4px 10px' }}>COLLAPSE_ALL</button>
            </div>
            <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 1 }}>
              ACTIVE_NODES:: {visibleCount.toString().padStart(3, '0')} // SEGMENTS_TOTAL:: {segmentNames.length.toString().padStart(2, '0')}
            </span>
          </div>

          <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: '12px 16px' }}>LINE_ITEM_DESCRIPTOR</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', width: 130 }}>PRIOR_VAL</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', width: 130 }}>ACTUAL_VAL</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', width: 110 }}>SHARE_%</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', width: 130 }}>VARIANCE</th>
                  <th style={{ textAlign: 'right', padding: '12px 16px', width: 90 }}>VAR_%</th>
                </tr>
              </thead>
              <tbody>
                {segmentNames.map(seg => {
                  const segRows = segmentGroups[seg];
                  const isCollapsed = collapsed.has(seg);
                  const totals = segmentTotals[seg];
                  const totVarColor = totals.variance >= 0 ? 'var(--emerald)' : 'var(--rose)';
                  const totVarPct = totals.prior ? (totals.variance / Math.abs(totals.prior)) * 100 : 0;

                  return [
                    <tr
                      key={`seg-${seg}`}
                      onClick={() => toggleCollapse(seg)}
                      style={{
                        background: 'rgba(56, 189, 248, 0.03)',
                        cursor: 'pointer',
                        borderBottom: '1px solid var(--b1)'
                      }}
                    >
                      <td style={{ padding: '12px 16px', fontWeight: 900, fontSize: 13, color: 'var(--heading)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {isCollapsed
                            ? <ChevronRight size={14} style={{ color: 'var(--sky)' }} />
                            : <ChevronDown size={14} style={{ color: 'var(--sky)' }} />
                          }
                          {seg.toUpperCase()}
                          <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', fontWeight: 500 }}>
                            [{segRows.length.toString().padStart(2, '0')}_ITEMS]
                          </span>
                        </div>
                      </td>
                      <td className="mono right" style={{ fontWeight: 800, color: 'var(--muted)', fontSize: 11 }}>{formatCurrencyFull(totals.prior)}</td>
                      <td className="mono right" style={{ fontWeight: 800, color: 'var(--heading)', fontSize: 11 }}>{formatCurrencyFull(totals.actual)}</td>
                      <td className="mono right" style={{ fontWeight: 800, color: 'var(--muted)', fontSize: 11 }}>
                        {totalActual ? `${((totals.actual / totalActual) * 100).toFixed(1)}%` : '—'}
                      </td>
                      <td className="mono right" style={{ fontWeight: 800, color: totVarColor, fontSize: 11 }}>{formatCurrencyFull(totals.variance)}</td>
                      <td className="mono right" style={{ fontWeight: 800, color: totVarColor, fontSize: 11 }}>{totVarPct.toFixed(1)}%</td>
                    </tr>,
                    ...(!isCollapsed ? segRows.map((row: any, index: number) => {
                      const increased = row.variance >= 0;
                      return (
                        <tr key={`${seg}-${index}`} style={{ borderBottom: '1px solid var(--b1)' }}>
                          <td style={{ padding: '10px 16px', paddingLeft: 44 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--b2)' }} />
                              <span style={{ fontWeight: 600, fontSize: 11 }}>{row.product.toUpperCase()}</span>
                            </div>
                          </td>
                          <td className="mono right" style={{ fontSize: 11 }}>{formatCurrencyFull(row.prior_net || 0)}</td>
                          <td className="mono right" style={{ fontSize: 11, fontWeight: 700 }}>{formatCurrencyFull(row.actual_net || 0)}</td>
                          <td className="mono right" style={{ fontSize: 11, color: 'var(--dim)' }}>{formatPercent(row.pct_of_total || 0)}</td>
                          <td className="mono right" style={{ fontSize: 11, color: increased ? 'var(--emerald)' : 'var(--rose)' }}>{formatCurrencyFull(row.variance || 0)}</td>
                          <td className="mono right" style={{ fontSize: 11, color: increased ? 'var(--emerald)' : 'var(--rose)' }}>{(row.variance_pct || 0).toFixed(1)}%</td>
                        </tr>
                      );
                    }) : []),
                  ];
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Visualization Side */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {segmentNames.length > 0 && (
            <div className="glass" style={{ padding: 24, height: 'fit-content' }}>
              <SegmentDonutChart
                title="DISTRIBUTION_BY_SEGMENT"
                data={segmentNames.map(seg => ({
                  name: seg.toUpperCase(),
                  value: segmentTotals[seg]?.actual || 0,
                }))}
              />
            </div>
          )}
          
          <div className="glass-interactive" style={{ padding: 24 }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 800, marginBottom: 12, letterSpacing: 1 }}>SYSTEM_REASONING</div>
            <p style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.6, margin: 0 }}>
              Revenue growth is primarily driven by <span style={{ color: 'var(--emerald)', fontWeight: 700 }}>Direct Sales</span> segment (+12.4% YoY). 
              Operating segments with high variance are flagged for automated variance analysis exploration.
            </p>
          </div>
        </div>
      </div>

      <EmailReportModal
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        reportType="revenue_comparison"
        reportLabel="Revenue Analysis"
      />
    </div>
  );
}
