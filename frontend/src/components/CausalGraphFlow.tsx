import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { useStore } from '../store/useStore';

/* ---- Formatting ---- */
function fmt(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '\u2014';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${n < 0 ? '-' : ''}\u20BE${(abs / 1e3).toFixed(0)}K`;
  return `\u20BE${n.toFixed(0)}`;
}

interface GraphNode {
  id: string;
  label: string;
  value: number;
  change: number | null;
  type: string;
  level: number;
}

interface GraphEdge {
  source: string;
  target: string;
  impact: string;
  strength: string;
}

interface CausalGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  root_causes: Array<{ metric: string; change_pct: number; impact: string }>;
  impact_chain: Array<{ from: string; to: string; effect: string }>;
}

interface Props {
  financials?: Record<string, number>;
  previous?: Record<string, number>;
  healthScore?: number;
  healthGrade?: string;
}

/* ---- Node colors by type ---- */
function nodeColor(type: string, value?: number): string {
  if (type === 'health') return 'var(--violet)';
  if (type === 'result') return (value ?? 0) >= 0 ? 'var(--emerald)' : 'var(--rose)';
  if (type === 'profit') return (value ?? 0) >= 0 ? 'var(--emerald)' : 'var(--rose)';
  if (type === 'expense') return 'var(--amber)';
  if (type === 'income') return 'var(--sky)';
  return 'var(--muted)';
}

/* ---- Edge color ---- */
function edgeColor(impact: string): string {
  return impact === 'positive' ? '#34d399' : '#f87171';
}

export default function CausalGraphFlow({ financials, previous, healthScore, healthGrade }: Props) {
  const { pnl } = useStore();
  const [data, setData] = useState<CausalGraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    const fin = financials || pnl;
    if (!fin || Object.keys(fin).length === 0) return;

    setLoading(true);
    api.causalGraph(fin, previous, healthScore, healthGrade)
      .then((res: unknown) => {
        const d = res as CausalGraphData;
        if (d && d.nodes) setData(d);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [financials, pnl, previous, healthScore, healthGrade]);

  if (loading) {
    return <div style={{ padding: 20, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>Building causal graph...</div>;
  }

  if (!data || !data.nodes.length) {
    return <div style={{ padding: 20, textAlign: 'center', color: 'var(--dim)', fontSize: 11 }}>No causal data available</div>;
  }

  // Group nodes by level
  const levels: Record<number, GraphNode[]> = {};
  data.nodes.forEach(n => {
    if (!levels[n.level]) levels[n.level] = [];
    levels[n.level].push(n);
  });
  const levelKeys = Object.keys(levels).map(Number).sort();

  // Layout constants
  const NODE_W = 140;
  const NODE_H = 72;
  const H_GAP = 30;
  const V_GAP = 24;
  const MARGIN_LEFT = 20;
  const MARGIN_TOP = 20;

  // Compute positions
  const positions: Record<string, { x: number; y: number }> = {};
  let maxWidth = 0;
  levelKeys.forEach((lvl, colIdx) => {
    const nodesInLevel = levels[lvl];
    const totalH = nodesInLevel.length * NODE_H + (nodesInLevel.length - 1) * V_GAP;
    const startY = MARGIN_TOP + (300 - totalH) / 2; // center vertically
    nodesInLevel.forEach((n, rowIdx) => {
      const x = MARGIN_LEFT + colIdx * (NODE_W + H_GAP);
      const y = Math.max(MARGIN_TOP, startY + rowIdx * (NODE_H + V_GAP));
      positions[n.id] = { x, y };
      maxWidth = Math.max(maxWidth, x + NODE_W);
    });
  });

  const svgWidth = maxWidth + MARGIN_LEFT + 40;
  const svgHeight = Math.max(320, ...Object.values(positions).map(p => p.y + NODE_H + 20));

  // Get connected edges for a hovered node
  const hoveredEdges = hovered
    ? data.edges.filter(e => e.source === hovered || e.target === hovered)
    : [];
  const connectedNodeIds = new Set(hoveredEdges.flatMap(e => [e.source, e.target]));

  return (
    <div style={{ width: '100%', overflowX: 'auto' }}>
      <svg width={svgWidth} height={svgHeight} style={{ fontFamily: "'Inter', sans-serif" }}>
        <defs>
          <marker id="arrow-pos" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#34d399" opacity="0.7" />
          </marker>
          <marker id="arrow-neg" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#f87171" opacity="0.7" />
          </marker>
        </defs>

        {/* Edges */}
        {data.edges.map((edge, i) => {
          const src = positions[edge.source];
          const tgt = positions[edge.target];
          if (!src || !tgt) return null;

          const x1 = src.x + NODE_W;
          const y1 = src.y + NODE_H / 2;
          const x2 = tgt.x;
          const y2 = tgt.y + NODE_H / 2;

          const isHighlighted = hovered ? (edge.source === hovered || edge.target === hovered) : false;
          const isDimmed = hovered && !isHighlighted;

          const color = edgeColor(edge.impact);
          const sw = edge.strength === 'strong' ? 2.5 : edge.strength === 'moderate' ? 1.8 : 1.2;
          const midX = (x1 + x2) / 2;

          return (
            <g key={i} style={{ opacity: isDimmed ? 0.15 : 1, transition: 'opacity .2s' }}>
              <path
                d={`M${x1},${y1} C${midX},${y1} ${midX},${y2} ${x2},${y2}`}
                fill="none"
                stroke={color}
                strokeWidth={isHighlighted ? sw + 1 : sw}
                strokeDasharray={edge.strength === 'weak' ? '4,4' : 'none'}
                markerEnd={edge.impact === 'positive' ? 'url(#arrow-pos)' : 'url(#arrow-neg)'}
                opacity={0.7}
              />
            </g>
          );
        })}

        {/* Nodes */}
        {data.nodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;

          const isHovered = hovered === node.id;
          const isConnected = hovered ? connectedNodeIds.has(node.id) : false;
          const isDimmed = hovered && !isHovered && !isConnected;
          const color = nodeColor(node.type, node.value);

          return (
            <g
              key={node.id}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}
              style={{ cursor: 'pointer', opacity: isDimmed ? 0.25 : 1, transition: 'opacity .2s' }}
            >
              <rect
                x={pos.x}
                y={pos.y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill="rgba(15,20,34,.85)"
                stroke={isHovered ? color : `${color}55`}
                strokeWidth={isHovered ? 2 : 1}
              />
              {/* Metric name */}
              <text
                x={pos.x + NODE_W / 2}
                y={pos.y + 16}
                textAnchor="middle"
                fill="rgba(255,255,255,.5)"
                fontSize="9"
                fontWeight="600"
                letterSpacing="0.8"
                style={{ textTransform: 'uppercase' } as React.CSSProperties}
              >
                {node.label}
              </text>
              {/* Value */}
              <text
                x={pos.x + NODE_W / 2}
                y={pos.y + 40}
                textAnchor="middle"
                fill={color}
                fontSize="16"
                fontWeight="800"
                fontFamily="'JetBrains Mono', monospace"
              >
                {node.type === 'health' ? `${node.value.toFixed(0)}/100` : fmt(node.value)}
              </text>
              {/* Change badge */}
              {node.change != null && (
                <text
                  x={pos.x + NODE_W / 2}
                  y={pos.y + 58}
                  textAnchor="middle"
                  fill={node.change > 0 ? (node.type === 'expense' ? '#f87171' : '#34d399') : (node.type === 'expense' ? '#34d399' : '#f87171')}
                  fontSize="10"
                  fontWeight="700"
                  fontFamily="'JetBrains Mono', monospace"
                >
                  {node.change > 0 ? '\u2191' : '\u2193'}{Math.abs(node.change).toFixed(1)}%
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Root causes */}
      {data.root_causes.length > 0 && (
        <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(248,113,113,.06)', borderRadius: 8, borderLeft: '3px solid var(--rose)' }}>
          <p style={{ fontSize: 10, fontWeight: 700, color: 'var(--rose)', margin: '0 0 6px 0', fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: 1 }}>Root Causes</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {data.root_causes.map((rc, i) => (
              <span key={i} style={{ fontSize: 11, color: 'var(--text)', padding: '3px 8px', background: 'rgba(248,113,113,.08)', borderRadius: 4 }}>
                {rc.metric}: {rc.change_pct > 0 ? '+' : ''}{rc.change_pct.toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
