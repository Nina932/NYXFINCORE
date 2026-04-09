import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bell, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { api } from '../api/client';
import ActionBar from '../components/ActionBar';
import { downloadCsv } from '../utils/exportCsv';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };

export default function AlertsPage() {
  const [filter, setFilter] = useState<string>('all');

  const { data, isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.alerts(),
    refetchInterval: 15000,
  });

  const dataObj = data as Record<string, unknown> | null | undefined;
  let raw = Array.isArray(data) ? data : (dataObj?.alerts || []);
  if (!Array.isArray(raw)) raw = [];
  const alerts = raw as { severity: string; message: string; metric?: string; created_at?: string; id?: number }[];
  const filtered = filter === 'all' ? alerts : alerts.filter(a => a.severity === filter);

  const counts = { critical: alerts.filter(a => a.severity === 'critical').length, warning: alerts.filter(a => a.severity === 'warning').length, info: alerts.filter(a => a.severity === 'info').length };

  const sevIcon = (sev: string) => {
    if (sev === 'critical') return <AlertCircle size={14} style={{ color: 'var(--rose)' }} />;
    if (sev === 'warning') return <AlertTriangle size={14} style={{ color: 'var(--amber)' }} />;
    return <Info size={14} style={{ color: 'var(--blue)' }} />;
  };

  const sevColor = (sev: string) => sev === 'critical' ? 'var(--rose)' : sev === 'warning' ? 'var(--amber)' : 'var(--blue)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <ActionBar
        title="Alerts"
        subtitle="Auto-refreshes every 15 seconds"
        icon={<Bell size={20} style={{ color: 'var(--amber)' }} />}
        exports={alerts.length > 0 ? ['csv'] : undefined}
        onExport={() => downloadCsv(alerts.map((a: Record<string, unknown>) => ({ severity: a.severity, message: a.message, metric: a.metric, created: a.created_at })), 'alerts.csv')}
      />

      {/* Counters */}
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

      {/* Alert list */}
      {isLoading ? (
        <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>Loading alerts...</p></div>
      ) : filtered.length === 0 ? (
        <div style={{ ...card, padding: 24, textAlign: 'center' }}><p style={{ color: 'var(--muted)', fontSize: 12 }}>No alerts</p></div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map((a, i) => (
            <div key={a.id ?? i} style={{ ...card, padding: 12, display: 'flex', alignItems: 'center', gap: 10, borderLeftWidth: 3, borderLeftColor: sevColor(a.severity) }}>
              {sevIcon(a.severity)}
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, color: 'var(--heading)' }}>{a.message}</p>
                <div style={{ display: 'flex', gap: 10, marginTop: 2 }}>
                  {a.metric && <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>{a.metric}</span>}
                  {a.created_at && <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>{a.created_at}</span>}
                </div>
              </div>
              <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: `${sevColor(a.severity)}15`, color: sevColor(a.severity), fontFamily: 'var(--mono)', textTransform: 'uppercase' }}>
                {a.severity}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
