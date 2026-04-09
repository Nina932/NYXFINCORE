import { useNavigate } from 'react-router-dom';
import { ResponsiveContainer, Area, AreaChart } from 'recharts';
import type { LucideIcon } from 'lucide-react';
import { TrendingUp, TrendingDown, ArrowUpRight } from 'lucide-react';

interface KPICardProps {
  title: string;
  value: string;
  change?: number;
  changeSuffix?: string;
  icon?: LucideIcon;
  color?: string;
  sparkData?: number[];
  href?: string;
  badge?: string;
  badgeColor?: string;
  loading?: boolean;
  delay?: number;
}

export default function KPICard({
  title, value, change, changeSuffix = '%', icon: Icon, color = 'var(--sky)',
  sparkData, href, badge, badgeColor, loading = false, delay = 0,
}: KPICardProps) {
  const navigate = useNavigate();
  const isPositive = change !== undefined && change >= 0;
  const isNegative = value.includes('-');
  const sparkPoints = sparkData?.map((v, i) => ({ v, i }));

  if (loading) {
    return (
      <div style={{
        padding: '14px 16px', borderRadius: 10,
        background: 'var(--glass-flat)', border: '1px solid var(--glass-border)',
      }}>
        <div className="skeleton" style={{ height: 10, width: 80, marginBottom: 24 }} />
        <div className="skeleton" style={{ height: 36, width: 140, marginBottom: 16 }} />
        <div className="skeleton" style={{ height: 10, width: 60 }} />
      </div>
    );
  }

  return (
    <div
      onClick={() => href && navigate(href)}
      className="glow-border"
      style={{
        padding: '14px 16px',
        cursor: href ? 'pointer' : 'default',
        position: 'relative',
        overflow: 'hidden',
        animation: `fade-in .5s ease ${delay * 0.12}s both`,
        borderRadius: 10,
        background: `linear-gradient(160deg, var(--glass-flat) 0%, color-mix(in srgb, ${color} 4%, var(--glass-flat)) 100%)`,
        border: '1px solid var(--glass-border)',
        boxShadow: 'var(--shadow-sm)',
        transition: 'all .3s cubic-bezier(.4,0,.2,1)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.transform = 'scale(1.02)';
        e.currentTarget.style.boxShadow = `var(--shadow-md), 0 0 30px color-mix(in srgb, ${color} 10%, transparent)`;
        e.currentTarget.style.borderColor = `color-mix(in srgb, ${color} 30%, transparent)`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = '';
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
        e.currentTarget.style.borderColor = 'var(--glass-border)';
      }}
    >
      {/* Gradient top accent line (2px) */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 40%, var(--violet)))`,
        opacity: 0.6,
      }} />

      {/* Background glow */}
      <div style={{
        position: 'absolute', top: -20, right: -20,
        width: 80, height: 80, borderRadius: '50%',
        background: `radial-gradient(circle, color-mix(in srgb, ${color} 8%, transparent), transparent 70%)`,
        filter: 'blur(20px)',
      }} />

      {/* Icon in circle */}
      {Icon && (
        <div style={{
          position: 'absolute', top: 14, right: 16,
          width: 28, height: 28, borderRadius: '50%',
          background: `color-mix(in srgb, ${color} 8%, transparent)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'transform .3s',
        }}>
          <Icon size={16} style={{ color, opacity: 0.7 }} />
        </div>
      )}

      {/* Label — 11px uppercase */}
      <div style={{
        fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '0.8px', color: 'var(--muted)', marginBottom: 8,
        fontFamily: 'var(--font)',
      }}>
        {title}
      </div>

      {/* Value — 32px mono 800 */}
      <div className={isNegative ? 'value-critical' : ''} style={{
        fontSize: 22, fontWeight: 800, fontFamily: 'var(--mono)',
        color: isNegative ? 'var(--rose)' : 'var(--heading)',
        lineHeight: 1, letterSpacing: '-1.5px', marginBottom: 6,
        animation: 'metric-count-up 0.5s ease-out forwards',
      }}>
        {value}
      </div>

      {/* Badge + Trend */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
        {badge && (
          <span style={{
            fontSize: 11, padding: '4px 10px',
            borderRadius: 8, fontWeight: 600, fontFamily: 'var(--mono)',
            background: `color-mix(in srgb, ${badgeColor || color} 12%, transparent)`,
            color: badgeColor || color,
            border: `1px solid color-mix(in srgb, ${badgeColor || color} 15%, transparent)`,
          }}>
            {badge}
          </span>
        )}
        {change !== undefined && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 12, fontWeight: 600, fontFamily: 'var(--mono)',
            color: isPositive ? 'var(--emerald)' : 'var(--rose)',
            padding: '3px 8px', borderRadius: 6,
            background: isPositive ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)',
          }}>
            {isPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            <span>{isPositive ? '+' : ''}{change.toFixed(1)}{changeSuffix}</span>
          </div>
        )}
      </div>

      {/* Sparkline — AreaChart, 40px height, gradient fill */}
      {sparkPoints && sparkPoints.length > 1 && (
        <div style={{ width: '100%', height: 36, marginTop: 12, opacity: 0.5 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={sparkPoints}>
              <defs>
                <linearGradient id={`grad-${title}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="v"
                stroke={color} strokeWidth={1.5}
                fill={`url(#grad-${title})`}
                dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Navigate arrow */}
      {href && (
        <div style={{
          position: 'absolute', bottom: 18, right: 18,
          opacity: 0, transition: 'opacity .3s, transform .3s',
          transform: 'translate(4px, 4px)',
        }} className="kpi-nav-hint">
          <ArrowUpRight size={14} style={{ color: 'var(--muted)' }} />
        </div>
      )}
    </div>
  );
}
