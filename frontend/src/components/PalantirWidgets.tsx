import { motion, useSpring, useTransform, animate } from 'framer-motion';
import { useEffect, useState } from 'react';

/**
 * NumberRoll — Sophisticated rolling counter for financial values.
 */
export function NumberRoll({ 
  value, 
  prefix = '', 
  suffix = '', 
  decimals = 0,
  precision = 0.1 
}: { 
  value: number; 
  prefix?: string; 
  suffix?: string; 
  decimals?: number;
  precision?: number;
}) {
  const spring = useSpring(value, { stiffness: 45, damping: 15, mass: 1 });
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  useEffect(() => {
    return spring.on('change', (latest) => {
      setDisplayValue(latest);
    });
  }, [spring]);

  const formatted = displayValue.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <span style={{ fontVariantNumeric: 'tabular-nums' }}>
      {prefix}{formatted}{suffix}
    </span>
  );
}

interface MetricSliderProps {
  label: string;
  value: number; // 0 to 100
  minLabel?: string;
  maxLabel?: string;
  statusLabel?: string;
  statusColor?: string;
}

/**
 * MetricSlider — High-density technical slider with chevron indicator and glow effects.
 */
export function MetricSlider({ 
  label, 
  value, 
  minLabel = 'LOW', 
  maxLabel = 'HIGH', 
  statusLabel, 
  statusColor = 'var(--sky)',
  onChange
}: MetricSliderProps & { onChange?: (val: number) => void }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color: 'var(--muted)', textTransform: 'uppercase', fontFamily: 'var(--mono)' }}>
            {label}
          </span>
          <div title="Manual Sensitivity Adjustment" style={{ cursor: 'help', color: 'var(--dim)', opacity: 0.5 }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {statusLabel && (
            <span style={{ fontSize: 9, fontWeight: 800, color: statusColor, fontFamily: 'var(--mono)', textShadow: `0 0 5px ${statusColor}44` }}>
              {statusLabel}
            </span>
          )}
          <div style={{ display: 'flex', gap: 1 }}>
            <button 
              onClick={() => onChange?.(-5)}
              style={{ padding: '0 4px', background: 'var(--bg3)', border: 'none', color: 'var(--muted)', fontSize: 10, cursor: 'pointer', fontFamily: 'var(--mono)' }}
            >-</button>
            <button 
              onClick={() => onChange?.(5)}
              style={{ padding: '0 4px', background: 'var(--bg3)', border: 'none', color: 'var(--muted)', fontSize: 10, cursor: 'pointer', fontFamily: 'var(--mono)' }}
            >+</button>
          </div>
        </div>
      </div>
      
      <div style={{ position: 'relative', height: 2, background: 'var(--bg4)', borderRadius: 1 }}>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', justifyContent: 'space-between', opacity: 0.3 }}>
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(i => (
            <div key={i} style={{ width: 1, height: 4, background: 'var(--b3)', marginTop: -1 }} />
          ))}
        </div>
        
        <motion.div 
          initial={{ left: 0 }}
          animate={{ left: `${value}%` }}
          transition={{ type: 'spring', stiffness: 60, damping: 20 }}
          style={{ 
            position: 'absolute', 
            top: -10, 
            marginLeft: -6,
            zIndex: 10
          }} 
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 12L0 6L6 0L12 6L6 12Z" fill={statusColor} />
            <path d="M6 10L2 6L6 2L10 6L6 10Z" fill="black" opacity="0.3" />
          </svg>
          <div style={{ width: 1, height: 16, background: statusColor, margin: '0 auto', boxShadow: `0 0 8px ${statusColor}` }} />
        </motion.div>
        
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 1.2, ease: 'circOut' }}
          style={{ 
            position: 'absolute', 
            height: '100%', 
            background: `linear-gradient(90deg, transparent, ${statusColor})`,
            boxShadow: `0 0 10px ${statusColor}33`,
            borderRadius: 1
          }} 
        />
      </div>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
        <span style={{ fontSize: 8, color: 'var(--dim)', fontFamily: 'var(--mono)', letterSpacing: 0.5 }}>{minLabel}</span>
        <span style={{ fontSize: 8, color: 'var(--dim)', fontFamily: 'var(--mono)', letterSpacing: 0.5 }}>{maxLabel}</span>
      </div>
    </div>
  );
}

export function TechnicalStat({ 
  label, 
  value, 
  numericValue,
  prefix = '',
  suffix = '',
  decimals = 0,
  subValue, 
  trend, 
  progress = 0,
  color = 'var(--text)',
  status = 'NOMINAL',
  isSimulated = false
}: { 
  label: string; 
  value?: string; 
  numericValue?: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  subValue?: string; 
  trend?: { val: string; pos: boolean }; 
  progress?: number;
  color?: string;
  status?: string;
  isSimulated?: boolean;
}) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ 
        opacity: 1, 
        y: 0,
        borderColor: isSimulated ? 'var(--amber)' : 'var(--b2)',
        background: isSimulated ? 'rgba(245,158,11,0.03)' : 'var(--bg1)'
      }}
      className="kpi-card panel-living"
      style={{
        padding: '20px 24px',
        position: 'relative',
        minHeight: 140,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        overflow: 'hidden',
        transition: 'all 0.4s ease'
      }}
    >
      <div className={`scan-line ${isSimulated ? 'active' : ''}`} style={{ animationDelay: `${Math.random() * 5}s`, opacity: isSimulated ? 0.6 : 0.3 }} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', letterSpacing: 1.5, textTransform: 'uppercase', fontFamily: 'var(--mono)', maxWidth: '65%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {label}
        </div>
        <div style={{ 
          fontSize: 8, 
          fontWeight: 900, 
          color: isSimulated ? 'var(--amber)' : (color === 'var(--text)' ? 'var(--sky)' : color), 
          fontFamily: 'var(--mono)',
          padding: '2px 8px',
          border: `1px solid ${isSimulated ? 'var(--amber)' : (color === 'var(--text)' ? 'var(--sky)' : color)}22`,
          borderRadius: 1,
          background: 'rgba(15,20,34,0.6)',
          letterSpacing: 1,
          whiteSpace: 'nowrap'
        }}>
          {status}
        </div>
      </div>
      
      <div className="kpi-value-glow" style={{ fontSize: 32, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--heading)', lineHeight: 1.1, letterSpacing: -1, margin: '10px 0' }}>
        {numericValue !== undefined ? (
          <NumberRoll value={numericValue} prefix={prefix} suffix={suffix} decimals={decimals} />
        ) : value}
      </div>
      
      <div style={{ marginTop: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)', fontWeight: 600 }}>{subValue || 'CAPACITY'}</span>
          {trend && (
            <span style={{ 
              fontSize: 10, 
              fontWeight: 800, 
              fontFamily: 'var(--mono)', 
              color: trend.pos ? 'var(--emerald)' : 'var(--rose)',
              display: 'flex',
              alignItems: 'center',
              gap: 4
            }}>
              {trend.pos ? '▲' : '▼'}{trend.val}
            </span>
          )}
        </div>
        <div style={{ height: 3, background: 'var(--bg3)', borderRadius: 1, overflow: 'hidden' }}>
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(100, Math.max(0, Number(progress)))}%` }}
            transition={{ type: 'spring', stiffness: 50, damping: 15 }}
            style={{ height: '100%', background: isSimulated ? 'var(--amber)' : (color === 'var(--text)' ? 'var(--sky)' : color), boxShadow: `0 0 10px ${isSimulated ? 'var(--amber)' : (color === 'var(--text)' ? 'var(--sky)' : color)}33` }} 
          />
        </div>
      </div>
    </motion.div>
  );
}

/**
 * TechnicalStatsGrid — 4-column responsive container for technical KPI cards.
 */
export function TechnicalStatsGrid({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
      gap: 16,
      marginBottom: 28
    }}>
      {children}
    </div>
  );
}

/**
 * SegmentBarChart — High-density grouped thin-bar charts for segment analysis.
 */
export function SegmentBarChart({ 
  title, 
  data 
}: { 
  title: string; 
  data: { label: string; current: number; prior: number; target: number }[] 
}) {
  const totalCurrent = data.reduce((s, d) => s + d.current, 0);

  return (
    <div className="glass" style={{ padding: 16, background: 'var(--bg1)', border: '1px solid var(--b2)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 2, height: 12, background: 'var(--sky)' }} />
          <div className="card-title" style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: 1.5, fontWeight: 700 }}>{title.toUpperCase()}</div>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 6, height: 6, background: 'var(--sky)', borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: 'var(--muted)', fontFamily: 'var(--mono)', fontWeight: 600 }}>ACTUAL</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 6, height: 6, background: 'var(--bg3)', borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: 'var(--muted)', fontFamily: 'var(--mono)', fontWeight: 600 }}>TARGET</span>
          </div>
        </div>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {data.map((item, idx) => {
          const share = (item.current / totalCurrent) * 100;
          const growth = ((item.current / item.prior) - 1) * 100;
          return (
            <div key={idx}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--heading)', marginBottom: 2 }}>{item.label}</div>
                  <div style={{ display: 'flex', gap: 8, fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
                    <span>SHARE: {share.toFixed(1)}%</span>
                    <span style={{ color: growth >= 0 ? 'var(--emerald)' : 'var(--rose)' }}>
                      {growth >= 0 ? '+' : ''}{growth.toFixed(1)}% YoY
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 12, color: 'var(--heading)', fontFamily: 'var(--mono)', fontWeight: 700 }}>{(item.current / 1e6).toFixed(1)}M</div>
                  <div style={{ fontSize: 8, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>TARGET: {(item.target / 1e6).toFixed(1)}M</div>
                </div>
              </div>
              
              <div style={{ position: 'relative', height: 6, background: 'var(--bg3)', borderRadius: 1, overflow: 'hidden' }}>
                {/* Target marker - more visible now */}
                <div style={{ 
                  position: 'absolute', 
                  height: '100%', 
                  width: 2, 
                  background: 'var(--muted)', 
                  left: `${(item.target / (item.target * 1.2)) * 100}%`, 
                  zIndex: 5,
                  opacity: 0.4
                }} />
                
                {/* Current Actual bar */}
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${(item.current / (item.target * 1.2)) * 100}%` }}
                  transition={{ duration: 1.2, delay: idx * 0.1, ease: 'circOut' }}
                  style={{ 
                    position: 'absolute', 
                    height: '100%', 
                    background: `linear-gradient(90deg, var(--sky)00, var(--sky))`, 
                    boxShadow: '0 0 15px var(--sky)33'
                  }} 
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
