import { useState, useEffect } from 'react';
import {
  Eye, Search, Upload, CheckCircle, AlertTriangle, XCircle,
  ChevronRight, FileText, Scale, DollarSign, ArrowRight, Filter, X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';

const DEST_CONFIG: Record<string, { color: string; icon: any; page: string }> = {
  'P&L': { color: 'var(--violet)', icon: FileText, page: '/pnl' },
  'Balance Sheet': { color: 'var(--sky)', icon: Scale, page: '/balance-sheet' },
};

function fmt(n: number | null | undefined): string {
  if (n == null || isNaN(n) || n === 0) return '—';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${n < 0 ? '-' : ''}₾${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${n < 0 ? '-' : ''}₾${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${n < 0 ? '-' : ''}₾${(abs / 1e3).toFixed(1)}K`;
  return `₾${n.toFixed(0)}`;
}

function fmtFull(n: number | null | undefined): string {
  if (n == null || isNaN(n) || n === 0) return '—';
  return `${n < 0 ? '-' : ''}₾${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

type ParsedRow = {
  code: string;
  name: string;
  value: number;
  field_key: string;
  account_class: number;
  statement: string;
  is_total: boolean;
  destination: string;
  destination_page: string;
  source: string;
  confidence: number;
  status: string;
};

/* ─── COA Hierarchical Browser Component ─── */
const CLASS_META: Record<number, { label: string; statement: string; color: string; icon: any }> = {
  1: { label: 'Current Assets', statement: 'Balance Sheet', color: '#4C90F0', icon: Scale },
  2: { label: 'Noncurrent Assets', statement: 'Balance Sheet', color: '#2D72D2', icon: Scale },
  3: { label: 'Current Liabilities', statement: 'Balance Sheet', color: '#E76A6E', icon: Scale },
  4: { label: 'Noncurrent Liabilities', statement: 'Balance Sheet', color: '#CD4246', icon: Scale },
  5: { label: 'Equity', statement: 'Balance Sheet', color: '#32A467', icon: Scale },
  6: { label: 'Revenue', statement: 'P&L', color: '#32A467', icon: DollarSign },
  7: { label: 'Cost of Sales', statement: 'P&L', color: '#EC9A3C', icon: FileText },
  8: { label: 'Operating Expenses', statement: 'P&L', color: '#7961DB', icon: FileText },
  9: { label: 'Other P&L', statement: 'P&L', color: '#738091', icon: FileText },
};

function COABrowser({ accounts, search, navigate }: { accounts: any[]; search: string; navigate: any }) {
  const [expandedClasses, setExpandedClasses] = useState<Set<number>>(new Set());
  const [expandedPrefixes, setExpandedPrefixes] = useState<Set<string>>(new Set());
  const [selectedAccount, setSelectedAccount] = useState<any>(null);

  // Group accounts by class → prefix2 (e.g., 11, 12, 31) → individual accounts
  const grouped: Record<number, Record<string, any[]>> = {};
  accounts.forEach((obj: any) => {
    const p = obj.properties || {};
    const cls = p.account_class || parseInt(p.code?.[0]) || 0;
    if (!cls) return;
    if (search) {
      const s = search.toLowerCase();
      if (!(p.code || '').toLowerCase().includes(s) && !(p.name_en || '').toLowerCase().includes(s) && !(p.name_ka || '').toLowerCase().includes(s)) return;
    }
    const prefix2 = (p.code || '').substring(0, 2);
    if (!grouped[cls]) grouped[cls] = {};
    if (!grouped[cls][prefix2]) grouped[cls][prefix2] = [];
    grouped[cls][prefix2].push(obj);
  });

  const toggleClass = (cls: number) => {
    const next = new Set(expandedClasses);
    next.has(cls) ? next.delete(cls) : next.add(cls);
    setExpandedClasses(next);
  };

  const togglePrefix = (prefix: string) => {
    const next = new Set(expandedPrefixes);
    next.has(prefix) ? next.delete(prefix) : next.add(prefix);
    setExpandedPrefixes(next);
  };

  return (
    <div style={{ display: 'flex', gap: 16, minHeight: 500 }}>
      {/* Left: Hierarchy Tree */}
      <div style={{ flex: 1, overflowY: 'auto', maxHeight: '70vh', paddingRight: 8 }} className="custom-scrollbar">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(cls => {
          const meta = CLASS_META[cls];
          const prefixes = grouped[cls] || {};
          const totalInClass = Object.values(prefixes).reduce((s, arr) => s + arr.length, 0);
          if (totalInClass === 0) return null;
          const isExpanded = expandedClasses.has(cls);
          const Icon = meta.icon;

          return (
            <div key={cls} style={{ marginBottom: 4 }}>
              {/* Class Header */}
              <button onClick={() => toggleClass(cls)} style={{
                display: 'flex', alignItems: 'center', gap: 12, width: '100%',
                padding: '10px 14px', border: 'none', cursor: 'pointer', textAlign: 'left',
                background: isExpanded ? 'rgba(255,255,255,0.03)' : 'rgba(15,20,34,0.4)',
                borderLeft: `4px solid ${meta.color}`,
                borderRadius: 2, transition: 'all .2s',
                marginBottom: 2
              }}>
                <ChevronRight size={14} style={{ color: meta.color, transform: isExpanded ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }} />
                <Icon size={14} style={{ color: meta.color }} />
                <span style={{ flex: 1, fontSize: 11, fontWeight: 900, color: 'var(--heading)', fontFamily: 'var(--mono)', letterSpacing: 0.5 }}>
                  {cls}000 // {meta.label.toUpperCase()}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: meta.color, fontWeight: 800, background: `${meta.color}15`, padding: '2px 6px', borderRadius: 2 }}>{totalInClass}_ACCT</span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: 2 }}>{meta.statement.toUpperCase()}</span>
                </div>
              </button>

              {/* Sub-groups */}
              {isExpanded && Object.entries(prefixes).sort(([a], [b]) => a.localeCompare(b)).map(([prefix, accts]) => {
                const isPrefixExpanded = expandedPrefixes.has(prefix);
                const firstName = (accts[0]?.properties?.name_en || '').split(' // ')[0];
                return (
                  <div key={prefix} style={{ marginLeft: 24, borderLeft: '1px solid var(--b1)', marginBottom: 2 }}>
                    <button onClick={() => togglePrefix(prefix)} style={{
                      display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                      padding: '8px 12px', border: 'none', cursor: 'pointer', textAlign: 'left',
                      background: isPrefixExpanded ? 'rgba(255,255,255,0.02)' : 'transparent',
                      transition: 'all .2s'
                    }}>
                      <ChevronRight size={12} style={{ color: 'var(--muted)', transform: isPrefixExpanded ? 'rotate(90deg)' : 'none' }} />
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 800 }}>{prefix}XX</span>
                      <span style={{ fontSize: 10, color: 'var(--muted)', flex: 1, fontWeight: 500 }}>
                        {accts.length > 1 ? `${accts.length.toString().padStart(2, '0')} ACCOUNTS_DETECTED` : firstName.toUpperCase()}
                      </span>
                    </button>

                    {/* Individual accounts */}
                    {isPrefixExpanded && accts.sort((a: any, b: any) => (a.properties?.code || '').localeCompare(b.properties?.code || '')).map((obj: any) => {
                      const p = obj.properties || {};
                      const isSelected = selectedAccount?.object_id === obj.object_id;
                      return (
                        <button key={obj.object_id} onClick={() => setSelectedAccount(isSelected ? null : obj)} style={{
                          display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                          padding: '6px 12px', paddingLeft: 36, border: 'none', cursor: 'pointer', textAlign: 'left',
                          background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                          borderLeft: isSelected ? '2px solid var(--sky)' : '2px solid transparent',
                          transition: 'all .1s'
                        }}>
                          <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', width: 60, flexShrink: 0, fontWeight: 700 }}>{p.code}</span>
                          <span style={{ fontSize: 11, color: isSelected ? 'var(--heading)' : 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: isSelected ? 700 : 500 }}>
                            {(p.ifrs_bs_line || p.ifrs_pl_line || p.name_ka || p.name_en || '').toUpperCase()}
                          </span>
                          <span style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', fontWeight: 800 }}>{p.side || 'N/A'}</span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Right: Selected Account Detail */}
      <div style={{ width: 340, flexShrink: 0 }}>
        {selectedAccount ? (
          <div className="glass-interactive" style={{ padding: 20, position: 'sticky', top: 0, border: '1px solid var(--sky-muted)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 800, marginBottom: 4 }}>OBJECT_IDENTIFIER</div>
                <div style={{ fontSize: 18, fontWeight: 900, color: 'var(--heading)', letterSpacing: -0.5, fontFamily: 'var(--mono)' }}>
                  {selectedAccount.properties?.code}
                </div>
              </div>
              <button 
                onClick={() => setSelectedAccount(null)}
                className="btn-minimal" 
                style={{ padding: 4 }}
              >
                <X size={14} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* Content sections */}
              <div>
                <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', marginBottom: 6, letterSpacing: 1 }}>MAPPING_DESCRIPTOR</div>
                <div style={{ padding: '8px 12px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--b1)', borderRadius: 2 }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--sky)', marginBottom: 4 }}>
                    {(selectedAccount.properties?.ifrs_bs_line || selectedAccount.properties?.ifrs_pl_line || 'UNMAPPED_ENTITY').toUpperCase()}
                  </div>
                  {selectedAccount.properties?.name_ka && (
                    <div style={{ fontSize: 10, color: 'var(--text)', marginBottom: 2, display: 'flex', gap: 8 }}>
                      <span style={{ color: 'var(--dim)', fontWeight: 800 }}>KA::</span> {selectedAccount.properties.name_ka}
                    </div>
                  )}
                  {selectedAccount.properties?.name_en && (
                    <div style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', gap: 8 }}>
                      <span style={{ color: 'var(--dim)', fontWeight: 800 }}>RU::</span> {selectedAccount.properties.name_en}
                    </div>
                  )}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', marginBottom: 6, letterSpacing: 1 }}>CLASSIFICATION_METADATA</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {[
                    ['IFRS_SECTION', selectedAccount.properties?.ifrs_section],
                    ['STATEMENT_TARGET', selectedAccount.properties?.statement === 'income_statement' ? 'P&L' : 'BALANCE_SHEET'],
                    ['NORMAL_BALANCE', selectedAccount.properties?.side],
                    ['TYPE_KEY', selectedAccount.properties?.account_type],
                    ['CLASS_INDEX', selectedAccount.properties?.account_class],
                  ].filter(([, v]) => v).map(([label, val]) => (
                    <div key={label as string} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 500 }}>{label}</span>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--heading)', fontWeight: 800 }}>{String(val).toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedAccount.markings?.length > 0 && (
                <div>
                  <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', marginBottom: 6, letterSpacing: 1 }}>GOVERNANCE_MARKINGS</div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {selectedAccount.markings.map((m: string) => (
                      <span key={m} style={{ fontSize: 9, fontFamily: 'var(--mono)', background: 'rgba(56, 189, 248, 0.1)', color: 'var(--sky)', padding: '2px 8px', borderRadius: 2, border: '1px solid rgba(56, 189, 248, 0.2)', fontWeight: 800 }}>{m.toUpperCase()}</span>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ marginTop: 8 }}>
                <button 
                  className="btn-minimal" 
                  style={{ width: '100%', height: 36, background: 'var(--sky)', color: 'var(--heading)', fontWeight: 900, fontSize: 10, letterSpacing: 1 }}
                  onClick={() => navigate(selectedAccount.properties?.account_class <= 5 ? '/balance-sheet' : selectedAccount.properties?.account_class === 6 ? '/revenue' : '/costs')}
                >
                  NAVIGATE_TO_TARGET_STATEMENT <ArrowRight size={12} />
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="glass" style={{ padding: 40, textAlign: 'center', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', opacity: 0.5, border: '1px dashed var(--b1)' }}>
            <Eye size={48} style={{ color: 'var(--dim)', marginBottom: 16 }} />
            <div style={{ fontSize: 12, color: 'var(--heading)', fontWeight: 900, fontFamily: 'var(--mono)', letterSpacing: 1 }}>WAITING_FOR_SELECTION</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 8, maxWidth: 200, lineHeight: 1.5 }}>SELECT AN ENTITY FROM THE LEDGER HIERARCHY TO INSPECT CORE ATTRIBUTES</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function TransactionsPage() {
  const navigate = useNavigate();
  const { pnl, company, period, doc_type, account_classifications } = useStore();
  const [search, setSearch] = useState('');
  const [filterStatement, setFilterStatement] = useState<string | null>(null);
  const [parsedData, setParsedData] = useState<any>(null);
  const [ontologyAccounts, setOntologyAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'parsed' | 'ontology'>('parsed');

  // Fetch actual parsed financial data from backend
  useEffect(() => {
    if (period) {
      setLoading(true);
      fetch(`/api/ontology/parsed-data/${period}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setParsedData(d); })
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [period]);

  // Also fetch ontology accounts for the classification view
  useEffect(() => {
    fetch('/api/ontology/objects?type=Account&limit=500')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.objects) setOntologyAccounts(d.objects); })
      .catch(() => {});
  }, []);

  const rows: ParsedRow[] = parsedData?.accounts || [];
  const filtered = rows.filter(r => {
    if (search) {
      const s = search.toLowerCase();
      if (!r.code.toLowerCase().includes(s) && !r.name.toLowerCase().includes(s)) return false;
    }
    if (filterStatement === 'pl' && r.statement !== 'income_statement') return false;
    if (filterStatement === 'bs' && r.statement !== 'balance_sheet') return false;
    return true;
  });

  const plRows = rows.filter(r => r.statement === 'income_statement');
  const bsRows = rows.filter(r => r.statement === 'balance_sheet');
  const totalValue = rows.reduce((s, r) => s + Math.abs(r.value), 0);
  const ontoCount = ontologyAccounts.length;

  if (!pnl && !parsedData) {
    return (
      <div className="empty-state" style={{ height: '60vh' }}>
        <Eye size={36} className="empty-state-icon" />
        <div className="empty-state-title">Data Transparency</div>
        <div className="empty-state-desc">Upload a Trial Balance or P&L report to see how every number is parsed, classified, and routed</div>
        <button className="btn btn-primary" onClick={() => navigate('/library')} style={{ marginTop: 8 }}>
          <Upload size={13} /> Upload Data
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 4px', animation: 'slide-up 0.4s ease both', position: 'relative', overflow: 'hidden' }}>
      <div className="scanline" />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--b1)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 900, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, margin: 0, letterSpacing: -0.5 }}>
            <Eye size={22} style={{ color: 'var(--sky)' }} /> DATA_TRANSPARENCY_HUB
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
            {parsedData?.company || company} // PERIOD::{period} // TRACE::{doc_type === 'trial_balance' ? 'TRIAL_BALANCE' : 'REP_EXTRACT'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {/* Tab toggle */}
          <div style={{ display: 'flex', background: 'rgba(15,20,34,0.4)', padding: 2, borderRadius: 2, border: '1px solid var(--b1)' }}>
            <button onClick={() => setTab('parsed')} style={{
              padding: '6px 16px', fontSize: 10, fontWeight: 800, border: 'none', cursor: 'pointer',
              background: tab === 'parsed' ? 'var(--sky)' : 'transparent',
              color: tab === 'parsed' ? '#000' : 'var(--muted)',
              borderRadius: 2, fontFamily: 'var(--mono)', transition: 'all 0.2s'
            }}>PARSED_NODES ({rows.length})</button>
            <button onClick={() => setTab('ontology')} style={{
              padding: '6px 16px', fontSize: 10, fontWeight: 800, border: 'none', cursor: 'pointer',
              background: tab === 'ontology' ? 'var(--sky)' : 'transparent',
              color: tab === 'ontology' ? '#000' : 'var(--muted)',
              borderRadius: 2, fontFamily: 'var(--mono)', transition: 'all 0.2s'
            }}>COA_MAPPING ({ontoCount})</button>
          </div>
          <div className="input" style={{ display: 'flex', alignItems: 'center', gap: 8, width: 220, padding: '0 12px', height: 32, borderRadius: 2, background: 'rgba(15,20,34,0.6)' }}>
            <Search size={12} style={{ color: 'var(--dim)', flexShrink: 0 }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="FILTER_ENTITIES..."
              style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 11, width: '100%', fontFamily: 'var(--mono)' }} />
          </div>
        </div>
      </div>

      {/* ── PARSED DATA TAB ── */}
      {tab === 'parsed' && (
        <>
          {/* Summary Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
            <div className="glass-interactive" style={{ padding: '16px 20px', borderLeft: '3px solid var(--b2)', cursor: 'pointer' }} onClick={() => setFilterStatement(null)}>
              <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', marginBottom: 8 }}>TOTAL_PARSED_SEQ</div>
              <div style={{ fontSize: 24, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--heading)', letterSpacing: -1 }}>{rows.length}</div>
            </div>
            <div className="glass-interactive" style={{ padding: '16px 20px', borderLeft: '3px solid var(--violet)', cursor: 'pointer' }} onClick={() => setFilterStatement('pl')}>
              <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1, color: 'var(--violet)', marginBottom: 8 }}>P&L_FLIGHT_NODES</div>
              <div style={{ fontSize: 24, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--violet)', letterSpacing: -1 }}>{plRows.length}</div>
            </div>
            <div className="glass-interactive" style={{ padding: '16px 20px', borderLeft: '3px solid var(--sky)', cursor: 'pointer' }} onClick={() => setFilterStatement('bs')}>
              <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1, color: 'var(--sky)', marginBottom: 8 }}>BS_POSITION_NODES</div>
              <div style={{ fontSize: 24, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--sky)', letterSpacing: -1 }}>{bsRows.length}</div>
            </div>
            <div className="glass-interactive" style={{ padding: '16px 20px', borderLeft: '3px solid var(--emerald)' }}>
              <div style={{ fontSize: 9, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1, color: 'var(--emerald)', marginBottom: 8 }}>PARSING_ACCURACY</div>
              <div style={{ fontSize: 24, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--emerald)', letterSpacing: -1 }}>100%</div>
            </div>
          </div>

          {/* Table Container */}
          <div className="glass" style={{ padding: 0, overflow: 'hidden', borderBottom: 'none' }}>
             <div style={{ padding: '12px 16px', background: 'rgba(15,20,34,0.4)', borderBottom: '1px solid var(--b1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 1 }}>
                  LEDGER_DATA_STREAM {filterStatement && `// FILTER::${filterStatement.toUpperCase()}`}
                </div>
                {filterStatement && (
                  <button onClick={() => setFilterStatement(null)} className="btn-minimal" style={{ fontSize: 9, padding: '2px 8px', color: 'var(--sky)' }}>CLEAR_FILTER</button>
                )}
             </div>
             
             <div style={{ overflowX: 'auto', maxHeight: '55vh' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 100 }}>REF_CODE</th>
                      <th>LINE_ITEM_DESCRIPTOR</th>
                      <th style={{ width: 140 }}>DESTINATION</th>
                      <th className="right" style={{ width: 140 }}>AMOUNT (₾)</th>
                      <th style={{ textAlign: 'center', width: 80 }}>STATE</th>
                      <th style={{ width: 40 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row, i) => {
                      const destCfg = DEST_CONFIG[row.destination] || { color: 'var(--dim)', icon: FileText, page: '/pnl' };
                      const DestIcon = destCfg.icon;
                      const indent = row.code.split('.').length - 1;
                      return (
                        <tr key={i} className={row.is_total ? 'total' : ''} style={{ background: row.is_total ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                          <td className="mono" style={{ fontSize: 10, color: 'var(--sky)', fontWeight: 700 }}>{row.code}</td>
                          <td style={{
                            paddingLeft: `${16 + indent * 20}px`,
                            fontWeight: row.is_total ? 900 : 500,
                            color: row.is_total ? 'var(--heading)' : 'var(--text)',
                            fontSize: row.is_total ? 12 : 11,
                            letterSpacing: row.is_total ? -0.2 : 0
                          }}>
                            {row.name.toUpperCase()}
                          </td>
                          <td>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 9, color: destCfg.color, fontWeight: 800, background: `${destCfg.color}08`, padding: '3px 8px', borderRadius: 2, border: `1px solid ${destCfg.color}22` }}>
                              <DestIcon size={10} /> {row.destination.toUpperCase()}
                            </div>
                          </td>
                          <td className="mono right" style={{
                            fontWeight: row.is_total ? 900 : 700,
                            color: row.value < 0 ? 'var(--rose)' : row.value > 0 ? 'var(--heading)' : 'var(--dim)',
                            fontSize: 12,
                          }}>
                            {fmtFull(row.value)}
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <div style={{ display: 'inline-flex', padding: 4, borderRadius: '50%', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                              <CheckCircle size={10} style={{ color: 'var(--emerald)' }} />
                            </div>
                          </td>
                          <td>
                            <button onClick={() => navigate(row.destination_page)} className="btn-minimal" style={{ padding: 4 }}>
                              <ArrowRight size={12} />
                            </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </div>
        </>
      )}

      {/* ── ONTOLOGY TAB ── */}
      {tab === 'ontology' && (
        <div style={{ animation: 'fade-in 0.3s ease both' }}>
           <COABrowser accounts={ontologyAccounts} search={search} navigate={navigate} />
        </div>
      )}

      {/* Lineage Footer */}
      <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', display: 'flex', gap: 12, padding: '12px 4px', borderTop: '1px solid var(--b1)', opacity: 0.6, letterSpacing: 0.5 }}>
        <span style={{ color: 'var(--sky)' }}>PIPELINE_TRACE::</span>
        <span>UPLOAD</span>
        <ChevronRight size={10} style={{ alignSelf: 'center' }} />
        <span>PARSING_ENGINE</span>
        <ChevronRight size={10} style={{ alignSelf: 'center' }} />
        <span>{doc_type === 'trial_balance' ? 'TB_NORMALIZATION' : 'REP_FIELD_EXTRACTION'}</span>
        <ChevronRight size={10} style={{ alignSelf: 'center' }} />
        <span>LEDGER_PERSISTENCE</span>
        <ChevronRight size={10} style={{ alignSelf: 'center' }} />
        <span>ONTOLOGY_SYNC</span>
      </div>
    </div>
  );
}
