import { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import { fmtCompact } from '../utils/formatters';

/* ---- NYX Core Palette ---- */
const P = {
  primary: '#00f2ff',   /* Cyan Neon — primary accent */
  positive: '#34C578',  /* Refined Green */
  negative: '#E05555',  /* Alert Red */
  warning: '#E8A73E',   /* Golden Orange */
  muted: '#516275',     /* Navy Gray */
  text: '#7D8FA3',
  heading: '#E8ECF2',
  blue: '#3B7DD8',      /* Interactive Blue */
  violet: '#8A79C0',
  teal: '#2BA8A0',
  cyan: '#00f2ff',
  amber: '#E8A73E',
  gold: '#C9A96E',      /* Warm Gold — premium accent */
};

const FONT = 'Inter, sans-serif';
const MONO = '"JetBrains Mono", "Roboto Mono", monospace';


/* ================================================================
   1. FinancialGauge - Semi-circular gauge with needle
   ================================================================ */

interface FinancialGaugeProps {
  value: number;
  max?: number;
  grade?: string;
  label?: string;
}

export function FinancialGauge({ value, max = 100, label = 'HEALTH SCORE', reasoning = 'NOMINAL' }: FinancialGaugeProps & { reasoning?: string }) {
  const clamped = Math.min(Math.max(value, 0), max);

  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        center: ['50%', '70%'],
        radius: '95%',
        min: 0,
        max,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 1,
            color: [
              [0.3, P.negative],
              [0.7, P.warning],
              [1, P.positive]
            ],
            opacity: 0.15
          },
        },
        pointer: {
          icon: 'path://M0,0 L1,5 L2,0 Z',
          length: '65%',
          width: 2,
          offsetCenter: [0, '5%'],
          itemStyle: {
            color: P.primary,
            shadowBlur: 8,
            shadowColor: P.primary,
          },
        },
        axisTick: {
          length: 3,
          lineStyle: { color: 'rgba(255,255,255,0.2)', width: 1 },
        },
        splitLine: {
          length: 6,
          lineStyle: { color: P.primary, width: 1, opacity: 0.4 },
        },
        axisLabel: {
          show: false
        },
        detail: {
          offsetCenter: [0, '35%'],
          formatter: (v: number) => `{val|${v.toFixed(0)}}{unit|%}\n{reason|${reasoning}}`,
          rich: {
            val: { fontSize: 22, fontWeight: 800, fontFamily: MONO, color: P.heading },
            unit: { fontSize: 10, fontFamily: MONO, color: P.muted, padding: [0, 0, 4, 1] },
            reason: { fontSize: 8, fontWeight: 900, fontFamily: MONO, color: P.primary, padding: [4, 0, 0, 0], letterSpacing: 1.5 },
          },
        },
        data: [{ value: clamped }],
      },
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        center: ['50%', '70%'],
        radius: '80%',
        min: 0,
        max,
        axisLine: {
          lineStyle: {
            width: 6,
            color: [
              [clamped/max, `${P.primary}44`],
              [1, 'rgba(255,255,255,0.02)']
            ],
          },
        },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        detail: { show: false },
      }
    ],
  }), [clamped, max, reasoning]);

  return (
    <div style={{ position: 'relative', height: 130 }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, textAlign: 'center', fontSize: 9, fontWeight: 900, color: 'var(--muted)', letterSpacing: 2, fontFamily: MONO, opacity: 0.8 }}>
        {label.toUpperCase()}
      </div>
      <ReactECharts
        option={option}
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'svg' }}
        notMerge={true}
      />
    </div>
  );
}

/* ================================================================
   2. PLWaterfallChart - Professional waterfall
   ================================================================ */

interface WaterfallItem {
  label: string;
  value: number;
}

export function PLWaterfallChart({ data }: { data: WaterfallItem[] }) {
  const option = useMemo(() => {
    const categories = data.map(d => d.label);
    const baseValues: any[] = [];
    const positiveValues: any[] = [];
    const negativeValues: any[] = [];
    let running = 0;

    data.forEach((item, i) => {
      const val = item.value;
      if (i === 0 || i === data.length - 1) {
        // Total
        baseValues.push(0);
        positiveValues.push(val);
        negativeValues.push('-');
        running = val;
      } else {
        // Incremental
        if (val >= 0) {
          baseValues.push(running);
          positiveValues.push(val);
          negativeValues.push('-');
        } else {
          baseValues.push(running + val);
          positiveValues.push('-');
          negativeValues.push(Math.abs(val));
        }
        running += val;
      }
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        backgroundColor: 'rgba(15,23,42,0.95)',
        borderColor: 'rgba(56,189,248,0.15)',
        borderWidth: 1,
        textStyle: { color: P.heading, fontSize: 11, fontFamily: MONO },
        formatter: (params: any) => {
          const idx = params[0]?.dataIndex ?? 0;
          const item = data[idx];
          if (!item) return '';
          const color = item.value >= 0 ? P.positive : P.negative;
          return `<div style="font-weight:600;margin-bottom:4px">${item.label}</div>
            <span style="color:${color};font-weight:700">${fmtCompact(item.value)}</span>`;
        },
      },
      grid: { left: 60, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisTick: { show: false },
        axisLabel: {
          color: P.muted,
          fontSize: 8,
          fontFamily: MONO,
          rotate: categories.length > 5 ? 25 : 0,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'solid' } },
        axisLabel: {
          color: P.muted,
          fontSize: 8,
          fontFamily: MONO,
          formatter: (v: number) => fmtCompact(v),
        },
      },
      series: [
        {
          name: 'Base',
          type: 'bar',
          stack: 'waterfall',
          itemStyle: { borderColor: 'transparent', color: 'transparent' },
          emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
          data: baseValues,
        },
        {
          name: 'Positive',
          type: 'bar',
          stack: 'waterfall',
          barWidth: '40%',
          label: {
            show: true,
            position: 'top',
            formatter: (p: any) => fmtCompact(data[p.dataIndex].value),
            color: P.text,
            fontSize: 9,
            fontFamily: MONO
          },
          itemStyle: { color: P.positive },
          data: positiveValues,
        },
        {
          name: 'Negative',
          type: 'bar',
          stack: 'waterfall',
          barWidth: '40%',
          itemStyle: { color: P.negative },
          data: negativeValues,
        }
      ]
    };
  }, [data]);

  return <ReactECharts option={option} style={{ height: 300, width: '100' }} opts={{ renderer: 'svg' }} notMerge={true} />;
}

/* ================================================================
   3. RevenueTrendChart - Multi-series time chart with Ghost Line
   ================================================================ */

interface TrendPeriod {
  period: string;
  revenue: number;
  gross_profit: number;
  net_profit: number;
}

export function RevenueTrendChart({ data, simGrowth = 0 }: { data: TrendPeriod[]; simGrowth?: number }) {
  const option = useMemo(() => {
    if (!data || data.length === 0) return {};

    const periods = data.map(d => d.period);
    const revenues = data.map(d => d.revenue);
    const gpArr = data.map(d => d.gross_profit);
    const netArr = data.map(d => d.net_profit);

    // Simulated Forecast Series
    const simData = revenues.map((v, i) => {
      if (i === revenues.length - 1) return v * (1 + simGrowth / 100);
      return null;
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 20, 34, 0.95)',
        borderColor: 'rgba(0, 242, 255, 0.2)',
        borderWidth: 1,
        textStyle: { color: P.heading, fontSize: 11, fontFamily: MONO },
        axisPointer: { type: 'cross', lineStyle: { color: P.primary, type: 'dashed' } }
      },
      legend: {
        data: ['Revenue', 'Gross Profit', 'Net Profit', 'Simulated Forecast'],
        bottom: 0,
        textStyle: { color: P.muted, fontSize: 8, fontFamily: MONO },
        itemWidth: 8,
        itemHeight: 2
      },
      grid: { left: 50, right: 10, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: periods,
        boundaryGap: false,
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        axisTick: { show: false },
        axisLabel: { color: P.muted, fontSize: 9, fontFamily: MONO, margin: 15 },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.03)', type: 'solid' } },
        axisLabel: {
          color: P.muted,
          fontSize: 9,
          fontFamily: MONO,
          formatter: (v: number) => fmtCompact(v),
        },
      },
      series: [
        {
          name: 'Revenue',
          type: 'line',
          data: revenues,
          step: 'end',
          lineStyle: { width: 1.5, color: P.primary },
          areaStyle: { color: 'rgba(0, 242, 255, 0.03)', origin: 'start' },
          symbol: 'none',
          z: 10,
        },
        {
          name: 'Simulated Forecast',
          type: 'line',
          data: simData,
          lineStyle: { type: 'dashed', color: P.violet, width: 2 },
          symbol: 'circle',
          symbolSize: 8,
          itemStyle: { color: P.violet, shadowBlur: 10, shadowColor: P.violet },
          label: {
            show: simGrowth !== 0,
            position: 'top',
            formatter: () => 'PROJECTED',
            color: P.violet,
            fontSize: 9,
            fontWeight: 800,
            fontFamily: MONO
          },
          z: 20
        },
        {
          name: 'Gross Profit',
          type: 'line',
          data: gpArr,
          smooth: false,
          lineStyle: { width: 1, color: P.positive },
          symbol: 'none',
        },
        {
          name: 'Net Profit',
          type: 'line',
          data: netArr,
          smooth: false,
          lineStyle: { width: 1, color: P.violet },
          symbol: 'none',
        }
      ],
      animationDuration: 500,
      animationEasing: 'cubicOut',
    };
  }, [data, simGrowth]);

  return <ReactECharts option={option} style={{ height: 360, width: '100%' }} opts={{ renderer: 'svg' }} notMerge={false} />;
}

/* ================================================================
   4. SegmentSunburst - Hierarchical revenue breakdown
   ================================================================ */

interface SegmentData {
  name: string;
  value: number;
  children?: SegmentData[];
}

export function SegmentSunburst({ data, total }: { data: SegmentData[]; total?: number }) {
  const option = useMemo(() => {
    const totalRev = total || data.reduce((s, d) => s + d.value, 0);
    const palette = [P.primary, P.positive, P.violet, P.warning, P.teal, P.cyan, P.negative, P.blue];

    const buildItems = (items: SegmentData[], depth: number): any[] =>
      items.map((item, i) => ({
        name: item.name,
        value: item.value,
        itemStyle: {
          color: depth === 0 ? palette[i % palette.length] : undefined,
          borderWidth: 2,
          borderColor: 'rgba(15,23,42,0.8)',
        },
        label: {
          fontSize: depth === 0 ? 11 : 9,
          fontFamily: FONT,
          color: P.heading,
        },
        children: item.children ? buildItems(item.children, depth + 1) : undefined,
      }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: 'rgba(15,23,42,0.95)',
        borderColor: 'rgba(56,189,248,0.15)',
        borderWidth: 1,
        textStyle: { color: P.heading, fontSize: 11, fontFamily: MONO },
        formatter: (p: any) => {
          const pct = totalRev > 0 ? ((p.value / totalRev) * 100).toFixed(1) : '0';
          return `<div style="font-weight:600">${p.name}</div>
            <div>${fmtCompact(p.value)} <span style="color:${P.muted}">(${pct}%)</span></div>`;
        },
      },
      series: [
        {
          type: 'sunburst',
          data: buildItems(data, 0),
          radius: ['22%', '92%'],
          sort: undefined,
          emphasis: { focus: 'ancestor' },
          levels: [{}, { r0: '22%', r: '55%' }, { r0: '55%', r: '92%' }],
          label: { color: P.heading, fontFamily: FONT },
        },
      ],
      graphic: {
        type: 'text', left: 'center', top: 'center',
        style: { text: fmtCompact(totalRev), fontSize: 16, fontWeight: 700, fontFamily: MONO, fill: P.heading }
      }
    };
  }, [data, total]);

  return <ReactECharts option={option} style={{ height: 360, width: '100%' }} opts={{ renderer: 'svg' }} notMerge={true} />;
}

/* ================================================================
   5. MarginHeatmap - 2D matrix of product/region performance
   ================================================================ */

export function MarginHeatmap({ data }: { data: any[] }) {
  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { position: 'top' },
    grid: { height: '70%', top: '10%' },
    xAxis: { type: 'category', data: data.map(d => d.region), splitArea: { show: true } },
    yAxis: { type: 'category', data: data.map(d => d.product), splitArea: { show: true } },
    visualMap: {
      min: 0, max: 50, calculable: true, orient: 'horizontal', left: 'center', bottom: '0%',
      inRange: { color: ['rgba(239,68,68,0.1)', 'rgba(16,185,129,0.5)'] }
    },
    series: [{
      name: 'Margin', type: 'heatmap',
      data: data.map((d, i) => [i, i, d.value]),
      label: { show: true, fontFamily: MONO, fontSize: 8 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } }
    }]
  }), [data]);

  return <ReactECharts option={option} style={{ height: 260, width: '100%' }} />;
}

/* ================================================================
   6. CapitalHierarchyMap - Treemap for ownership/control
   ================================================================ */

export function CapitalHierarchyMap({ data }: { data: any[] }) {
  const option = useMemo(() => ({
    backgroundColor: 'transparent',
    tooltip: { formatter: (info: any) => `${info.name}: ${info.value}% Equity` },
    series: [{
      type: 'treemap',
      data: data.map(d => ({ name: d.name, value: d.value, control: d.control_pct })),
      leafDepth: 2,
      levels: [{
        itemStyle: { borderColor: 'rgba(15,23,42,1)', borderWidth: 2, gapWidth: 2 },
        upperLabel: { show: true, height: 24, fontFamily: MONO, fontSize: 9, color: P.heading, textBorderColor: 'transparent' }
      }],
      label: {
        show: true,
        formatter: '{b}',
        fontSize: 10,
        fontFamily: MONO,
        color: '#fff',
        padding: [0, 4]
      },
      breadcrumb: { show: false }
    }]
  }), [data]);

  return <ReactECharts option={option} style={{ height: 220, width: '100%' }} />;
}

// Default export for generic ECharts usage
export default ReactECharts;
