import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileText, Play, Loader2, Download, Clock, CheckCircle,
  AlertTriangle, TrendingUp, Shield, BarChart3, BookOpen, Mail,
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { formatCurrency } from '../utils/format';
import EmailReportModal from '../components/EmailReportModal';

interface ReportSection {
  title: string;
  content: string;
  data_tables: { name: string; rows: { metric: string; value: unknown }[] }[];
  charts: string[];
  generation_time_ms: number;
}

const SECTION_ICONS: Record<string, React.ElementType> = {
  'Executive Summary': BookOpen,
  'Key Financial Metrics': BarChart3,
  'Causal Analysis & Key Drivers': TrendingUp,
  'Risk Assessment': AlertTriangle,
  'Strategic Recommendations': Shield,
  'Appendix: Data Tables': FileText,
};

const SECTION_COLORS: Record<string, string> = {
  'Executive Summary': 'var(--sky)',
  'Key Financial Metrics': 'var(--emerald)',
  'Causal Analysis & Key Drivers': 'var(--violet)',
  'Risk Assessment': 'var(--rose)',
  'Strategic Recommendations': 'var(--amber)',
  'Appendix: Data Tables': 'var(--muted)',
};

export default function StructuredReportPage() {
  const { pnl, balance_sheet, company, period, orchestrator } = useStore();
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<{ title: string; sections: ReportSection[]; total_generation_time_ms: number; metadata: Record<string, unknown> } | null>(null);
  const [error, setError] = useState('');
  const [expandedSection, setExpandedSection] = useState<number | null>(null);
  const [emailOpen, setEmailOpen] = useState(false);

  const generateReport = async () => {
    if (!pnl) return;
    setLoading(true);
    setError('');
    try {
      const orch = orchestrator as Record<string, unknown> | null;
      const healthScore = (orch?.health_score as number) || 0;
      const data = await api.generateReport({ financials: pnl, balance_sheet, company, period, health_score: healthScore }) as any;
      if (data.error) throw new Error(data.error);
      setReport(data);
      setExpandedSection(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate report');
    } finally {
      setLoading(false);
    }
  };

  if (!pnl) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 16 }}>
        <FileText size={48} style={{ color: 'var(--dim)' }} />
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)' }}>Upload data to generate reports</h2>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={20} style={{ color: 'var(--sky)' }} />
            AI-Generated Financial Report
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
            Professional multi-section report powered by Nemotron 3 Super
          </p>
        </div>
        <button onClick={generateReport} disabled={loading} className="btn btn-primary" style={{ padding: '10px 20px' }}>
          {loading ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Generating Report...</> : <><Play size={14} /> Generate Full Report</>}
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="glass" style={{ padding: 30, textAlign: 'center' }}>
          <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', color: 'var(--sky)', marginBottom: 12 }} />
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--heading)' }}>Generating 5 report sections in parallel...</div>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>Each section researched and written by Nemotron 3 Super (120B)</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 16, flexWrap: 'wrap' }}>
            {['Executive Summary', 'Key Metrics', 'Causal Analysis', 'Risk Assessment', 'Recommendations'].map((s, i) => (
              <div key={i} style={{ fontSize: 10, padding: '4px 10px', borderRadius: 4, background: 'var(--bg3)', color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--amber)', animation: 'pulse-soft 1.5s ease-in-out infinite', animationDelay: `${i * 0.2}s` }} />
                {s}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="glass" style={{ padding: 14, borderColor: 'var(--rose)' }}>
          <span style={{ color: 'var(--rose)', fontSize: 12 }}>{error}</span>
        </div>
      )}

      {/* Report */}
      {report && !loading && (
        <>
          {/* Report header */}
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass" style={{ padding: 20, borderLeft: '4px solid var(--sky)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--heading)' }}>{report.title}</h2>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={11} /> Generated in {(report.total_generation_time_ms / 1000).toFixed(1)}s
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CheckCircle size={11} style={{ color: 'var(--emerald)' }} /> {report.sections.length} sections
                  </span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--dim)' }}>
                    Model: {String(report.metadata?.model || 'nemotron')}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={async () => {
                  if (!report) return;
                  try {
                    const blob = await api.pdfReport({
                      current: pnl,
                      balance_sheet: balance_sheet || {},
                      company: company || 'Company',
                      period: period || '',
                    });
                    if (blob instanceof Blob) {
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = `FinAI_Report_${(period || '').replace(/\s/g, '_')}.pdf`;
                      document.body.appendChild(a);
                      a.click();
                      document.body.removeChild(a);
                      URL.revokeObjectURL(url);
                    } else {
                      setError('PDF generation failed');
                    }
                  } catch (e) {
                    setError(e instanceof Error ? e.message : 'PDF download failed');
                  }
                }} className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 11 }}>
                  <Download size={12} /> PDF Report
                </button>
                <button onClick={() => setEmailOpen(true)} className="btn btn-ghost" style={{ padding: '6px 14px', fontSize: 11 }}>
                  <Mail size={12} /> Email Report
                </button>
                <button onClick={() => {
                  if (!report) return;
                  // Build HTML for email-ready content
                  const html = `<html><head><style>body{font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#1C2127}h1{color:#2D72D2;border-bottom:2px solid #2D72D2;padding-bottom:8px}h2{color:#4C90F0;margin-top:24px}table{width:100%;border-collapse:collapse;margin:12px 0}td{padding:6px 12px;border-bottom:1px solid #E5E8EB}td:last-child{text-align:right;font-family:monospace;font-weight:600}.footer{margin-top:30px;padding-top:12px;border-top:1px solid #E5E8EB;font-size:11px;color:#738091}</style></head><body>` +
                    `<h1>${report.title}</h1><p>${company || ''} &middot; ${period || ''}</p>` +
                    report.sections.map(s => {
                      let sectionHtml = `<h2>${s.title}</h2><p>${s.content.replace(/\n/g, '<br>')}</p>`;
                      if (s.data_tables?.length) {
                        s.data_tables.forEach(t => {
                          sectionHtml += `<p><strong>${t.name}</strong></p><table>`;
                          t.rows.forEach(r => {
                            sectionHtml += `<tr><td>${r.metric}</td><td>${typeof r.value === 'number' ? '₾' + Number(r.value).toLocaleString() : r.value}</td></tr>`;
                          });
                          sectionHtml += '</table>';
                        });
                      }
                      return sectionHtml;
                    }).join('<hr>') +
                    `<div class="footer">Generated by FinAI OS &middot; ${new Date().toISOString().split('T')[0]}</div></body></html>`;
                  const blob = new Blob([html], { type: 'text/html' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `FinAI_Report_${(period || '').replace(/\s/g, '_')}.html`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  URL.revokeObjectURL(url);
                }} className="btn btn-ghost" style={{ padding: '6px 14px', fontSize: 11 }}>
                  <Download size={12} /> Email-Ready HTML
                </button>
              </div>
            </div>
          </motion.div>

          {/* Section cards */}
          {report.sections.map((section, i) => {
            const Icon = SECTION_ICONS[section.title] || FileText;
            const color = SECTION_COLORS[section.title] || 'var(--sky)';
            const isExpanded = expandedSection === i;

            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass"
                style={{ padding: 0, overflow: 'hidden', cursor: 'pointer' }}
                onClick={() => setExpandedSection(isExpanded ? null : i)}
              >
                {/* Section header */}
                <div style={{
                  padding: '14px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  borderLeft: `3px solid ${color}`,
                  background: isExpanded ? 'rgba(255,255,255,.02)' : 'transparent',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Icon size={16} style={{ color }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{section.title}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {section.generation_time_ms > 0 && (
                      <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
                        {(section.generation_time_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                    <span style={{ fontSize: 10, color: 'var(--muted)', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .2s' }}>▼</span>
                  </div>
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    transition={{ duration: 0.2 }}
                    style={{ padding: '0 18px 18px', borderTop: '1px solid var(--b1)' }}
                  >
                    <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.8, whiteSpace: 'pre-line', paddingTop: 14 }}>
                      {section.content}
                    </div>

                    {/* Data tables */}
                    {section.data_tables.length > 0 && (
                      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {section.data_tables.map((table, ti) => (
                          <div key={ti}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 8 }}>{table.name}</div>
                            <div style={{ fontSize: 11 }}>
                              {table.rows.map((row, ri) => (
                                <div key={ri} style={{
                                  display: 'flex', justifyContent: 'space-between',
                                  padding: '6px 0', borderBottom: '1px solid var(--b1)',
                                }}>
                                  <span style={{ color: 'var(--muted)' }}>{row.metric}</span>
                                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, color: 'var(--heading)' }}>
                                    {typeof row.value === 'number' ? formatCurrency(row.value) : String(row.value)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </>
      )}

      <EmailReportModal open={emailOpen} onClose={() => setEmailOpen(false)} reportType="structured_report" reportLabel="AI-Generated Financial Report" />
    </div>
  );
}
