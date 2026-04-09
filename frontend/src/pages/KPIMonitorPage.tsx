import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Activity, Loader2, CheckCircle, XCircle, Minus, RefreshCw } from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import ActionBar from '../components/ActionBar';
import { downloadCsv } from '../utils/exportCsv';
import { formatPercent, formatCurrency } from '../utils/format';
import { t } from '../i18n/translations';

interface KPIResult {
  metric: string;
  target: number;
  actual: number;
  status: string;
  gap_pct?: number;
}

export default function KPIMonitorPage() {
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

  // Auto-evaluate on mount if data exists
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
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 16 }}>
        <Activity size={48} style={{ color: 'var(--dim)' }} />
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)' }}>{t('ui.upload_first')}</h2>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <ActionBar
        title="KPI Monitor"
        subtitle="Track financial KPIs against industry targets"
        icon={<Activity size={20} style={{ color: 'var(--emerald)' }} />}
        exports={kpis.length > 0 ? ['csv'] : undefined}
        onExport={() => downloadCsv(kpis.map(k => ({ metric: k.metric, target: k.target, actual: k.actual, status: k.status })), 'kpi_monitor.csv')}
      >
        <button onClick={run} disabled={loading} className="btn btn-primary" style={{ padding: '6px 14px', fontSize: 11 }}>
          {loading ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Evaluating...</> : <><RefreshCw size={13} /> Re-evaluate</>}
        </button>
      </ActionBar>

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
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', marginBottom: 6 }}>{k.metric.replace(/_/g, ' ')}</div>
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

      {/* Loading skeleton */}
      {loading && kpis.length === 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton" style={{ height: 60 }} />)}
        </div>
      )}
    </div>
  );
}
