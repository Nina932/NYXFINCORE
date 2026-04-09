import { useMemo } from 'react';
import { useStore } from '../store/useStore';

export default function NyxLogo({
  className = "",
  size = 40,
}: {
  className?: string;
  size?: number;
}) {
  const theme = useStore((s) => s.theme);
  const isDark = theme === 'dark';

  // Dark: bright cyan glow  |  Light: deep dark blue
  const mainHex    = isDark ? '#00E5FF' : '#1D4ED8';
  const innerFill  = isDark ? '#00C8FF' : '#3B82F6';
  const gridStroke = isDark ? '#1E3D5A' : '#94A3B8';
  const pulseClr   = isDark ? '#00E5FF' : '#1D4ED8';

  // ── Honeycomb cell centres (computed once) ──
  const cells = useMemo(() => {
    const S = 18, sq3 = Math.sqrt(3), CX = 100, CY = 90;
    const c: [number, number][] = [];
    for (let q = -2; q <= 2; q++)
      for (let r = -2; r <= 2; r++)
        if (Math.max(Math.abs(q), Math.abs(r), Math.abs(q + r)) <= 2)
          c.push([
            +(CX + S * 1.5 * q).toFixed(1),
            +(CY + S * sq3 * (r + q / 2)).toFixed(1),
          ]);
    return c;
  }, []);

  // Flat-top hex polygon string
  const hp = (cx: number, cy: number) =>
    [0, 1, 2, 3, 4, 5]
      .map((i) => {
        const a = (Math.PI / 3) * i;
        return `${(cx + 18 * Math.cos(a)).toFixed(1)},${(cy + 18 * Math.sin(a)).toFixed(1)}`;
      })
      .join(' ');

  return (
    <svg
      viewBox="0 0 200 200"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ width: size, height: size }}
    >
      <defs>
        {/* Main hex intense glow */}
        <filter id="nyx-glow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation={isDark ? 6 : 5} result="b1" />
          <feGaussianBlur stdDeviation={isDark ? 12 : 10} result="b2" />
          <feMerge>
            <feMergeNode in="b2" />
            <feMergeNode in="b1" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        {/* Subtle glow for pulse rings */}
        <filter id="nyx-pulse" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation={isDark ? 2.5 : 2} result="bl" />
          <feMerge>
            <feMergeNode in="bl" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* ── Honeycomb grid — clean vector wireframe ── */}
      <g stroke={gridStroke} strokeWidth="0.7" fill="none">
        <animate
          attributeName="opacity"
          values={isDark ? '0.2;0.38;0.2' : '0.12;0.25;0.12'}
          dur="4s"
          repeatCount="indefinite"
        />
        {cells.map(([cx, cy], i) => (
          <polygon key={i} points={hp(cx, cy)} />
        ))}
      </g>

      {/* ── Expanding pulse rings — sonar-style vector ripple ── */}
      <g transform="translate(100 90)" filter="url(#nyx-pulse)">
        {[0, 1, 2].map((i) => (
          <polygon
            key={i}
            points="0,-48 42,-24 42,24 0,48 -42,24 -42,-24"
            stroke={pulseClr}
            strokeWidth="1.5"
            fill="none"
          >
            <animate
              attributeName="opacity"
              values={isDark ? '0.5;0' : '0.4;0'}
              dur="3s"
              begin={`${i}s`}
              repeatCount="indefinite"
            />
            <animateTransform
              attributeName="transform"
              type="scale"
              values="1;1.55"
              dur="3s"
              begin={`${i}s`}
              repeatCount="indefinite"
            />
          </polygon>
        ))}
      </g>

      {/* ── Main glowing hexagon ── */}
      <polygon
        points="100,42 142,66 142,114 100,138 58,114 58,66"
        stroke={mainHex}
        strokeWidth="3"
        fill="none"
        filter="url(#nyx-glow)"
      >
        <animate
          attributeName="stroke-opacity"
          values="1;0.65;1"
          dur="3s"
          repeatCount="indefinite"
        />
      </polygon>

      {/* ── Inner subtle fill ── */}
      <polygon
        points="100,42 142,66 142,114 100,138 58,114 58,66"
        fill={innerFill}
        opacity={isDark ? 0.04 : 0.06}
      />
    </svg>
  );
}
