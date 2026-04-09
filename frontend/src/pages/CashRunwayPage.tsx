import { useState, useEffect, useMemo } from 'react';
import { Clock, Play, Loader2, AlertTriangle, CheckCircle, TrendingDown, Mail, Send } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { formatCurrency } from '../utils/format';
import ActionBar from '../components/ActionBar';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 10 };

export default function CashRunwayPage() {
  const { pnl, balance_sheet } = useStore();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [emailDialog, setEmailDialog] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailData, setEmailData] = useState({
    recipients: '',
    customMessage: '',
  });
  const [emailSuccess, setEmailSuccess] = useState('');

  const cash = balance_sheet?.cash ?? balance_sheet?.cash_and_equivalents ?? 0;
  const revenue = pnl?.revenue ?? pnl?.total_revenue ?? 0;
  const expenses = Math.abs(pnl?.cogs ?? 0) + Math.abs(pnl?.selling_expenses ?? 0) + Math.abs(pnl?.admin_expenses ?? pnl?.ga_expenses ?? 0);
  const netMonthly = revenue - expenses;


  const run = async () => {
    if (!pnl) return;
    setLoading(true); setError('');
    try { setResult(await api.runway(cash, revenue, expenses) as Record<string, unknown>); }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setLoading(false); }
  };

  const sendEmailReport = async () => {
    if (!result || !emailData.recipients.trim()) return;

    setEmailLoading(true);
    setEmailSuccess('');
    try {
      const recipients = emailData.recipients.split(',').map(email => email.trim()).filter(email => email);
      await api.sendEmailReport({
        recipients,
        report_type: 'cash_runway',
        company_name: 'Company', // Could be made configurable
        period: 'Current Period', // Could be made configurable
        custom_message: emailData.customMessage || undefined,
      });
      setEmailSuccess('Email report sent successfully!');
      setEmailDialog(false);
      setEmailData({ recipients: '', customMessage: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send email');
    } finally {
      setEmailLoading(false);
    }
  };

  useEffect(() => { if (pnl && !result) run(); }, [pnl]);

  const months = (result?.months as number) ?? 0;
  const riskLevel = (result?.risk_level as string) ?? '';
  const burnRate = (result?.burn_rate as number) ?? 0;
  const riskColor = riskLevel === 'safe' || riskLevel === 'low' ? 'var(--emerald)' : riskLevel === 'medium' ? 'var(--amber)' : 'var(--rose)';

  // Generate cash projection data for chart
  const projectionData = useMemo(() => {
    if (!cash || !burnRate) return [];
    const data = [];
    let balance = cash;
    const projMonths = Math.min(Math.max(months * 1.5, 6), 36);
    for (let m = 0; m <= projMonths; m++) {
      data.push({
        month: m,
        label: `M${m}`,
        cash: Math.max(balance, 0),
        danger: balance < 0 ? Math.abs(balance) : 0,
      });
      balance -= Math.abs(burnRate);
    }
    return data;
  }, [cash, burnRate, months]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <ActionBar
        title="Cash Runway"
        subtitle="Cash depletion projection"
        icon={<Clock size={20} style={{ color: 'var(--sky)' }} />}
      >
        <button onClick={run} disabled={loading || !pnl} className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 11 }}>
          {loading ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Calculating...</> : <><Play size={13} /> Calculate</>}
        </button>
        {result && (
          <button
            onClick={() => setEmailDialog(true)}
            className="btn btn-secondary"
            style={{ padding: '6px 14px', fontSize: 11, marginLeft: 8 }}
          >
            <Mail size={13} style={{ marginRight: 4 }} /> Email Report
          </button>
        )}
      </ActionBar>

      {error && <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px' }}>{error}</div>}
      {!pnl && <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>Upload financial data first.</p></div>}

      {result && (
        <>
          {/* Hero Metric */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
            <div style={{ ...card, padding: 20, textAlign: 'center', gridColumn: 'span 1' }}>
              <div style={{ fontSize: 42, fontWeight: 800, color: riskColor, fontFamily: 'var(--mono)', lineHeight: 1 }}>{months.toFixed(0)}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>months of runway</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginTop: 8 }}>
                {riskLevel === 'safe' || riskLevel === 'low' ? <CheckCircle size={12} style={{ color: riskColor }} /> : <AlertTriangle size={12} style={{ color: riskColor }} />}
                <span style={{ fontSize: 9, fontFamily: 'var(--mono)', padding: '2px 6px', borderRadius: 3, background: `color-mix(in srgb, ${riskColor} 12%, transparent)`, color: riskColor, textTransform: 'uppercase', letterSpacing: 1 }}>
                  {riskLevel}
                </span>
              </div>
            </div>
            {[
              { label: 'Cash Balance', value: formatCurrency(cash), color: 'var(--sky)' },
              { label: 'Monthly Burn', value: formatCurrency(burnRate), color: 'var(--rose)' },
              { label: 'Net Monthly', value: formatCurrency(netMonthly), color: netMonthly >= 0 ? 'var(--emerald)' : 'var(--rose)' },
            ].map(m => (
              <div key={m.label} style={{ ...card, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--muted)', marginBottom: 6 }}>{m.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: m.color, fontFamily: 'var(--mono)' }}>{m.value}</div>
              </div>
            ))}
          </div>

          {/* Cash Projection Chart */}
          {projectionData.length > 0 && (
            <div style={{ ...card, padding: 16 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6, margin: '0 0 14px 0' }}>
                <TrendingDown size={14} style={{ color: 'var(--amber)' }} /> Cash Depletion Projection
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={projectionData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" />
                  <XAxis dataKey="label" tick={{ fontSize: 9, fill: 'var(--muted)' }} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} tickFormatter={(v: number) => `₾${(v/1e6).toFixed(0)}M`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8, fontSize: 11 }}
                    formatter={(value: any) => formatCurrency(Number(value || 0))}
                  />
                  <ReferenceLine y={0} stroke="var(--rose)" strokeDasharray="3 3" label={{ value: 'Zero', fill: 'var(--rose)', fontSize: 9 }} />
                  <Area type="monotone" dataKey="cash" stroke="var(--sky)" fill="rgba(56,189,248,.1)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* Email Report Dialog */}
      {emailDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--bg1)',
            borderRadius: 12,
            padding: 24,
            width: '90%',
            maxWidth: 500,
            border: '1px solid var(--b1)',
          }}>
            <h3 style={{
              fontSize: 18,
              fontWeight: 600,
              color: 'var(--heading)',
              marginBottom: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}>
              <Mail size={20} style={{ color: 'var(--sky)' }} />
              Send Cash Runway Report
            </h3>

            <div style={{ marginBottom: 16 }}>
              <label style={{
                display: 'block',
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--heading)',
                marginBottom: 4,
              }}>
                Recipients (comma-separated emails)
              </label>
              <input
                type="email"
                multiple
                value={emailData.recipients}
                onChange={(e) => setEmailData(prev => ({ ...prev, recipients: e.target.value }))}
                placeholder="email1@example.com, email2@example.com"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--b1)',
                  borderRadius: 6,
                  background: 'var(--bg2)',
                  color: 'var(--text)',
                  fontSize: 14,
                }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{
                display: 'block',
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--heading)',
                marginBottom: 4,
              }}>
                Custom Message (optional)
              </label>
              <textarea
                value={emailData.customMessage}
                onChange={(e) => setEmailData(prev => ({ ...prev, customMessage: e.target.value }))}
                placeholder="Add a personal message to the email..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--b1)',
                  borderRadius: 6,
                  background: 'var(--bg2)',
                  color: 'var(--text)',
                  fontSize: 14,
                  resize: 'vertical',
                }}
              />
            </div>

            {emailSuccess && (
              <div style={{
                background: 'rgba(34,197,94,.1)',
                border: '1px solid rgba(34,197,94,.2)',
                color: 'var(--emerald)',
                padding: '8px 12px',
                borderRadius: 6,
                fontSize: 12,
                marginBottom: 16,
              }}>
                {emailSuccess}
              </div>
            )}

            <div style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
            }}>
              <button
                onClick={() => setEmailDialog(false)}
                className="btn btn-secondary"
                style={{ padding: '8px 16px', fontSize: 12 }}
              >
                Cancel
              </button>
              <button
                onClick={sendEmailReport}
                disabled={emailLoading || !emailData.recipients.trim()}
                className="btn btn-primary"
                style={{ padding: '8px 16px', fontSize: 12 }}
              >
                {emailLoading ? (
                  <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite', marginRight: 4 }} /> Sending...</>
                ) : (
                  <><Send size={12} style={{ marginRight: 4 }} /> Send Report</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
