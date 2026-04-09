import { useEffect } from 'react';
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  MarkerType,
} from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface CausalInsight {
  variable: string;
  effect_on: string;
  estimated_effect: number;
  confidence: number;
  severity: string;
}

interface CausalGraphProps {
  insights: CausalInsight[];
}

export default function CausalGraph({ insights }: CausalGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (!insights.length) return;

    // Collect unique variables
    const vars = new Set<string>();
    insights.forEach(i => {
      vars.add(i.variable);
      vars.add(i.effect_on);
    });
    const varList = Array.from(vars);

    // Layout: arrange in a circle for better visibility
    const cx = 300, cy = 250, radius = 200;
    const newNodes: Node[] = varList.map((label, i) => {
      const angle = (2 * Math.PI * i) / varList.length - Math.PI / 2;
      const isSource = insights.some(ins => ins.variable === label);
      const isTarget = insights.some(ins => ins.effect_on === label);
      const severity = insights.find(ins => ins.variable === label)?.severity;

      let borderColor = 'rgba(255,255,255,.15)';
      if (severity === 'critical') borderColor = '#f87171';
      else if (severity === 'high') borderColor = '#fbbf24';
      else if (isSource) borderColor = '#38bdf8';
      else if (isTarget) borderColor = '#a78bfa';

      return {
        id: label,
        data: { label },
        position: { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) },
        style: {
          background: 'rgba(15,20,34,.85)',
          backdropFilter: 'blur(8px)',
          color: '#e2e8f0',
          border: `2px solid ${borderColor}`,
          borderRadius: 10,
          padding: '10px 14px',
          fontSize: 11,
          fontWeight: 600,
          fontFamily: "'Inter', sans-serif",
          boxShadow: `0 0 12px ${borderColor}33`,
          minWidth: 100,
          textAlign: 'center' as const,
        },
      };
    });

    const newEdges: Edge[] = insights.map((ins, i) => {
      const isPositive = ins.estimated_effect > 0;
      const strokeColor = isPositive ? '#34d399' : '#f87171';
      const strokeWidth = Math.max(1.5, Math.min(5, Math.abs(ins.estimated_effect) * 20));

      return {
        id: `edge-${i}`,
        source: ins.variable,
        target: ins.effect_on,
        label: `${ins.estimated_effect > 0 ? '+' : ''}${(ins.estimated_effect * 100).toFixed(1)}%`,
        type: 'smoothstep',
        animated: ins.severity === 'critical' || ins.severity === 'high',
        style: { stroke: strokeColor, strokeWidth },
        labelStyle: {
          fill: strokeColor,
          fontWeight: 700,
          fontSize: 10,
          fontFamily: "'JetBrains Mono', monospace",
        },
        labelBgStyle: {
          fill: 'rgba(15,20,34,.9)',
          fillOpacity: 0.9,
        },
        labelBgPadding: [4, 6] as [number, number],
        labelBgBorderRadius: 4,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 16,
          height: 16,
        },
      };
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [insights, setNodes, setEdges]);

  if (!insights.length) {
    return (
      <div style={{
        height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--muted)', fontSize: 12, fontStyle: 'italic',
      }}>
        Run deep analysis to see the causal graph
      </div>
    );
  }

  return (
    <div style={{
      height: 480, borderRadius: 12, overflow: 'hidden',
      border: '1px solid var(--glass-border)',
      background: 'var(--bg0)',
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="rgba(255,255,255,.03)" variant={BackgroundVariant.Dots} gap={20} />
        <Controls
          style={{ background: 'rgba(15,20,34,.8)', borderRadius: 8, border: '1px solid rgba(255,255,255,.08)' }}
        />
        <MiniMap
          nodeColor={() => 'rgba(56,189,248,.4)'}
          maskColor="rgba(0,0,0,.7)"
          style={{ background: 'rgba(15,20,34,.9)', borderRadius: 8, border: '1px solid rgba(255,255,255,.06)' }}
        />
      </ReactFlow>
    </div>
  );
}
