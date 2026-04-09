import { useState, useEffect } from 'react';
import { FileText, Download, Loader2, FileOutput, Sheet, AlertCircle, Mail, Database, DollarSign } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { useToast } from '../components/Toast';
import EmailReportModal from '../components/EmailReportModal';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };

export default function ReportsPage() {
  const { pnl, balance_sheet, revenue_breakdown, cogs_breakdown, pl_line_items, company, period, dataset_id, datasets } = useStore();
  const [loadingType, setLoadingType] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailReportType, setEmailReportType] = useState('modern_excel');
  const [selectedDataset, setSelectedDataset] = useState<number | undefined>(dataset_id || undefined);
  const [fxRate, setFxRate] = useState(2.72); // GEL/USD default
  const { toast } = useToast();

  // Load datasets if not in store
  useEffect(() => {
    if (!datasets || datasets.length === 0) {
      fetch('/api/agent/agents/datasets')
        .then(r => r.json())
        .then(d => {
          const list = d.datasets || d;
          if (Array.isArray(list)) useStore.getState().setDatasets(list);
        })
        .catch(() => {});
    }
  }, []);

  const safeName = (name: string) => name.replace(/[^\x20-\x7E]/g, '').replace(/\s+/g, '_').replace(/_+/g, '_').trim() || 'FinAI';

  const triggerDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  };

  const downloadPDF = async (type: 'full' | 'brief') => {
    setLoadingType(type); setError('');
    try {
      const payload = {
        current: pnl || {},
        balance_sheet: balance_sheet || {},
        company: company || 'NYX Core Thinker LLC',
        company_id: selectedDataset || dataset_id || 1,
        period: period || '',
        industry: 'fuel_distribution',
      };
      const blob = type === 'full' ? await api.pdfReport(payload) : await api.briefReport(payload);
      triggerDownload(blob, `${safeName(company || 'FinAI')}_${type}_report.pdf`);
      toast('Report downloaded', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally { setLoadingType(null); }
  };

  const downloadMRExcel = async () => {
    setLoadingType('mr_excel'); setError('');
    try {
      // Call the MR report endpoint with dataset_id and FX rate
      const response = await fetch('/api/mr/generate-excel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
        body: JSON.stringify({
          dataset_id: selectedDataset || dataset_id || undefined,
          company_name: company || 'NYX Core Thinker LLC',
          period: period || '',
          gel_usd_rate: fxRate,
        }),
      });
      if (!response.ok) throw new Error(`MR Export failed: ${response.status}`);
      const blob = await response.blob();
      triggerDownload(blob, `${safeName(company || 'NYX Core Thinker')}_MR_Report.xlsx`);
      toast('MR Report downloaded', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'MR Export failed');
    } finally { setLoadingType(null); }
  };

  const downloadExcel = async () => {
    setLoadingType('excel'); setError('');
    try {
      const blob = await api.excelReport({
        pnl: pnl || {},
        balance_sheet: balance_sheet || {},
        revenue_breakdown: revenue_breakdown || [],
        cogs_breakdown: cogs_breakdown || [],
        pl_line_items: pl_line_items || [],
        company: company ?? 'Company',
        period: period ?? '',
      });
      triggerDownload(blob, `${safeName(company || 'FinAI')}_report.xlsx`);
      toast('Excel report downloaded', 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally { setLoadingType(null); }
  };

  const availableDatasets = (datasets || []).filter((d: any) => d.record_count > 0 && d.record_count < 50000);
  const hasData = !!(pnl && Object.keys(pnl).length > 0);
  const fxValid = fxRate > 0;
  const noDataset = availableDatasets.length === 0 && !dataset_id;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileOutput size={20} style={{ color: 'var(--sky)' }} /> Reports
        </h1>
        <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>Generate and download financial reports</p>
      </div>

      {/* Warnings */}
      {noDataset && (
        <div style={{
          background: 'rgba(245,158,11,.06)', border: '1px solid rgba(245,158,11,.15)',
          color: 'var(--amber, #F59E0B)', fontSize: 12, borderRadius: 8, padding: '8px 14px',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <AlertCircle size={14} /> No datasets available. Upload a financial file first to generate reports.
        </div>
      )}

      {!fxValid && (
        <div style={{
          background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)',
          color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <AlertCircle size={14} /> FX rate must be greater than 0.
        </div>
      )}

      {/* Dataset Selector + Currency Converter */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Database size={13} style={{ color: 'var(--sky)' }} />
          <select
            value={selectedDataset || ''}
            onChange={e => setSelectedDataset(e.target.value ? parseInt(e.target.value) : undefined)}
            style={{
              padding: '6px 10px', borderRadius: 6, background: 'var(--bg2)', color: 'var(--text)',
              border: '1px solid var(--b1)', fontSize: 12, minWidth: 200,
            }}
          >
            <option value="">Auto-select best dataset</option>
            {availableDatasets.map((ds: any) => (
              <option key={ds.id} value={ds.id}>
                {ds.original_filename || ds.name} — {ds.period} ({ds.record_count} records)
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <DollarSign size={13} style={{ color: fxValid ? 'var(--emerald)' : 'var(--rose)' }} />
          <span style={{ fontSize: 11, color: 'var(--muted)' }}>GEL/USD:</span>
          <input
            type="number"
            value={fxRate}
            onChange={e => setFxRate(parseFloat(e.target.value) || 0)}
            step="0.01"
            style={{
              width: 70, padding: '6px 8px', borderRadius: 6, background: 'var(--bg2)', color: 'var(--text)',
              border: `1px solid ${fxValid ? 'var(--b1)' : 'var(--rose)'}`, fontSize: 12, textAlign: 'center',
            }}
          />
        </div>
      </div>

      {error && (
        <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle size={14} /> {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
        {[
          { type: 'mr_excel' as const, title: 'MR Report (Excel)', desc: '6-sheet corporate workbook: Executive Summary, P&L, Balance Sheet, Revenue, COGS, KPI Dashboard. Uses correct GL data with prior year comparison.', icon: Sheet, action: downloadMRExcel, badge: 'RECOMMENDED' },
          { type: 'full' as const, title: 'Full PDF Report', desc: 'Complete AI-powered analysis: diagnosis, strategy, sensitivity, decisions, and executive summary.', icon: FileText, action: () => downloadPDF('full') },
          { type: 'brief' as const, title: 'Executive Brief', desc: 'One-page PDF summary with key KPIs, health score, top recommendations, and critical alerts.', icon: FileOutput, action: () => downloadPDF('brief') },
          { type: 'email' as const, title: 'Email Report', desc: 'Send a professional Excel report with financial analysis directly to stakeholders via email.', icon: Mail, action: () => setEmailModalOpen(true) },
        ].map(report => (
          <div key={report.type} style={{ ...card, padding: 20, position: 'relative' }}>
            {'badge' in report && report.badge && (
              <span style={{
                position: 'absolute', top: 10, right: 10, fontSize: 8, fontWeight: 700,
                padding: '2px 6px', borderRadius: 4, background: 'rgba(16,185,129,.15)',
                color: 'var(--emerald)', letterSpacing: 1, textTransform: 'uppercase',
              }}>
                {report.badge}
              </span>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ width: 36, height: 36, borderRadius: 8, background: 'rgba(56,189,248,.08)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <report.icon size={18} style={{ color: 'var(--sky)' }} />
              </div>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)' }}>{report.title}</h3>
                <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                  {report.type === 'mr_excel' ? 'XLSX · 6 sheets' : report.type === 'email' ? 'EMAIL + XLSX' : 'PDF'}
                </span>
              </div>
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 14 }}>{report.desc}</p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={report.action} disabled={loadingType !== null || (report.type === 'mr_excel' && (!fxValid || noDataset)) || (report.type !== 'email' && !hasData && noDataset)} style={{
                display: 'flex', alignItems: 'center', gap: 6, flex: 1, justifyContent: 'center',
                background: loadingType === report.type ? 'var(--bg3)'
                  : report.type === 'mr_excel' ? 'linear-gradient(135deg, #1B3A5C, #2563EB)' : 'linear-gradient(135deg, var(--sky), var(--blue))',
                color: '#fff', fontWeight: 600, padding: '10px 18px',
                borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12,
              }}>
                {loadingType === report.type ? (
                  <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
                ) : (
                  <>{report.type === 'email' ? <Mail size={14} /> : <Download size={14} />} {report.type === 'email' ? 'Send Email' : 'Download'}</>
                )}
              </button>
              {report.type !== 'email' && (
                <button onClick={() => {
                  const typeMap: Record<string, string> = { mr_excel: 'modern_excel', full: 'full_pdf', brief: 'brief_pdf' };
                  setEmailReportType(typeMap[report.type] || 'pl_comparison');
                  setEmailModalOpen(true);
                }} style={{
                  display: 'flex', alignItems: 'center', gap: 4, padding: '10px 14px',
                  borderRadius: 8, border: '1px solid rgba(37,99,235,.3)', background: 'transparent',
                  color: 'var(--sky)', cursor: 'pointer', fontSize: 11, fontWeight: 600,
                }}>
                  <Mail size={12} /> Email
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <EmailReportModal
        open={emailModalOpen}
        onClose={() => setEmailModalOpen(false)}
        reportType={emailReportType}
        reportLabel={
          emailReportType === 'modern_excel' ? 'MR Report (Excel)' :
          emailReportType === 'full_pdf' ? 'Full PDF Report' :
          emailReportType === 'brief_pdf' ? 'Executive Brief' :
          emailReportType === 'pl_comparison' ? 'P&L Report' :
          'Financial Report'
        }
      />
    </div>
  );
}
