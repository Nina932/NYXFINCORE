import { useState, useId } from 'react';
import { ResponsiveContainer, Area, AreaChart } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';

/* ─── Types ─── */
interface ConditionalRule {
  condition: 'gt' | 'lt' | 'eq';
  threshold: number;
  color: string;
}

interface MetricCardWidgetProps {
  label: string;
  value: number | string;
  format?: 'currency' | 'percentage' | 'number' | 'string';
  secondaryValue?: number | string;
  secondaryLabel?: string;
  conditionalRules?: ConditionalRule[];
  sparkData?: number[];
  size?: 'compact' | 'regular' | 'large';
  layout?: 'card' | 'tag' | 'list';
  onClick?: () => void;
  description?: string;
}

/* ─── Formatting ─── */
function formatValue(v: number | string, fmt?: string): string {
  if (typeof v === 'string') return v;
  if (fmt === 'currency') {
    const abs = Math.abs(v);
    const sign = v < 0 ? '-' : '';
    if (abs >= 1e9) return `${sign}\u20BE${(abs / 1e9).toFixed(1)}B`;
    if (abs >= 1e6) return `${sign}\u20BE${(abs / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `${sign}\u20BE${(abs / 1e3).toFixed(0)}K`;
    return `${sign}\u20BE${abs.toFixed(0)}`;
  }
  if (fmt === 'percentage') return `${v.toFixed(1)}%`;
  if (fmt === 'number') return v.toLocaleString('en-US', { maximumFractionDigits: 0 });
  return String(v);
}

function resolveColor(value: number | string, rules?: ConditionalRule[]): string | null {
  if (!rules || typeof value !== 'number') return null;
  for (const rule of rules) {
    if (rule.condition === 'gt' && value > rule.threshold) return rule.color;
    if (rule.condition === 'lt' && value < rule.threshold) return rule.color;
    if (rule.condition === 'eq' && value === rule.threshold) return rule.color;
  }
  return null;
}

/* ─── Size presets — refined for financial density ─── */
const SIZES: Record<string, { padding: string; valueFontSize: number; labelFontSize: number; sparkHeight: number }> = {
  compact: { padding: '12px 14px', valueFontSize: 18, labelFontSize: 10, sparkHeight: 24 },
  regular: { padding: '16px 18px', valueFontSize: 22, labelFontSize: 11, sparkHeight: 28 },
  large: { padding: '20px 22px', valueFontSize: 28, labelFontSize: 11, sparkHeight: 32 },
};

/* ─── Component ─── */
export default function MetricCardWidget({
  label, value, format, secondaryValue, secondaryLabel,
  conditionalRules, sparkData, size = 'regular', layout = 'card',
  onClick, description,
}: MetricCardWidgetProps) {
  const gradientId = useId();
  const [hovered, setHovered] = useState(false);

  const s = SIZES[size] || SIZES.regular;
  const conditionalColor = resolveColor(value, conditionalRules);
  const primaryColor = conditionalColor || 'var(--sky)';
  const isNegative = typeof value === 'number' && value < 0;
  const displayColor = isNegative ? 'var(--rose)' : conditionalColor || 'var(--heading)';
  const sparkPoints = sparkData?.map((v, i) => ({ v, i }));

  /* ─── Tag layout ─── */
  if (layout === 'tag') {
    return (
      <span
        onClick={onClick}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 14px', borderRadius: 8, cursor: onClick ? 'pointer' : 'default',
          background: `color-mix(in srgb, ${primaryColor} 10%, transparent)`,
          border: `1px solid color-mix(in srgb, ${primaryColor} 20%, transparent)`,
          fontSize: 12, fontFamily: 'var(--mono)', fontWeight: 600, color: primaryColor,
          transition: 'all .2s ease',
        }}
      >
        <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 500, fontFamily: 'var(--font)' }}>{label}</span>
        {formatValue(value, format)}
      </span>
    );
  }

  /* ─── List layout ─── */
  if (layout === 'list') {
    return (
      <div
        onClick={onClick}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 14px', cursor: onClick ? 'pointer' : 'default',
          borderBottom: '1px solid var(--b1)',
          transition: 'background .2s',
          background: hovered ? 'var(--bg3)' : 'transparent',
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 12, color: 'var(--text)' }}>{label}</span>
          {description && <span style={{ fontSize: 10, color: 'var(--dim)' }}>{description}</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {secondaryValue !== undefined && (
            <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
              {secondaryLabel ? `${secondaryLabel}: ` : ''}{formatValue(secondaryValue, format)}
            </span>
          )}
          <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--mono)', color: displayColor }}>
            {formatValue(value, format)}
          </span>
        </div>
      </div>
    );
  }

  /* ─── Card layout (default) — clean financial tile ─── */
  return (
    <div
      onClick={onClick}
      style={{
        padding: s.padding,
        cursor: onClick ? 'pointer' : 'default',
        borderRadius: 8,
        background: 'var(--bg1)',
        border: `1px solid ${hovered ? 'var(--b2)' : 'var(--b1)'}`,
        transition: 'border-color .15s ease',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >

      {/* Label */}
      <div style={{
        fontSize: s.labelFontSize, fontWeight: 500,
        color: 'var(--muted)', marginBottom: size === 'compact' ? 6 : 10,
        fontFamily: 'var(--font)',
      }}>
        {label}
      </div>

      {/* Primary value — financial-grade typography */}
      <div style={{
        fontSize: s.valueFontSize, fontWeight: 700, fontFamily: 'var(--mono)',
        color: displayColor, lineHeight: 1, letterSpacing: '-0.04em',
        marginBottom: 6, fontVariantNumeric: 'tabular-nums',
        animation: 'metric-count-up 0.4s ease-out forwards',
      }}>
        {formatValue(value, format)}
      </div>

      {/* Secondary value */}
      {secondaryValue !== undefined && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 12, fontWeight: 600, fontFamily: 'var(--mono)',
          marginTop: 4,
        }}>
          {typeof secondaryValue === 'number' && (
            secondaryValue >= 0
              ? <TrendingUp size={13} style={{ color: 'var(--emerald)' }} />
              : <TrendingDown size={13} style={{ color: 'var(--rose)' }} />
          )}
          <span style={{
            color: typeof secondaryValue === 'number'
              ? (secondaryValue >= 0 ? 'var(--emerald)' : 'var(--rose)')
              : 'var(--muted)',
            padding: '3px 8px', borderRadius: 6,
            background: typeof secondaryValue === 'number'
              ? (secondaryValue >= 0 ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)')
              : 'transparent',
          }}>
            {secondaryLabel ? `${secondaryLabel} ` : ''}
            {typeof secondaryValue === 'number'
              ? `${secondaryValue >= 0 ? '+' : ''}${secondaryValue.toFixed(1)}%`
              : secondaryValue}
          </span>
        </div>
      )}

      {/* Description */}
      {description && (
        <div style={{ fontSize: 11, color: 'var(--dim)', marginTop: 8, lineHeight: 1.4 }}>
          {description}
        </div>
      )}

      {/* Sparkline */}
      {sparkPoints && sparkPoints.length > 1 && (
        <div style={{ width: '100%', height: s.sparkHeight, marginTop: size === 'compact' ? 10 : 18, opacity: 0.5 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkPoints}>
              <defs>
                <linearGradient id={`spark-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={primaryColor} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={primaryColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v"
                stroke={primaryColor} strokeWidth={1.5}
                fill={`url(#spark-${gradientId})`}
                dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
