import { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  MiniMap, 
  useNodesState, 
  useEdgesState, 
  addEdge,
  MarkerType,
  Panel,
  Handle,
  Position,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  Loader2, 
  Network, 
  LayoutGrid,
  Activity
} from 'lucide-react';
import { useObject } from '../hooks/useOntology';

import TechNode from './graph/TechNode';
import GlobalNode from './graph/GlobalNode';
import DataStreamEdge from './graph/DataStreamEdge';

/* ─── Type colors ─── */
const TYPE_COLORS: Record<string, string> = {
  Company: '#3B82F6', Account: '#8B5CF6', FinancialPeriod: '#14B8A6',
  FinancialStatement: '#10B981', KPI: '#F59E0B', RiskSignal: '#EF4444',
  Forecast: '#06B6D4', Action: '#EAB308', Benchmark: '#14B8A6',
  Standard: '#94A3B8',
};

const REL_COLORS: Record<string, string> = {
  has_kpi: '#F59E0B', derived_from_accounts: '#8B5CF6', triggered_by_kpi: '#EF4444',
  governed_by_standard: '#94A3B8', applies_to_accounts: '#94A3B8',
  triggers_risk: '#EF4444', benchmarked_by: '#14B8A6', benchmarks_kpi: '#14B8A6',
  belongs_to: '#3B82F6', part_of: '#14B8A6', generates: '#10B981',
  monitors: '#06B6D4', impacts: '#EAB308', has_periods: '#14B8A6',
};

const nodeTypes = {
  tech: TechNode,
  global: GlobalNode,
};

const edgeTypes = {
  dataStream: DataStreamEdge,
};

interface ObjectGraphProps {
  seedObjectId: string;
  seedType: string;
  onNavigate?: (objectId: string) => void;
}

export default function ObjectGraph({ seedObjectId, seedType, onNavigate }: ObjectGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [viewMode, setViewMode] = useState<'local' | 'global'>('local');
  const [loading, setLoading] = useState(false);
  
  const { object: centerObject, isLoading: centerLoading } = useObject(seedObjectId);

  // Layout helper: Simple radial layout for local, cluster layout for global
  const layoutNodes = useCallback((nodesToLayout: Node[], edgesToLayout: Edge[], mode: 'local' | 'global') => {
    if (mode === 'local') {
      const centerX = 400;
      const centerY = 300;
      const radius = 250;
      
      return nodesToLayout.map((node, i) => {
        if (node.id === seedObjectId) return { ...node, position: { x: centerX, y: centerY } };
        
        const angle = (2 * Math.PI * (i - 1)) / (nodesToLayout.length - 1) - Math.PI / 2;
        return {
          ...node,
          position: {
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle),
          }
        };
      });
    } else {
      // Global mode: Cluster by type
      const types = Object.keys(TYPE_COLORS);
      const centerX = 1000;
      const centerY = 1000;
      const typeRadius = 800;
      
      const typePositions: Record<string, { x: number, y: number }> = {};
      types.forEach((t, i) => {
        const angle = (2 * Math.PI * i) / types.length;
        typePositions[t] = {
          x: centerX + typeRadius * Math.cos(angle),
          y: centerY + typeRadius * Math.sin(angle),
        };
      });

      const typeCounts: Record<string, number> = {};

      return nodesToLayout.map((node) => {
        const type = node.data.type as string;
        const basePos = typePositions[type] || { x: centerX, y: centerY };
        const count = typeCounts[type] || 0;
        typeCounts[type] = count + 1;
        
        const innerAngle = (count * 0.5); // Spiral/randomish spread
        const innerRadius = 20 * Math.sqrt(count);
        
        return {
          ...node,
          position: {
            x: basePos.x + innerRadius * Math.cos(innerAngle),
            y: basePos.y + innerRadius * Math.sin(innerAngle),
          }
        };
      });
    }
  }, [seedObjectId]);

  const fetchGraphData = useCallback(async (mode: 'local' | 'global') => {
    setLoading(true);
    try {
      const endpoint = mode === 'local' 
        ? `/api/ontology/objects/${encodeURIComponent(seedObjectId)}/related`
        : `/api/ontology/stats`; // In a real app, global might fetch a summary or all nodes
      
      const res = await fetch(endpoint);
      const data = await res.json();
      
      const newNodes: Node[] = [];
      const newEdges: Edge[] = [];

      if (mode === 'local') {
        const props = (centerObject?.properties || {}) as any;
        // Add center node
        newNodes.push({
          id: seedObjectId,
          type: 'tech',
          data: { 
            label: props.name_en || props.code || seedObjectId,
            type: seedType,
            keyValue: props.value ?? props.amount ?? null,
          },
          position: { x: 0, y: 0 },
        });

        const related = data.related || data.relationships || {};
        Object.entries(related).forEach(([relName, items]) => {
          const arr = items as any[];
          arr.slice(0, 15).forEach((item) => {
            const nodeId = item.id || item.object_id;
            const nodeType = item.type || item.object_type || 'Unknown';
            
            newNodes.push({
              id: nodeId,
              type: 'tech',
              data: {
                label: item.display_name || item.name || nodeId,
                type: nodeType,
                keyValue: item.value ?? item.amount ?? null,
              },
              position: { x: 0, y: 0 },
            });

            newEdges.push({
              id: `edge-${seedObjectId}-${nodeId}`,
              source: seedObjectId,
              target: nodeId,
              type: 'dataStream',
              data: { color: REL_COLORS[relName] || 'var(--b3)', label: relName },
              markerEnd: { type: MarkerType.ArrowClosed, color: REL_COLORS[relName] || 'var(--b3)' },
            });
          });
        });
      } else {
        // Global Mode Simulation (Thousands of nodes)
        // Since we don't have a "get all nodes" endpoint that's fast, we simulate the structure
        const types = Object.keys(TYPE_COLORS);
        for (let i = 0; i < 1500; i++) {
          const type = types[i % types.length];
          const id = `global-${i}`;
          newNodes.push({
            id,
            type: 'global',
            data: { type, color: TYPE_COLORS[type] },
            position: { x: 0, y: 0 },
          });
          
          if (i > 0 && Math.random() > 0.7) {
            newEdges.push({
              id: `edge-global-${i}`,
              source: `global-${Math.floor(Math.random() * i)}`,
              target: id,
              type: 'default',
              style: { stroke: TYPE_COLORS[type], opacity: 0.1, strokeWidth: 0.5 },
            });
          }
        }
      }

      const positionedNodes = layoutNodes(newNodes, newEdges, mode);
      setNodes(positionedNodes);
      setEdges(newEdges);
    } catch (err) {
      console.error('Failed to fetch graph data:', err);
    } finally {
      setLoading(false);
    }
  }, [seedObjectId, seedType, centerObject, layoutNodes, setNodes, setEdges]);

  useEffect(() => {
    if (centerObject || viewMode === 'global') {
      fetchGraphData(viewMode);
    }
  }, [centerObject, viewMode, fetchGraphData]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const toggleView = () => setViewMode(v => v === 'local' ? 'global' : 'local');

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: 'var(--bg0)' }}>
      {/* Scanline Mount Sequence Overlay */}
      <div className="scanline-mount" />

      {(loading || centerLoading) && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, background: 'rgba(8,11,20,0.4)', backdropFilter: 'blur(4px)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Loader2 size={32} className="spin" style={{ color: 'var(--sky)' }} />
            <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', textTransform: 'uppercase', letterSpacing: 2 }}>
              INITIALIZING_MATRIX_STREAM...
            </div>
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={(_, node) => node.type === 'tech' && onNavigate?.(node.id)}
        onNodeDoubleClick={(_, node) => {
           if (viewMode === 'global') {
             onNavigate?.(node.id);
             setViewMode('local');
           }
        }}
        fitView
        className={viewMode === 'global' ? 'matrix-grid' : ''}
      >
        <Background color="var(--b1)" gap={20} />
        <Controls />
        <MiniMap 
          nodeColor={(n) => (n.data?.color as string) || 'var(--sky)'} 
          maskColor="rgba(8, 11, 20, 0.7)"
          style={{ background: 'var(--bg1)', border: '1px solid var(--b2)' }}
        />
        
        {/* Floating Panel for View Switcher */}
        <Panel position="top-right">
          <div className="industrial-panel" style={{ padding: 4, display: 'flex', gap: 4 }}>
            <button
              onClick={() => setViewMode('local')}
              className={`btn-minimal ${viewMode === 'local' ? 'active-premium' : ''}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
                fontSize: 10, fontFamily: 'var(--mono)',
                color: viewMode === 'local' ? 'var(--sky)' : 'var(--muted)'
              }}
            >
              <Network size={12} /> LOCAL_EXPLORER
            </button>
            <button
              onClick={() => setViewMode('global')}
              className={`btn-minimal ${viewMode === 'global' ? 'active-premium' : ''}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
                fontSize: 10, fontFamily: 'var(--mono)',
                color: viewMode === 'global' ? 'var(--sky)' : 'var(--muted)'
              }}
            >
              <LayoutGrid size={12} /> GLOBAL_MATRIX
            </button>
          </div>
        </Panel>

        {/* Tactical Overlay */}
        <Panel position="bottom-left">
           <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', opacity: 0.6, letterSpacing: 1 }}>
              COORD_SCAN: {nodes.length} UNITS_SYNCED | STREAM_STATUS: NOMINAL
           </div>
        </Panel>
      </ReactFlow>

      <style>{`
        .active-premium {
          background: rgba(0, 242, 255, 0.05) !important;
          border: 1px solid var(--sky) !important;
        }
        .btn-minimal {
          border: 1px solid transparent;
          border-radius: 2px;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .btn-minimal:hover {
          background: rgba(255,255,255,0.03);
          color: var(--heading) !important;
        }
        .react-flow__controls-button {
          background: var(--bg2) !important;
          border-bottom: 1px solid var(--b1) !important;
          fill: var(--muted) !important;
        }
        .react-flow__controls-button:hover {
          background: var(--bg3) !important;
          fill: var(--sky) !important;
        }
      `}</style>
    </div>
  );
}
