import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Bell, Activity, Clock, AlertTriangle, AlertCircle, Info,
  CheckCircle, XCircle, Minus, RefreshCw, Loader2, Play, TrendingDown,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts';
import { useStore } from '../store/useStore';
import { api, captainChat } from '../api/client';
import { useObjects } from '../hooks/useOntology';
import { useReactiveFilter } from '../hooks/useReactiveFilter';
import ActionBar from '../components/ActionBar';
import AIInsightPanel from '../components/AIInsightPanel';
import { downloadCsv } from '../utils/exportCsv';
import { downloadExcel } from '../utils/exportExcel';
import { formatPercent, formatCurrency } from '../utils/format';

/* ─── Types ─── */
interface KPIResult {
  metric: string;
  target: number;
  actual: number;
  status: string;
  gap_pct?: number;
}

type TabKey = 'alerts' | 'kpi' | 'runway';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 10 };

/* ─── Tab Button ─── */
function TabBtn({ active, label, badge, badgeColor, icon: Icon, onClick }: {
  active: boolean; label: string; badge?: number; badgeColor?: string; icon: React.ElementType; onClick: () => void;
}) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '7px 16px',
      borderRadius: 8, fontSize: 12, fontWeight: active ? 600 : 400, cursor: 'pointer',
      background: active ? 'rgba(56,189,248,.08)' : 'transparent',
      border: `1px solid ${active ? 'var(--sky)' : 'var(--b1)'}`,
      color: active ? 'var(--sky)' : 'var(--muted)', transition: 'all .15s',
    }}>
      <Icon size={14} />
      {label}
      {badge !== undefined && badge > 0 && (
        <span style={{
          fontFamily: 'var(--mono)', fontSize: 9, padding: '1px 6px', borderRadius: 10,
          background: `${badgeColor ?? 'var(--sky)'}15`, color: badgeColor ?? 'var(--sky)',
        }}>
          {badge}
        </span>
      )}
    </button>
  );
}

/* ─── Resolution Stats Banner ─── */
function ResolutionStatsBanner() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    api.alertResolutionStats().then((d: unknown) => setStats(d as Record<string, unknown>)).catch(() => {});
  }, []);

  if (!stats || (stats as Record<string, unknown>).error) return null;

  const total = (stats.total_decisions as number) || 0;
  if (total === 0) return null;

  const dcounts = (stats.decision_counts as Record<string, number>) || {};
  const resolved = (dcounts.resolve || 0) + (dcounts.dismiss || 0);
  const escalated = dcounts.escalate || 0;
  const fpRate = (stats.false_positive_rate as number) || 0;
  const avgHrs = (stats.avg_time_hours as number) || 0;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 4 }}>
      {[
        { label: 'Total Resolved', value: `${resolved}`, color: 'var(--emerald)' },
        { label: 'Avg Resolution', value: avgHrs > 0 ? `${avgHrs.toFixed(1)}h` : '<1h', color: 'var(--sky)' },
        { label: 'Escalation Rate', value: `${((escalated / Math.max(total, 1)) * 100).toFixed(0)}%`, color: 'var(--amber)' },
        { label: 'False Positive', value: `${fpRate.toFixed(0)}%`, color: 'var(--violet)' },
      ].map(s => (
        <div key={s.label} style={{ ...card, padding: 12, textAlign: 'center' }}>
          <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--mono)', color: s.color }}>{s.value}</div>
          <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>{s.label}</div>
        </div>
      ))}
    </div>
  );
}

/* ─── Alerts Tab ─── */
function AlertsTab() {
  const [filter, setFilter] = useState<string>('all');
  const [investigating, setInvestigating] = useState<number | null>(null);
  const [investigation, setInvestigation] = useState<Record<number, string>>({});
  const [resolving, setResolving] = useState<number | null>(null);
  const [resolveExplanation, setResolveExplanation] = useState('');
  const [resolveType, setResolveType] = useState('root_cause_fixed');
  const [resolved, setResolved] = useState<Record<number, { decision: string; by: string; at: string }>>({});
  const alertFilter = useReactiveFilter('selectedAlert');

  // Ontology risk signals via useObjects hook
  const { objects: riskSignals, isLoading: riskLoading } = useObjects({
    type: 'RiskSignal',
    where: { severity: 'critical' },
    limit: 50,
    enabled: true,
  });

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.alerts(),
    refetchInterval: 15000,
  });

  const raw = Array.isArray(data) ? data : ((data as Record<string, unknown> | undefined)?.alerts ?? []);
  const alerts = raw as { severity: string; message: string; metric?: string; created_at?: string; id?: number }[];
  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.severity === filter);

  const counts = {
    critical: alerts.filter(a => a.severity === 'critical').length,
    warning: alerts.filter(a => a.severity === 'warning').length,
    info: alerts.filter(a => a.severity === 'info').length,
  };

  const sevIcon = (sev: string) => {
    if (sev === 'critical') return <AlertCircle size={14} style={{ color: 'var(--rose)' }} />;
    if (sev === 'warning') return <AlertTriangle size={14} style={{ color: 'var(--amber)' }} />;
    return <Info size={14} style={{ color: 'var(--blue)' }} />;
  };
  const sevColor = (sev: string) => sev === 'critical' ? 'var(--rose)' : sev === 'warning' ? 'var(--amber)' : 'var(--blue)';

  const handleResolve = async (alertId: number, decision: string) => {
    if (decision === 'resolve' && resolving !== alertId) {
      setResolving(alertId);
      setResolveExplanation('');
      setResolveType('root_cause_fixed');
      return;
    }
    try {
      if (decision === 'escalate') {
        await api.escalateAlert(alertId, 'Escalated for review');
      } else if (decision === 'acknowledge') {
        await api.resolveAlert(alertId, 'acknowledge', '', 'accepted_risk');
      } else if (decision === 'dismiss') {
        await api.resolveAlert(alertId, 'dismiss', 'False positive', 'false_positive');
      } else {
        await api.resolveAlert(alertId, decision, resolveExplanation, resolveType);
      }
      setResolved(prev => ({ ...prev, [alertId]: { decision, by: 'user', at: new Date().toISOString().slice(0, 16) } }));
      setResolving(null);
      refetch();
    } catch { /* silent */ }
  };

  const actionBtnStyle = (bg: string, fg: string): React.CSSProperties => ({
    fontSize: 9, padding: '3px 7px', borderRadius: 4,
    background: `${bg}12`, border: `1px solid ${bg}25`, color: fg,
    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap',
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Resolution Stats */}
      <ResolutionStatsBanner />

      {/* Severity filter pills */}
      <div style={{ display: 'flex', gap: 8 }}>
        {[
          { key: 'all', label: `All (${alerts.length})` },
          { key: 'critical', label: `Critical (${counts.critical})`, color: 'var(--rose)' },
          { key: 'warning', label: `Warning (${counts.warning})`, color: 'var(--amber)' },
          { key: 'info', label: `Info (${counts.info})`, color: 'var(--blue)' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: '4px 12px', borderRadius: 14, fontSize: 10, fontFamily: 'var(--mono)',
            background: filter === f.key ? (f.color ? `${f.color}15` : 'rgba(56,189,248,.1)') : 'var(--bg2)',
            border: `1px solid ${filter === f.key ? (f.color ?? 'var(--sky)') : 'var(--b1)'}`,
            color: filter === f.key ? (f.color ?? 'var(--sky)') : 'var(--muted)', cursor: 'pointer',
          }}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Ontology Risk Signals (from useObjects hook) */}
      {riskSignals.length > 0 && (
        <div style={{ ...card, padding: 14, borderColor: 'rgba(239,68,68,.15)', background: 'rgba(239,68,68,.02)' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--rose)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertCircle size={13} /> Ontology Risk Signals ({riskSignals.length} critical)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {riskSignals.slice(0, 5).map((sig: any, i: number) => {
              const props = sig.properties || sig;
              return (
                <div key={sig.object_id || i} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px',
                  background: 'rgba(239,68,68,.04)', borderRadius: 4,
                }}>
                  <AlertTriangle size={10} style={{ color: 'var(--rose)', flexShrink: 0 }} />
                  <span style={{ fontSize: 10, color: 'var(--text)', flex: 1 }}>
                    {props.message || props.metric || sig.object_id}
                  </span>
                  <span style={{ fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--rose)' }}>
                    {props.severity || 'critical'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Export */}
      {alerts.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={() => downloadCsv(alerts.map((a: Record<string, unknown>) => ({ severity: a.severity, message: a.message, metric: a.metric, created: a.created_at })), 'alerts.csv')}
            className="btn btn-ghost" style={{ fontSize: 10, padding: '4px 10px' }}>Export CSV</button>
        </div>
      )}

      {/* Alert list */}
      {isLoading ? (
        <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>Loading alerts...</p></div>
      ) : filtered.length === 0 ? (
        <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>No alerts</p></div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map((a, idx) => {
            const alertIdx = a.id ?? idx;
            const isInvestigating = investigating === alertIdx;
            const result = investigation[alertIdx];
            const isResolvedAlert = resolved[alertIdx];
            const isResolvingThis = resolving === alertIdx;
            return (
            <div key={alertIdx}>
              <div style={{ ...card, padding: 12, display: 'flex', alignItems: 'center', gap: 10, borderLeftWidth: 3, borderLeftColor: isResolvedAlert ? 'var(--emerald)' : sevColor(a.severity), borderRadius: (result || isResolvingThis) ? '8px 8px 0 0' : 8 }}>
                {isResolvedAlert ? <CheckCircle size={14} style={{ color: 'var(--emerald)' }} /> : sevIcon(a.severity)}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12, color: isResolvedAlert ? 'var(--muted)' : '#fff', margin: 0, textDecoration: isResolvedAlert ? 'line-through' : 'none' }}>{a.message}</p>
                  <div style={{ display: 'flex', gap: 10, marginTop: 2, flexWrap: 'wrap' }}>
                    {a.metric && <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{a.metric}</span>}
                    {a.created_at && <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>{a.created_at}</span>}
                    {isResolvedAlert && (
                      <span style={{ fontSize: 9, padding: '1px 5px', borderRadius: 3, background: 'rgba(16,185,129,.1)', color: 'var(--emerald)', fontFamily: 'var(--mono)' }}>
                        {isResolvedAlert.decision} by {isResolvedAlert.by} at {isResolvedAlert.at}
                      </span>
                    )}
                  </div>
                </div>

                {/* Resolution action buttons */}
                {!isResolvedAlert && (
                  <div style={{ display: 'flex', gap: 3, flexShrink: 0 }}>
                    <button onClick={() => handleResolve(alertIdx, 'acknowledge')} style={actionBtnStyle('var(--amber)', 'var(--amber)')}>
                      <Minus size={9} /> Ack
                    </button>
                    <button onClick={() => handleResolve(alertIdx, 'resolve')} style={actionBtnStyle('var(--emerald)', 'var(--emerald)')}>
                      <CheckCircle size={9} /> Resolve
                    </button>
                    <button onClick={() => handleResolve(alertIdx, 'escalate')} style={actionBtnStyle('var(--rose)', 'var(--rose)')}>
                      <AlertCircle size={9} /> Escalate
                    </button>
                    <button onClick={() => handleResolve(alertIdx, 'dismiss')} style={actionBtnStyle('var(--dim)', 'var(--dim)')}>
                      <XCircle size={9} /> Dismiss
                    </button>
                  </div>
                )}

                <button
                  disabled={isInvestigating}
                  onClick={async () => {
                    setInvestigating(alertIdx);
                    try {
                      const res = await captainChat(`Investigate this financial alert: "${a.message}" (severity: ${a.severity}, metric: ${a.metric || 'unknown'}). What could cause this? What should management do?`);
                      setInvestigation(prev => ({ ...prev, [alertIdx]: res.content }));
                    } catch { setInvestigation(prev => ({ ...prev, [alertIdx]: 'AI investigation unavailable.' })); }
                    finally { setInvestigating(null); }
                  }}
                  style={{ fontSize: 9, padding: '3px 8px', borderRadius: 4, background: 'rgba(56,189,248,.08)', border: '1px solid rgba(56,189,248,.15)', color: 'var(--sky)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}
                >
                  {isInvestigating ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} /> : <Info size={10} />}
                  Investigate
                </button>
                <span
                  onClick={() => alertFilter.set({ index: alertIdx, message: a.message, severity: a.severity, metric: a.metric })}
                  style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: `${sevColor(a.severity)}15`, color: sevColor(a.severity), fontFamily: 'var(--mono)', textTransform: 'uppercase', cursor: 'pointer' }}
                >
                  {a.severity}
                </span>
              </div>

              {/* Resolve panel */}
              {isResolvingThis && (
                <div style={{ ...card, borderTop: 'none', borderTopLeftRadius: 0, borderTopRightRadius: 0, padding: '12px 14px', borderLeft: '3px solid var(--emerald)', marginTop: -1 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span style={{ fontSize: 10, color: 'var(--muted)', minWidth: 90 }}>Resolution Type:</span>
                      <select
                        value={resolveType}
                        onChange={e => setResolveType(e.target.value)}
                        style={{ flex: 1, padding: '4px 8px', borderRadius: 6, fontSize: 11, background: 'var(--bg3)', border: '1px solid var(--b1)', color: 'var(--text)' }}
                      >
                        <option value="root_cause_fixed">Root Cause Fixed</option>
                        <option value="workaround">Workaround Applied</option>
                        <option value="false_positive">False Positive</option>
                        <option value="accepted_risk">Accepted Risk</option>
                      </select>
                    </div>
                    <textarea
                      value={resolveExplanation}
                      onChange={e => setResolveExplanation(e.target.value)}
                      placeholder="Explain what was done to resolve this alert..."
                      rows={2}
                      style={{ width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 11, background: 'var(--bg3)', border: '1px solid var(--b1)', color: 'var(--text)', resize: 'vertical', fontFamily: 'inherit' }}
                    />
                    <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                      <button onClick={() => setResolving(null)} style={{ fontSize: 10, padding: '4px 12px', borderRadius: 6, background: 'var(--bg3)', border: '1px solid var(--b1)', color: 'var(--muted)', cursor: 'pointer' }}>
                        Cancel
                      </button>
                      <button onClick={() => handleResolve(alertIdx, 'resolve')} style={{ fontSize: 10, padding: '4px 12px', borderRadius: 6, background: 'var(--emerald)', border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
                        Confirm Resolution
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Selected alert detail panel */}
              {(alertFilter.value as any)?.index === alertIdx && (
                <div style={{ ...card, borderTop: 'none', borderTopLeftRadius: 0, borderTopRightRadius: 0, padding: '10px 14px', borderLeft: '3px solid var(--sky)', marginTop: -1, background: 'rgba(56,189,248,.03)' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--sky)', marginBottom: 4 }}>Selected Alert Context</div>
                  <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.5 }}>
                    Severity: {a.severity} {a.metric ? `| Metric: ${a.metric}` : ''} {a.created_at ? `| Time: ${a.created_at}` : ''}
                  </div>
                  <button
                    onClick={() => alertFilter.clear()}
                    style={{ fontSize: 9, padding: '3px 8px', borderRadius: 4, background: 'var(--bg3)', border: '1px solid var(--b1)', color: 'var(--muted)', cursor: 'pointer', marginTop: 6 }}
                  >
                    Clear Selection
                  </button>
                </div>
              )}
              {result && (
                <div style={{ ...card, borderTop: 'none', borderTopLeftRadius: 0, borderTopRightRadius: 0, padding: '10px 14px', borderLeft: `3px solid var(--sky)`, marginTop: -1 }}>
                  <div style={{ fontSize: 11, lineHeight: 1.7, color: 'var(--text)', whiteSpace: 'pre-wrap' }}>{result}</div>
                </div>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── KPI Tab ─── */
function KPITab() {
  const { pnl } = useStore();
  const [kpis, setKpis] = useState<KPIResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const run = async () => {
    if (!pnl) return;
    setLoading(true); setError('');
    try {
      const data = await api.kpi(pnl);
      const d = data as Record<string, unknown>;
      const arr = Array.isArray(data) ? data : (d?.kpis ?? d?.kpi_statuses ?? []) as KPIResult[];
      setKpis(arr);
    } catch (err) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (pnl && kpis.length === 0) run(); }, [pnl]);

  const statusIcon = (s: string) => {
    if (s === 'on_track') return <CheckCircle size={14} style={{ color: 'var(--emerald)' }} />;
    if (s === 'at_risk') return <Minus size={14} style={{ color: 'var(--amber)' }} />;
    return <XCircle size={14} style={{ color: 'var(--rose)' }} />;
  };
  const statusColor = (s: string) => s === 'on_track' ? 'var(--emerald)' : s === 'at_risk' ? 'var(--amber)' : 'var(--rose)';

  const onTrack = kpis.filter(k => k.status === 'on_track').length;
  const atRisk = kpis.filter(k => k.status === 'at_risk').length;
  const missed = kpis.filter(k => k.status === 'missed' || k.status === 'off_track').length;

  if (!pnl) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 12 }}>
        <Activity size={36} style={{ color: 'var(--dim)' }} />
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>Upload financial data to evaluate KPIs</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {kpis.length > 0 && (
            <button onClick={() => downloadCsv(kpis.map(k => ({ metric: k.metric, target: k.target, actual: k.actual, status: k.status })), 'kpi_monitor.csv')}
              className="btn btn-ghost" style={{ fontSize: 10, padding: '4px 10px' }}>Export CSV</button>
          )}
        </div>
        <button onClick={run} disabled={loading} className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 11 }}>
          {loading ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Evaluating...</> : <><RefreshCw size={13} /> Re-evaluate</>}
        </button>
      </div>

      {error && <div className="glass" style={{ padding: 12, borderColor: 'var(--rose)', color: 'var(--rose)', fontSize: 12 }}>{error}</div>}

      {/* Summary cards */}
      {kpis.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {[
            { label: 'On Track', count: onTrack, icon: CheckCircle, color: 'var(--emerald)' },
            { label: 'At Risk', count: atRisk, icon: Minus, color: 'var(--amber)' },
            { label: 'Missed', count: missed, icon: XCircle, color: 'var(--rose)' },
          ].map(s => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="glass" style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `color-mix(in srgb, ${s.color} 10%, transparent)` }}>
                  <Icon size={18} style={{ color: s.color }} />
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--mono)', color: s.color }}>{s.count}</div>
                  <div style={{ fontSize: 10, color: 'var(--muted)' }}>{s.label}</div>
                </div>
              </div>
            );
          })}
        </motion.div>
      )}

      {/* KPI list */}
      {kpis.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {kpis.map((k, i) => {
            const pct = k.target ? Math.min(150, (k.actual / k.target) * 100) : 0;
            return (
              <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                className="glass" style={{ padding: 14, display: 'flex', alignItems: 'center', gap: 14 }}>
                {statusIcon(k.status)}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', marginBottom: 2 }}>{k.metric.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 9, color: 'var(--dim)', marginBottom: 4 }}>
                    {k.status === 'on_track' ? 'Performing within target range' :
                     k.status === 'at_risk' ? 'Approaching threshold - monitor closely' :
                     'Below target - action recommended'}
                  </div>
                  <div style={{ height: 8, background: 'var(--bg3)', borderRadius: 4, overflow: 'hidden' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, pct)}%` }}
                      transition={{ duration: 0.5, delay: 0.2 + i * 0.04 }}
                      style={{ height: '100%', background: statusColor(k.status), borderRadius: 4, opacity: 0.7 }}
                    />
                  </div>
                </div>
                <div style={{ textAlign: 'right', minWidth: 80 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, color: statusColor(k.status) }}>
                    {Math.abs(k.actual) > 1000 ? formatCurrency(k.actual) : formatPercent(k.actual)}
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)' }}>
                    target: {Math.abs(k.target) > 1000 ? formatCurrency(k.target) : formatPercent(k.target)}
                  </div>
                  {k.gap_pct !== undefined && (
                    <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: k.gap_pct >= 0 ? 'var(--emerald)' : 'var(--rose)' }}>
                      {k.gap_pct >= 0 ? '+' : ''}{k.gap_pct.toFixed(1)}%
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {loading && kpis.length === 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton" style={{ height: 60 }} />)}
        </div>
      )}
    </div>
  );
}

/* ─── Cash Runway Tab ─── */
function RunwayTab() {
  const { pnl, balance_sheet } = useStore();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const cash = balance_sheet?.cash ?? balance_sheet?.cash_and_equivalents ?? 0;
  const revenue = pnl?.revenue ?? pnl?.total_revenue ?? 0;
  const expenses = Math.abs(pnl?.cogs ?? 0) + Math.abs(pnl?.selling_expenses ?? 0) + Math.abs(pnl?.admin_expenses ?? pnl?.ga_expenses ?? 0);
  const netMonthly = revenue - expenses;

  const run = async () => {
    if (!pnl) return;
    setLoading(true); setError('');
    try { setResult(await api.runway(cash, revenue, expenses) as Record<string, unknown>); }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed'); }
    finally { setLoading(false); }
  };

  useEffect(() => { if (pnl && !result) run(); }, [pnl]);

  const months = (result?.months as number) ?? 0;
  const riskLevel = (result?.risk_level as string) ?? '';
  const burnRate = (result?.burn_rate as number) ?? 0;
  const riskColor = riskLevel === 'safe' || riskLevel === 'low' ? 'var(--emerald)' : riskLevel === 'medium' ? 'var(--amber)' : 'var(--rose)';

  const projectionData = useMemo(() => {
    if (!cash || !burnRate) return [];
    const data = [];
    let balance = cash;
    const projMonths = Math.min(Math.max(months * 1.5, 6), 36);
    for (let m = 0; m <= projMonths; m++) {
      data.push({ month: m, label: `M${m}`, cash: Math.max(balance, 0), danger: balance < 0 ? Math.abs(balance) : 0 });
      balance -= Math.abs(burnRate);
    }
    return data;
  }, [cash, burnRate, months]);

  if (!pnl) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 200, gap: 12 }}>
        <Clock size={36} style={{ color: 'var(--dim)' }} />
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>Upload financial data to calculate runway</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={run} disabled={loading} className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 11 }}>
          {loading ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Calculating...</> : <><Play size={13} /> Calculate</>}
        </button>
      </div>

      {error && <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px' }}>{error}</div>}

      {result && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 10 }}>
            <div style={{ ...card, padding: 20, textAlign: 'center' }}>
              <div style={{ fontSize: 42, fontWeight: 800, color: riskColor, fontFamily: 'var(--mono)', lineHeight: 1 }}>{months.toFixed(0)}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 6 }}>months of runway</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4, marginTop: 8 }}>
                {riskLevel === 'safe' || riskLevel === 'low' ? <CheckCircle size={12} style={{ color: riskColor }} /> : <AlertTriangle size={12} style={{ color: riskColor }} />}
                <span style={{ fontSize: 9, fontFamily: 'var(--mono)', padding: '2px 6px', borderRadius: 3, background: `color-mix(in srgb, ${riskColor} 12%, transparent)`, color: riskColor, textTransform: 'uppercase', letterSpacing: 1 }}>
                  {riskLevel}
                </span>
              </div>
            </div>
            {[
              { label: 'Cash Balance', value: formatCurrency(cash), color: 'var(--sky)' },
              { label: 'Monthly Burn', value: formatCurrency(burnRate), color: 'var(--rose)' },
              { label: 'Net Monthly', value: formatCurrency(netMonthly), color: netMonthly >= 0 ? 'var(--emerald)' : 'var(--rose)' },
            ].map(m => (
              <div key={m.label} style={{ ...card, padding: 16 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--muted)', marginBottom: 6 }}>{m.label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: m.color, fontFamily: 'var(--mono)' }}>{m.value}</div>
              </div>
            ))}
          </div>

          {projectionData.length > 0 && (
            <div style={{ ...card, padding: 16 }}>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6, margin: '0 0 14px 0' }}>
                <TrendingDown size={14} style={{ color: 'var(--amber)' }} /> Cash Depletion Projection
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={projectionData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" />
                  <XAxis dataKey="label" tick={{ fontSize: 9, fill: 'var(--muted)' }} />
                  <YAxis tick={{ fontSize: 9, fill: 'var(--muted)' }} tickFormatter={(v: number) => `₾${(v/1e6).toFixed(0)}M`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8, fontSize: 11 }}
                    formatter={(value: any) => formatCurrency(Number(value || 0))}
                  />
                  <ReferenceLine y={0} stroke="var(--rose)" strokeDasharray="3 3" label={{ value: 'Zero', fill: 'var(--rose)', fontSize: 9 }} />
                  <Area type="monotone" dataKey="cash" stroke="var(--sky)" fill="rgba(56,189,248,.1)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Main Monitoring Page ─── */
export default function MonitoringPage() {
  const [tab, setTab] = useState<TabKey>('alerts');
  const { pnl } = useStore();

  // Fetch alert count for badge
  const { data: alertData } = useQuery({
    queryKey: ['alerts-badge'],
    queryFn: () => api.alerts(),
    refetchInterval: 15000,
  });
  const alertCount = Array.isArray(alertData) ? alertData.length : ((alertData as Record<string, unknown> | undefined)?.alerts as unknown[] | undefined)?.length ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <ActionBar
        title="Monitoring"
        subtitle="Alerts, KPIs, and Cash Runway — unified view"
        icon={<Bell size={20} style={{ color: 'var(--amber)' }} />}
        exports={['excel']}
        onExport={async () => {
          try {
            await downloadExcel(
              { pnl: pnl || {}, monitoring: true, company: 'Company', period: '' },
              `Monitoring_Export.xlsx`,
            );
          } catch { /* fallback */ }
        }}
      />

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 8 }}>
        <TabBtn active={tab === 'alerts'} label="Alerts" badge={alertCount} badgeColor="var(--rose)" icon={Bell} onClick={() => setTab('alerts')} />
        <TabBtn active={tab === 'kpi'} label="KPI Status" icon={Activity} onClick={() => setTab('kpi')} />
        <TabBtn active={tab === 'runway'} label="Cash Runway" icon={Clock} onClick={() => setTab('runway')} />
      </div>

      {/* Tab content */}
      {tab === 'alerts' && <AlertsTab />}
      {tab === 'kpi' && <KPITab />}
      {tab === 'runway' && <RunwayTab />}

      {/* AI Insight Panel */}
      <AIInsightPanel pageName="Monitoring" context={`${alertCount} active alerts, current tab: ${tab}`} />
    </div>
  );
}
