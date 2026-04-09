import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Workflow, Brain, Target, BarChart3, Shield, Activity,
  BookOpen, Lightbulb, Loader2, CheckCircle2, Clock, XCircle,
  ChevronRight, Zap, FileText, AlertTriangle, Search,
  ArrowRight,
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { StepperWidget } from '../components/widgets';
import { useUsageMetrics } from '../hooks/useUsageMetrics';

/* ─── Orchestrator Pipeline Stages ─── */
interface StageInfo {
  id: string;
  name: string;
  icon: React.ElementType;
  color: string;
  glow: string;
  route?: string;
  metricKey?: string;
  metricLabel?: string;
}

const PIPELINE_STAGES: StageInfo[] = [
  { id: 'diagnosis', name: 'Diagnosis', icon: Activity, color: '#34d399', glow: 'rgba(52,211,153,.25)', route: '/reasoning', metricKey: 'health_score', metricLabel: 'Health' },
  { id: 'decision', name: 'Decision', icon: Target, color: '#60a5fa', glow: 'rgba(96,165,250,.25)', route: '/decisions', metricKey: 'actions_count', metricLabel: 'Actions' },
  { id: 'strategy', name: 'Strategy', icon: Shield, color: '#a78bfa', glow: 'rgba(167,139,250,.25)', route: '/strategy', metricKey: 'strategy_phase', metricLabel: 'Phase' },
  { id: 'simulation', name: 'Simulation', icon: BarChart3, color: '#f472b6', glow: 'rgba(244,114,182,.25)', route: '/sensitivity', metricKey: 'simulations', metricLabel: 'Sims' },
  { id: 'monitoring', name: 'Monitoring', icon: AlertTriangle, color: '#fbbf24', glow: 'rgba(251,191,36,.25)', route: '/alerts', metricKey: 'alerts_count', metricLabel: 'Alerts' },
  { id: 'learning', name: 'Learning', icon: BookOpen, color: '#22d3ee', glow: 'rgba(34,211,238,.25)', metricKey: 'learning_records', metricLabel: 'Records' },
  { id: 'analogy', name: 'Analogy', icon: Lightbulb, color: '#fb923c', glow: 'rgba(251,146,60,.25)', metricKey: 'analogies_found', metricLabel: 'Matches' },
];

/* ─── Composable Workflows ─── */
interface WorkflowDef {
  name: string;
  color: string;
  steps: string[];
}

const COMPOSABLE_WORKFLOWS: WorkflowDef[] = [
  {
    name: 'Financial Analysis',
    color: '#60a5fa',
    steps: ['Ingest Data', 'Classify Accounts', 'Build Statements', 'Calculate Ratios', 'Diagnose Health', 'Generate Insights', 'Create Report'],
  },
  {
    name: 'Invoice Validation',
    color: '#34d399',
    steps: ['Parse Document', 'Extract Fields', 'Match PO', 'Verify Amounts', 'Check Duplicates', 'Flag Anomalies', 'Approve/Reject'],
  },
  {
    name: 'Anomaly Response',
    color: '#f87171',
    steps: ['Detect Spike', 'Root Cause Analysis', 'Impact Assessment', 'Recommend Action'],
  },
];

/* ─── Helpers ─── */
function getStageStatus(stageId: string, orch: Record<string, unknown> | null): 'success' | 'never' | 'failed' {
  if (!orch) return 'never';
  const stageData = orch[stageId] as Record<string, unknown> | undefined;
  if (!stageData) return 'never';
  if (stageData.error) return 'failed';
  return 'success';
}

function getStageMetric(stageId: string, orch: Record<string, unknown> | null, stage: StageInfo): string | null {
  if (!orch) return null;
  const data = orch[stageId] as Record<string, unknown> | undefined;
  if (!data) return null;

  switch (stageId) {
    case 'diagnosis': {
      const score = (data as any)?.health_score ?? (data as any)?.score ?? null;
      return score !== null ? `${score}/100` : null;
    }
    case 'decision': {
      const actions = (data as any)?.actions ?? (data as any)?.recommended_actions;
      return Array.isArray(actions) ? `${actions.length} actions` : null;
    }
    case 'strategy': {
      const phase = (data as any)?.current_phase ?? (data as any)?.phase;
      return phase ? String(phase) : null;
    }
    case 'monitoring': {
      const alerts = (data as any)?.alerts ?? (data as any)?.active_alerts;
      return Array.isArray(alerts) ? `${alerts.length} active` : null;
    }
    default:
      return null;
  }
}

/* ─── Status Icon Component ─── */
function StatusIcon({ status }: { status: 'success' | 'never' | 'failed' }) {
  if (status === 'success') return <CheckCircle2 size={12} style={{ color: 'var(--emerald)' }} />;
  if (status === 'failed') return <XCircle size={12} style={{ color: 'var(--rose)' }} />;
  return <Clock size={12} style={{ color: 'var(--dim)' }} />;
}

/* ─── Arrow between nodes ─── */
function PipelineArrow({ animated = false }: { animated?: boolean }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      width: 28, flexShrink: 0, position: 'relative',
    }}>
      {animated && (
        <div style={{
          position: 'absolute', width: '100%', height: 2, top: '50%',
          background: 'linear-gradient(90deg, transparent, var(--sky), transparent)',
          animation: 'pulse-soft 1.5s ease-in-out infinite',
          opacity: 0.5, borderRadius: 1,
        }} />
      )}
      <ChevronRight size={16} style={{
        color: animated ? 'var(--sky)' : 'var(--dim)',
        opacity: animated ? 0.8 : 0.5,
        transition: 'all 0.3s',
      }} />
    </div>
  );
}

/* ─── Main Component ─── */
export default function WorkflowPage() {
  const navigate = useNavigate();
  const { orchestrator, pnl } = useStore();
  const orch = orchestrator as Record<string, unknown> | null;
  const { trackAction } = useUsageMetrics();
  const [workflows, setWorkflows] = useState<{ name: string; steps: number; description?: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);
  const [logs, setLogs] = useState<{ t: string; m: string; s: 'info' | 'warn' | 'err' }[]>([]);

  const addLog = (m: string, s: 'info' | 'warn' | 'err' = 'info') => {
    setLogs(prev => [...prev, { t: new Date().toLocaleTimeString(), m, s }].slice(-50));
  };

  const runPipeline = async () => {
    setRunning(true);
    setLogs([]);
    addLog('INITIATING_FULL_ORCHESTRATION_SEQUENCE', 'info');
    
    // Simulate log streaming
    const steps = [
      'Establishing connection to DuckDB warehouse...',
      'Authenticating ontology nodes...',
      'Starting Diagnosis (IFRS_HEALTH_CORE)...',
      'Running Decision Engine (CAUSAL_INFERENCE)...',
      'Mapping Strategic Actions...',
      'Generating Sentiment Analysis from market feeds...',
      'Finalizing mission parameters...'
    ];

    for (const step of steps) {
       await new Promise(r => setTimeout(r, 600));
       addLog(step.toUpperCase(), 'info');
    }

    try {
      const financials = pnl || { revenue: 51163023, cogs: 44572426, net_profit: -5234070, operating_expenses: 4877061 };
      const data = await api.orchestrate(financials, {}) as Record<string, unknown>;
      setRunResult(data);
      useStore.getState().setOrchestrator(data);
      addLog('SEQUENCE_COMPLETED_SUCCESSFULLY', 'info');
    } catch (err) {
      setRunResult({ error: 'Pipeline execution failed' });
      addLog('PIPELINE_EXECUTION_CRITICAL_FAILURE', 'err');
    } finally {
      setRunning(false);
    }
  };

  // Fetch workflow list from backend
  useEffect(() => {
    api.workflowPipeline()
      .then((data: any) => {
        if (data && !data.error) {
          if (data.nodes) {
            setWorkflows(data.nodes.map((n: Record<string, unknown>) => ({
              name: n.label as string || n.id as string,
              steps: 1,
              description: n.description as string || '',
            })));
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const hasOrchestratorData = orch !== null;
  const lastRunTime = orch ? ((orch as any).timestamp || (orch as any).run_at || null) : null;

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 8 }}>
        <Loader2 size={20} style={{ animation: 'spin 1s linear infinite', color: 'var(--sky)' }} />
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>Loading pipeline...</span>
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
            <Workflow size={22} style={{ color: 'var(--sky)' }} />
            ORCHESTRATOR_MISSION_CONTROL
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>
            SYSTEM_INTELLIGENCE_PIPELINE | STATUS: <span style={{ color: running ? 'var(--sky)' : 'var(--emerald)' }}>{running ? 'EXECUTING_CAUSAL_LOOPS' : 'NOMINAL'}</span>
            {lastRunTime && (
              <span style={{ marginLeft: 12, opacity: 0.6 }}>
                LAST_SEQ: {new Date(lastRunTime).toLocaleTimeString()}
              </span>
            )}
          </p>
        </div>
        <button onClick={runPipeline} disabled={running} className="btn-minimal" style={{
          padding: '10px 24px', fontSize: 12, fontWeight: 800,
          background: running ? 'var(--bg2)' : 'var(--sky)',
          color: running ? 'var(--muted)' : '#000',
          borderColor: running ? 'var(--b1)' : 'var(--sky)',
        }}>
          {running ? <><Loader2 size={14} className="spin" /> EXECUTING...</> : <><Zap size={14} /> TRIGGER_FULL_SEQ</>}
        </button>
      </div>

      {/* ═══ Pipeline Content & Terminal ═══ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, flex: 1 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* ═══ Stepper Widget — Pipeline Progress ═══ */}
          <div className="glass" style={{ padding: '20px', borderLeft: '4px solid var(--b1)' }}>
            <div style={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--dim)', marginBottom: 16, fontFamily: 'var(--mono)' }}>
              PIPELINE_EXECUTION_STATE
            </div>
            <StepperWidget
              steps={PIPELINE_STAGES.map((stage) => ({
                id: stage.id,
                label: stage.name.toUpperCase(),
                isCompleted: getStageStatus(stage.id, orch) === 'success',
                onClick: stage.route ? () => { trackAction('stepper_nav', { stage: stage.id }); navigate(stage.route!); } : undefined,
              }))}
              activeStep={PIPELINE_STAGES.findIndex(s => getStageStatus(s.id, orch) !== 'success')}
              type="non-linear"
            />
          </div>

          {/* ═══ 7-Stage Orchestrator Pipeline ═══ */}
          <div className="glass" style={{ padding: 24, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
              <h3 style={{ fontSize: 13, fontWeight: 900, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8, letterSpacing: 1, fontFamily: 'var(--mono)' }}>
                <Activity size={14} style={{ color: 'var(--sky)' }} />
                INTELLIGENCE_GRID_SEQ
              </h3>
              <span style={{
                fontSize: 8, fontFamily: 'var(--mono)', padding: '4px 12px',
                borderRadius: 2,
                background: hasOrchestratorData ? 'rgba(16, 185, 129, 0.05)' : 'rgba(255, 255, 255, 0.02)',
                color: hasOrchestratorData ? 'var(--emerald)' : 'var(--dim)',
                border: `1px solid ${hasOrchestratorData ? 'rgba(16, 185, 129, 0.2)' : 'var(--b1)'}`,
                fontWeight: 800, letterSpacing: 1
              }}>
                {hasOrchestratorData ? 'MATRIX_POPULATED' : 'WAITING_FOR_DATA'}
              </span>
            </div>

            {/* Pipeline nodes */}
            <div style={{
              display: 'flex', alignItems: 'stretch', gap: 0,
              overflowX: 'auto', padding: '12px 4px',
            }}>
              {PIPELINE_STAGES.map((stage, idx) => {
                const status = getStageStatus(stage.id, orch);
                const metric = getStageMetric(stage.id, orch, stage);
                const Icon = stage.icon;
                const isClickable = !!stage.route;

                return (
                  <div key={stage.id} style={{ display: 'flex', alignItems: 'center' }}>
                    {idx > 0 && <PipelineArrow animated={hasOrchestratorData && getStageStatus(PIPELINE_STAGES[idx - 1].id, orch) === 'success'} />}
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: idx * 0.05 }}
                      onClick={() => isClickable && navigate(stage.route!)}
                      className="glass-interactive"
                      style={{
                        position: 'relative',
                        borderLeft: `3px solid ${status === 'success' ? stage.color : status === 'failed' ? 'var(--rose)' : 'var(--b2)'}`,
                        padding: '16px 20px',
                        minWidth: 140,
                        flexShrink: 0,
                        background: status === 'success' ? `${stage.color}05` : 'rgba(15,20,34,0.3)',
                        boxShadow: status === 'success' ? `0 0 20px ${stage.color}15` : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: 4,
                          background: `${stage.color}18`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          border: `1px solid ${stage.color}33`
                        }}>
                          <Icon size={16} style={{ color: stage.color }} />
                        </div>
                        <StatusIcon status={status} />
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 900, color: 'var(--heading)', letterSpacing: 0.5, fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>{stage.name}</div>
                      {metric ? <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: stage.color, marginTop: 6, fontWeight: 700 }}>[{metric}]</div> : <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', marginTop: 6, opacity: 0.5 }}>NODATA_REC</div>}
                    </motion.div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Composable Workflows */}
          <div className="glass" style={{ padding: 24, borderTop: '1px solid var(--b1)' }}>
            <h3 style={{ fontSize: 13, fontWeight: 900, color: 'var(--heading)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10, letterSpacing: 1, fontFamily: 'var(--mono)' }}>
              <Brain size={14} style={{ color: 'var(--emerald)' }} />
              COMPOSABLE_AI_WORKFLOW_REPLICATORS
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {COMPOSABLE_WORKFLOWS.map((wf, wfIdx) => (
                <div key={wf.name}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                    <div style={{ width: 10, height: 10, borderRadius: 2, background: wf.color, boxShadow: `0 0 10px ${wf.color}40` }} />
                    <span style={{ fontSize: 13, fontWeight: 900, color: 'var(--heading)', letterSpacing: 0.5 }}>{wf.name.toUpperCase()}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', padding: '4px 0' }}>
                    {wf.steps.map((step, sIdx) => (
                      <div key={sIdx} style={{ display: 'flex', alignItems: 'center' }}>
                        {sIdx > 0 && <div style={{ width: 24, height: 1, flexShrink: 0, background: `linear-gradient(90deg, ${wf.color}44, transparent)` }} />}
                        <div className="glass-interactive p-2 px-3 text-[10px] font-mono whitespace-nowrap">{step.toUpperCase()}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* LOG TERMINAL SIDEBAR */}
        <div className="command-panel flex flex-col bg-black/60 border-b1 p-0 overflow-hidden">
           <div className="p-3 border-b border-b1 bg-bg2/40 flex justify-between items-center">
              <div className="text-[10px] font-bold text-sky uppercase tracking-widest flex items-center gap-2">
                 <Shield size={12} /> Execution_Log
              </div>
              {running && <Loader2 size={12} className="spin text-sky" />}
           </div>
           <div className="flex-1 overflow-y-auto p-4 font-mono text-[10px] space-y-2">
              {logs.length === 0 ? (
                 <div className="text-dim/40 italic">Waiting for execution sequence...</div>
              ) : (
                 logs.map((log, i) => (
                    <div key={i} className="flex gap-3">
                       <span className="text-dim opacity-50">[{log.t}]</span>
                       <span className={log.s === 'err' ? 'text-rose' : log.s === 'warn' ? 'text-amber' : 'text-sky'}>
                          {log.m}
                       </span>
                    </div>
                 ))
              )}
           </div>
           <div className="p-2 bg-sky/5 border-t border-b1 text-[8px] text-dim flex justify-between px-3">
              <span>STATUS: {running ? 'STREAMING' : 'IDLE'}</span>
              <span>BUFFER: {logs.length}/50</span>
           </div>
        </div>
      </div>

      {/* ═══ System Architecture ═══ */}
      {workflows.length > 0 && (
        <div className="glass" style={{ padding: 24, borderTop: '1px solid var(--b1)' }}>
          <h3 style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8, letterSpacing: 1, fontFamily: 'var(--mono)' }}>
            <Search size={14} style={{ color: 'var(--sky)' }} />
            SYSTEM_PIPELINE_NODES_REGISTRY
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            {workflows.map((w, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass-interactive"
                style={{
                  padding: '12px 16px', borderRadius: 2,
                  background: 'rgba(15,20,34,0.2)', border: '1px solid var(--b1)',
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--heading)', fontFamily: 'var(--mono)' }}>{w.name.toUpperCase()}</div>
                {w.description && (
                  <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 4, lineHeight: 1.4, fontFamily: 'var(--mono)', opacity: 0.8 }}>
                    {w.description}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
