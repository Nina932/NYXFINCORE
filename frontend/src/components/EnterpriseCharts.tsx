/**
 * EnterpriseCharts — Reusable enterprise-grade visualization components
 * Treemap, Sunburst, Heatmap, Waterfall, Gauge, Radar, Sankey, Funnel
 * Built on ECharts 6 for maximum capability.
 */
import ReactECharts from 'echarts-for-react';
import { useMemo } from 'react';

/* ─── Shared palette ─── */
const PALETTE = ['#00D8FF', '#48BB78', '#9F7AEA', '#ED8936', '#F56565', '#D4AF37', '#3182CE', '#E53E8E', '#38B2AC', '#667EEA'];
const FONT = "'JetBrains Mono', 'Fira Code', monospace";

interface ChartContainerProps {
  title?: string;
  subtitle?: string;
  height?: string;
  children: React.ReactNode;
}

export function ChartContainer({ title, subtitle, height = '400px', children }: ChartContainerProps) {
  return (
    <div className="glass" style={{ padding: 16, height }}>
      {title && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>{title}</div>
          {subtitle && <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 2 }}>{subtitle}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

/* ═══════════════════════════════════════════════
   TREEMAP — Hierarchical data visualization
   ═══════════════════════════════════════════════ */
interface TreemapNode {
  name: string;
  value: number;
  children?: TreemapNode[];
  itemStyle?: { color?: string };
}

interface TreemapChartProps {
  data: TreemapNode[];
  height?: string;
  title?: string;
  onDrillDown?: (node: TreemapNode) => void;
}

export function TreemapChart({ data, height = '360px', title }: TreemapChartProps) {
  const option = useMemo(() => ({
    tooltip: {
      formatter: (info: any) => {
        const val = info.value;
        const name = info.name;
        return `<div style="font-family:${FONT};font-size:11px"><b>${name}</b><br/>Value: ${typeof val === 'number' ? val.toLocaleString() : val}</div>`;
      }
    },
    series: [{
      type: 'treemap',
      data,
      width: '100%',
      height: '100%',
      roam: false,
      nodeClick: 'zoomToNode',
      breadcrumb: {
        show: true,
        itemStyle: { color: 'rgba(0,216,255,0.15)', borderColor: 'rgba(0,216,255,0.3)', textStyle: { color: '#E2E8F0', fontFamily: FONT, fontSize: 10 } },
      },
      label: { show: true, formatter: '{b}', fontSize: 11, fontFamily: FONT, color: '#F7FAFC' },
      upperLabel: { show: true, height: 24, color: '#E2E8F0', fontFamily: FONT, fontSize: 10, backgroundColor: 'transparent' },
      itemStyle: { borderColor: 'rgba(0,0,0,0.3)', borderWidth: 1, gapWidth: 2 },
      levels: [
        { itemStyle: { borderColor: 'rgba(0,216,255,0.4)', borderWidth: 2, gapWidth: 3 }, upperLabel: { show: false } },
        { itemStyle: { borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1, gapWidth: 1 }, colorSaturation: [0.35, 0.6] },
        { itemStyle: { borderColor: 'rgba(255,255,255,0.05)', borderWidth: 1 }, colorSaturation: [0.3, 0.5] },
      ],
      colorMappingBy: 'value',
      visualMin: 0,
      color: PALETTE,
    }]
  }), [data]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   SUNBURST — Radial hierarchical breakdown
   ═══════════════════════════════════════════════ */
interface SunburstNode {
  name: string;
  value?: number;
  children?: SunburstNode[];
  itemStyle?: { color?: string };
}

interface SunburstChartProps {
  data: SunburstNode[];
  height?: string;
  title?: string;
}

export function SunburstChart({ data, height = '360px' }: SunburstChartProps) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'item', formatter: (p: any) => `<div style="font-family:${FONT};font-size:11px"><b>${p.name}</b><br/>${p.value?.toLocaleString() || ''}</div>` },
    series: [{
      type: 'sunburst',
      data,
      radius: ['15%', '90%'],
      sort: undefined,
      emphasis: { focus: 'ancestor' },
      itemStyle: { borderRadius: 4, borderWidth: 2, borderColor: 'rgba(0,0,0,0.2)' },
      label: { fontFamily: FONT, fontSize: 10, color: '#F7FAFC', minAngle: 10 },
      levels: [
        {},
        { r0: '15%', r: '40%', label: { fontSize: 11, fontWeight: 600 }, itemStyle: { borderWidth: 2 } },
        { r0: '40%', r: '65%', label: { fontSize: 10 }, itemStyle: { borderWidth: 1 } },
        { r0: '65%', r: '90%', label: { show: false }, itemStyle: { borderWidth: 1 } },
      ],
      color: PALETTE,
    }]
  }), [data]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   HEATMAP — Matrix visualization
   ═══════════════════════════════════════════════ */
interface HeatmapChartProps {
  data: [number, number, number][]; // [x, y, value]
  xLabels: string[];
  yLabels: string[];
  height?: string;
  title?: string;
  min?: number;
  max?: number;
  colorRange?: [string, string];
}

export function HeatmapChart({ data, xLabels, yLabels, height = '360px', min = 0, max = 100, colorRange = ['#0E131F', '#00D8FF'] }: HeatmapChartProps) {
  const option = useMemo(() => ({
    tooltip: {
      position: 'top',
      formatter: (p: any) => `<div style="font-family:${FONT};font-size:11px"><b>${xLabels[p.data[0]]}</b> × <b>${yLabels[p.data[1]]}</b><br/>Value: ${p.data[2]}</div>`
    },
    grid: { left: 100, right: 40, top: 20, bottom: 60 },
    xAxis: { type: 'category', data: xLabels, splitArea: { show: true }, axisLabel: { fontFamily: FONT, fontSize: 9, color: '#A0AEC0', rotate: 30 } },
    yAxis: { type: 'category', data: yLabels, splitArea: { show: true }, axisLabel: { fontFamily: FONT, fontSize: 9, color: '#A0AEC0' } },
    visualMap: {
      min, max, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
      inRange: { color: colorRange },
      textStyle: { color: '#A0AEC0', fontFamily: FONT, fontSize: 9 },
    },
    series: [{
      type: 'heatmap',
      data,
      label: { show: true, fontFamily: FONT, fontSize: 9, color: '#F7FAFC' },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,216,255,0.4)' } },
    }]
  }), [data, xLabels, yLabels, min, max, colorRange]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   WATERFALL — Bridge / variance analysis
   ═══════════════════════════════════════════════ */
interface WaterfallItem {
  name: string;
  value: number;
  isTotal?: boolean;
}

interface WaterfallChartProps {
  data: WaterfallItem[];
  height?: string;
  title?: string;
}

export function WaterfallChart({ data, height = '360px' }: WaterfallChartProps) {
  const option = useMemo(() => {
    const invisible: number[] = [];
    const positive: (number | '-')[] = [];
    const negative: (number | '-')[] = [];
    let running = 0;

    data.forEach(item => {
      if (item.isTotal) {
        invisible.push(0);
        positive.push(running > 0 ? running : '-');
        negative.push(running < 0 ? Math.abs(running) : '-');
      } else if (item.value >= 0) {
        invisible.push(running);
        positive.push(item.value);
        negative.push('-');
        running += item.value;
      } else {
        running += item.value;
        invisible.push(running);
        positive.push('-');
        negative.push(Math.abs(item.value));
      }
    });

    return {
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p: any) => {
        const idx = p[0]?.dataIndex;
        const item = data[idx];
        return `<div style="font-family:${FONT};font-size:11px"><b>${item?.name}</b><br/>${item?.value >= 0 ? '+' : ''}${item?.value?.toLocaleString()}</div>`;
      }},
      grid: { left: 60, right: 20, top: 20, bottom: 50 },
      xAxis: { type: 'category', data: data.map(d => d.name), axisLabel: { fontFamily: FONT, fontSize: 9, color: '#A0AEC0', rotate: 20 } },
      yAxis: { type: 'value', axisLabel: { fontFamily: FONT, fontSize: 9, color: '#A0AEC0', formatter: (v: number) => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}K` : String(v) }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
      series: [
        { type: 'bar', stack: 'wf', data: invisible, itemStyle: { borderColor: 'transparent', color: 'transparent' }, emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } } },
        { type: 'bar', stack: 'wf', name: 'Increase', data: positive, itemStyle: { color: '#48BB78', borderRadius: [3, 3, 0, 0] }, label: { show: true, position: 'top', fontFamily: FONT, fontSize: 9, color: '#48BB78', formatter: (p: any) => p.value !== '-' ? `+${Number(p.value).toLocaleString()}` : '' } },
        { type: 'bar', stack: 'wf', name: 'Decrease', data: negative, itemStyle: { color: '#F56565', borderRadius: [3, 3, 0, 0] }, label: { show: true, position: 'top', fontFamily: FONT, fontSize: 9, color: '#F56565', formatter: (p: any) => p.value !== '-' ? `-${Number(p.value).toLocaleString()}` : '' } },
      ]
    };
  }, [data]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   GAUGE — KPI gauge with gradient
   ═══════════════════════════════════════════════ */
interface GaugeChartProps {
  value: number;
  max?: number;
  title?: string;
  suffix?: string;
  height?: string;
  thresholds?: { value: number; color: string }[];
}

export function GaugeChart({ value, max = 100, title = '', suffix = '', height = '220px', thresholds }: GaugeChartProps) {
  const colors: [number, string][] = thresholds
    ? thresholds.map(t => [t.value / max, t.color])
    : [[0.3, '#F56565'], [0.6, '#ED8936'], [0.8, '#48BB78'], [1, '#00D8FF']];

  const option = useMemo(() => ({
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max,
      splitNumber: 5,
      itemStyle: { color: '#00D8FF' },
      progress: { show: true, width: 18, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: colors.map(([offset, color]) => ({ offset, color })) } } },
      pointer: { show: true, length: '60%', width: 4, itemStyle: { color: '#E2E8F0' } },
      axisLine: { lineStyle: { width: 18, color: [[1, 'rgba(255,255,255,0.06)']] } },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { width: 2, color: 'rgba(255,255,255,0.15)' } },
      axisLabel: { distance: 22, fontFamily: FONT, fontSize: 9, color: '#718096' },
      anchor: { show: true, size: 14, itemStyle: { borderWidth: 3, borderColor: '#00D8FF', color: '#0E131F' } },
      title: { show: true, offsetCenter: [0, '70%'], fontSize: 12, fontFamily: FONT, color: '#A0AEC0' },
      detail: { valueAnimation: true, fontSize: 28, fontWeight: 800, fontFamily: FONT, color: '#F7FAFC', offsetCenter: [0, '45%'], formatter: `{value}${suffix}` },
      data: [{ value, name: title }]
    }]
  }), [value, max, title, suffix, colors]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   RADAR — Multi-dimensional comparison
   ═══════════════════════════════════════════════ */
interface RadarChartProps {
  indicators: { name: string; max: number }[];
  series: { name: string; values: number[]; color?: string }[];
  height?: string;
}

export function RadarChart({ indicators, series, height = '360px' }: RadarChartProps) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'item' },
    legend: { data: series.map(s => s.name), bottom: 0, textStyle: { color: '#A0AEC0', fontFamily: FONT, fontSize: 10 } },
    radar: {
      indicator: indicators.map(ind => ({ name: ind.name, max: ind.max })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#A0AEC0', fontFamily: FONT, fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      splitArea: { areaStyle: { color: ['rgba(0,216,255,0.02)', 'rgba(0,216,255,0.04)'] } },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    series: [{
      type: 'radar',
      data: series.map((s, i) => ({
        value: s.values,
        name: s.name,
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2, color: s.color || PALETTE[i] },
        itemStyle: { color: s.color || PALETTE[i] },
      }))
    }]
  }), [indicators, series]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   SANKEY — Flow / allocation diagram
   ═══════════════════════════════════════════════ */
interface SankeyLink { source: string; target: string; value: number }
interface SankeyNode { name: string; itemStyle?: { color?: string } }

interface SankeyChartProps {
  nodes: SankeyNode[];
  links: SankeyLink[];
  height?: string;
}

export function SankeyChart({ nodes, links, height = '400px' }: SankeyChartProps) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'item', formatter: (p: any) => {
      if (p.dataType === 'edge') return `<div style="font-family:${FONT};font-size:11px">${p.data.source} → ${p.data.target}<br/>${p.data.value.toLocaleString()}</div>`;
      return `<div style="font-family:${FONT};font-size:11px"><b>${p.name}</b></div>`;
    }},
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeGap: 12,
      nodeWidth: 20,
      data: nodes.map((n, i) => ({ ...n, itemStyle: n.itemStyle || { color: PALETTE[i % PALETTE.length] } })),
      links,
      lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.3 },
      label: { fontFamily: FONT, fontSize: 10, color: '#E2E8F0' },
      itemStyle: { borderWidth: 1, borderColor: 'rgba(0,0,0,0.2)' },
    }]
  }), [nodes, links]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   FUNNEL — Conversion / pipeline chart
   ═══════════════════════════════════════════════ */
interface FunnelItem { name: string; value: number }

interface FunnelChartProps {
  data: FunnelItem[];
  height?: string;
}

export function FunnelChart({ data, height = '320px' }: FunnelChartProps) {
  const option = useMemo(() => ({
    tooltip: { trigger: 'item', formatter: (p: any) => `<div style="font-family:${FONT};font-size:11px"><b>${p.name}</b><br/>${p.value.toLocaleString()} (${p.percent?.toFixed(1)}%)</div>` },
    series: [{
      type: 'funnel',
      left: '10%',
      top: 10,
      bottom: 10,
      width: '80%',
      sort: 'descending',
      gap: 4,
      label: { show: true, position: 'inside', fontFamily: FONT, fontSize: 11, color: '#F7FAFC', formatter: '{b}\n{c}' },
      labelLine: { length: 10, lineStyle: { width: 1, type: 'solid' } },
      itemStyle: { borderColor: 'rgba(0,0,0,0.2)', borderWidth: 1 },
      emphasis: { label: { fontSize: 14 } },
      data: data.map((d, i) => ({ ...d, itemStyle: { color: PALETTE[i % PALETTE.length] } })),
    }]
  }), [data]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}

/* ═══════════════════════════════════════════════
   DRILLDOWN BAR — Clickable drill-in bar chart
   ═══════════════════════════════════════════════ */
interface DrilldownCategory {
  name: string;
  value: number;
  children?: { name: string; value: number }[];
}

interface DrilldownBarChartProps {
  data: DrilldownCategory[];
  height?: string;
  valueFormatter?: (v: number) => string;
}

export function DrilldownBarChart({ data, height = '360px', valueFormatter }: DrilldownBarChartProps) {
  const fmt = valueFormatter || ((v: number) => v >= 1e6 ? `${(v/1e6).toFixed(1)}M` : v >= 1e3 ? `${(v/1e3).toFixed(0)}K` : String(v));

  const option = useMemo(() => ({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (p: any) => `<div style="font-family:${FONT};font-size:11px"><b>${p[0]?.name}</b><br/>${fmt(p[0]?.value)}</div>` },
    grid: { left: 80, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLabel: { fontFamily: FONT, fontSize: 10, color: '#A0AEC0' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontFamily: FONT, fontSize: 9, color: '#718096', formatter: (v: number) => fmt(v) },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    series: [{
      type: 'bar',
      data: data.map((d, i) => ({
        value: d.value,
        itemStyle: {
          color: PALETTE[i % PALETTE.length],
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barMaxWidth: 50,
      label: { show: true, position: 'top', fontFamily: FONT, fontSize: 9, color: '#A0AEC0', formatter: (p: any) => fmt(p.value) },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,216,255,0.3)' } },
    }],
    animationEasing: 'elasticOut',
  }), [data, fmt]);

  return <ReactECharts option={option} style={{ height }} theme="dark" />;
}
