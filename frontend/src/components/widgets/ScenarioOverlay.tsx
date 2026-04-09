import { useState, useCallback } from 'react';
import { X, Play, RotateCcw, Loader2, TrendingUp, TrendingDown } from 'lucide-react';

/* ─── Types ─── */
interface ScenarioVariable {
  id: string;
  label: string;
  currentValue: number;
  min: number;
  max: number;
  step: number;
  format: 'currency' | 'percentage' | 'number';
  adjustedValue?: number;
}

interface ScenarioOverlayProps {
  variables: ScenarioVariable[];
  onVariableChange: (id: string, value: number) => void;
  onRun: (adjustments: Record<string, number>) => void;
  onReset: () => void;
  onClose?: () => void;
  results?: Record<string, number>;
  isRunning?: boolean;
}

/* ─── Format helper ─── */
function fmtVar(v: number, format: string): string {
  if (format === 'percentage') return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;
  if (format === 'currency') {
    const abs = Math.abs(v);
    const sign = v < 0 ? '-' : '';
    if (abs >= 1e6) return `${sign}\u20BE${(abs / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `${sign}\u20BE${(abs / 1e3).toFixed(0)}K`;
    return `${sign}\u20BE${abs.toFixed(0)}`;
  }
  return v.toFixed(1);
}

/* ─── Component ─── */
export default function ScenarioOverlay({
  variables, onVariableChange, onRun, onReset, onClose, results, isRunning,
}: ScenarioOverlayProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const handleRun = useCallback(() => {
    const adjustments: Record<string, number> = {};
    for (const v of variables) {
      adjustments[v.id] = v.adjustedValue ?? v.currentValue;
    }
    onRun(adjustments);
  }, [variables, onRun]);

  const hasChanges = variables.some(v =>
    (v.adjustedValue !== undefined && v.adjustedValue !== v.currentValue)
  );

  return (
    <div style={{
      position: 'fixed', top: 0, right: 0, bottom: 0,
      width: 420, maxWidth: '100vw', zIndex: 1000,
      background: 'var(--bg1)', borderLeft: '1px solid var(--b2)',
      boxShadow: '-8px 0 40px rgba(0,0,0,.4)',
      display: 'flex', flexDirection: 'column',
      animation: 'slide-in-right .3s ease both',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 24px', borderBottom: '1px solid var(--b1)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <h3 style={{
            fontSize: 16, fontWeight: 700, color: 'var(--heading)',
            margin: 0, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            What-If Scenario
          </h3>
          <p style={{ fontSize: 11, color: 'var(--muted)', margin: '4px 0 0' }}>
            Adjust assumptions and see impact
          </p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: 8,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--bg3)', border: '1px solid var(--b1)',
              color: 'var(--muted)', cursor: 'pointer',
              transition: 'all .2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg2)';
              e.currentTarget.style.color = 'var(--heading)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--bg3)';
              e.currentTarget.style.color = 'var(--muted)';
            }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Variables */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
        <div style={{
          fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '1px', color: 'var(--muted)', marginBottom: 12,
        }}>
          Adjust Variables
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {variables.map((v) => {
            const current = v.adjustedValue ?? v.currentValue;
            const delta = current - v.currentValue;
            const pctRange = v.max - v.min;
            const fillPct = pctRange > 0 ? ((current - v.min) / pctRange) * 100 : 50;
            const isChanged = delta !== 0;

            return (
              <div key={v.id} style={{
                padding: '14px 16px', borderRadius: 10,
                background: isChanged ? 'color-mix(in srgb, var(--sky) 4%, var(--bg3))' : 'var(--bg3)',
                border: `1px solid ${isChanged ? 'color-mix(in srgb, var(--sky) 20%, transparent)' : 'var(--b1)'}`,
                transition: 'all .3s',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--heading)' }}>
                    {v.label}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {isChanged && (
                      <span style={{
                        fontSize: 10, fontFamily: 'var(--mono)', fontWeight: 600,
                        color: delta > 0 ? 'var(--emerald)' : 'var(--rose)',
                        padding: '2px 6px', borderRadius: 4,
                        background: delta > 0 ? 'rgba(16,185,129,.08)' : 'rgba(239,68,68,.08)',
                      }}>
                        {delta > 0 ? '+' : ''}{delta.toFixed(1)}%
                      </span>
                    )}
                    <span style={{
                      fontSize: 14, fontWeight: 700, fontFamily: 'var(--mono)',
                      color: isChanged ? 'var(--sky)' : 'var(--text)',
                    }}>
                      {fmtVar(current, v.format)}
                    </span>
                  </div>
                </div>

                {/* Slider track */}
                <div style={{ position: 'relative', height: 6, marginBottom: 6 }}>
                  <div style={{
                    position: 'absolute', top: 0, left: 0, right: 0, height: 6,
                    borderRadius: 3, background: 'var(--b1)',
                  }} />
                  <div style={{
                    position: 'absolute', top: 0, left: 0, height: 6,
                    width: `${fillPct}%`, borderRadius: 3,
                    background: isChanged
                      ? 'linear-gradient(90deg, var(--sky), var(--violet))'
                      : 'var(--dim)',
                    transition: 'width .15s ease',
                  }} />
                  <input
                    type="range"
                    min={v.min} max={v.max} step={v.step}
                    value={current}
                    onChange={(e) => onVariableChange(v.id, parseFloat(e.target.value))}
                    style={{
                      position: 'absolute', top: -4, left: 0, width: '100%',
                      height: 14, opacity: 0, cursor: 'pointer', margin: 0,
                    }}
                  />
                </div>

                {/* Min / Max labels */}
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
                    {fmtVar(v.min, v.format)}
                  </span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>
                    {fmtVar(v.max, v.format)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Results section */}
        {results && Object.keys(results).length > 0 && (
          <div style={{ marginTop: 24 }}>
            <div style={{
              fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
              letterSpacing: '1px', color: 'var(--emerald)', marginBottom: 12,
            }}>
              Projected Impact
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {Object.entries(results).map(([key, value]) => {
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                const isPositive = value >= 0;
                return (
                  <div key={key} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: 8,
                    background: 'var(--bg3)', border: '1px solid var(--b1)',
                  }}>
                    <span style={{ fontSize: 12, color: 'var(--text)' }}>{label}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {isPositive
                        ? <TrendingUp size={12} style={{ color: 'var(--emerald)' }} />
                        : <TrendingDown size={12} style={{ color: 'var(--rose)' }} />
                      }
                      <span style={{
                        fontSize: 14, fontWeight: 700, fontFamily: 'var(--mono)',
                        color: isPositive ? 'var(--emerald)' : 'var(--rose)',
                      }}>
                        {fmtVar(value, 'currency')}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div style={{
        padding: '16px 24px', borderTop: '1px solid var(--b1)',
        display: 'flex', gap: 10,
      }}>
        <button
          onClick={onReset}
          disabled={isRunning}
          style={{
            flex: 1, padding: '10px 16px', borderRadius: 8,
            background: 'var(--bg3)', border: '1px solid var(--b1)',
            color: 'var(--muted)', fontSize: 12, fontWeight: 600,
            cursor: isRunning ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            transition: 'all .2s',
            opacity: isRunning ? 0.5 : 1,
          }}
        >
          <RotateCcw size={13} /> Reset
        </button>
        <button
          onClick={handleRun}
          disabled={isRunning || !hasChanges}
          style={{
            flex: 2, padding: '10px 16px', borderRadius: 8,
            background: hasChanges && !isRunning
              ? 'var(--gradient-primary, linear-gradient(135deg, var(--sky), var(--violet)))'
              : 'var(--bg3)',
            border: 'none',
            color: hasChanges && !isRunning ? '#fff' : 'var(--dim)',
            fontSize: 12, fontWeight: 700,
            cursor: isRunning || !hasChanges ? 'not-allowed' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            boxShadow: hasChanges && !isRunning ? '0 4px 20px rgba(37,99,235,.3)' : 'none',
            transition: 'all .2s',
          }}
        >
          {isRunning
            ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Running...</>
            : <><Play size={14} /> Run Scenario</>
          }
        </button>
      </div>
    </div>
  );
}
