import { useState } from 'react';
import { X, AlertTriangle, AlertCircle } from 'lucide-react';

interface Alert {
  id?: string | number;
  severity: string;
  message: string;
}

interface AlertBannerProps {
  alerts: Alert[];
}

export default function AlertBanner({ alerts }: AlertBannerProps) {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = alerts.filter((a) => !dismissed.has(String(a.id ?? a.message)));
  if (visible.length === 0) return null;

  const dismiss = (key: string) => {
    setDismissed((prev) => new Set(prev).add(key));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
      {visible.map((alert, i) => {
        const key = String(alert.id ?? alert.message ?? i);
        const isCritical = alert.severity === 'critical';
        const Icon = isCritical ? AlertCircle : AlertTriangle;
        const color = isCritical ? 'var(--rose)' : 'var(--amber)';

        return (
          <div
            key={key}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 14px', borderRadius: 8,
              background: isCritical ? 'rgba(248,113,113,.06)' : 'rgba(251,191,36,.06)',
              border: `1px solid ${isCritical ? 'rgba(248,113,113,.15)' : 'rgba(251,191,36,.15)'}`,
            }}
          >
            <Icon size={16} style={{ color, flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: 12, color }}>{alert.message}</span>
            <button
              onClick={() => dismiss(key)}
              style={{ background: 'none', border: 'none', color, cursor: 'pointer', padding: 2, opacity: 0.7 }}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
