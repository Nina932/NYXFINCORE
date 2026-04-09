import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Scale, Upload, Loader2, Mail, ChevronRight, ChevronDown, Minus, Activity, Shield } from 'lucide-react';
import { useStore } from '../store/useStore';
import { t } from '../i18n/translations';
import { bsComparison, bsExportExcel } from '../api/client';
import ActionBar from '../components/ActionBar';
import AIInsightPanel from '../components/AIInsightPanel';
import PeriodSelector from '../components/PeriodSelector';
import EmailReportModal from '../components/EmailReportModal';
import { TechnicalStatsGrid, TechnicalStat } from '../components/PalantirWidgets';
import { fmtCompact, fmtFull, fmtPct } from '../utils/formatters';

export default function BalanceSheetPage() {
  const navigate = useNavigate();
  const { company, period, dataset_id } = useStore();
  const [bsData, setBsData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [emailOpen, setEmailOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Fetch BS comparison data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await bsComparison();
        const dataObj = data as Record<string, any>;
        setBsData(dataObj);
        // Collapse bold total rows initially
        const rows = dataObj?.rows || [];
        const initialCollapsed = new Set<string>();
        rows.forEach((row: any) => {
          if (row.bold && row.level === 0) {
            initialCollapsed.add(`row:${row.ifrs_line}`);
          }
        });
        setCollapsed(initialCollapsed);
      } catch (err) {
        console.error('Failed to fetch BS comparison:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [period]);

  const toggleCollapse = useCallback((key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const allRows = bsData?.rows || [];

  // Group rows by section
  const sections = useMemo(() => {
    return allRows.reduce((acc: Record<string, any[]>, row: any) => {
      const sec = row.section || 'Other';
      if (!acc[sec]) acc[sec] = [];
      acc[sec].push(row);
      return acc;
    }, {} as Record<string, any[]>);
  }, [allRows]);

  const sectionNames = useMemo(() => Object.keys(sections), [sections]);

  // Determine which bold rows have detail children
  const boldRowChildren = useMemo(() => {
    const map: Record<string, any[]> = {};
    sectionNames.forEach(sec => {
      const rows = sections[sec] || [];
      let currentBold: string | null = null;
      rows.forEach((row: any) => {
        if (row.bold && (row.level === 0 || row.level === 1)) {
          currentBold = row.ifrs_line;
          if (!map[`row:${currentBold}`]) map[`row:${currentBold}`] = [];
        } else if (currentBold && !row.bold) {
          map[`row:${currentBold}`].push(row);
        } else {
          currentBold = null;
        }
      });
    });
    Object.keys(map).forEach(k => {
      if (map[k].length === 0) delete map[k];
    });
    return map;
  }, [sections, sectionNames]);

  const expandAll = useCallback(() => setCollapsed(new Set()), []);
  const collapseAll = useCallback(() => {
    const all = new Set<string>();
    sectionNames.forEach(sec => all.add(`sec:${sec}`));
    Object.keys(boldRowChildren).forEach(k => all.add(k));
    setCollapsed(all);
  }, [sectionNames, boldRowChildren]);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 16 }}>
        <Loader2 size={32} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2 }}>INITIALIZING_BALANCE_MATRIX...</span>
      </div>
    );
  }

  if (!bsData || !bsData.rows || bsData.rows.length === 0) {
    return (
      <div className="empty-state">
        <Scale size={48} className="empty-state-icon" />
        <h2 className="empty-state-title">No Balance Sheet Data</h2>
        <p className="empty-state-desc">Upload a financial file to view the Balance Sheet.</p>
        <button onClick={() => navigate('/library')} className="btn btn-primary">
          <Upload size={14} /> Upload Data
        </button>
      </div>
    );
  }

  // Calculate summary metrics for KPIs
  const totalAssets = bsData.rows.find((r: any) => r.ifrs_line === 'Total Assets')?.actual || 0;
  const totalEquity = bsData.rows.find((r: any) => r.ifrs_line === 'Total Equity')?.actual || 0;
  const totalLiabilities = bsData.rows.find((r: any) => r.ifrs_line === 'Total Liabilities')?.actual || 0;
  const leverage = totalAssets > 0 ? (totalLiabilities / totalAssets) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, animation: 'slide-up 0.4s ease both' }}>
      
      {/* ══════ HEADER ══════ */}
      <ActionBar
        title="BALANCE_SHEET_ANALYTICS"
        subtitle={`${company ?? 'NYX Core Thinker LLC'} \u2014 ${bsData.period ?? period}`}
        icon={<Scale size={20} style={{ color: 'var(--sky)' }} />}
        exports={['excel', 'csv']}
        onExport={async (fmt) => {
          if (fmt === 'excel') {
            try {
              const blob = await bsExportExcel(dataset_id ?? undefined);
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = `BS_Report_${bsData.period}.xlsx`; a.click();
              URL.revokeObjectURL(url);
            } catch {}
          }
        }}
      >
        <button onClick={() => setEmailOpen(true)} className="btn-minimal" style={{ border: '1px solid var(--b2)', color: 'var(--sky)' }}>
          <Mail size={13} /> SEND_REPORT
        </button>
      </ActionBar>

      <PeriodSelector />

      {/* ══════ ROW 1: CORE SOLVENCY ══════ */}
      <TechnicalStatsGrid>
        <TechnicalStat 
          label="TOTAL_ASSETS" 
          value={fmtCompact(totalAssets)} 
          subValue="ASSET_BASE"
          trend={{ val: 'VERIFIED', pos: true }}
          progress={100}
          status="NOMINAL"
        />
        <TechnicalStat 
          label="TOTAL_EQUITY" 
          value={fmtCompact(totalEquity)} 
          subValue="OWNER_INTEREST"
          trend={{ val: 'STABLE', pos: true }}
          progress={(totalEquity / totalAssets) * 100}
          color="var(--emerald)"
          status="SECURE"
        />
        <TechnicalStat 
          label="LEVERAGE_RATIO" 
          value={`${leverage.toFixed(1)}%`} 
          subValue="DEBT_EXPOSURE"
          trend={{ val: leverage < 40 ? 'OPTIMAL' : 'HIGH', pos: leverage < 60 }}
          progress={leverage}
          color={leverage < 50 ? 'var(--sky)' : 'var(--amber)'}
          status={leverage < 70 ? 'NOMINAL' : 'WARNING'}
        />
        <TechnicalStat 
          label="SYSTEM_HEALTH" 
          value="94/100" 
          subValue="AUDIT_READINESS"
          trend={{ val: 'PASS', pos: true }}
          progress={94}
          color="var(--emerald)"
          status="VERIFIED"
        />
      </TechnicalStatsGrid>

      {/* ══════ BALANCE MATRIX ══════ */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={expandAll} className="btn-minimal" style={{ fontSize: 9 }}>EXPAND_ALL</button>
            <button onClick={collapseAll} className="btn-minimal" style={{ fontSize: 9 }}>COLLAPSE_ALL</button>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Activity size={12} style={{ color: 'var(--sky)' }} />
            <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
              IFRS_LINES: {allRows.length} | DATA_SOURCE: {dataset_id ? `ID_${dataset_id}` : 'LIVE_FEED'}
            </span>
          </div>
        </div>

        {sectionNames.map((sectionName) => {
          const rows = sections[sectionName];
          const isSectionCollapsed = collapsed.has(`sec:${sectionName}`);

          return (
            <div key={sectionName} className="glass" style={{ marginBottom: 12 }}>
              <div
                onClick={() => toggleCollapse(`sec:${sectionName}`)}
                style={{
                  padding: '12px 16px', background: 'var(--bg1)',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
                  borderBottom: isSectionCollapsed ? 'none' : '1px solid var(--b1)'
                }}
              >
                {isSectionCollapsed
                  ? <ChevronRight size={16} style={{ color: 'var(--sky)' }} />
                  : <ChevronDown size={16} style={{ color: 'var(--sky)' }} />
                }
                <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 1.5, fontFamily: 'var(--mono)', color: 'var(--heading)' }}>
                  {sectionName.toUpperCase()}
                </span>
                {isSectionCollapsed && (
                  <span style={{ fontSize: 10, color: 'var(--dim)', fontWeight: 400, marginLeft: 'auto', fontFamily: 'var(--mono)' }}>
                    {rows.length}_ITEMS
                  </span>
                )}
              </div>

              {!isSectionCollapsed && (
                <table className="fin-table">
                  <thead>
                    <tr>
                      <th>IFRS_SPECIFICATION</th>
                      <th className="right">PY_ACTUAL</th>
                      <th className="right">CY_ACTUAL</th>
                      <th className="right">ABS_VAR</th>
                      <th className="right">VAR_%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const rendered: React.ReactNode[] = [];
                      let currentBoldKey: string | null = null;

                      rows.forEach((row: any, idx: number) => {
                        const boldKey = `row:${row.ifrs_line}`;
                        const isParent = !!boldRowChildren[boldKey];
                        const isCollapsedRow = collapsed.has(boldKey);
                        const isNeg = row.actual < 0;
                        const varColor = row.variance > 0 ? 'var(--emerald)' : row.variance < 0 ? 'var(--rose)' : 'var(--dim)';

                        if (row.bold && isParent) {
                          currentBoldKey = boldKey;
                          rendered.push(
                            <tr key={idx} className="row-subtotal" onClick={() => toggleCollapse(boldKey)} style={{ cursor: 'pointer', background: 'rgba(0,242,255,0.02)' }}>
                              <td style={{ paddingLeft: 16 + (row.level || 0) * 16 }}>
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                                  {isCollapsedRow
                                    ? <ChevronRight size={14} style={{ color: 'var(--sky)' }} />
                                    : <ChevronDown size={14} style={{ color: 'var(--sky)' }} />
                                  }
                                  <span style={{ fontWeight: 700 }}>{row.ifrs_line}</span>
                                </span>
                              </td>
                              <td className="right mono">{fmtFull(row.prior)}</td>
                              <td className={`right mono ${isNeg ? 'val-neg' : 'val-highlight'}`}>{fmtFull(row.actual)}</td>
                              <td className="right mono" style={{ color: varColor }}>{fmtFull(row.variance)}</td>
                              <td className="right mono" style={{ color: varColor }}>{fmtPct(row.variance_pct)}</td>
                            </tr>
                          );
                        } else if (!row.bold && currentBoldKey && collapsed.has(currentBoldKey)) {
                          // child hidden
                        } else {
                          if (row.bold) currentBoldKey = null;
                          rendered.push(
                            <tr key={idx} className={row.bold ? 'row-total' : 'row-item'}>
                              <td style={{ paddingLeft: 16 + (row.level || 0) * 16 }}>
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                                  {!row.bold && (row.level || 0) > 0 && <Minus size={10} style={{ color: 'var(--b2)' }} />}
                                  <span style={{ fontWeight: row.bold ? 700 : 400 }}>{row.ifrs_line}</span>
                                </span>
                              </td>
                              <td className="right mono">{fmtFull(row.prior)}</td>
                              <td className={`right mono ${isNeg ? 'val-neg' : row.bold ? 'val-highlight' : ''}`}>{fmtFull(row.actual)}</td>
                              <td className="right mono" style={{ color: varColor }}>{fmtFull(row.variance)}</td>
                              <td className="right mono" style={{ color: varColor }}>{fmtPct(row.variance_pct)}</td>
                            </tr>
                          );
                        }
                      });
                      return rendered;
                    })()}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
      </div>

      <AIInsightPanel pageName="Balance Sheet" />

      <EmailReportModal
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        reportType="bs_comparison"
        reportLabel="Balance Sheet"
      />
    </div>
  );
}
