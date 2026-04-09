import { useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Bar, Cell, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Sector, Legend,
  Area, Line, BarChart,
} from 'recharts';

/* ---- NYX Core Palette ---- */
const P = {
  sky: '#00f2ff',
  blue: '#3B7DD8',
  emerald: '#34C578',
  rose: '#E05555',
  amber: '#E8A73E',
  violet: '#8A79C0',
  teal: '#2BA8A0',
  cyan: '#5AACCC',
  gold: '#C9A96E',
};

const DONUT_COLORS = [P.sky, P.gold, P.emerald, P.violet, P.amber, P.teal, P.cyan, P.rose, P.blue];

/* ---- Helpers ---- */
function fmtCompact(n: number): string {
  if (n == null || isNaN(n)) return '\u2014';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e3).toFixed(0)}K`;
  return `\u20BE${n.toFixed(0)}`;
}

/* ================================================================
   A) RevenueWaterfallChart
   ================================================================ */

interface WaterfallItem {
  label: string;
  value: number;
}

// Custom bar shape for waterfall effect
const WaterfallBar = (props: any) => {
  const { x, y, width, height, payload } = props;
  if (!payload) return null;
  const isPositive = payload._waterfallValue >= 0;
  const fill = isPositive ? 'url(#waterfall-pos)' : 'url(#waterfall-neg)';
  const r = 4;
  // Build rounded rect path (top corners rounded)
  const h = Math.abs(height);
  const barY = height >= 0 ? y : y;
  if (h < 1) return null;
  return (
    <g>
      <defs>
        <linearGradient id="waterfall-pos" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={P.emerald} stopOpacity={0.9} />
          <stop offset="100%" stopColor={P.teal} stopOpacity={0.7} />
        </linearGradient>
        <linearGradient id="waterfall-neg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={P.rose} stopOpacity={0.9} />
          <stop offset="100%" stopColor="#FB7185" stopOpacity={0.7} />
        </linearGradient>
        <linearGradient id="waterfall-total" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={P.sky} stopOpacity={0.9} />
          <stop offset="100%" stopColor={P.blue} stopOpacity={0.7} />
        </linearGradient>
      </defs>
      <rect
        x={x}
        y={barY}
        width={width}
        height={h}
        rx={r}
        ry={r}
        fill={payload._isTotal ? 'url(#waterfall-total)' : fill}
        style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))' }}
      />
      {/* Connector line to next bar */}
      {payload._connectorTo != null && (
        <line
          x1={x + width}
          y1={payload._isTotal ? barY : (isPositive ? barY : barY + h)}
          x2={x + width + 20}
          y2={payload._isTotal ? barY : (isPositive ? barY : barY + h)}
          stroke="var(--b2)"
          strokeDasharray="3 2"
          strokeWidth={1}
        />
      )}
    </g>
  );
};

export function RevenueWaterfallChart({ data }: { data: WaterfallItem[] }) {
  const chartData = useMemo(() => {
    // totals are items whose value = sum of preceding items (like GP, EBITDA, Net)
    const totals = new Set(['Gross Profit', 'EBITDA', 'EBIT', 'Net Profit']);
    let running = 0;
    return data.map((item, i) => {
      const isTotal = totals.has(item.label);
      const val = item.value;
      let base: number;
      let top: number;

      if (i === 0 || isTotal) {
        // First item or total: bar starts from 0
        base = 0;
        top = val;
        running = val;
      } else {
        // Incremental: bar starts from running, extends by val
        base = running;
        top = running + val;
        running = top;
      }

      return {
        name: item.label,
        base: Math.min(base, top),
        size: Math.abs(top - base),
        _waterfallValue: val,
        _isTotal: isTotal || i === 0,
        _connectorTo: i < data.length - 1 ? i + 1 : null,
        _displayVal: val,
      };
    });
  }, [data]);

  return (
    <div style={{ width: '100%' }}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 12, right: 12, bottom: 8, left: 8 }}>
          <defs>
            <linearGradient id="waterfall-pos" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={P.emerald} stopOpacity={0.9} />
              <stop offset="100%" stopColor={P.teal} stopOpacity={0.7} />
            </linearGradient>
            <linearGradient id="waterfall-neg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={P.rose} stopOpacity={0.9} />
              <stop offset="100%" stopColor="#FB7185" stopOpacity={0.7} />
            </linearGradient>
            <linearGradient id="waterfall-total" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={P.sky} stopOpacity={0.9} />
              <stop offset="100%" stopColor={P.blue} stopOpacity={0.7} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 9, fill: 'var(--muted)', fontFamily: 'Inter, Calibri, sans-serif' }}
            axisLine={{ stroke: 'var(--b1)' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 9, fill: 'var(--muted)', fontFamily: 'var(--mono)' }}
            tickFormatter={(v: number) => fmtCompact(v)}
            axisLine={false}
            tickLine={false}
            width={55}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg2)', border: '1px solid var(--b2)',
              borderRadius: 8, fontSize: 11, fontFamily: 'var(--mono)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            }}
            formatter={(value: any, name: any, props: any) => {
              const v = props.payload._displayVal;
              return [fmtCompact(v), props.payload.name];
            }}
            labelFormatter={() => ''}
          />
          {/* Invisible base bar */}
          <Bar dataKey="base" stackId="waterfall" fill="transparent" isAnimationActive={false} />
          {/* Visible value bar */}
          <Bar
            dataKey="size"
            stackId="waterfall"
            radius={[4, 4, 0, 0]}
            isAnimationActive={true}
            animationDuration={800}
            animationEasing="ease-out"
          >
            {chartData.map((entry, i) => {
              let fill: string;
              if (entry._isTotal) fill = 'url(#waterfall-total)';
              else if (entry._waterfallValue >= 0) fill = 'url(#waterfall-pos)';
              else fill = 'url(#waterfall-neg)';
              return <Cell key={i} fill={fill} />;
            })}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
      {/* Value labels below chart */}
      <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: -4 }}>
        {chartData.map((d, i) => (
          <div key={i} style={{
            textAlign: 'center', flex: 1, fontSize: 10, fontWeight: 600,
            fontFamily: 'var(--mono)',
            color: d._isTotal ? P.sky : d._waterfallValue >= 0 ? P.emerald : P.rose,
          }}>
            {fmtCompact(d._displayVal)}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================
   B) GaugeChart
   ================================================================ */

interface GaugeProps {
  value: number;
  max: number;
  label: string;
  thresholds: { green: number; yellow: number; red: number };
}

const renderGaugeNeedle = (cx: number, cy: number, value: number, max: number) => {
  const angle = 180 - (value / max) * 180;
  const rad = (angle * Math.PI) / 180;
  const len = 70;
  const x2 = cx + len * Math.cos(rad);
  const y2 = cy - len * Math.sin(rad);
  return (
    <g>
      {/* Needle */}
      <line
        x1={cx} y1={cy} x2={x2} y2={y2}
        stroke="var(--heading)"
        strokeWidth={2.5}
        strokeLinecap="round"
        style={{
          transition: 'all 1s cubic-bezier(0.34, 1.56, 0.64, 1)',
        }}
      />
      {/* Center dot */}
      <circle cx={cx} cy={cy} r={5} fill="var(--heading)" stroke="var(--bg2)" strokeWidth={2} />
    </g>
  );
};

export function GaugeChart({ value, max, label, thresholds }: GaugeProps) {
  const clamped = Math.min(Math.max(value, 0), max);

  // Build 3 arc segments
  const segments = [
    { start: 0, end: thresholds.red / max, color: P.rose },
    { start: thresholds.red / max, end: thresholds.yellow / max, color: P.amber },
    { start: thresholds.yellow / max, end: 1, color: P.emerald },
  ];

  const gaugeData = segments.map((s, i) => ({
    name: `seg-${i}`,
    value: (s.end - s.start) * 100,
    fill: s.color,
  }));

  // Determine value color
  const valColor = clamped >= thresholds.yellow ? P.emerald :
                   clamped >= thresholds.red ? P.amber : P.rose;

  return (
    <div style={{ width: '100%', position: 'relative' }}>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <defs>
            <linearGradient id="gauge-green" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={P.emerald} stopOpacity={0.8} />
              <stop offset="100%" stopColor={P.teal} stopOpacity={0.9} />
            </linearGradient>
            <linearGradient id="gauge-yellow" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={P.amber} stopOpacity={0.8} />
              <stop offset="100%" stopColor="#FBBF24" stopOpacity={0.9} />
            </linearGradient>
            <linearGradient id="gauge-red" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={P.rose} stopOpacity={0.8} />
              <stop offset="100%" stopColor="#FB7185" stopOpacity={0.9} />
            </linearGradient>
          </defs>
          <Pie
            data={gaugeData}
            cx="50%"
            cy="85%"
            startAngle={180}
            endAngle={0}
            innerRadius={60}
            outerRadius={80}
            paddingAngle={1}
            dataKey="value"
            isAnimationActive={true}
            animationDuration={1000}
            stroke="none"
          >
            {gaugeData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} opacity={0.85} />
            ))}
          </Pie>
          {/* Needle overlay via customized label */}
          <Pie
            data={[{ value: 100 }]}
            cx="50%"
            cy="85%"
            startAngle={180}
            endAngle={0}
            innerRadius={0}
            outerRadius={0}
            dataKey="value"
            isAnimationActive={false}
            {...({ activeIndex: 0 } as any)}
            activeShape={(props: any) => renderGaugeNeedle(props.cx, props.cy, clamped, max)}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Center value label */}
      <div style={{
        position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)',
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: 28, fontWeight: 800, fontFamily: 'var(--mono)',
          color: valColor, lineHeight: 1,
        }}>
          {Math.round(clamped)}
        </div>
        <div style={{
          fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: 1.5, color: 'var(--muted)', marginTop: 4,
        }}>
          {label}
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   C) SegmentDonutChart
   ================================================================ */

interface DonutItem {
  name: string;
  value: number;
  color?: string;
}

const renderActiveDonutShape = (props: any) => {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, percent } = props;
  return (
    <g>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        style={{ filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.3))' }}
      />
      <text x={cx} y={cy - 8} textAnchor="middle" fill="var(--heading)" fontSize={13} fontWeight={700} fontFamily="var(--mono)">
        {payload.name}
      </text>
      <text x={cx} y={cy + 12} textAnchor="middle" fill="var(--muted)" fontSize={11} fontFamily="var(--mono)">
        {`${(percent * 100).toFixed(1)}%`}
      </text>
    </g>
  );
};

export function SegmentDonutChart({ data, title }: { data: DonutItem[]; title: string }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  const chartData = data.map((d, i) => ({
    ...d,
    color: d.color || DONUT_COLORS[i % DONUT_COLORS.length],
  }));

  return (
    <div style={{ width: '100%' }}>
      {title && (
        <div style={{
          fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: 1.5, color: 'var(--muted)', marginBottom: 8, textAlign: 'center',
        }}>
          {title}
        </div>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <defs>
            {chartData.map((d, i) => (
              <linearGradient key={i} id={`donut-grad-${i}`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={d.color} stopOpacity={0.95} />
                <stop offset="100%" stopColor={d.color} stopOpacity={0.65} />
              </linearGradient>
            ))}
          </defs>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={2}
            dataKey="value"
            isAnimationActive={true}
            animationDuration={800}
            animationEasing="ease-out"
            activeShape={renderActiveDonutShape}
            stroke="none"
            label={({ name, percent }: any) =>
              `${name} ${(percent * 100).toFixed(0)}%`
            }
            labelLine={{ stroke: 'var(--b2)', strokeWidth: 1 }}
          >
            {chartData.map((d, i) => (
              <Cell key={i} fill={`url(#donut-grad-${i})`} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: 'var(--bg2)', border: '1px solid var(--b2)',
              borderRadius: 8, fontSize: 11, fontFamily: 'var(--mono)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            }}
            formatter={(value: any) => [fmtCompact(Number(value)), '']}
          />
        </PieChart>
      </ResponsiveContainer>
      {/* Center total */}
      <div style={{
        textAlign: 'center', marginTop: -160, position: 'relative', pointerEvents: 'none',
      }}>
        <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--mono)', color: 'var(--heading)' }}>
          {fmtCompact(total)}
        </div>
        <div style={{ fontSize: 8, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--dim)' }}>
          Total
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   D) MultiLineTimeSeries
   ================================================================ */

interface TimeSeriesData {
  name: string;
  data: { period: string; value: number }[];
  color: string;
}

export function MultiLineTimeSeries({ series }: { series: TimeSeriesData[] }) {
  // Merge all series into a unified dataset keyed by period
  const merged = useMemo(() => {
    const periodMap: Record<string, Record<string, number>> = {};
    const allPeriods = new Set<string>();

    series.forEach(s => {
      s.data.forEach(d => {
        allPeriods.add(d.period);
        if (!periodMap[d.period]) periodMap[d.period] = {};
        periodMap[d.period][s.name] = d.value;
      });
    });

    return Array.from(allPeriods).sort().map(p => ({
      period: p,
      ...periodMap[p],
    }));
  }, [series]);

  if (!merged.length) return null;

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={merged} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={i} id={`ts-area-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" vertical={false} />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 9, fill: 'var(--muted)' }}
          axisLine={{ stroke: 'var(--b1)' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 9, fill: 'var(--muted)', fontFamily: 'var(--mono)' }}
          tickFormatter={(v: number) => fmtCompact(v)}
          axisLine={false}
          tickLine={false}
          width={55}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--bg2)', border: '1px solid var(--b2)',
            borderRadius: 8, fontSize: 11, fontFamily: 'var(--mono)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}
          formatter={(value: any) => fmtCompact(Number(value))}
        />
        <Legend
          wrapperStyle={{ fontSize: 10, color: 'var(--muted)' }}
          iconType="circle"
          iconSize={8}
        />
        {series.map((s, i) => (
          <Area
            key={`area-${i}`}
            type="monotone"
            dataKey={s.name}
            stroke="none"
            fill={`url(#ts-area-${i})`}
            isAnimationActive={true}
            animationDuration={800}
          />
        ))}
        {series.map((s, i) => (
          <Line
            key={`line-${i}`}
            type="monotone"
            dataKey={s.name}
            stroke={s.color}
            strokeWidth={2}
            dot={{ r: 3, fill: s.color, strokeWidth: 0 }}
            activeDot={{ r: 5, stroke: s.color, strokeWidth: 2, fill: 'var(--bg2)' }}
            isAnimationActive={true}
            animationDuration={800}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* ================================================================
   E) MarginBarsChart
   ================================================================ */

interface MarginItem {
  product: string;
  revenue: number;
  cogs: number;
  margin_pct: number;
}

export function MarginBarsChart({ data }: { data: MarginItem[] }) {
  const sorted = useMemo(() =>
    [...data].sort((a, b) => b.revenue - a.revenue),
  [data]);

  const chartData = sorted.map(d => ({
    name: d.product.length > 18 ? d.product.slice(0, 16) + '...' : d.product,
    fullName: d.product,
    revenue: d.revenue,
    cogs: d.cogs,
    profit: d.revenue - d.cogs,
    margin: d.margin_pct,
  }));

  const marginColor = (pct: number) =>
    pct >= 15 ? P.emerald : pct >= 5 ? P.amber : P.rose;

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 36 + 40)}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 8, right: 60, bottom: 8, left: 8 }}
      >
        <defs>
          <linearGradient id="margin-rev" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={P.sky} stopOpacity={0.85} />
            <stop offset="100%" stopColor={P.blue} stopOpacity={0.7} />
          </linearGradient>
          <linearGradient id="margin-cogs" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={P.rose} stopOpacity={0.7} />
            <stop offset="100%" stopColor="#FB7185" stopOpacity={0.55} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--b1)" horizontal={false} />
        <XAxis
          type="number"
          tick={{ fontSize: 9, fill: 'var(--muted)', fontFamily: 'var(--mono)' }}
          tickFormatter={(v: number) => fmtCompact(v)}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 9, fill: 'var(--muted)' }}
          axisLine={false}
          tickLine={false}
          width={110}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--bg2)', border: '1px solid var(--b2)',
            borderRadius: 8, fontSize: 11, fontFamily: 'var(--mono)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          }}
          formatter={(value: any, name: any) => [fmtCompact(Number(value)), name]}
          labelFormatter={(label: any, payload: any) => payload?.[0]?.payload?.fullName || label}
        />
        <Bar
          dataKey="cogs"
          stackId="stack"
          fill="url(#margin-cogs)"
          name="COGS"
          radius={[0, 0, 0, 0]}
          isAnimationActive={true}
          animationDuration={800}
        />
        <Bar
          dataKey="profit"
          stackId="stack"
          name="Gross Profit"
          radius={[0, 4, 4, 0]}
          isAnimationActive={true}
          animationDuration={800}
        >
          {chartData.map((entry, i) => (
            <Cell key={i} fill={marginColor(entry.margin)} opacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
