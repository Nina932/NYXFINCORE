import { useState, useEffect } from 'react';
import {
  Brain, Loader2, Play, Sparkles, Search, CheckCircle, XCircle,
  Clock, ChevronRight, Cpu, GitBranch, ListChecks, Zap, AlertCircle,
  ArrowRight, Target, X,
} from 'lucide-react';
import { api } from '../api/client';
import { useToast } from '../components/Toast';
import type { ToastType } from '../components/Toast';

/* ─── Shared styles ─── */
const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
const label9: React.CSSProperties = { fontSize: 9, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: 'var(--muted)' };
const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: '10px 16px', fontSize: 12, fontWeight: 600, fontFamily: 'var(--font)',
  cursor: 'pointer', borderBottom: active ? '2px solid var(--sky)' : '2px solid transparent',
  color: active ? 'var(--heading)' : 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6,
  transition: 'all 0.15s ease', background: 'transparent', border: 'none',
  borderBottomWidth: 2, borderBottomStyle: 'solid' as const,
  borderBottomColor: active ? 'var(--sky)' : 'transparent',
});

type TabKey = 'aip' | 'react' | 'planner';

/* ─── AIP Types ─── */
interface AIPFunction {
  name: string;
  description: string;
  input_types?: string[];
  output_type?: string;
  category?: string;
}

interface AIPResult {
  function: string;
  narrative?: string;
  confidence?: number;
  impacted_entities?: { id: string; type: string; label?: string }[];
  result?: unknown;
  error?: string;
}

/* ─── ReAct Types ─── */
interface ReActStep {
  step: number;
  thought: string;
  action: string;
  observation: string;
}

interface ReActResult {
  goal: string;
  steps: ReActStep[];
  final_answer: string;
  success: boolean;
  execution_time_ms?: number;
}

/* ─── Planner Types ─── */
interface PlanStep {
  step: number;
  action: string;
  description: string;
  endpoint?: string;
  status?: 'pending' | 'completed' | 'failed';
  result?: string;
}

interface PlanResult {
  goal: string;
  steps: PlanStep[];
}

interface PlanExecResult {
  goal: string;
  steps: (PlanStep & { status: string; result?: string })[];
  success: boolean;
}

/* ═══════════════════════════════════════════ */
export default function DeepReasoningPage() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<TabKey>('aip');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 4px', animation: 'slide-up 0.4s ease both', position: 'relative', overflow: 'hidden' }}>
      <div className="scanline" />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--b1)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 900, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, margin: 0, letterSpacing: -0.5 }}>
            <Brain size={22} style={{ color: 'var(--sky)' }} /> CAUSAL_INFERENCE_ENGINE
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
            DEEP_REASONING_V4 | AGENT_STATUS: <span style={{ color: 'var(--emerald)' }}>READY_FOR_TASK</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ padding: '4px 12px', background: 'rgba(56, 189, 248, 0.05)', border: '1px solid var(--sky)', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', borderRadius: 2 }}>
            CORES: 128_QUANTUM
          </div>
          <div style={{ padding: '4px 12px', background: 'rgba(167, 139, 250, 0.05)', border: '1px solid var(--violet)', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--violet)', borderRadius: 2 }}>
            LATENCY: 42MS
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--b1)', gap: 2, background: 'rgba(15,20,34,0.3)', padding: '4px 4px 0' }}>
        <button 
          style={{
            ...tabStyle(activeTab === 'aip'),
            fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: 1, textTransform: 'uppercase',
            padding: '12px 24px', borderRadius: '4px 4px 0 0',
            background: activeTab === 'aip' ? 'rgba(0, 242, 255, 0.05)' : 'transparent'
          }} 
          onClick={() => setActiveTab('aip')}
        >
          <Cpu size={14} /> AIP_LOGIC_MODELS
        </button>
        <button 
          style={{
            ...tabStyle(activeTab === 'react'),
            fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: 1, textTransform: 'uppercase',
            padding: '12px 24px', borderRadius: '4px 4px 0 0',
            background: activeTab === 'react' ? 'rgba(0, 242, 255, 0.05)' : 'transparent'
          }} 
          onClick={() => setActiveTab('react')}
        >
          <Zap size={14} /> REACT_AUTONOMOUS
        </button>
        <button 
          style={{
            ...tabStyle(activeTab === 'planner'),
            fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: 1, textTransform: 'uppercase',
            padding: '12px 24px', borderRadius: '4px 4px 0 0',
            background: activeTab === 'planner' ? 'rgba(0, 242, 255, 0.05)' : 'transparent'
          }} 
          onClick={() => setActiveTab('planner')}
        >
          <ListChecks size={14} /> HEURISTIC_PLANNER
        </button>
      </div>

      {/* Tab Panels */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {activeTab === 'aip' && <AIPTab toast={toast} />}
        {activeTab === 'react' && <ReActTab toast={toast} />}
        {activeTab === 'planner' && <PlannerTab toast={toast} />}
      </div>
    </div>
  );
}

/* ═══════════════ TAB 1: AIP Logic ═══════════════ */
function AIPTab({ toast }: { toast: (msg: string, type?: ToastType) => void }) {
  const [functions, setFunctions] = useState<AIPFunction[]>([]);
  const [loading, setLoading] = useState(true);
  const [execModal, setExecModal] = useState<AIPFunction | null>(null);
  const [objectId, setObjectId] = useState('');
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<AIPResult | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch('/api/aip/functions', { headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) } })
      .then(r => r.json())
      .then(data => setFunctions(Array.isArray(data) ? data : data.functions || []))
      .catch(() => toast('Failed to load AIP functions', 'error'))
      .finally(() => setLoading(false));
  }, []);

  const execute = async () => {
    if (!execModal) return;
    setExecuting(true);
    setResult(null);
    try {
      const res = await fetch('/api/aip/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
        body: JSON.stringify({ function: execModal.name, object_ids: objectId.split(',').map(s => s.trim()).filter(Boolean) }),
      });
      const data = await res.json();
      setResult(data);
      toast('Function executed', 'success');
    } catch {
      toast('Execution failed', 'error');
    } finally {
      setExecuting(false);
    }
  };

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 100, gap: 16 }}>
      <Loader2 size={32} className="spin" style={{ color: 'var(--sky)' }} />
      <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2 }}>POLLING_ONTOLOGY_PRIMITIVES...</div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2, borderBottom: '1px solid var(--b1)', paddingBottom: 8 }}>
        _AVAILABLE_PRIMITIVE_FUNCTIONS
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
        {functions.map((fn, i) => (
          <div key={i} className="glass-interactive" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 32, height: 32, borderRadius: 4, background: 'rgba(0, 242, 255, 0.05)', border: '1px solid rgba(0, 242, 255, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Sparkles size={16} style={{ color: 'var(--sky)' }} />
              </div>
              <span style={{ fontSize: 14, fontWeight: 900, color: 'var(--heading)', letterSpacing: 0.5 }}>{fn.name.toUpperCase()}</span>
            </div>
            <p style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.6, opacity: 0.8, minHeight: 48 }}>{fn.description}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              {fn.input_types?.map((t, j) => (
                <span key={j} style={{ fontSize: 8, padding: '3px 8px', borderRadius: 2, background: 'rgba(0, 242, 255, 0.05)', color: 'var(--sky)', fontFamily: 'var(--mono)', border: '1px solid rgba(0, 242, 255, 0.1)' }}>
                  IN::{t.toUpperCase()}
                </span>
              ))}
              {fn.output_type && (
                <span style={{ fontSize: 8, padding: '3px 8px', borderRadius: 2, background: 'rgba(16, 185, 129, 0.05)', color: 'var(--emerald)', fontFamily: 'var(--mono)', border: '1px solid rgba(16, 185, 129, 0.1)' }}>
                  OUT::{fn.output_type.toUpperCase()}
                </span>
              )}
            </div>
            <button
              onClick={() => { setExecModal(fn); setObjectId(''); setResult(null); }}
              className="btn-minimal"
              style={{ marginTop: 12, padding: '10px 16px', justifyContent: 'center', fontSize: 11, fontWeight: 800, letterSpacing: 1 }}
            >
              <Play size={12} style={{ marginRight: 6 }} /> TRIGGER_INVOCATION
            </button>
          </div>
        ))}
      </div>

      {/* Execution Modal */}
      {execModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.75)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)' }}
          onClick={(e) => { if (e.target === e.currentTarget) setExecModal(null); }}>
          <div className="glass" style={{ padding: 32, width: 540, maxHeight: '90vh', overflow: 'auto', border: '1px solid var(--sky)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h3 style={{ fontSize: 16, fontWeight: 900, color: 'var(--heading)', margin: 0, display: 'flex', alignItems: 'center', gap: 12, fontFamily: 'var(--mono)' }}>
                <Cpu size={20} style={{ color: 'var(--sky)' }} /> {execModal.name.toUpperCase()}
              </h3>
              <button onClick={() => setExecModal(null)} className="btn-minimal" style={{ padding: 6 }}>
                <X size={16} />
              </button>
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 24, lineHeight: 1.6 }}>{execModal.description}</p>

            <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--dim)', letterSpacing: 2, marginBottom: 8, fontFamily: 'var(--mono)' }}>ENTITY_PRIMITIVE_IDS</div>
            <input
              value={objectId}
              onChange={e => setObjectId(e.target.value)}
              placeholder="E.G. REVENUE_2026, COGS_Q1"
              style={{ 
                width: '100%', padding: '12px 16px', fontSize: 12, 
                background: 'var(--bg2)', border: '1px solid var(--b1)', 
                borderRadius: 2, color: 'var(--text)', marginTop: 4, 
                marginBottom: 24, boxSizing: 'border-box', fontFamily: 'var(--mono)'
              }}
            />

            <button onClick={execute} disabled={executing} className="btn-minimal" style={{ width: '100%', padding: '12px', justifyContent: 'center', background: 'var(--sky)', color: 'var(--heading)', fontSize: 12, fontWeight: 900 }}>
              {executing ? <><Loader2 size={14} className="spin" /> EXECUTING...</> : <><Play size={14} /> RUN_FUNCTION</>}
            </button>

            {/* Result display */}
            {result && (
              <div style={{ marginTop: 24, padding: 20, background: 'rgba(15,20,34,0.4)', borderRadius: 2, border: '1px solid var(--b1)' }}>
                <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--sky)', letterSpacing: 2, marginBottom: 12, fontFamily: 'var(--mono)' }}>FUNCTION_OUTPUT_LOG</div>
                {result.narrative && (
                  <p style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.6, marginBottom: 16, borderLeft: '3px solid var(--sky)', paddingLeft: 12 }}>{result.narrative}</p>
                )}
                {result.confidence != null && (
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 6, fontFamily: 'var(--mono)' }}>
                       <span style={{ color: 'var(--dim)' }}>CONFIDENCE_INDEX</span>
                       <span style={{ fontWeight: 800, color: result.confidence > 0.7 ? 'var(--emerald)' : 'var(--amber)' }}>{(result.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${(result.confidence * 100)}%`, height: '100%', background: result.confidence > 0.7 ? 'var(--emerald)' : 'var(--amber)', borderRadius: 2 }} />
                    </div>
                  </div>
                )}
                {result.impacted_entities && result.impacted_entities.length > 0 && (
                  <div>
                    <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--dim)', letterSpacing: 1, marginBottom: 8, fontFamily: 'var(--mono)' }}>TRACE_ENTITIES</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {result.impacted_entities.map((e, i) => (
                        <span key={i} style={{ fontSize: 9, padding: '3px 8px', borderRadius: 2, background: 'rgba(167, 139, 250, 0.05)', color: 'var(--violet)', border: '1px solid rgba(167, 139, 250, 0.2)', fontFamily: 'var(--mono)' }}>
                          {e.type.toUpperCase()}:{e.id.toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {result.error && <p style={{ fontSize: 11, color: 'var(--rose)', marginTop: 12, fontFamily: 'var(--mono)' }}>ERROR::{result.error.toUpperCase()}</p>}
                {!result.narrative && !result.error && result.result != null && (
                  <pre style={{ fontSize: 10, color: 'var(--dim)', marginTop: 12, padding: 12, background: 'rgba(0,0,0,0.5)', borderRadius: 2, overflow: 'auto', fontFamily: 'var(--mono)' }}>
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════ TAB 2: ReAct Agent ═══════════════ */
function ReActTab({ toast }: { toast: (msg: string, type?: ToastType) => void }) {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReActResult | null>(null);

  const solve = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('/api/agent/agents/react/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
        body: JSON.stringify({ goal: goal.trim() }),
      });
      const data = await res.json();
      setResult(data);
      toast('ReAct agent completed', 'success');
    } catch {
      toast('ReAct solve failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Input */}
      <div className="glass" style={{ padding: 24, display: 'flex', gap: 12, alignItems: 'flex-end', borderLeft: '4px solid var(--sky)' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--sky)', letterSpacing: 2, marginBottom: 8, fontFamily: 'var(--mono)' }}>REASONING_GOAL_PROMPT</div>
          <input
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') solve(); }}
            placeholder='E.G. "ANALYZE_REVENUE_SPIKE" OR "VERIFY_ACCOUNT_COHERENCE"'
            style={{ width: '100%', padding: '12px 16px', fontSize: 13, background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 2, color: 'var(--text)', marginTop: 4, boxSizing: 'border-box', fontFamily: 'var(--mono)' }}
          />
        </div>
        <button onClick={solve} disabled={loading || !goal.trim()} className="btn-minimal" style={{ padding: '12px 24px', background: 'var(--sky)', color: 'var(--heading)', fontSize: 12, fontWeight: 900, letterSpacing: 1 }}>
          {loading ? <><Loader2 size={14} className="spin" /> REASONING...</> : <><Zap size={14} /> SOLVE</>}
        </button>
      </div>

      {/* Result */}
      {loading && (
        <div className="empty-state" style={{ padding: 100 }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--sky)', marginBottom: 16 }} />
          <div className="empty-state-title">MODELING_CAUSAL_TRACE...</div>
          <p style={{ opacity: 0.6, fontSize: 10, fontFamily: 'var(--mono)' }}>Executing ReAct loops over knowledge baseline.</p>
        </div>
      )}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Status Bar */}
          <div className="glass" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {result.success ? <CheckCircle size={18} style={{ color: 'var(--emerald)' }} /> : <AlertCircle size={18} style={{ color: 'var(--rose)' }} />}
              <span style={{ fontSize: 13, fontWeight: 800, color: result.success ? 'var(--emerald)' : 'var(--rose)', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                REASONING_{result.success ? 'CONCLUDED' : 'ABORTED'}
              </span>
            </div>
            {result.execution_time_ms != null && (
              <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', border: '1px solid var(--b1)', padding: '4px 10px', borderRadius: 2 }}>
                LATENCY::{result.execution_time_ms}MS
              </div>
            )}
          </div>

          {/* Step Trace */}
          <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2, borderBottom: '1px solid var(--b1)', paddingBottom: 8 }}>
            _CAUSAL_LOG_STREAM ({result.steps?.length || 0} NODES)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {(result.steps || []).map((step, i) => (
              <div key={i} className="glass" style={{ padding: 20, borderLeft: '4px solid var(--sky)', background: 'rgba(15,20,34,0.3)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <span style={{ fontSize: 9, fontWeight: 900, padding: '3px 10px', borderRadius: 2, background: 'rgba(0, 242, 255, 0.05)', color: 'var(--sky)', fontFamily: 'var(--mono)', border: '1px solid rgba(0, 242, 255, 0.2)' }}>
                    SEQ::0{step.step}
                  </span>
                  <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, var(--b1), transparent)' }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--violet)', fontFamily: 'var(--mono)', letterSpacing: 1, marginBottom: 6 }}>{'>'} THOUGHT</div>
                    <p style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.6, opacity: 0.9 }}>{step.thought}</p>
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: 12, borderRadius: 2 }}>
                    <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--emerald)', fontFamily: 'var(--mono)', letterSpacing: 1, marginBottom: 6 }}>{'>'} ACTION</div>
                    <p style={{ fontSize: 11, color: 'var(--emerald)', fontFamily: 'var(--mono)', opacity: 0.8 }}>{step.action}</p>
                  </div>
                  <div style={{ borderTop: '1px dashed var(--b1)', paddingTop: 12 }}>
                    <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--amber)', fontFamily: 'var(--mono)', letterSpacing: 1, marginBottom: 6 }}>{'>'} OBSERVATION</div>
                    <p style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.5, fontStyle: 'italic' }}>{step.observation}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Final Answer */}
          <div className="glass" style={{ padding: 24, borderLeft: '4px solid var(--emerald)', background: 'rgba(16, 185, 129, 0.02)' }}>
            <div style={{ fontSize: 10, fontWeight: 900, color: 'var(--emerald)', letterSpacing: 2, marginBottom: 12, fontFamily: 'var(--mono)' }}>CONCLUSION_VECTOR</div>
            <p style={{ fontSize: 14, color: 'var(--heading)', lineHeight: 1.7, fontWeight: 600 }}>{result.final_answer}</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════ TAB 3: Planning Agent ═══════════════ */
function PlannerTab({ toast }: { toast: (msg: string, type?: ToastType) => void }) {
  const [goal, setGoal] = useState('');
  const [loading, setLoading] = useState(false);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [execLoading, setExecLoading] = useState(false);
  const [execResult, setExecResult] = useState<PlanExecResult | null>(null);

  const createPlan = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setPlan(null);
    setExecResult(null);
    try {
      const res = await fetch('/api/agent/agents/planner/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
        body: JSON.stringify({ goal: goal.trim() }),
      });
      const data = await res.json();
      setPlan(data);
      toast('Plan created', 'success');
    } catch {
      toast('Plan creation failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const executePlan = async () => {
    if (!goal.trim()) return;
    setExecLoading(true);
    setExecResult(null);
    try {
      const res = await fetch('/api/agent/agents/planner/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(localStorage.getItem('token') ? { Authorization: `Bearer ${localStorage.getItem('token')}` } : {}) },
        body: JSON.stringify({ goal: goal.trim() }),
      });
      const data = await res.json();
      setExecResult(data);
      toast(data.success ? 'Plan executed successfully' : 'Plan executed with issues', data.success ? 'success' : 'error');
    } catch {
      toast('Plan execution failed', 'error');
    } finally {
      setExecLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Input */}
      <div className="glass" style={{ padding: 24, display: 'flex', gap: 12, alignItems: 'flex-end', borderLeft: '4px solid var(--violet)' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--violet)', letterSpacing: 2, marginBottom: 8, fontFamily: 'var(--mono)' }}>STRATEGIC_PLANNING_TARGET</div>
          <input
            value={goal}
            onChange={e => setGoal(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') createPlan(); }}
            placeholder='E.G. "PREPARE_ANNUAL_REPORT" OR "MONTH_END_CONSOLIDATION"'
            style={{ width: '100%', padding: '12px 16px', fontSize: 13, background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 2, color: 'var(--text)', marginTop: 4, boxSizing: 'border-box', fontFamily: 'var(--mono)' }}
          />
        </div>
        <button onClick={createPlan} disabled={loading || !goal.trim()} className="btn-minimal" style={{ padding: '12px 24px', background: 'var(--violet)', color: 'var(--heading)', fontSize: 12, fontWeight: 900, letterSpacing: 1, borderColor: 'var(--violet)' }}>
          {loading ? <><Loader2 size={14} className="spin" /> DRAFTING...</> : <><ListChecks size={14} /> GENERATE_PLAN</>}
        </button>
      </div>

      {loading && (
        <div className="empty-state" style={{ padding: 80 }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--violet)', marginBottom: 16 }} />
          <div className="empty-state-title" style={{ color: 'var(--violet)' }}>OPTIMIZING_WORKFLOW_NODES...</div>
        </div>
      )}

      {/* Plan display */}
      {plan && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--b1)', paddingBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 900, color: 'var(--dim)', fontFamily: 'var(--mono)', letterSpacing: 1 }}>
               SEQ_TARGET::{plan.goal.toUpperCase()}
            </div>
            <button onClick={executePlan} disabled={execLoading} className="btn-minimal" style={{ background: 'var(--emerald)', color: 'var(--heading)', borderColor: 'var(--emerald)', fontWeight: 900, padding: '8px 20px' }}>
              {execLoading ? <><Loader2 size={12} className="spin" /> EXECUTING...</> : <><Play size={12} /> EXECUTE_FULL_STACK</>}
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {(plan.steps || []).map((step, i) => {
              const exec = execResult?.steps?.[i];
              const statusColor = exec?.status === 'completed' ? 'var(--emerald)' : exec?.status === 'failed' ? 'var(--rose)' : 'var(--sky)';
              const StatusIcon = exec?.status === 'completed' ? CheckCircle : exec?.status === 'failed' ? XCircle : ChevronRight;

              return (
                <div key={i} className="glass-interactive" style={{ padding: 20, display: 'flex', gap: 16, alignItems: 'flex-start', borderLeft: `3px solid ${statusColor}` }}>
                  <div style={{ minWidth: 32, height: 32, borderRadius: 2, background: 'rgba(15,20,34,0.4)', border: `1px solid ${statusColor}33`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <StatusIcon size={16} style={{ color: statusColor }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <span style={{ fontSize: 9, fontWeight: 900, color: statusColor, fontFamily: 'var(--mono)', letterSpacing: 1 }}>STEP_0{step.step}</span>
                      <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--heading)', letterSpacing: 0.2 }}>{step.action.toUpperCase()}</span>
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.5 }}>{step.description}</p>
                    {step.endpoint && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10 }}>
                        <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--sky)' }} />
                        <span style={{ fontSize: 9, color: 'var(--sky)', fontFamily: 'var(--mono)', textTransform: 'lowercase' }}>{step.endpoint}</span>
                      </div>
                    )}
                    {exec?.result && (
                      <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(0,0,0,0.2)', border: `1px solid ${statusColor}22`, borderRadius: 2 }}>
                        <p style={{ fontSize: 10, color: exec.status === 'completed' ? 'var(--emerald)' : 'var(--rose)', fontStyle: 'italic', fontFamily: 'var(--mono)' }}>
                          OUTPUT::{exec.result.toUpperCase()}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
