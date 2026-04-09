import { useState, useEffect } from 'react';
import { RefreshCcw, Activity, Zap, Database, BarChart3, Loader2, Play, Info } from 'lucide-react';
import MetricCardWidget from '../components/widgets/MetricCardWidget';
import { api } from '../api/client';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8, padding: 16 };

export default function FlywheelPage() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await api.flywheelStatus();
      setStatus(data);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchStatus(); }, []);

  const triggerCycle = async () => {
    setTriggering(true);
    try {
      await api.flywheelTrigger();
      await fetchStatus();
    } catch {}
    setTriggering(false);
  };

  const fw = status?.flywheel || {};
  const cal = status?.calibration || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <RefreshCcw size={20} style={{ color: 'var(--violet)' }} /> Data Flywheel
          </h1>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
            Self-improving AI loop: Collect → Score → Learn → Calibrate → Improve
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={triggerCycle} disabled={triggering} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 16px', borderRadius: 8, fontSize: 11, fontWeight: 600,
            background: 'var(--gradient-primary)', color: 'var(--heading)',
            border: 'none', cursor: 'pointer', opacity: triggering ? 0.7 : 1,
          }}>
            {triggering ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={13} />}
            Run Cycle
          </button>
          <button onClick={fetchStatus} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 14px', borderRadius: 8, fontSize: 11,
            background: 'var(--bg2)', color: 'var(--text)',
            border: '1px solid var(--b1)', cursor: 'pointer',
          }}>
            <RefreshCcw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* Flywheel Pipeline Visualization */}
      <div style={{ ...card, padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0, flexWrap: 'wrap' }}>
          {[
            { label: 'COLLECT', icon: Database, color: 'var(--sky)', desc: 'Log interactions' },
            { label: 'SCORE', icon: Zap, color: 'var(--violet)', desc: 'LLM-as-judge' },
            { label: 'LEARN', icon: Activity, color: 'var(--emerald)', desc: 'Sync corrections to KG' },
            { label: 'CALIBRATE', icon: BarChart3, color: 'var(--amber)', desc: 'Adjust predictions' },
            { label: 'IMPROVE', icon: RefreshCcw, color: 'var(--cerulean)', desc: 'Better responses' },
          ].map((step, i) => (
            <div key={step.label} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                padding: '12px 20px', borderRadius: 12,
                background: `color-mix(in srgb, ${step.color} 8%, transparent)`,
                border: `1px solid color-mix(in srgb, ${step.color} 20%, transparent)`,
                minWidth: 100,
              }}>
                <step.icon size={20} style={{ color: step.color }} />
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1, color: step.color }}>{step.label}</span>
                <span style={{ fontSize: 8, color: 'var(--muted)' }}>{step.desc}</span>
              </div>
              {i < 4 && (
                <div style={{ width: 30, height: 2, background: 'var(--b2)', margin: '0 -1px' }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        <MetricCardWidget label="Total Interactions" value={fw.total_interactions ?? 0} format="number" size="compact"
          conditionalRules={[{ condition: 'gt', threshold: 0, color: 'var(--sky)' }]} />
        <MetricCardWidget label="Scored" value={fw.scored ?? 0} format="number" size="compact"
          conditionalRules={[{ condition: 'gt', threshold: 0, color: 'var(--emerald)' }]} />
        <MetricCardWidget label="Avg Quality" value={fw.avg_quality ? fw.avg_quality * 5 : 0} format="number" size="compact"
          secondaryLabel="out of 5"
          conditionalRules={[{ condition: 'gt', threshold: 3, color: 'var(--emerald)' }, { condition: 'lt', threshold: 3, color: 'var(--rose)' }]} />
        <MetricCardWidget label="Cycles Run" value={status?.cycle_count ?? 0} format="number" size="compact"
          conditionalRules={[{ condition: 'gt', threshold: 0, color: 'var(--violet)' }]} />
        <MetricCardWidget label="Active Calibrations" value={cal.active_factors ?? 0} format="number" size="compact"
          conditionalRules={[{ condition: 'gt', threshold: 0, color: 'var(--amber)' }]} />
      </div>

      {/* Empty state — no interactions yet */}
      {!loading && status && (fw.total_interactions ?? 0) === 0 && (
        <div style={{
          ...card, padding: 24, display: 'flex', alignItems: 'flex-start', gap: 14,
          background: 'color-mix(in srgb, var(--sky) 6%, var(--bg2))',
          border: '1px solid color-mix(in srgb, var(--sky) 20%, var(--b1))',
        }}>
          <Info size={18} style={{ color: 'var(--sky)', flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', marginBottom: 4 }}>
              No interactions recorded yet
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', margin: 0, lineHeight: 1.6 }}>
              The Data Flywheel improves itself over time by learning from your usage.
              Start by uploading financial data, asking questions in the chat, or running analyses.
              Once enough interactions are collected, the flywheel will score response quality,
              sync corrections to the knowledge graph, and calibrate predictions automatically.
            </p>
          </div>
        </div>
      )}

      {/* Recent Cycles */}
      {status?.recent_cycles && status.recent_cycles.length > 0 && (
        <div style={card}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={14} style={{ color: 'var(--sky)' }} /> Recent Cycles
          </div>
          <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                <th style={{ padding: '6px 8px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)' }}>Cycle</th>
                <th style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--muted)', fontSize: 9 }}>Scored</th>
                <th style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--muted)', fontSize: 9 }}>Synced</th>
                <th style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--muted)', fontSize: 9 }}>Calibrated</th>
                <th style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--muted)', fontSize: 9 }}>Duration</th>
              </tr>
            </thead>
            <tbody>
              {status.recent_cycles.map((c: any, i: number) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--b1)' }}>
                  <td style={{ padding: '6px 8px', fontFamily: 'var(--mono)', color: 'var(--sky)' }}>#{c.cycle}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{c.scored}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{c.synced_to_kg}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)' }}>{c.calibrations_updated}</td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{c.duration_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Calibration Factors */}
      {cal.factors && Object.keys(cal.factors).length > 0 && (
        <div style={card}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            <BarChart3 size={14} style={{ color: 'var(--amber)' }} /> Active Calibration Factors
          </div>
          {Object.entries(cal.factors).map(([key, factor]) => (
            <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid var(--b1)', fontSize: 11 }}>
              <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)' }}>{key}</span>
              <span style={{ color: 'var(--amber)', fontWeight: 600, fontFamily: 'var(--mono)' }}>{String(factor)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Status info */}
      <div style={{ fontSize: 10, color: 'var(--muted)', display: 'flex', gap: 16 }}>
        <span>Loop: {status?.running ? 'Running' : 'Idle'}</span>
        <span>Interval: {status?.cycle_interval_seconds ?? 300}s</span>
        <span>Scoring queue: {status?.scoring_queue_size ?? 0}</span>
        {status?.learning?.corrections_pending_sync > 0 && (
          <span style={{ color: 'var(--amber)' }}>Pending KG sync: {status.learning.corrections_pending_sync}</span>
        )}
      </div>
    </div>
  );
}
