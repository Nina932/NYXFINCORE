import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Globe, RefreshCcw, Layers, Info, CheckCircle2, AlertTriangle, Building2, ArrowRight } from 'lucide-react';
import { api } from '../api/client';

interface ConsolidationStatus {
  entity_count: number;
  group_structure: { parent: string; subsidiaries: [string, number][] }[];
  has_last_result: boolean;
}

interface SeedResult {
  status: string;
  parent: string;
  subsidiaries: string[];
}

interface ConsolidationResult {
  period?: string;
  parent_financials?: Record<string, number>;
  consolidated?: Record<string, number>;
  eliminations?: { type: string; entity?: string; account?: string; debit?: number; credit?: number }[];
  nci?: Record<string, number>;
  reconciliation?: Record<string, unknown>;
}

export default function ConsolidationPage() {
  const [status, setStatus] = useState<ConsolidationStatus | null>(null);
  const [result, setResult] = useState<ConsolidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState('');

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const s = await api.consolidationStatus() as unknown as ConsolidationStatus;
      setStatus(s);
      if (s.has_last_result) {
        try {
          const r = await (api as any).consolidationResult?.() ||
            await fetch('/api/consolidation/results/latest', { headers: { 'Content-Type': 'application/json' } }).then(r => r.ok ? r.json() : null);
          if (r) setResult(r);
        } catch { /* no result yet */ }
      }
    } catch (err) {
      console.error('Consolidation fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const handleSeed = async () => {
    setSeeding(true);
    setError('');
    try {
      await api.consolidationSeed();
      await fetchStatus();
    } catch (err) {
      setError('Seeding failed: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setSeeding(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setError('');
    try {
      const res = await api.consolidationRun() as unknown as ConsolidationResult;
      setResult(res);
      await fetchStatus();
    } catch (err) {
      setError('Consolidation failed: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setRunning(false);
    }
  };

  const treeOption = useMemo(() => {
    if (!status || status.entity_count === 0) return {};
    const structs = status.group_structure;
    if (!structs.length) return {};

    const treeData = {
      name: structs[0].parent || 'Group Parent',
      symbolSize: 40,
      itemStyle: { color: '#00D8FF' },
      children: (structs[0].subsidiaries || []).map(([name, pct]) => ({
        name: `${name} (${pct}%)`,
        symbolSize: 28,
        itemStyle: { color: pct === 100 ? '#48BB78' : '#9F7AEA' },
      }))
    };

    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'tree',
        data: [treeData],
        top: '10%', bottom: '10%', left: '20%', right: '20%',
        symbol: 'emptyCircle',
        orient: 'LR',
        expandAndCollapse: false,
        label: {
          position: 'left', rotate: 0, verticalAlign: 'middle', align: 'right',
          fontSize: 11, color: '#E2E8F0', fontFamily: 'JetBrains Mono, monospace'
        },
        leaves: { label: { position: 'right', align: 'left' } },
        lineStyle: { color: '#00D8FF', opacity: 0.4, width: 2 },
        emphasis: { focus: 'descendant' },
        animationDurationUpdate: 750
      }]
    };
  }, [status]);

  const consolidated = result?.consolidated || {};
  const eliminations = result?.eliminations || [];
  const nci = result?.nci || {};

  const formatVal = (v: number) => {
    const abs = Math.abs(v);
    if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
    return v.toFixed(0);
  };

  if (loading && !status) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 8 }}>
        <RefreshCcw size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--sky)' }} />
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>Loading consolidation engine...</span>
      </div>
    );
  }

  // Empty state — no entities registered
  if (status && status.entity_count === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Globe size={20} style={{ color: 'var(--sky)' }} /> Multi-Entity Consolidation
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>IFRS 10 / ASC 810 Compliant Engine</p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 20 }}>
          <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'rgba(0,216,255,0.06)', border: '1px solid rgba(0,216,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Building2 size={36} style={{ color: 'var(--sky)' }} />
          </div>
          <div style={{ textAlign: 'center', maxWidth: 440 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', marginBottom: 8 }}>No Entities Registered</h2>
            <p style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.7 }}>
              Seed the consolidation engine with parent + subsidiary entities to run IFRS 10 group consolidation with intercompany elimination.
            </p>
          </div>
          <button onClick={handleSeed} disabled={seeding} className="btn btn-primary" style={{ padding: '10px 24px', fontSize: 12 }}>
            {seeding ? <RefreshCcw size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Layers size={14} />}
            {seeding ? 'Seeding...' : 'Seed Subsidiary Data'}
          </button>
          {error && <p style={{ fontSize: 11, color: 'var(--rose)' }}>{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Globe size={20} style={{ color: 'var(--sky)' }} /> Multi-Entity Consolidation
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
            IFRS 10 / ASC 810 Compliant Engine — {status?.entity_count || 0} entities registered
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={handleSeed} disabled={seeding} className="btn btn-ghost" style={{ fontSize: 11 }}>
            {seeding ? <RefreshCcw size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Building2 size={14} />}
            Seed Entities
          </button>
          <button onClick={handleRun} disabled={running} className="btn btn-primary" style={{ fontSize: 12 }}>
            {running ? <RefreshCcw size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Layers size={14} />}
            {running ? 'Consolidating...' : 'Run Group Consolidation'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass" style={{ padding: 12, borderColor: 'var(--rose)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={14} style={{ color: 'var(--rose)' }} />
          <span style={{ color: 'var(--rose)', fontSize: 12 }}>{error}</span>
        </div>
      )}

      {/* KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {[
          { label: 'Entities', value: String(status?.entity_count || 0), color: 'var(--sky)', sub: 'GROUP MEMBERS' },
          { label: 'Group Structures', value: String(status?.group_structure?.length || 0), color: 'var(--violet)', sub: 'PARENT-SUB MAPS' },
          { label: 'Consolidated', value: result ? 'YES' : 'PENDING', color: result ? 'var(--emerald)' : 'var(--amber)', sub: result ? 'POST-ELIMINATION' : 'RUN NEEDED' },
          { label: 'Eliminations', value: String(eliminations.length), color: 'var(--rose)', sub: 'IC ENTRIES' },
        ].map(kpi => (
          <div key={kpi.label} className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)', fontFamily: 'var(--mono)', marginBottom: 6 }}>{kpi.label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: kpi.color, fontFamily: 'var(--mono)' }}>{kpi.value}</div>
            <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', marginTop: 4 }}>{kpi.sub}</div>
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
        {/* Tree View */}
        <div className="glass" style={{ padding: 16, minHeight: 360 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Building2 size={14} style={{ color: 'var(--sky)' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Group Structure</span>
            </div>
            <Info size={12} style={{ color: 'var(--dim)' }} />
          </div>
          {status && status.entity_count > 0 ? (
            <ReactECharts
              option={treeOption}
              style={{ height: '300px' }}
              theme="dark"
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 250, color: 'var(--dim)', fontSize: 12 }}>
              No entities to visualize
            </div>
          )}
        </div>

        {/* Elimination Journal */}
        <div className="glass" style={{ padding: 16, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Elimination Journal Entries</span>
            {eliminations.length > 0 && (
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--emerald)' }}>
                <CheckCircle2 size={10} /> {eliminations.length} entries
              </span>
            )}
          </div>
          <div style={{ overflow: 'auto', maxHeight: 300 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--b2)' }}>
                  {['Type', 'Entity', 'Account', 'Debit', 'Credit'].map(h => (
                    <th key={h} style={{ padding: '6px 10px', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontFamily: 'var(--mono)', textAlign: h === 'Debit' || h === 'Credit' ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {eliminations.length > 0 ? eliminations.map((e, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                    <td style={{ padding: '8px 10px' }}>
                      <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: 'rgba(0,216,255,0.08)', color: 'var(--sky)', fontWeight: 600 }}>{e.type}</span>
                    </td>
                    <td style={{ padding: '8px 10px', color: 'var(--text)' }}>{e.entity || '-'}</td>
                    <td style={{ padding: '8px 10px', color: 'var(--heading)', fontWeight: 500 }}>{e.account || '-'}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--emerald)' }}>{e.debit ? formatVal(e.debit) : '-'}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--rose)' }}>{e.credit ? formatVal(e.credit) : '-'}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={5} style={{ padding: 40, textAlign: 'center', color: 'var(--dim)', fontSize: 12 }}>
                      No elimination entries. Run consolidation to generate intercompany eliminations.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Consolidated Financial Position */}
      {Object.keys(consolidated).length > 0 && (
        <div className="glass" style={{ padding: 16, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Consolidated Financial Position (IFRS)</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b2)' }}>
                {['Line Item', 'Consolidated Value'].map(h => (
                  <th key={h} style={{ padding: '6px 12px', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)', fontFamily: 'var(--mono)', textAlign: h !== 'Line Item' ? 'right' : 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(consolidated).map(([account, value], i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 500, color: 'var(--heading)' }}>{account.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                  <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600, color: value < 0 ? 'var(--rose)' : 'var(--sky)' }}>{formatVal(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* NCI Section */}
      {Object.keys(nci).length > 0 && (
        <div className="glass" style={{ padding: 16 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
            <ArrowRight size={14} style={{ color: 'var(--violet)' }} /> Non-Controlling Interest (NCI)
          </span>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
            {Object.entries(nci).map(([key, val]) => (
              <div key={key} style={{ padding: 10, background: 'var(--bg3)', borderRadius: 6 }}>
                <div style={{ fontSize: 9, color: 'var(--muted)', textTransform: 'uppercase', fontFamily: 'var(--mono)' }}>{key.replace(/_/g, ' ')}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--violet)', fontFamily: 'var(--mono)', marginTop: 4 }}>{formatVal(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
