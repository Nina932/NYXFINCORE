import { useState, useEffect } from 'react';
import { Brain, CheckCircle, AlertTriangle, Play, ChevronDown, ChevronRight, Loader2, FileSpreadsheet, Zap } from 'lucide-react';
import { api } from '../api/client';
import { useStore } from '../store/useStore';
import PipelineVisualization from '../components/PipelineVisualization';

function fmt(n: string | number | null | undefined): string {
  const v = typeof n === 'string' ? parseFloat(n) : n;
  if (v == null || isNaN(v)) return '—';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `₾${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `₾${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `₾${(v / 1e3).toFixed(0)}K`;
  return `₾${v.toFixed(0)}`;
}

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 0.9 ? '#10B981' : value >= 0.7 ? '#F59E0B' : '#EF4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 60, height: 6, background: 'var(--b2)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${value * 100}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 10, color, fontWeight: 600 }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

export default function IngestionPlanPage() {
  const { datasets } = useStore();
  const [selectedDataset, setSelectedDataset] = useState<number | null>(null);
  const [plan, setPlan] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [expandedJEs, setExpandedJEs] = useState<Set<number>>(new Set());
  const [datasetList, setDatasetList] = useState<any[]>([]);

  // Load datasets
  useEffect(() => {
    fetch('/api/agent/agents/datasets').then(r => r.json())
      .then(d => setDatasetList(d.datasets || []))
      .catch(() => {});
  }, []);

  const loadPlan = async (dsId: number) => {
    setSelectedDataset(dsId);
    setLoading(true);
    setPlan(null);
    setResult(null);
    try {
      const p = await (api as any).intelligentIngestPlan(dsId);
      setPlan(p);
    } catch (e: any) {
      alert(`Plan failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const executePlan = async () => {
    if (!selectedDataset) return;
    setExecuting(true);
    try {
      const r = await (api as any).intelligentIngestExecute(selectedDataset);
      setResult(r);
    } catch (e: any) {
      alert(`Execution failed: ${e.message}`);
    } finally {
      setExecuting(false);
    }
  };

  const toggleJE = (idx: number) => {
    const next = new Set(expandedJEs);
    if (next.has(idx)) next.delete(idx); else next.add(idx);
    setExpandedJEs(next);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 4 }}>
      {/* Pipeline Visualization */}
      <PipelineVisualization />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Brain size={22} /> Intelligent Ingestion
        </h1>
        {plan && !result && (
          <button onClick={executePlan} disabled={executing}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 20px', borderRadius: 8,
              background: executing ? 'var(--b2)' : 'var(--emerald)', color: '#fff', border: 'none',
              cursor: executing ? 'wait' : 'pointer', fontWeight: 700, fontSize: 14 }}>
            {executing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {executing ? 'Executing...' : 'Execute Plan → Create Journal Entries'}
          </button>
        )}
      </div>

      {/* Dataset Selector */}
      <div className="glass" style={{ padding: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>Select Dataset to Analyze</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {datasetList.filter(d => d.record_count > 0).map(d => (
            <button key={d.id} onClick={() => loadPlan(d.id)}
              style={{ padding: '8px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                border: selectedDataset === d.id ? '2px solid var(--sky)' : '1px solid var(--b2)',
                background: selectedDataset === d.id ? 'var(--sky)11' : 'var(--bg2)',
                color: 'var(--text)', fontWeight: selectedDataset === d.id ? 700 : 400 }}>
              <FileSpreadsheet size={12} style={{ marginRight: 4 }} />
              {d.period || d.name?.substring(0, 20)} ({d.record_count} records)
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="glass" style={{ padding: 40, textAlign: 'center' }}>
          <Loader2 size={24} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
          <div style={{ marginTop: 8, color: 'var(--muted)' }}>Analyzing dataset... Classifying accounts... Planning journal entries...</div>
        </div>
      )}

      {/* Execution Result */}
      {result && (
        <div className="glass" style={{ padding: 20, border: '2px solid var(--emerald)' }}>
          <h3 style={{ fontSize: 16, fontWeight: 800, color: 'var(--emerald)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle size={20} /> Execution Complete
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginTop: 12 }}>
            <div><span style={{ fontSize: 10, color: 'var(--muted)' }}>JEs Created</span><div style={{ fontSize: 24, fontWeight: 800, color: 'var(--emerald)' }}>{result.entries_created}</div></div>
            <div><span style={{ fontSize: 10, color: 'var(--muted)' }}>JEs Posted</span><div style={{ fontSize: 24, fontWeight: 800, color: 'var(--emerald)' }}>{result.entries_posted}</div></div>
            <div><span style={{ fontSize: 10, color: 'var(--muted)' }}>Posting Lines</span><div style={{ fontSize: 24, fontWeight: 800, color: 'var(--sky)' }}>{result.total_posting_lines}</div></div>
            <div><span style={{ fontSize: 10, color: 'var(--muted)' }}>Classifications Learned</span><div style={{ fontSize: 24, fontWeight: 800, color: 'var(--violet)' }}>{result.classifications_learned || 0}</div></div>
            <div><span style={{ fontSize: 10, color: 'var(--muted)' }}>Errors</span><div style={{ fontSize: 24, fontWeight: 800, color: result.errors?.length ? 'var(--rose)' : 'var(--emerald)' }}>{result.errors?.length || 0}</div></div>
          </div>
          <div style={{ marginTop: 12 }}>
            <a href="/journal" style={{ color: 'var(--sky)', fontSize: 13, fontWeight: 600 }}>→ View Journal Entries</a>
          </div>
        </div>
      )}

      {/* Plan Display */}
      {plan && !loading && (
        <>
          {/* File Analysis */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Zap size={16} style={{ color: 'var(--sky)' }} />
              <span style={{ fontSize: 14, fontWeight: 700 }}>System Analysis</span>
              <ConfidenceBar value={plan.confidence} />
            </div>
            <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.6 }}>{plan.file_analysis}</div>
            <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 12 }}>
              <span><strong>Period:</strong> {plan.period}</span>
              <span><strong>Accounts:</strong> {plan.postable_accounts} postable / {plan.total_accounts_parsed} total</span>
              <span><strong>Review needed:</strong> {plan.needs_review_count}</span>
            </div>
          </div>

          {/* Reasoning Steps */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Brain size={14} /> Reasoning Steps
            </div>
            {plan.steps_taken?.map((step: string, i: number) => (
              <div key={i} style={{ fontSize: 12, padding: '4px 0', color: step.startsWith('   ') ? 'var(--muted)' : 'var(--text)',
                paddingLeft: step.startsWith('   ') ? 16 : 0, fontFamily: 'var(--mono)' }}>
                {step}
              </div>
            ))}
          </div>

          {/* Classification Summary */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>Classification Summary</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {Object.entries(plan.classification_summary || {}).map(([group, info]: [string, any]) => (
                <div key={group} style={{ padding: 12, borderRadius: 6, border: '1px solid var(--b2)', background: 'var(--bg2)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', marginBottom: 4 }}>
                    {group.replace(/_/g, ' ')}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--heading)' }}>{info.count} accounts</div>
                  <div style={{ fontSize: 11, color: 'var(--dim)', marginTop: 2 }}>{fmt(info.total)}</div>
                  <ConfidenceBar value={info.confidence_avg || 0} />
                </div>
              ))}
            </div>
          </div>

          {/* Planned Journal Entries */}
          <div className="glass" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
              Planned Journal Entries ({plan.planned_journal_entries?.length || 0})
            </div>
            {plan.planned_journal_entries?.map((je: any, idx: number) => (
              <div key={idx} style={{ marginBottom: 8, border: '1px solid var(--b2)', borderRadius: 6, overflow: 'hidden' }}>
                <div onClick={() => toggleJE(idx)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
                  cursor: 'pointer', background: 'var(--bg2)' }}>
                  {expandedJEs.has(idx) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 700 }}>{je.description}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted)' }}>{je.explanation}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 12, fontFamily: 'var(--mono)', fontWeight: 700 }}>{fmt(je.total_debit)}</div>
                    <div style={{ fontSize: 10, color: je.is_balanced ? 'var(--emerald)' : 'var(--rose)' }}>
                      {je.is_balanced ? '✓ Balanced' : '✗ Imbalanced'}
                    </div>
                  </div>
                  <span style={{ fontSize: 10, color: 'var(--muted)', minWidth: 50, textAlign: 'right' }}>{je.lines?.length} lines</span>
                </div>

                {expandedJEs.has(idx) && (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                    <thead><tr style={{ borderBottom: '1px solid var(--b2)', background: 'rgba(56,189,248,0.03)' }}>
                      {['Account', 'Name', 'Debit', 'Credit', 'Description'].map(h => (
                        <th key={h} style={{ padding: '6px 8px', textAlign: h === 'Debit' || h === 'Credit' ? 'right' : 'left',
                          fontSize: 9, textTransform: 'uppercase', color: 'var(--muted)' }}>{h}</th>
                      ))}
                    </tr></thead>
                    <tbody>{je.lines?.map((l: any, li: number) => (
                      <tr key={li} style={{ borderBottom: '1px solid var(--b1)' }}>
                        <td style={{ padding: '5px 8px', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600 }}>{l.account_code}</td>
                        <td style={{ padding: '5px 8px', fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.account_name}</td>
                        <td style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'var(--mono)', color: parseFloat(l.debit) > 0 ? 'var(--heading)' : 'var(--dim)' }}>{parseFloat(l.debit) > 0 ? fmt(l.debit) : '—'}</td>
                        <td style={{ padding: '5px 8px', textAlign: 'right', fontFamily: 'var(--mono)', color: parseFloat(l.credit) > 0 ? 'var(--heading)' : 'var(--dim)' }}>{parseFloat(l.credit) > 0 ? fmt(l.credit) : '—'}</td>
                        <td style={{ padding: '5px 8px', fontSize: 10, color: 'var(--muted)', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.description}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
            ))}
          </div>

          {/* Accounts Needing Review */}
          {plan.needs_review_count > 0 && (
            <div className="glass" style={{ padding: 16, border: '1px solid var(--amber)33' }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--amber)' }}>
                <AlertTriangle size={14} /> Accounts Needing Review ({plan.needs_review_count})
              </div>
              {plan.needs_review?.map((acct: any, i: number) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 0', borderBottom: '1px solid var(--b1)', fontSize: 12 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, minWidth: 70 }}>{acct.account_code}</span>
                  <span style={{ flex: 1, color: 'var(--text)' }}>{acct.account_name}</span>
                  <span style={{ fontFamily: 'var(--mono)', minWidth: 80, textAlign: 'right' }}>{fmt(acct.net_amount)}</span>
                  <ConfidenceBar value={acct.confidence} />
                  <span style={{ fontSize: 10, color: 'var(--muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{acct.reasoning}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
