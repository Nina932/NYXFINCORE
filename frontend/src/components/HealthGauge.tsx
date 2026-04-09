import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface HealthGaugeProps {
  score: number;
  grade: string;
  size?: number;
  clickable?: boolean;
}

const GRADE_COLORS: Record<string, string> = {
  A: 'var(--emerald)',
  B: 'var(--amber)',
  C: 'var(--amber)',
  D: 'var(--rose)',
  F: 'var(--rose)',
};

const GRADE_LABELS: Record<string, string> = {
  A: 'Excellent',
  B: 'Good',
  C: 'Fair',
  D: 'Poor',
  F: 'Critical',
};

const GRADE_RAW: Record<string, string> = {
  A: '#34d399',
  B: '#fbbf24',
  C: '#fbbf24',
  D: '#f87171',
  F: '#f87171',
};

export default function HealthGauge({ score, grade, size = 200, clickable = true }: HealthGaugeProps) {
  const navigate = useNavigate();
  const [animatedScore, setAnimatedScore] = useState(0);
  const [mounted, setMounted] = useState(false);

  const gradeKey = grade.charAt(0).toUpperCase();
  const color = GRADE_COLORS[gradeKey] || 'var(--muted)';
  const rawColor = GRADE_RAW[gradeKey] || '#5a6a85';
  const label = GRADE_LABELS[gradeKey] || 'Unknown';

  useEffect(() => {
    setMounted(true);
    const duration = 800;
    const steps = 40;
    const increment = score / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= score) {
        setAnimatedScore(score);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.round(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [score]);

  const radius = (size - 30) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (animatedScore / 100) * circumference;
  const isCritical = gradeKey === 'D' || gradeKey === 'F';

  return (
    <div
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: clickable ? 'pointer' : 'default' }}
      onClick={() => clickable && navigate('/orchestrator')}
    >
      <div style={{ position: 'relative', borderRadius: '50%', padding: 2, background: `${rawColor}0d` }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={cx} cy={cy} r={radius} fill="none" stroke="var(--bg4)" strokeWidth="12" />
          {[...Array(20)].map((_, i) => {
            const angle = (i / 20) * 360 - 90;
            const rad = (angle * Math.PI) / 180;
            const x1 = cx + (radius - 8) * Math.cos(rad);
            const y1 = cy + (radius - 8) * Math.sin(rad);
            const x2 = cx + (radius + 2) * Math.cos(rad);
            const y2 = cy + (radius + 2) * Math.sin(rad);
            return (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={i < (animatedScore / 5) ? rawColor : 'var(--bg4)'}
                strokeWidth="2" strokeLinecap="round" opacity={0.5}
              />
            );
          })}
          <circle
            cx={cx} cy={cy} r={radius} fill="none"
            stroke={rawColor} strokeWidth="12"
            strokeDasharray={`${progress} ${circumference}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`}
            style={{ transition: mounted ? 'stroke-dasharray 0.8s ease-out' : 'none' }}
          />
          <circle
            cx={cx} cy={cy} r={radius} fill="none"
            stroke={rawColor} strokeWidth="12"
            strokeDasharray={`${progress} ${circumference}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${cx} ${cy})`}
            opacity={0.3} filter="url(#gaugeGlow)"
            style={{ transition: mounted ? 'stroke-dasharray 0.8s ease-out' : 'none' }}
          />
          <defs>
            <filter id="gaugeGlow">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          <text x={cx} y={cy - 8} textAnchor="middle" dominantBaseline="central"
            fill={rawColor} fontSize="48" fontWeight="bold" fontFamily="var(--mono)"
            style={isCritical ? { animation: 'pulse 2s infinite' } : {}}
          >
            {grade}
          </text>
          <text x={cx} y={cy + 30} textAnchor="middle" dominantBaseline="central"
            fill="var(--muted)" fontSize="14" fontFamily="var(--mono)"
          >
            {animatedScore}/100
          </text>
        </svg>
      </div>
      <div style={{ marginTop: 10, textAlign: 'center' }}>
        <span style={{ fontSize: 12, fontWeight: 500, color }}>
          Financial Health: {label}
        </span>
      </div>
    </div>
  );
}
