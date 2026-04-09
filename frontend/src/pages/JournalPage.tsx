import { useState, useEffect } from 'react';
import { BookOpen, Plus, Check, X, RotateCcw, Shield, Send, Clock } from 'lucide-react';
import { api } from '../api/client';

const STATUS_COLORS: Record<string, string> = {
  draft: 'var(--amber)', posted: 'var(--emerald)', reversed: 'var(--rose)', submitted: 'var(--sky)',
};

function fmt(n: string | number | null): string {
  const v = typeof n === 'string' ? parseFloat(n) : n;
  if (!v || isNaN(v)) return '₾0';
  return `₾${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

interface Line { account_code: string; debit: string; credit: string; description: string; cost_center: string }

export default function JournalPage() {
  const [entries, setEntries] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [filter, setFilter] = useState('');

  // Form state
  const [postingDate, setPostingDate] = useState(new Date().toISOString().split('T')[0]);
  const [period, setPeriod] = useState('January 2026');
  const [fiscalYear, setFiscalYear] = useState(2026);
  const [description, setDescription] = useState('');
  const [reference, setReference] = useState('');
  const [lines, setLines] = useState<Line[]>([
    { account_code: '', debit: '0', credit: '0', description: '', cost_center: '' },
    { account_code: '', debit: '0', credit: '0', description: '', cost_center: '' },
  ]);

  const totalDr = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
  const totalCr = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const isBalanced = Math.abs(totalDr - totalCr) < 0.01 && totalDr > 0;

  const load = () => {
    setLoading(true);
    Promise.all([
      api.journalList(filter || undefined).then((d: any) => setEntries(d.entries || [])),
      api.journalStats().then((d: any) => setStats(d)),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const addLine = () => setLines([...lines, { account_code: '', debit: '0', credit: '0', description: '', cost_center: '' }]);
  const removeLine = (i: number) => { if (lines.length > 2) setLines(lines.filter((_, j) => j !== i)); };
  const updateLine = (i: number, field: keyof Line, val: string) => {
    const updated = [...lines];
    updated[i] = { ...updated[i], [field]: val };
    setLines(updated);
  };

  const handleCreate = async () => {
    try {
      await api.journalCreate({
        posting_date: postingDate + 'T00:00:00', period, fiscal_year: fiscalYear,
        description, reference, lines: lines.filter(l => l.account_code),
      });
      setShowForm(false);
      setDescription(''); setReference('');
      setLines([{ account_code: '', debit: '0', credit: '0', description: '', cost_center: '' },
                 { account_code: '', debit: '0', credit: '0', description: '', cost_center: '' }]);
      load();
    } catch (e: any) { alert(e.message); }
  };

  const handleAction = async (id: number, action: string) => {
    try {
      if (action === 'post') await api.journalPost(id);
      else if (action === 'submit') await api.journalSubmit(id);
      else if (action === 'approve') await api.journalApprove(id);
      else if (action === 'reject') {
        const reason = prompt('Rejection reason:');
        if (!reason) return;
        await api.journalReject(id, reason);
      }
      else if (action === 'reverse') await api.journalReverse(id);
      load();
      if (selected?.id === id) {
        api.journalDetail(id).then((d: any) => setSelected(d));
      }
    } catch (e: any) { alert(e.message); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}>
          <BookOpen size={22} /> Journal Entries
        </h1>
        <button onClick={() => setShowForm(!showForm)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
            background: 'var(--sky)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
          <Plus size={14} /> New Entry
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display: 'flex', gap: 12 }}>
          {[
            { label: 'Draft', value: stats.draft, color: 'var(--amber)' },
            { label: 'Submitted', value: stats.submitted, color: 'var(--sky)' },
            { label: 'Posted', value: stats.posted, color: 'var(--emerald)' },
            { label: 'Total', value: stats.total, color: 'var(--muted)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass" style={{ padding: '10px 16px', minWidth: 90, cursor: 'pointer' }}
              onClick={() => setFilter(label.toLowerCase() === 'total' ? '' : label.toLowerCase())}>
              <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>{label}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color }}>{value || 0}</div>
            </div>
          ))}
        </div>
      )}

      {/* Create Form */}
      {showForm && (
        <div className="glass" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>New Journal Entry</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Posting Date</label>
              <input type="date" value={postingDate} onChange={e => setPostingDate(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Period</label>
              <input value={period} onChange={e => setPeriod(e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Fiscal Year</label>
              <input type="number" value={fiscalYear} onChange={e => setFiscalYear(+e.target.value)}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Description</label>
              <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Journal description..."
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Reference</label>
              <input value={reference} onChange={e => setReference(e.target.value)} placeholder="INV-001..."
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
          </div>

          {/* Posting Lines */}
          <div style={{ marginBottom: 12, fontSize: 12, fontWeight: 600 }}>Posting Lines</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginBottom: 12 }}>
            <thead><tr style={{ borderBottom: '2px solid var(--b2)' }}>
              {['Account', 'Debit', 'Credit', 'Description', 'Cost Center', ''].map(h => (
                <th key={h} style={{ padding: '6px 8px', textAlign: 'left', fontSize: 10, textTransform: 'uppercase', color: 'var(--muted)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>{lines.map((line, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                <td style={{ padding: 4 }}><input value={line.account_code} onChange={e => updateLine(i, 'account_code', e.target.value)} placeholder="1110"
                  style={{ width: 80, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 12 }} /></td>
                <td style={{ padding: 4 }}><input value={line.debit} onChange={e => updateLine(i, 'debit', e.target.value)}
                  style={{ width: 100, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 12, textAlign: 'right' }} /></td>
                <td style={{ padding: 4 }}><input value={line.credit} onChange={e => updateLine(i, 'credit', e.target.value)}
                  style={{ width: 100, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 12, textAlign: 'right' }} /></td>
                <td style={{ padding: 4 }}><input value={line.description} onChange={e => updateLine(i, 'description', e.target.value)}
                  style={{ width: '100%', padding: '4px 6px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 12 }} /></td>
                <td style={{ padding: 4 }}><input value={line.cost_center} onChange={e => updateLine(i, 'cost_center', e.target.value)} placeholder=""
                  style={{ width: 80, padding: '4px 6px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', fontSize: 12 }} /></td>
                <td style={{ padding: 4 }}><button onClick={() => removeLine(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--rose)', fontSize: 14 }}>×</button></td>
              </tr>
            ))}</tbody>
            <tfoot><tr style={{ borderTop: '2px solid var(--b2)' }}>
              <td style={{ padding: '6px 8px', fontWeight: 700 }}>TOTAL</td>
              <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, fontFamily: 'var(--mono)', color: isBalanced ? 'var(--emerald)' : 'var(--rose)' }}>{fmt(totalDr)}</td>
              <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700, fontFamily: 'var(--mono)', color: isBalanced ? 'var(--emerald)' : 'var(--rose)' }}>{fmt(totalCr)}</td>
              <td colSpan={3} style={{ padding: '6px 8px', fontSize: 11, color: isBalanced ? 'var(--emerald)' : 'var(--rose)' }}>
                {isBalanced ? '✓ Balanced' : `✗ Imbalance: ${fmt(Math.abs(totalDr - totalCr))}`}
              </td>
            </tr></tfoot>
          </table>

          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={addLine} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)', cursor: 'pointer', fontSize: 12 }}>+ Add Line</button>
            <button onClick={handleCreate} disabled={!isBalanced || !description}
              style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: isBalanced && description ? 'var(--emerald)' : 'var(--b2)',
                color: '#fff', cursor: isBalanced && description ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: 12 }}>
              Create Draft
            </button>
          </div>
        </div>
      )}

      {/* Journal List */}
      <div className="glass" style={{ padding: 16, overflow: 'auto' }}>
        {loading ? <div style={{ color: 'var(--muted)', padding: 20 }}>Loading...</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead><tr style={{ borderBottom: '2px solid var(--b2)' }}>
              {['Doc #', 'Date', 'Period', 'Description', 'DR', 'CR', 'Status', 'Actions'].map(h => (
                <th key={h} style={{ padding: '8px 10px', textAlign: h === 'Description' ? 'left' : 'center', fontSize: 10, textTransform: 'uppercase', color: 'var(--muted)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>{entries.map(e => (
              <tr key={e.id} style={{ borderBottom: '1px solid var(--b1)', cursor: 'pointer' }}
                onClick={() => api.journalDetail(e.id).then((d: any) => setSelected(d))}>
                <td style={{ padding: '8px 10px', fontFamily: 'var(--mono)', fontSize: 11 }}>{e.document_number}</td>
                <td style={{ padding: '8px 10px', textAlign: 'center', fontSize: 11 }}>{e.posting_date?.split('T')[0]}</td>
                <td style={{ padding: '8px 10px', textAlign: 'center', fontSize: 11 }}>{e.period}</td>
                <td style={{ padding: '8px 10px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.description}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(e.total_debit)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{fmt(e.total_credit)}</td>
                <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                  <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600,
                    background: `${STATUS_COLORS[e.status] || 'var(--muted)'}22`, color: STATUS_COLORS[e.status] }}>{e.status}</span>
                </td>
                <td style={{ padding: '8px 10px', textAlign: 'center' }} onClick={ev => ev.stopPropagation()}>
                  <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                    {e.status === 'draft' && <>
                      <button onClick={() => handleAction(e.id, 'post')} title="Post" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--emerald)' }}><Check size={14} /></button>
                      <button onClick={() => handleAction(e.id, 'submit')} title="Submit for Approval" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--sky)' }}><Send size={14} /></button>
                    </>}
                    {e.status === 'submitted' && <>
                      <button onClick={() => handleAction(e.id, 'approve')} title="Approve" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--emerald)' }}><Check size={14} /></button>
                      <button onClick={() => handleAction(e.id, 'reject')} title="Reject" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--rose)' }}><X size={14} /></button>
                    </>}
                    {e.status === 'posted' && <button onClick={() => handleAction(e.id, 'reverse')} title="Reverse" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--amber)' }}><RotateCcw size={14} /></button>}
                  </div>
                </td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>

      {/* Detail Panel */}
      {selected && (
        <div className="glass" style={{ padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700 }}>{selected.document_number} — {selected.description}</h3>
            <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}><X size={16} /></button>
          </div>
          <div style={{ display: 'flex', gap: 16, marginBottom: 12, fontSize: 12 }}>
            <span><strong>Status:</strong> <span style={{ color: STATUS_COLORS[selected.status] }}>{selected.status}</span></span>
            <span><strong>Period:</strong> {selected.period}</span>
            <span><strong>Date:</strong> {selected.posting_date?.split('T')[0]}</span>
            {selected.document_hash && <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Shield size={12} /> Hash: {selected.document_hash?.substring(0, 12)}...</span>}
          </div>
          {selected.lines && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead><tr style={{ borderBottom: '2px solid var(--b2)' }}>
                {['#', 'Account', 'Debit', 'Credit', 'Description'].map(h => (
                  <th key={h} style={{ padding: '6px 8px', textAlign: h === 'Description' ? 'left' : 'right', fontSize: 10, color: 'var(--muted)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>{selected.lines.map((l: any) => (
                <tr key={l.line_number} style={{ borderBottom: '1px solid var(--b1)' }}>
                  <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--muted)' }}>{l.line_number}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{l.account_code}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)', color: parseFloat(l.debit) > 0 ? 'var(--heading)' : 'var(--dim)' }}>{fmt(l.debit)}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)', color: parseFloat(l.credit) > 0 ? 'var(--heading)' : 'var(--dim)' }}>{fmt(l.credit)}</td>
                  <td style={{ padding: '6px 8px' }}>{l.description}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
