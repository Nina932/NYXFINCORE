import { useState, useMemo } from 'react';

/* ─── Types ─── */
export interface TimelineEvent {
  id: string;
  timestamp: string;
  title: string;
  description?: string;
  type: string;
  severity?: 'critical' | 'warning' | 'info' | 'success';
  icon?: React.ReactNode;
  properties?: Record<string, string>;
}

interface TimelineWidgetProps {
  events: TimelineEvent[];
  orientation?: 'vertical' | 'horizontal';
  order?: 'newest-first' | 'oldest-first';
  onEventClick?: (event: TimelineEvent) => void;
  showTimeBetween?: boolean;
  maxEvents?: number;
}

/* ─── Severity colors ─── */
const SEV_COLORS: Record<string, string> = {
  critical: 'var(--rose)',
  warning: 'var(--amber)',
  info: 'var(--sky)',
  success: 'var(--emerald)',
};

const SEV_BG: Record<string, string> = {
  critical: 'rgba(239,68,68,.08)',
  warning: 'rgba(245,158,11,.08)',
  info: 'rgba(56,189,248,.08)',
  success: 'rgba(16,185,129,.08)',
};

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return ts;
  }
}

function timeBetween(a: string, b: string): string {
  try {
    const da = new Date(a);
    const db = new Date(b);
    const diffMs = Math.abs(da.getTime() - db.getTime());
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `${diffMin}m`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ${diffMin % 60}m`;
    return `${Math.floor(diffHrs / 24)}d ${diffHrs % 24}h`;
  } catch {
    return '';
  }
}

/* ─── Component ─── */
export default function TimelineWidget({
  events, orientation = 'vertical', order = 'newest-first',
  onEventClick, showTimeBetween = false, maxEvents,
}: TimelineWidgetProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredGapIdx, setHoveredGapIdx] = useState<number | null>(null);

  const sorted = useMemo(() => {
    const list = [...events].sort((a, b) => {
      const ta = new Date(a.timestamp).getTime();
      const tb = new Date(b.timestamp).getTime();
      return order === 'newest-first' ? tb - ta : ta - tb;
    });
    return maxEvents ? list.slice(0, maxEvents) : list;
  }, [events, order, maxEvents]);

  if (sorted.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
        No events to display
      </div>
    );
  }

  /* ─── Horizontal ─── */
  if (orientation === 'horizontal') {
    return (
      <div style={{ display: 'flex', gap: 0, overflowX: 'auto', padding: '12px 4px', alignItems: 'flex-start' }}>
        {sorted.map((evt, idx) => {
          const sev = evt.severity || 'info';
          const dotColor = SEV_COLORS[sev] || SEV_COLORS.info;
          const isSelected = selectedId === evt.id;
          return (
            <div key={evt.id} style={{ display: 'flex', alignItems: 'flex-start' }}>
              <div
                onClick={() => {
                  setSelectedId(isSelected ? null : evt.id);
                  onEventClick?.(evt);
                }}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  minWidth: 120, maxWidth: 160, padding: '8px 12px',
                  cursor: onEventClick ? 'pointer' : 'default',
                  animation: `fade-in .4s ease ${idx * 0.06}s both`,
                }}
              >
                <div style={{
                  width: 12, height: 12, borderRadius: '50%',
                  background: dotColor, border: isSelected ? '2px solid var(--heading)' : `2px solid ${dotColor}`,
                  boxShadow: `0 0 8px ${dotColor}40`, flexShrink: 0,
                  transition: 'all .2s',
                }} />
                <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', marginTop: 6 }}>
                  {formatTimestamp(evt.timestamp)}
                </div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', textAlign: 'center', marginTop: 4, lineHeight: 1.3 }}>
                  {evt.title}
                </div>
              </div>
              {idx < sorted.length - 1 && (
                <div style={{
                  width: 40, height: 1, background: 'var(--b2)', marginTop: 14, flexShrink: 0,
                }} />
              )}
            </div>
          );
        })}
      </div>
    );
  }

  /* ─── Vertical (default) ─── */
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, padding: '4px 0' }}>
      {sorted.map((evt, idx) => {
        const sev = evt.severity || 'info';
        const dotColor = SEV_COLORS[sev] || SEV_COLORS.info;
        const bgColor = SEV_BG[sev] || SEV_BG.info;
        const isSelected = selectedId === evt.id;
        const isLast = idx === sorted.length - 1;
        const gap = showTimeBetween && idx < sorted.length - 1
          ? timeBetween(evt.timestamp, sorted[idx + 1].timestamp)
          : '';

        return (
          <div key={evt.id} style={{ animation: `fade-in .4s ease ${idx * 0.06}s both` }}>
            <div style={{ display: 'flex', gap: 14, minHeight: 48 }}>
              {/* Timeline column: dot + line */}
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                width: 20, flexShrink: 0,
              }}>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: dotColor,
                  border: isSelected ? '2px solid var(--heading)' : 'none',
                  boxShadow: `0 0 8px ${dotColor}40`,
                  flexShrink: 0, marginTop: 4,
                  transition: 'transform .2s',
                  transform: isSelected ? 'scale(1.3)' : 'scale(1)',
                }} />
                {!isLast && (
                  <div style={{
                    flex: 1, width: 1.5,
                    background: `linear-gradient(to bottom, ${dotColor}40, var(--b1))`,
                    marginTop: 4,
                  }} />
                )}
              </div>

              {/* Content */}
              <div
                onClick={() => {
                  setSelectedId(isSelected ? null : evt.id);
                  onEventClick?.(evt);
                }}
                style={{
                  flex: 1, paddingBottom: isLast ? 0 : 16,
                  cursor: onEventClick ? 'pointer' : 'default',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  {evt.icon && <span style={{ display: 'flex', alignItems: 'center' }}>{evt.icon}</span>}
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)', lineHeight: 1.3 }}>
                    {evt.title}
                  </span>
                  <span style={{
                    fontSize: 8, fontFamily: 'var(--mono)', textTransform: 'uppercase',
                    padding: '2px 6px', borderRadius: 4,
                    background: bgColor, color: dotColor, letterSpacing: '0.5px',
                  }}>
                    {sev}
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                    {formatTimestamp(evt.timestamp)}
                  </span>
                </div>
                {evt.description && (
                  <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.5, marginBottom: 4 }}>
                    {evt.description}
                  </div>
                )}
                {/* Properties */}
                {isSelected && evt.properties && Object.keys(evt.properties).length > 0 && (
                  <div style={{
                    marginTop: 8, padding: '8px 12px', borderRadius: 8,
                    background: 'var(--bg3)', border: '1px solid var(--b1)',
                    display: 'flex', flexDirection: 'column', gap: 4,
                    animation: 'fade-in .2s ease both',
                  }}>
                    {Object.entries(evt.properties).map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
                        <span style={{ color: 'var(--muted)', fontFamily: 'var(--mono)' }}>{k}</span>
                        <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)' }}>{v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Time gap indicator */}
            {gap && (
              <div
                onMouseEnter={() => setHoveredGapIdx(idx)}
                onMouseLeave={() => setHoveredGapIdx(null)}
                style={{
                  marginLeft: 6, marginBottom: 4,
                  fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)',
                  opacity: hoveredGapIdx === idx ? 1 : 0.5,
                  transition: 'opacity .2s',
                  cursor: 'default',
                }}
              >
                {gap}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
