import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Database, Play, Search, Terminal, ChevronDown, Table2, Sparkles, RefreshCw, Loader2, AlertTriangle } from 'lucide-react';

interface PrebuiltQuery {
  key: string;
  title: string;
  description: string;
}

interface AgentResult {
  title: string;
  sql: string;
  results: any[];
  row_count: number;
  description: string;
  suggestion?: string | null;
  error?: string;
}

export default function WarehousePage() {
  // Data tables
  const [tables, setTables] = useState<any[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [warehouseStats, setWarehouseStats] = useState<any>(null);

  // Pre-built queries
  const [prebuiltQueries, setPrebuiltQueries] = useState<PrebuiltQuery[]>([]);
  const [prebuiltLoading, setPrebuiltLoading] = useState<string | null>(null);
  const [prebuiltResult, setPrebuiltResult] = useState<AgentResult | null>(null);

  // AI Agent
  const [agentQuestion, setAgentQuestion] = useState('');
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentResult, setAgentResult] = useState<AgentResult | null>(null);

  // Raw SQL
  const [sqlOpen, setSqlOpen] = useState(false);
  const [sql, setSql] = useState('SELECT * FROM dw_financial_snapshots LIMIT 20');
  const [sqlResults, setSqlResults] = useState<any[]>([]);
  const [sqlError, setSqlError] = useState('');
  const [sqlLoading, setSqlLoading] = useState(false);

  useEffect(() => {
    api.warehouseTables().then((d: any) => setTables(Array.isArray(d) ? d : d?.tables || [])).catch(() => {});
    api.ontologyStats().then((d: any) => setWarehouseStats(d?.warehouse)).catch(() => {});
    api.dataAgentPrebuilt().then((d: any) => setPrebuiltQueries(d?.queries || [])).catch(() => {});
  }, []);

  const syncWarehouse = async () => {
    setSyncing(true);
    try {
      await api.warehouseSync();
      const d: any = await api.warehouseTables();
      setTables(Array.isArray(d) ? d : d?.tables || []);
    } catch { }
    finally { setSyncing(false); }
  };

  const runPrebuilt = async (key: string) => {
    setPrebuiltLoading(key);
    setPrebuiltResult(null);
    try {
      const data = await api.dataAgentQuery(key) as AgentResult;
      setPrebuiltResult(data);
    } catch (e) {
      setPrebuiltResult({ title: 'Error', sql: '', results: [], row_count: 0, description: '', error: String(e) });
    }
    finally { setPrebuiltLoading(null); }
  };

  const runAgentQuery = async () => {
    if (!agentQuestion.trim()) return;
    setAgentLoading(true);
    setAgentResult(null);
    try {
      const data = await api.dataAgentQuery(agentQuestion) as AgentResult;
      setAgentResult(data);
    } catch (e) {
      setAgentResult({ title: 'Error', sql: '', results: [], row_count: 0, description: '', error: String(e) });
    }
    finally { setAgentLoading(false); }
  };

  const runRawSql = async () => {
    if (!sql.trim()) return;
    setSqlLoading(true); setSqlError(''); setSqlResults([]);
    try {
      const data: any = await api.warehouseQuery(sql);
      if (data.results?.[0]?.error) {
        setSqlError(data.results[0].error);
      } else {
        setSqlResults(data.results || []);
      }
    } catch (e) { setSqlError(String(e)); }
    finally { setSqlLoading(false); }
  };

  const ResultTable = ({ results }: { results: any[] }) => {
    if (!results.length) return null;
    const columns = Object.keys(results[0]);
    return (
      <div style={{ overflow: 'auto', maxHeight: 360 }}>
        <table className="data-table">
          <thead>
            <tr>
              {columns.map(col => <th key={col}>{col}</th>)}
            </tr>
          </thead>
          <tbody>
            {results.map((row, i) => (
              <tr key={i}>
                {columns.map(col => (
                  <td key={col} className="mono" style={{
                    color: typeof row[col] === 'number' && row[col] < 0 ? 'var(--rose)' : undefined,
                  }}>
                    {row[col] != null
                      ? (typeof row[col] === 'number' ? row[col].toLocaleString() : String(row[col]).slice(0, 80))
                      : '\u2014'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const AgentResultPanel = ({ result, label }: { result: AgentResult; label: string }) => (
    <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid var(--b1)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)' }}>{result.title}</div>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{result.description}</div>
        </div>
        <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
          {result.row_count} rows
        </span>
      </div>
      {result.sql && (
        <div style={{
          padding: '8px 14px', background: 'rgba(0,0,0,.15)', borderBottom: '1px solid var(--b1)',
          fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', lineHeight: 1.6,
          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        }}>
          {result.sql}
        </div>
      )}
      {result.error && (
        <div style={{
          padding: '8px 14px', fontSize: 11, color: 'var(--rose)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <AlertTriangle size={13} /> {result.error}
        </div>
      )}
      {result.suggestion && (
        <div style={{
          padding: '6px 14px', fontSize: 10, color: 'var(--amber)',
          borderBottom: result.results.length ? '1px solid var(--b1)' : 'none',
        }}>
          {result.suggestion}
        </div>
      )}
      <ResultTable results={result.results} />
    </div>
  );

  const sqlColumns = sqlResults.length > 0 ? Object.keys(sqlResults[0]) : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ── Header + Data Tables Bar ─────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 16, fontWeight: 600, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6, margin: 0 }}>
          <Database size={16} style={{ color: 'var(--sky)' }} />
          Data Warehouse
        </h1>
        <button onClick={syncWarehouse} disabled={syncing} style={{
          display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px',
          borderRadius: 'var(--r1)', border: '1px solid var(--b2)',
          background: 'transparent', color: 'var(--muted)', cursor: 'pointer', fontSize: 11,
        }}>
          {syncing ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <RefreshCw size={12} />}
          Sync from SQLite
        </button>
      </div>

      {/* Tables Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 6 }}>
        {tables.map(t => (
          <div
            key={t.table}
            className="glass"
            style={{ padding: '8px 10px', textAlign: 'left', border: '1px solid var(--b1)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <Table2 size={12} style={{ color: 'var(--sky)' }} />
              <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--heading)', fontWeight: 500 }}>
                {t.table}
              </span>
            </div>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
              {t.rows?.toLocaleString() || 0} rows
            </div>
          </div>
        ))}
        {tables.length === 0 && (
          <div style={{ fontSize: 11, color: 'var(--muted)', padding: 12 }}>
            No warehouse tables. Click "Sync from SQLite" to populate.
          </div>
        )}
      </div>

      {/* ── Section 1: Pre-built Analytics ────────────────────── */}
      <div>
        <div style={{
          fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2,
          color: 'var(--dim)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <Sparkles size={11} style={{ color: 'var(--amber)' }} />
          Pre-built Analytics
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
          {prebuiltQueries.map(q => (
            <button
              key={q.key}
              onClick={() => runPrebuilt(q.key)}
              disabled={prebuiltLoading === q.key}
              className="glass"
              style={{
                padding: '12px 14px', cursor: 'pointer', textAlign: 'left',
                border: '1px solid var(--b1)', transition: 'border-color .15s',
                display: 'flex', flexDirection: 'column', gap: 6,
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--sky)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--b1)')}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>{q.title}</span>
                {prebuiltLoading === q.key
                  ? <Loader2 size={12} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
                  : <Play size={12} style={{ color: 'var(--sky)' }} />
                }
              </div>
              <span style={{ fontSize: 10, color: 'var(--muted)', lineHeight: 1.4 }}>{q.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Pre-built result */}
      {prebuiltResult && <AgentResultPanel result={prebuiltResult} label="Analytics" />}

      {/* ── Section 2: AI Data Agent ─────────────────────────── */}
      <div>
        <div style={{
          fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2,
          color: 'var(--dim)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <Search size={11} style={{ color: 'var(--sky)' }} />
          AI Data Agent
        </div>
        <div className="glass" style={{ padding: 12 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              type="text"
              value={agentQuestion}
              onChange={e => setAgentQuestion(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); runAgentQuery(); } }}
              placeholder="Ask about your data... e.g. 'Show me revenue by month'"
              style={{
                flex: 1, padding: '8px 12px', borderRadius: 'var(--r1)',
                border: '1px solid var(--b2)', background: 'var(--bg2)',
                color: 'var(--text)', fontSize: 12, outline: 'none',
              }}
            />
            <button onClick={runAgentQuery} disabled={agentLoading || !agentQuestion.trim()} style={{
              padding: '0 16px', borderRadius: 'var(--r1)', border: 'none',
              background: 'var(--blue)', color: '#fff', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 500,
              opacity: (!agentQuestion.trim() || agentLoading) ? 0.5 : 1,
            }}>
              {agentLoading
                ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
                : <Sparkles size={13} />
              }
              Ask
            </button>
          </div>
          <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 6 }}>
            Try: "top products", "expense trends", "revenue by segment", "data quality", "how many transactions"
          </div>
        </div>
      </div>

      {/* Agent result */}
      {agentResult && <AgentResultPanel result={agentResult} label="Agent" />}

      {/* ── Section 3: Raw SQL (collapsible) ──────────────────── */}
      <div>
        <button
          onClick={() => setSqlOpen(o => !o)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, background: 'none',
            border: 'none', cursor: 'pointer', padding: '4px 0', width: '100%',
          }}
        >
          <ChevronDown size={12} style={{
            color: 'var(--dim)', transition: 'transform .2s',
            transform: sqlOpen ? 'rotate(0deg)' : 'rotate(-90deg)',
          }} />
          <Terminal size={11} style={{ color: 'var(--dim)' }} />
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1.2,
            color: 'var(--dim)',
          }}>
            Advanced: Custom SQL
          </span>
        </button>

        {sqlOpen && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div className="glass" style={{ padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                <Database size={13} style={{ color: 'var(--sky)' }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>SQL Query</span>
                <span style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>DuckDB</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                <textarea
                  value={sql}
                  onChange={e => setSql(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); runRawSql(); } }}
                  rows={3}
                  style={{
                    flex: 1, padding: 8, borderRadius: 'var(--r1)',
                    border: '1px solid var(--b2)', background: 'var(--bg2)',
                    color: 'var(--text)', fontSize: 11, fontFamily: 'var(--mono)',
                    resize: 'vertical', outline: 'none', lineHeight: 1.5,
                  }}
                />
                <button onClick={runRawSql} disabled={sqlLoading} style={{
                  width: 50, borderRadius: 'var(--r1)', border: 'none',
                  background: 'var(--blue)', color: '#fff', cursor: 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2,
                }}>
                  {sqlLoading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={14} />}
                  <span style={{ fontSize: 8 }}>Run</span>
                </button>
              </div>
              <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 4 }}>Ctrl+Enter to execute</div>
            </div>

            {sqlError && (
              <div style={{
                padding: '8px 12px', borderRadius: 'var(--r1)',
                background: 'rgba(231,106,110,.08)', border: '1px solid rgba(231,106,110,.2)',
                fontSize: 11, color: 'var(--rose)', display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <AlertTriangle size={13} /> {sqlError}
              </div>
            )}

            {sqlResults.length > 0 && (
              <div className="glass" style={{ overflow: 'auto' }}>
                <div style={{
                  padding: '8px 12px', borderBottom: '1px solid var(--b1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                    {sqlResults.length} rows {'\u2022'} {sqlColumns.length} columns
                  </span>
                </div>
                <ResultTable results={sqlResults} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Warehouse Stats */}
      {warehouseStats && (
        <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', padding: '0 4px' }}>
          Engine: {warehouseStats.engine || 'none'} {'\u2022'} Path: {warehouseStats.db_path || '\u2014'}
        </div>
      )}
    </div>
  );
}
