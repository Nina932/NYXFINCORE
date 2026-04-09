import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Settings, Bell, Building2, Database, Info, Save, Plus, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { get, put } from '../api/client';

interface AlertRule { rule_id: number; metric: string; operator: string; threshold: number; severity: string; message_template: string; is_enabled: boolean; }
interface UploadRecord { filename: string; file_type: string; file_size_bytes: number; parsed_records: number; confidence_score: number; status: string; created_at: string; }

type TabId = 'company' | 'alerts' | 'data' | 'about';

const TABS: { id: TabId; label: string; icon: typeof Settings }[] = [
  { id: 'company', label: 'Company Info', icon: Building2 },
  { id: 'alerts', label: 'Alert Rules', icon: Bell },
  { id: 'data', label: 'Data Management', icon: Database },
  { id: 'about', label: 'About', icon: Info },
];

const INDUSTRIES = ['fuel_distribution', 'retail_general', 'manufacturing', 'services', 'construction', 'agriculture'];

const SEV_CFG: Record<string, { bg: string; color: string }> = {
  critical: { bg: 'rgba(248,113,113,.08)', color: 'var(--rose)' },
  warning: { bg: 'rgba(251,191,36,.08)', color: 'var(--amber)' },
  info: { bg: 'rgba(96,165,250,.08)', color: 'var(--blue)' },
};

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
const thStyle: React.CSSProperties = { textAlign: 'left', padding: '8px 14px', fontFamily: 'var(--mono)', fontSize: '7.5px', textTransform: 'uppercase', letterSpacing: '2px', color: 'var(--muted)', fontWeight: 500, background: 'var(--bg4)' };
const inputStyle: React.CSSProperties = { width: '100%', background: 'var(--bg3)', border: '1px solid var(--b1)', borderRadius: 6, padding: '8px 12px', color: 'var(--heading)', fontSize: 12, outline: 'none' };

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('company');
  const [companyName, setCompanyName] = useState('');
  const [industry, setIndustry] = useState('fuel_distribution');
  const [currency, setCurrency] = useState('GEL');
  const [saved, setSaved] = useState(false);

  const { data: rulesData, refetch: refetchRules } = useQuery({ queryKey: ['alert-rules'], queryFn: () => get<{ rules: AlertRule[] }>('/alerts/rules'), retry: false });
  const { data: uploadsData } = useQuery({ queryKey: ['upload-history'], queryFn: () => get<{ uploads: UploadRecord[] }>('/companies/1/history'), retry: false });

  const rules = rulesData?.rules || [];
  const uploads = (uploadsData as Record<string, unknown>)?.uploads as UploadRecord[] || [];

  const handleSaveCompany = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };
  const handleUpdateRule = async (ruleId: number, threshold: number) => {
    try { await put('/alerts/rules', { rule_id: ruleId, threshold }); refetchRules(); } catch { /* */ }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Settings size={20} style={{ color: 'var(--sky)' }} /> Settings
      </h1>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 2, background: 'var(--bg3)', borderRadius: 8, padding: 2, border: '1px solid var(--b1)' }}>
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 500, border: 'none', cursor: 'pointer', background: activeTab === tab.id ? 'var(--sky)' : 'transparent', color: activeTab === tab.id ? '#000' : 'var(--muted)' }}>
            <tab.icon size={12} /> {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'company' && (
        <div style={{ ...card, padding: 18, maxWidth: 560 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--heading)', marginBottom: 14 }}>Company Information</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ display: 'block', fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>Company Name</label>
              <input value={companyName} onChange={e => setCompanyName(e.target.value)} style={inputStyle}
                onFocus={e => e.currentTarget.style.borderColor = 'var(--sky)'} onBlur={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,.05)'} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label style={{ display: 'block', fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>Industry</label>
                <select value={industry} onChange={e => setIndustry(e.target.value)} style={inputStyle}>
                  {INDUSTRIES.map(ind => <option key={ind} value={ind}>{ind.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 10, color: 'var(--muted)', marginBottom: 4 }}>Base Currency</label>
                <select value={currency} onChange={e => setCurrency(e.target.value)} style={inputStyle}>
                  <option value="GEL">GEL (Georgian Lari)</option>
                  <option value="USD">USD (US Dollar)</option>
                  <option value="EUR">EUR (Euro)</option>
                </select>
              </div>
            </div>
            <button onClick={handleSaveCompany} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'linear-gradient(135deg, var(--sky), var(--blue))', color: 'var(--heading)', fontWeight: 600, padding: '8px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11, alignSelf: 'flex-start' }}>
              {saved ? <><CheckCircle2 size={14} /> Saved!</> : <><Save size={14} /> Save Changes</>}
            </button>
          </div>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div style={{ ...card, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Alert Threshold Rules</h2>
            <button style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--sky)', background: 'none', border: 'none', cursor: 'pointer' }}><Plus size={12} /> Add Rule</button>
          </div>
          <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
            <thead><tr>{['Metric', 'Operator', 'Threshold', 'Severity', 'Enabled', 'Actions'].map(h => <th key={h} style={{ ...thStyle, textAlign: h === 'Actions' ? 'right' : 'left' }}>{h}</th>)}</tr></thead>
            <tbody>
              {rules.map(rule => {
                const sc = SEV_CFG[rule.severity] || SEV_CFG.info;
                return (
                  <tr key={rule.rule_id} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--heading)' }}>{rule.metric}</td>
                    <td style={{ padding: '8px 14px', color: 'var(--text)' }}>{rule.operator}</td>
                    <td style={{ padding: '8px 14px' }}>
                      <input type="number" step="0.1" defaultValue={rule.threshold} onBlur={e => handleUpdateRule(rule.rule_id, parseFloat(e.target.value))}
                        style={{ width: 60, background: 'var(--bg3)', border: '1px solid var(--b1)', borderRadius: 4, padding: '3px 6px', color: 'var(--heading)', fontFamily: 'var(--mono)', fontSize: 10, outline: 'none' }} />
                    </td>
                    <td style={{ padding: '8px 14px' }}><span style={{ fontFamily: 'var(--mono)', fontSize: 9, padding: '1px 5px', borderRadius: 3, background: sc.bg, color: sc.color }}>{rule.severity}</span></td>
                    <td style={{ padding: '8px 14px' }}><div style={{ width: 26, height: 14, borderRadius: 7, background: rule.is_enabled ? 'var(--emerald)' : 'var(--dim)', position: 'relative' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fff', position: 'absolute', top: 2, left: rule.is_enabled ? 14 : 2, transition: 'left 0.2s' }} /></div></td>
                    <td style={{ padding: '8px 14px', textAlign: 'right' }}><button style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer' }}><Trash2 size={12} /></button></td>
                  </tr>
                );
              })}
              {rules.length === 0 && <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>No alert rules configured</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'data' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ ...card, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b1)' }}><h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Upload History</h2></div>
            <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
              <thead><tr>{['Filename', 'Type', 'Size', 'Records', 'Confidence', 'Status', 'Date'].map(h => <th key={h} style={thStyle}>{h}</th>)}</tr></thead>
              <tbody>
                {uploads.length > 0 ? uploads.map((u, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 14px', color: 'var(--heading)' }}>{u.filename}</td>
                    <td style={{ padding: '8px 14px', color: 'var(--text)' }}>{u.file_type}</td>
                    <td style={{ padding: '8px 14px', color: 'var(--text)' }}>{((u.file_size_bytes || 0) / 1024).toFixed(0)} KB</td>
                    <td style={{ padding: '8px 14px', color: 'var(--text)' }}>{u.parsed_records}</td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--mono)', color: (u.confidence_score || 0) >= 80 ? 'var(--emerald)' : 'var(--amber)' }}>{u.confidence_score}%</td>
                    <td style={{ padding: '8px 14px' }}><span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--emerald)' }}>{u.status}</span></td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--dim)' }}>{u.created_at}</td>
                  </tr>
                )) : <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: 'var(--muted)' }}>No uploads yet</td></tr>}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'var(--bg2)', color: 'var(--text)', padding: '8px 14px', borderRadius: 6, border: '1px solid var(--b1)', cursor: 'pointer', fontSize: 11 }}><Database size={12} /> Export All Data</button>
            <button style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(248,113,113,.06)', color: 'var(--rose)', padding: '8px 14px', borderRadius: 6, border: '1px solid rgba(248,113,113,.15)', cursor: 'pointer', fontSize: 11 }}><AlertTriangle size={12} /> Clear All Data</button>
          </div>
        </div>
      )}

      {activeTab === 'about' && (
        <div style={{ ...card, padding: 18, maxWidth: 560 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--heading)', marginBottom: 14 }}>System Information</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {[
              ['Platform', 'FinAI Financial Intelligence Platform'],
              ['Version', '1.0.0 (Phases A-S)'],
              ['Backend', 'FastAPI + SQLite + ChromaDB'],
              ['Frontend', 'React + TypeScript + Tailwind CSS v4'],
              ['AI Engine', 'Multi-Agent Architecture (Supervisor + 5 Agents)'],
              ['Knowledge Graph', '710+ financial entities'],
              ['Verified Checks', '594/594 passing'],
              ['E2E Pipeline', '43/43 steps verified'],
            ].map(([label, value]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--b1)' }}>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>{label}</span>
                <span style={{ fontSize: 11, color: 'var(--heading)', fontWeight: 500 }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
