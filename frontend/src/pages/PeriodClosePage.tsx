import { useState, useEffect } from 'react';
import { Calendar, Lock, Unlock, CheckCircle, XCircle, AlertTriangle, Plus } from 'lucide-react';
import { api } from '../api/client';

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  open: { bg: '#10B98122', color: '#10B981', label: 'Open' },
  soft_close: { bg: '#F59E0B22', color: '#F59E0B', label: 'Soft Close' },
  hard_close: { bg: '#EF444422', color: '#EF4444', label: 'Closed' },
};

export default function PeriodClosePage() {
  const [periods, setPeriods] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [integrity, setIntegrity] = useState<any>(null);
  const [selectedPeriod, setSelectedPeriod] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [newPeriod, setNewPeriod] = useState({ period_name: '', fiscal_year: 2026, start_date: '', end_date: '' });

  const load = () => {
    setLoading(true);
    api.periodList().then((d: any) => setPeriods(d.periods || [])).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleClose = async (name: string, closeType: string) => {
    if (!confirm(`${closeType === 'hard_close' ? 'HARD CLOSE' : 'Soft close'} period "${name}"? ${closeType === 'hard_close' ? 'This will generate closing entries and prevent further posting.' : ''}`)) return;
    try {
      await api.periodClose(name, closeType);
      load();
    } catch (e: any) { alert(e.message); }
  };

  const handleReopen = async (name: string) => {
    if (!confirm(`Reopen period "${name}"? This is an admin action that will be logged.`)) return;
    try {
      await api.periodReopen(name);
      load();
    } catch (e: any) { alert(e.message); }
  };

  const handleIntegrity = async (name: string) => {
    setSelectedPeriod(name);
    try {
      const result = await api.periodIntegrity(name);
      setIntegrity(result);
    } catch (e: any) { alert(e.message); }
  };

  const handleCreate = async () => {
    try {
      await api.periodCreate({
        ...newPeriod,
        start_date: newPeriod.start_date + 'T00:00:00+04:00',
        end_date: newPeriod.end_date + 'T23:59:59+04:00',
      });
      setShowCreate(false);
      setNewPeriod({ period_name: '', fiscal_year: 2026, start_date: '', end_date: '' });
      load();
    } catch (e: any) { alert(e.message); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={22} /> Period Close Workflow
        </h1>
        <button onClick={() => setShowCreate(!showCreate)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8,
            background: 'var(--sky)', color: 'var(--heading)', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
          <Plus size={14} /> New Period
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="glass" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Create Fiscal Period</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 12 }}>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Period Name</label>
              <input value={newPeriod.period_name} onChange={e => setNewPeriod({ ...newPeriod, period_name: e.target.value })} placeholder="January 2026"
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Fiscal Year</label>
              <input type="number" value={newPeriod.fiscal_year} onChange={e => setNewPeriod({ ...newPeriod, fiscal_year: +e.target.value })}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>Start Date</label>
              <input type="date" value={newPeriod.start_date} onChange={e => setNewPeriod({ ...newPeriod, start_date: e.target.value })}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
            <div><label style={{ fontSize: 10, color: 'var(--muted)', display: 'block', marginBottom: 2 }}>End Date</label>
              <input type="date" value={newPeriod.end_date} onChange={e => setNewPeriod({ ...newPeriod, end_date: e.target.value })}
                style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--text)' }} /></div>
          </div>
          <button onClick={handleCreate} disabled={!newPeriod.period_name || !newPeriod.start_date}
            style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: 'var(--emerald)', color: 'var(--heading)', cursor: 'pointer', fontWeight: 600, fontSize: 12 }}>
            Create Period
          </button>
        </div>
      )}

      {/* Period List */}
      <div className="glass" style={{ padding: 16, overflow: 'auto' }}>
        {loading ? <div style={{ padding: 20, color: 'var(--muted)' }}>Loading...</div> : periods.length === 0 ? (
          <div style={{ padding: 30, textAlign: 'center', color: 'var(--muted)' }}>
            No fiscal periods created yet. Click "New Period" to create one.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead><tr style={{ borderBottom: '2px solid var(--b2)' }}>
              {['Period', 'Fiscal Year', 'Start', 'End', 'Status', 'Closed At', 'Actions'].map(h => (
                <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontSize: 10, textTransform: 'uppercase', color: 'var(--muted)' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>{periods.map((p, i) => {
              const s = STATUS_STYLE[p.status] || STATUS_STYLE.open;
              return (
                <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{p.period_name}</td>
                  <td style={{ padding: '8px 10px' }}>{p.fiscal_year}</td>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>{p.start_date?.split('T')[0]}</td>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>{p.end_date?.split('T')[0]}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 10, fontWeight: 600, background: s.bg, color: s.color }}>{s.label}</span>
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 11, color: 'var(--muted)' }}>{p.closed_at?.split('T')[0] || '—'}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => handleIntegrity(p.period_name)} title="Run Integrity Checks"
                        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--b2)', background: 'var(--bg2)', color: 'var(--sky)', cursor: 'pointer', fontSize: 11 }}>
                        <CheckCircle size={12} /> Check
                      </button>
                      {p.status === 'open' && <>
                        <button onClick={() => handleClose(p.period_name, 'soft_close')}
                          style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: 'var(--amber)', color: 'var(--heading)', cursor: 'pointer', fontSize: 11 }}>
                          Soft Close
                        </button>
                        <button onClick={() => handleClose(p.period_name, 'hard_close')}
                          style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: 'var(--rose)', color: 'var(--heading)', cursor: 'pointer', fontSize: 11 }}>
                          <Lock size={12} /> Hard Close
                        </button>
                      </>}
                      {(p.status === 'soft_close' || p.status === 'hard_close') && (
                        <button onClick={() => handleReopen(p.period_name)}
                          style={{ padding: '4px 8px', borderRadius: 4, border: 'none', background: 'var(--emerald)', color: 'var(--heading)', cursor: 'pointer', fontSize: 11 }}>
                          <Unlock size={12} /> Reopen
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}</tbody>
          </table>
        )}
      </div>

      {/* Integrity Check Results */}
      {integrity && (
        <div className="glass" style={{ padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>
            Integrity Checks — {selectedPeriod}
            <span style={{ marginLeft: 8, fontSize: 12, color: integrity.all_checks_passed ? 'var(--emerald)' : 'var(--rose)' }}>
              {integrity.all_checks_passed ? '✓ All Passed' : '✗ Issues Found'}
            </span>
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {integrity.checks?.map((c: any, i: number) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 6,
                background: c.passed ? '#10B98110' : '#EF444410', border: `1px solid ${c.passed ? '#10B98130' : '#EF444430'}` }}>
                {c.passed ? <CheckCircle size={16} style={{ color: 'var(--emerald)' }} /> : <XCircle size={16} style={{ color: 'var(--rose)' }} />}
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12 }}>{c.check.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>{c.detail}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--muted)' }}>{integrity.recommendation}</div>
        </div>
      )}
    </div>
  );
}
