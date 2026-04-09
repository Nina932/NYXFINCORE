import { useState, useEffect } from 'react';
import {
  Shield, CheckCircle, XCircle, AlertTriangle, Loader2,
  DollarSign, CreditCard, Building2, Briefcase, RefreshCw,
  TrendingUp, Clock, BarChart3, Download, Mail,
} from 'lucide-react';
import EmailReportModal from '../components/EmailReportModal';
import { api } from '../api/client';

/* ─── Types ─── */
interface ReconciliationCheck {
  name: string;
  expected: number;
  actual: number;
  difference: number;
  status: string;
}

interface SAPFIData {
  accounts_receivable?: {
    total_receivables?: number;
    aging_buckets?: Record<string, number>;
    dso?: number;
    collection_risk?: string;
    [key: string]: any;
  };
  accounts_payable?: {
    total_payables?: number;
    payment_schedule?: Record<string, number>;
    dpo?: number;
    [key: string]: any;
  };
  fixed_assets?: {
    total_assets?: number;
    categories?: Record<string, number>;
    depreciation_rate?: number;
    nbv?: number;
    [key: string]: any;
  };
  working_capital?: {
    ar?: number;
    ap?: number;
    net_wc?: number;
    cash_conversion_cycle?: number;
    [key: string]: any;
  };
  [key: string]: any;
}

/* ─── Helpers ─── */
const fmt = (n: number | undefined) =>
  n === undefined || n === null ? '--' : n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });

const fmtCurrency = (n: number | undefined) =>
  n === undefined || n === null ? '--' : `$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const statusColor = (status: string) => {
  const s = status?.toLowerCase();
  if (s === 'pass' || s === 'ok' || s === 'balanced') return 'var(--emerald)';
  if (s === 'fail' || s === 'error' || s === 'unbalanced') return 'var(--rose)';
  return '#EAB308';
};

const statusIcon = (status: string) => {
  const s = status?.toLowerCase();
  if (s === 'pass' || s === 'ok' || s === 'balanced') return <CheckCircle size={14} style={{ color: 'var(--emerald)' }} />;
  if (s === 'fail' || s === 'error' || s === 'unbalanced') return <XCircle size={14} style={{ color: 'var(--rose)' }} />;
  return <AlertTriangle size={14} style={{ color: '#EAB308' }} />;
};

const riskColor = (risk: string | undefined) => {
  if (!risk) return 'var(--muted)';
  const r = risk.toLowerCase();
  if (r === 'high' || r === 'critical') return 'var(--rose)';
  if (r === 'medium') return '#EAB308';
  return 'var(--emerald)';
};

/* ─── Section Card ─── */
function SectionCard({ title, icon: Icon, iconColor, children }: {
  title: string; icon: React.ElementType; iconColor: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 10,
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid var(--b1)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: `color-mix(in srgb, ${iconColor} 10%, transparent)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={14} style={{ color: iconColor }} />
        </div>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{title}</span>
      </div>
      <div style={{ padding: 16 }}>{children}</div>
    </div>
  );
}

/* ─── Metric Row ─── */
function MetricRow({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '5px 0', borderBottom: '1px solid var(--b1)',
    }}>
      <span style={{ fontSize: 11, color: 'var(--muted)' }}>{label}</span>
      <span style={{ fontSize: 11, fontWeight: 600, fontFamily: 'var(--mono)', color: color || 'var(--text)' }}>{value}</span>
    </div>
  );
}

/* ─── Main Page ─── */
export default function FinancialControlsPage() {
  const [recon, setRecon] = useState<any>(null);
  const [reconLoading, setReconLoading] = useState(true);
  const [sapFi, setSapFi] = useState<SAPFIData | null>(null);
  const [sapLoading, setSapLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);

  const loadData = async () => {
    setRefreshing(true);
    try {
      const [reconRes, sapRes] = await Promise.all([
        api.reconciliation(),
        api.sapFi(),
      ]);
      setRecon(reconRes);
      setSapFi(sapRes as SAPFIData | null);
    } finally {
      setReconLoading(false);
      setSapLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const downloadCSV = () => {
    const headers = ['Check', 'Expected', 'Actual', 'Difference', 'Status'];
    const csvChecks: ReconciliationCheck[] = recon?.checks || recon?.reconciliation_checks || [];
    const rows = csvChecks.map(c => [c.name, c.expected, c.actual, c.difference, c.status]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'financial_controls.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const checks: ReconciliationCheck[] = recon?.checks || recon?.reconciliation_checks || [];
  const overallStatus = recon?.overall_status || recon?.status || 'unknown';
  const ar = sapFi?.sap_fi_modules?.ar || sapFi?.accounts_receivable;
  const ap = sapFi?.sap_fi_modules?.ap || sapFi?.accounts_payable;
  const assets = sapFi?.sap_fi_modules?.assets || sapFi?.fixed_assets;
  const wc = sapFi?.working_capital;

  return (
    <div style={{ padding: 24, overflowY: 'auto', height: 'calc(100vh - 64px)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--heading)', letterSpacing: '-0.5px', marginBottom: 4 }}>
            Financial Controls
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            SAP-grade reconciliation, receivables, payables, and asset controls in one view.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={downloadCSV} style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
            borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(16,185,129,.08)', border: '1px solid var(--emerald)',
            color: 'var(--emerald)',
          }}>
            <Download size={12} />
            Export CSV
          </button>
          <button onClick={() => setEmailOpen(true)} style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
            borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(139,92,246,.08)', border: '1px solid var(--violet, #8B5CF6)',
            color: 'var(--violet, #8B5CF6)',
          }}>
            <Mail size={12} />
            Email
          </button>
          <button onClick={loadData} disabled={refreshing} style={{
            display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
            borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            background: 'rgba(56,189,248,.08)', border: '1px solid var(--sky)',
            color: 'var(--sky)', opacity: refreshing ? 0.6 : 1,
          }}>
            <RefreshCw size={12} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {/* ═══ Section 1: Reconciliation ═══ */}
      <SectionCard title="Reconciliation" icon={Shield} iconColor="var(--sky)">
        {reconLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 30 }}>
            <Loader2 size={20} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
          </div>
        ) : (
          <>
            {/* Overall status banner */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', marginBottom: 14,
              borderRadius: 8, background: `color-mix(in srgb, ${statusColor(overallStatus)} 8%, transparent)`,
              border: `1px solid ${statusColor(overallStatus)}30`,
            }}>
              {statusIcon(overallStatus)}
              <span style={{ fontSize: 12, fontWeight: 600, color: statusColor(overallStatus), textTransform: 'uppercase' }}>
                Overall: {overallStatus}
              </span>
              <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 'auto' }}>
                {checks.length} checks
              </span>
            </div>

            {/* Checks table */}
            <div style={{ borderRadius: 8, border: '1px solid var(--b1)', overflow: 'hidden' }}>
              {/* Header row */}
              <div style={{
                display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 80px',
                padding: '6px 12px', background: 'var(--bg1)',
                fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)',
                fontFamily: 'var(--mono)', fontWeight: 600,
              }}>
                <span>Check</span><span style={{ textAlign: 'right' }}>Expected</span>
                <span style={{ textAlign: 'right' }}>Actual</span><span style={{ textAlign: 'right' }}>Difference</span>
                <span style={{ textAlign: 'center' }}>Status</span>
              </div>
              {checks.map((c, i) => (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 80px',
                  padding: '8px 12px', background: i % 2 === 0 ? 'var(--bg2)' : 'transparent',
                  borderTop: '1px solid var(--b1)', alignItems: 'center',
                }}>
                  <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 500 }}>{c.name}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--muted)', textAlign: 'right' }}>{fmtCurrency(c.expected)}</span>
                  <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--muted)', textAlign: 'right' }}>{fmtCurrency(c.actual)}</span>
                  <span style={{
                    fontSize: 11, fontFamily: 'var(--mono)', textAlign: 'right',
                    color: c.difference === 0 ? 'var(--emerald)' : 'var(--rose)', fontWeight: 600,
                  }}>
                    {c.difference === 0 ? '0' : fmtCurrency(c.difference)}
                  </span>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <span style={{
                      fontSize: 9, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                      color: statusColor(c.status),
                      background: `color-mix(in srgb, ${statusColor(c.status)} 10%, transparent)`,
                      textTransform: 'uppercase',
                    }}>
                      {c.status}
                    </span>
                  </div>
                </div>
              ))}
              {checks.length === 0 && (
                <div style={{ padding: 20, textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>
                  No reconciliation data available. Upload financial data first.
                </div>
              )}
            </div>
          </>
        )}
      </SectionCard>

      {/* ═══ Section 2: SAP FI Modules ═══ */}
      <div style={{ marginTop: 20 }}>
        <div style={{
          fontSize: 9, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--dim)',
          fontWeight: 600, fontFamily: 'var(--mono)', marginBottom: 10, paddingLeft: 2,
        }}>
          SAP FI MODULES
        </div>

        {sapLoading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
            <Loader2 size={20} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
            {/* ── AR ── */}
            <SectionCard title="Accounts Receivable" icon={TrendingUp} iconColor="var(--emerald)">
              <MetricRow label="Total Receivables" value={fmtCurrency(ar?.total_receivables)} color="var(--emerald)" />
              <MetricRow label="DSO (Days Sales Outstanding)" value={ar?.dso !== undefined ? `${fmt(ar.dso)} days` : '--'} />
              <MetricRow label="Collection Risk" value={ar?.collection_risk || '--'} color={riskColor(ar?.collection_risk)} />
              {ar?.aging_buckets && (
                <>
                  <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontWeight: 600, marginTop: 10, marginBottom: 4, fontFamily: 'var(--mono)' }}>
                    AGING BUCKETS
                  </div>
                  {Object.entries(ar.aging_buckets).map(([bucket, val]) => (
                    <div key={bucket} style={{
                      display: 'flex', justifyContent: 'space-between', padding: '3px 0',
                    }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{bucket}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text)' }}>{fmtCurrency(val as number)}</span>
                    </div>
                  ))}
                </>
              )}
            </SectionCard>

            {/* ── AP ── */}
            <SectionCard title="Accounts Payable" icon={CreditCard} iconColor="#EAB308">
              <MetricRow label="Total Payables" value={fmtCurrency(ap?.total_payables)} color="#EAB308" />
              <MetricRow label="DPO (Days Payable Outstanding)" value={ap?.dpo !== undefined ? `${fmt(ap.dpo)} days` : '--'} />
              {ap?.payment_schedule && (
                <>
                  <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontWeight: 600, marginTop: 10, marginBottom: 4, fontFamily: 'var(--mono)' }}>
                    PAYMENT SCHEDULE
                  </div>
                  {Object.entries(ap.payment_schedule).map(([period, val]) => (
                    <div key={period} style={{
                      display: 'flex', justifyContent: 'space-between', padding: '3px 0',
                    }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{period}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text)' }}>{fmtCurrency(val as number)}</span>
                    </div>
                  ))}
                </>
              )}
            </SectionCard>

            {/* ── Assets ── */}
            <SectionCard title="Fixed Assets" icon={Building2} iconColor="#8B5CF6">
              <MetricRow label="Total Assets" value={assets?.total_assets || '--'} color="#8B5CF6" />
              <MetricRow label="Depreciation Rate" value={assets?.depreciation_rate !== undefined ? `${fmt(assets.depreciation_rate)}%` : '--'} />
              <MetricRow label="Net Book Value" value={fmtCurrency(assets?.total_net_book_value)} />
              {assets?.categories && (
                <>
                  <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontWeight: 600, marginTop: 10, marginBottom: 4, fontFamily: 'var(--mono)' }}>
                    BY CATEGORY
                  </div>
                  {Object.entries(assets.categories).map(([cat, val]) => (
                    <div key={cat} style={{
                      display: 'flex', justifyContent: 'space-between', padding: '3px 0',
                    }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)' }}>{cat}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text)' }}>{fmtCurrency(val as number)}</span>
                    </div>
                  ))}
                </>
              )}
            </SectionCard>

            {/* ── Working Capital ── */}
            <SectionCard title="Working Capital" icon={Briefcase} iconColor="var(--sky)">
              <MetricRow label="Accounts Receivable" value={fmtCurrency(wc?.accounts_receivable || wc?.ar)} color="var(--emerald)" />
              <MetricRow label="Accounts Payable" value={fmtCurrency(wc?.accounts_payable || wc?.ap)} color="#EAB308" />
              <MetricRow
                label="Net Working Capital"
                value={fmtCurrency(wc?.net_working_capital || wc?.net_wc)}
                color={(wc?.net_working_capital || wc?.net_wc) !== undefined ? ((wc?.net_working_capital || wc?.net_wc || 0) >= 0 ? 'var(--emerald)' : 'var(--rose)') : undefined}
              />
              <MetricRow
                label="Cash Conversion Cycle"
                value={wc?.cash_conversion_cycle !== undefined ? `${fmt(wc.cash_conversion_cycle)} days` : '--'}
              />
            </SectionCard>
          </div>
        )}
      </div>

      <EmailReportModal open={emailOpen} onClose={() => setEmailOpen(false)} reportType="bs_comparison" reportLabel="Financial Controls Report" />
    </div>
  );
}
