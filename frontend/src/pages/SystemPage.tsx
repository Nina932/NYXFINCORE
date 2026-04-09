import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  Server, RefreshCw, Brain, Activity, Database, Cpu,
  Clock, Zap, CheckCircle, XCircle, AlertTriangle,
  BookOpen, GitBranch, BarChart3,
} from 'lucide-react';
import { api } from '../api/client';
import { t } from '../i18n/translations';

function FadeIn({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay }}>{children}</motion.div>;
}

export default function SystemPage() {
  const { data: status, isLoading, refetch } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => api.status() as Promise<Record<string, unknown>>,
    retry: false,
    refetchInterval: 15000,
  });

  const { data: telemetry } = useQuery({
    queryKey: ['telemetry'],
    queryFn: () => api.telemetry() as Promise<Record<string, unknown>>,
    retry: false,
    refetchInterval: 15000,
  });

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: () => api.health() as Promise<Record<string, unknown>>,
    retry: false,
    refetchInterval: 30000,
  });

  const { data: kgStats } = useQuery({
    queryKey: ['kg-stats'],
    queryFn: () => fetch('/api/agent/agents/knowledge/stats').then(r => r.json()),
    retry: false,
  });

  const { data: workflow } = useQuery({
    queryKey: ['workflow'],
    queryFn: () => fetch('/api/agent/agents/workflow/pipeline').then(r => r.json()),
    retry: false,
  });

  const { data: activityMetrics } = useQuery({
    queryKey: ['activity-metrics'],
    queryFn: () => fetch('/api/agent/activity/metrics').then(r => r.json()),
    retry: false,
    refetchInterval: 15000,
  });

  // Extract data
  const registry = (status as Record<string, unknown>)?.registry as Record<string, unknown> | undefined;
  const agents = (registry?.agents as { name: string; description: string; capabilities: string[]; tool_count: number }[]) ?? [];
  const tel = (telemetry as Record<string, unknown>)?.metrics as Record<string, unknown> ?? {};
  const uptime = Number(tel.uptime_seconds ?? 0);
  const agentMetrics = tel.agents as Record<string, { calls: number; errors: number; avg_duration_ms: number }> ?? {};
  const am = activityMetrics as Record<string, unknown> | undefined;
  const totalCalls = Number(am?.total_events ?? 0) || Object.values(agentMetrics).reduce((s, a) => s + (a?.calls || 0), 0);
  const totalErrors = Number((am?.by_status as Record<string, number>)?.failure ?? 0) || Object.values(agentMetrics).reduce((s, a) => s + (a?.errors || 0), 0);

  // Health data
  const supervisor = (health as Record<string, unknown>)?.supervisor as Record<string, unknown> ?? {};
  const toolsRouted = Number(supervisor.tool_calls_routed ?? 0);
  const toolRouter = Boolean(supervisor.tool_router_installed);

  // KG data
  const kgTotal = Number((kgStats as Record<string, unknown>)?.total_entities ?? 0);
  const kgTypes = (kgStats as Record<string, unknown>)?.type_counts as Record<string, number> ?? {};

  // LLM stack
  const llmStack = (workflow as Record<string, unknown>)?.llm_stack as { tier: number; provider: string; model: string; context?: string; status: string }[] ?? [];
  const kSources = (workflow as Record<string, unknown>)?.knowledge_sources as { id: string; name: string; entities?: number; documents?: number }[] ?? [];

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* Header */}
      <FadeIn>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Server size={20} style={{ color: 'var(--sky)' }} /> System Status
            </h1>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
              Backend services, agents, knowledge graph, and LLM stack
            </p>
          </div>
          <button onClick={() => refetch()} className="btn btn-ghost">
            <RefreshCw size={13} /> {t('ui.refresh')}
          </button>
        </div>
      </FadeIn>

      {isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: 80 }} />)}
        </div>
      ) : (
        <>
          {/* Service Status Row */}
          <FadeIn delay={0.05}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
              {[
                { label: 'Backend API', icon: Server, status: 'online', color: 'var(--emerald)' },
                { label: 'SQLite DB', icon: Database, status: 'connected', color: 'var(--emerald)' },
                { label: 'ChromaDB', icon: BookOpen, status: kgTotal > 0 ? 'active' : 'unknown', color: kgTotal > 0 ? 'var(--emerald)' : 'var(--amber)' },
                { label: 'Tool Router', icon: GitBranch, status: toolRouter ? 'installed' : 'off', color: toolRouter ? 'var(--emerald)' : 'var(--rose)' },
                { label: 'Agent Mode', icon: Brain, status: String((status as Record<string, unknown>)?.mode ?? 'multi'), color: 'var(--violet)' },
              ].map((s, i) => {
                const Icon = s.icon;
                const isGood = ['online', 'connected', 'active', 'installed', 'multi'].includes(s.status);
                return (
                  <motion.div key={s.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
                    className="glass" style={{ padding: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>{s.label}</span>
                      <Icon size={14} style={{ color: s.color, opacity: 0.6 }} />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isGood
                        ? <CheckCircle size={12} style={{ color: 'var(--emerald)' }} />
                        : <AlertTriangle size={12} style={{ color: 'var(--amber)' }} />
                      }
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', textTransform: 'capitalize' }}>{s.status}</span>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </FadeIn>

          {/* Metrics Row */}
          <FadeIn delay={0.1}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
              {[
                { label: 'Uptime', value: formatUptime(uptime), icon: Clock, color: 'var(--sky)' },
                { label: 'Agent Calls', value: String(totalCalls), icon: Activity, color: 'var(--emerald)' },
                { label: 'Errors', value: String(totalErrors), icon: XCircle, color: totalErrors > 0 ? 'var(--rose)' : 'var(--emerald)' },
                { label: 'Tools Routed', value: String(toolsRouted), icon: Zap, color: 'var(--amber)' },
                { label: 'KG Entities', value: String(kgTotal), icon: BookOpen, color: 'var(--violet)' },
              ].map((m, i) => {
                const Icon = m.icon;
                return (
                  <motion.div key={m.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.04 }}
                    className="glass" style={{ padding: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)' }}>{m.label}</span>
                      <Icon size={13} style={{ color: m.color, opacity: 0.5 }} />
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--mono)', color: m.color }}>{m.value}</div>
                  </motion.div>
                );
              })}
            </div>
          </FadeIn>

          {/* Three-column: Agents + KG Types + LLM Stack */}
          <FadeIn delay={0.15}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
              {/* Agent Registry */}
              <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Brain size={14} style={{ color: 'var(--emerald)' }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Agent Registry ({agents.length})</span>
                </div>
                <div style={{ padding: 8 }}>
                  {agents.map((a, i) => (
                    <motion.div key={a.name} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.04 }}
                      style={{ padding: '10px 10px', borderRadius: 8, marginBottom: 4, background: i % 2 === 0 ? 'rgba(255,255,255,.01)' : 'transparent' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--emerald)', boxShadow: '0 0 6px var(--emerald)' }} />
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)' }}>{a.name}</span>
                        </div>
                        <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>{a.tool_count} tools</span>
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 4, paddingLeft: 14 }}>
                        {a.capabilities.slice(0, 5).map(c => (
                          <span key={c} style={{ fontSize: 8, padding: '1px 5px', borderRadius: 3, background: 'rgba(52,211,153,.06)', color: 'var(--emerald)', fontFamily: 'var(--mono)' }}>{c}</span>
                        ))}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>

              {/* Knowledge Graph Types */}
              <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <BarChart3 size={14} style={{ color: 'var(--amber)' }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Knowledge Graph ({kgTotal})</span>
                </div>
                <div style={{ padding: 10 }}>
                  {Object.entries(kgTypes).slice(0, 10).map(([type, count]) => (
                    <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 6px' }}>
                      <span style={{ flex: 1, fontSize: 11, color: 'var(--text)' }}>{type.replace(/_/g, ' ')}</span>
                      <div style={{ width: 60, height: 6, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.min(100, (count / 375) * 100)}%`, height: '100%', background: 'var(--amber)', borderRadius: 3, opacity: 0.6 }} />
                      </div>
                      <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--amber)', fontWeight: 600, width: 30, textAlign: 'right' }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* LLM Stack */}
              <div className="glass" style={{ padding: 0, overflow: 'hidden' }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--glass-border)', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Cpu size={14} style={{ color: 'var(--violet)' }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>LLM Stack</span>
                </div>
                <div style={{ padding: 8 }}>
                  {llmStack.map((llm, i) => {
                    const isActive = llm.status === 'active';
                    const colors = ['var(--emerald)', 'var(--sky)', 'var(--amber)', 'var(--muted)'];
                    return (
                      <motion.div key={llm.tier} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.04 }}
                        style={{ padding: '10px 10px', borderRadius: 8, marginBottom: 4, opacity: isActive ? 1 : 0.5 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            width: 22, height: 22, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 10, fontWeight: 800, fontFamily: 'var(--mono)',
                            background: `color-mix(in srgb, ${colors[i]} 12%, transparent)`, color: colors[i],
                          }}>{llm.tier}</div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>{llm.model}</div>
                            <div style={{ fontSize: 9, color: 'var(--muted)' }}>{llm.provider}{llm.context ? ` · ${llm.context}` : ''}</div>
                          </div>
                          {isActive && <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--emerald)', boxShadow: '0 0 8px var(--emerald)', animation: 'pulse-soft 2s ease-in-out infinite' }} />}
                        </div>
                      </motion.div>
                    );
                  })}

                  {/* Knowledge sources */}
                  <div style={{ borderTop: '1px solid var(--b1)', marginTop: 8, paddingTop: 8 }}>
                    <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: 1, padding: '0 10px 4px' }}>Data Sources</div>
                    {kSources.map(ks => (
                      <div key={ks.id} style={{ padding: '4px 10px', display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: 10, color: 'var(--muted)' }}>{ks.name}</span>
                        <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
                          {ks.entities || ks.documents || '—'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </FadeIn>
          {/* Infrastructure Status */}
          <FadeIn delay={0.2}>
            <div style={{ padding: '12px 16px', background: 'var(--bg3)', borderRadius: 8, border: '1px solid var(--b1)' }}>
              <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--heading)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Database size={14} style={{ color: 'var(--amber)' }} /> Infrastructure Status
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(() => {
                  const h = health as Record<string, unknown> | undefined;
                  const dbStatus = h?.database_status ?? (status ? 'connected' : 'unknown');
                  const smtpStatus = h?.smtp_status ?? h?.email_status ?? 'not configured';
                  const chromaStatus = kgTotal > 0 ? 'active' : 'unknown';
                  const dbOk = dbStatus === 'connected' || dbStatus === 'ok' || dbStatus === 'online';
                  const smtpOk = smtpStatus === 'connected' || smtpStatus === 'ok' || smtpStatus === 'configured' || smtpStatus === 'active';
                  const chromaOk = kgTotal > 0;
                  return (
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text)' }}>
                        {dbOk ? <CheckCircle size={12} style={{ color: 'var(--emerald)' }} /> : <AlertTriangle size={12} style={{ color: 'var(--amber)' }} />}
                        <span><b>Database:</b> {String(dbStatus)}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text)' }}>
                        {chromaOk ? <CheckCircle size={12} style={{ color: 'var(--emerald)' }} /> : <AlertTriangle size={12} style={{ color: 'var(--amber)' }} />}
                        <span><b>ChromaDB:</b> {chromaOk ? `active (${kgTotal} entities)` : 'not detected'}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text)' }}>
                        {smtpOk ? <CheckCircle size={12} style={{ color: 'var(--emerald)' }} /> : <Clock size={12} style={{ color: 'var(--amber)' }} />}
                        <span><b>SMTP Email:</b> {String(smtpStatus)}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text)' }}>
                        <Clock size={12} style={{ color: 'var(--amber)' }} />
                        <span><b>1C v8 Connector:</b> Framework ready</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text)' }}>
                        <Clock size={12} style={{ color: 'var(--amber)' }} />
                        <span><b>SAP OData Connector:</b> Framework ready</span>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          </FadeIn>
        </>
      )}
    </div>
  );
}
