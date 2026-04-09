import { useState } from 'react';
import { Mail, Send, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import { useStore } from '../store/useStore';

/* ── Email validation ── */
function isValidEmail(email: string): boolean {
  const trimmed = email.trim();
  if (!trimmed) return false;
  // Must have exactly one @, non-empty local part, domain with at least one dot
  const parts = trimmed.split('@');
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  if (!local || !domain) return false;
  if (!domain.includes('.')) return false;
  // domain parts must be non-empty
  const domainParts = domain.split('.');
  if (domainParts.some(p => p.length === 0)) return false;
  return true;
}

function validateRecipients(input: string): { valid: boolean; emails: string[]; invalidEmails: string[] } {
  if (!input.trim()) return { valid: false, emails: [], invalidEmails: [] };
  const emails = input.split(',').map(e => e.trim()).filter(Boolean);
  const invalidEmails = emails.filter(e => !isValidEmail(e));
  return { valid: emails.length > 0 && invalidEmails.length === 0, emails, invalidEmails };
}

interface EmailReportModalProps {
  open: boolean;
  onClose: () => void;
  reportType: string;       // "pl_comparison" | "bs_comparison" | "revenue_comparison" | "cogs_comparison" | "cash_runway"
  reportLabel: string;       // Human-readable label e.g. "Income Statement"
}

export default function EmailReportModal({ open, onClose, reportType, reportLabel }: EmailReportModalProps) {
  const { company, period, dataset_id } = useStore();
  const [recipients, setRecipients] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [touched, setTouched] = useState(false);

  if (!open) return null;

  const validation = validateRecipients(recipients);
  const showEmailError = touched && recipients.trim().length > 0 && !validation.valid;
  const canSend = validation.valid && !sending;

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    setError('');
    setSuccess('');

    try {
      const emailList = validation.emails;
      await api.sendEmailReport({
        recipients: emailList,
        report_type: reportType,
        company_name: company || 'NYX Core Thinker LLC',
        period: period || 'Current Period',
        custom_message: customMessage || undefined,
        dataset_id: dataset_id || undefined,
      });
      setSuccess(`Report sent to ${emailList.join(', ')}`);
      setTimeout(() => { onClose(); setSuccess(''); setRecipients(''); setCustomMessage(''); }, 2500);
    } catch (err: any) {
      setError(err?.message || 'Failed to send email. Check SMTP configuration.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,.55)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
    }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: 'var(--bg1)', borderRadius: 16, width: '92%', maxWidth: 480,
        border: '1px solid var(--b2)', boxShadow: '0 24px 48px rgba(0,0,0,.3)',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          background: 'linear-gradient(135deg, #1B3A5C, #2563EB)',
          padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Mail size={20} style={{ color: '#fff' }} />
            <div>
              <div style={{ color: '#fff', fontWeight: 700, fontSize: 15 }}>Email Report</div>
              <div style={{ color: 'rgba(255,255,255,.7)', fontSize: 11 }}>{reportLabel}</div>
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'rgba(255,255,255,.15)', border: 'none', borderRadius: 8,
            padding: 6, cursor: 'pointer', color: '#fff', display: 'flex',
          }}>
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* From */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>From</label>
            <div style={{
              padding: '8px 12px', borderRadius: 8, background: 'var(--bg2)', border: '1px solid var(--b1)',
              fontSize: 13, color: 'var(--dim)', fontFamily: 'var(--mono)',
            }}>
              FinAI Reports &lt;keshelavanina93@gmail.com&gt;
            </div>
          </div>

          {/* Recipients */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>To (comma-separated)</label>
            <input
              type="text"
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              onBlur={() => setTouched(true)}
              placeholder="cfo@company.com, finance@company.com"
              style={{
                width: '100%', padding: '10px 12px',
                border: `1px solid ${showEmailError ? 'var(--rose)' : 'var(--b1)'}`,
                borderRadius: 8,
                background: 'var(--bg2)', color: 'var(--text)', fontSize: 13,
                outline: 'none', transition: 'border-color .2s',
              }}
              onFocus={(e) => (e.target.style.borderColor = showEmailError ? 'var(--rose)' : '#2563EB')}
            />
            {showEmailError && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4, marginTop: 4,
                fontSize: 10, color: 'var(--rose)',
              }}>
                <AlertCircle size={11} />
                {validation.invalidEmails.length > 0
                  ? `Invalid email${validation.invalidEmails.length > 1 ? 's' : ''}: ${validation.invalidEmails.join(', ')}`
                  : 'Enter a valid email address (e.g. user@domain.com)'}
              </div>
            )}
          </div>

          {/* Report info */}
          <div style={{
            display: 'flex', gap: 12, padding: '10px 14px', borderRadius: 8,
            background: 'rgba(37,99,235,.06)', border: '1px solid rgba(37,99,235,.12)',
          }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Company</div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{company || 'NYX Core Thinker LLC'}</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1 }}>Period</div>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{period || 'Current'}</div>
            </div>
          </div>

          {/* Custom message */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>Message (optional)</label>
            <textarea
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              placeholder="Please review the attached financial report..."
              rows={3}
              style={{
                width: '100%', padding: '10px 12px', border: '1px solid var(--b1)', borderRadius: 8,
                background: 'var(--bg2)', color: 'var(--text)', fontSize: 13, resize: 'vertical',
                outline: 'none', transition: 'border-color .2s',
              }}
              onFocus={(e) => (e.target.style.borderColor = '#2563EB')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--b1)')}
            />
          </div>

          {/* Success */}
          {success && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(16,185,129,.08)', border: '1px solid rgba(16,185,129,.2)',
              color: 'var(--emerald)', padding: '10px 14px', borderRadius: 8, fontSize: 12,
            }}>
              <CheckCircle2 size={16} /> {success}
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{
              background: 'rgba(239,68,68,.08)', border: '1px solid rgba(239,68,68,.2)',
              color: 'var(--rose)', padding: '10px 14px', borderRadius: 8, fontSize: 12,
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px', borderTop: '1px solid var(--b1)',
          display: 'flex', gap: 10, justifyContent: 'flex-end',
        }}>
          <button onClick={onClose} style={{
            padding: '8px 18px', borderRadius: 8, border: '1px solid var(--b2)',
            background: 'transparent', color: 'var(--text)', fontSize: 12, fontWeight: 500,
            cursor: 'pointer',
          }}>
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={!canSend}
            style={{
              padding: '8px 22px', borderRadius: 8, border: 'none',
              background: !canSend ? 'var(--dim)' : 'linear-gradient(135deg, #1B3A5C, #2563EB)',
              color: '#fff', fontSize: 12, fontWeight: 600,
              cursor: !canSend ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {sending ? (
              <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Sending...</>
            ) : (
              <><Send size={14} /> Send Report</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
