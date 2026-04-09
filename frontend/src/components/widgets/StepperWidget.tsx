import { CheckCircle2 } from 'lucide-react';

/* ─── Types ─── */
interface Step {
  id: string;
  label: string;
  isCompleted: boolean;
  icon?: React.ReactNode;
  onClick?: () => void;
}

interface StepperWidgetProps {
  steps: Step[];
  activeStep?: number;
  type?: 'linear' | 'non-linear';
  completedColor?: string;
  activeColor?: string;
}

/* ─── Component ─── */
export default function StepperWidget({
  steps, activeStep = 0, type = 'linear',
  completedColor = 'var(--emerald)', activeColor = 'var(--sky)',
}: StepperWidgetProps) {
  if (steps.length === 0) return null;

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 0,
      overflowX: 'auto', padding: '8px 4px',
    }}>
      {steps.map((step, idx) => {
        const isActive = idx === activeStep;
        const isCompleted = step.isCompleted;
        const isPast = type === 'linear' ? idx < activeStep : false;
        const isFuture = type === 'linear' ? idx > activeStep && !isCompleted : !isCompleted;

        const nodeColor = isCompleted ? completedColor
          : isActive ? activeColor
          : 'var(--dim)';

        const lineColor = isCompleted || isPast
          ? completedColor
          : 'var(--b2)';

        const isClickable = type === 'non-linear' || !!step.onClick;

        return (
          <div
            key={step.id}
            style={{
              display: 'flex', alignItems: 'flex-start', flex: 1, minWidth: 100,
              animation: `fade-in .4s ease ${idx * 0.08}s both`,
            }}
          >
            {/* Step node + content */}
            <div
              onClick={() => step.onClick?.()}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                flex: 1, cursor: isClickable ? 'pointer' : 'default',
                position: 'relative',
              }}
            >
              {/* Connector line (before) */}
              {idx > 0 && (
                <div style={{
                  position: 'absolute', top: 16, right: '50%', width: '100%', height: 2,
                  background: lineColor, zIndex: 0,
                  transition: 'background .3s ease',
                }} />
              )}

              {/* Circle node */}
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: isCompleted
                  ? `color-mix(in srgb, ${completedColor} 15%, var(--bg2))`
                  : isActive
                    ? `color-mix(in srgb, ${activeColor} 15%, var(--bg2))`
                    : 'var(--bg3)',
                border: `2px solid ${nodeColor}`,
                boxShadow: isActive
                  ? `0 0 12px ${activeColor}30, 0 0 4px ${activeColor}20`
                  : isCompleted
                    ? `0 0 8px ${completedColor}20`
                    : 'none',
                zIndex: 1,
                transition: 'all .3s ease',
                transform: isActive ? 'scale(1.1)' : 'scale(1)',
              }}>
                {isCompleted ? (
                  <CheckCircle2 size={16} style={{ color: completedColor }} />
                ) : step.icon ? (
                  <span style={{ display: 'flex', color: nodeColor, opacity: isFuture ? 0.5 : 1 }}>{step.icon}</span>
                ) : (
                  <span style={{
                    fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)',
                    color: nodeColor, opacity: isFuture ? 0.5 : 1,
                  }}>
                    {idx + 1}
                  </span>
                )}
              </div>

              {/* Label */}
              <div style={{
                marginTop: 8, fontSize: 10, fontWeight: 600,
                color: isActive ? 'var(--heading)' : isCompleted ? 'var(--text)' : 'var(--dim)',
                textAlign: 'center', lineHeight: 1.3,
                maxWidth: 100, letterSpacing: '0.2px',
                transition: 'color .3s',
              }}>
                {step.label}
              </div>

              {/* Active indicator dot */}
              {isActive && (
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: activeColor, marginTop: 6,
                  boxShadow: `0 0 8px ${activeColor}60`,
                  animation: 'pulse-live 2s infinite',
                }} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
