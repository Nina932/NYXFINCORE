import React, { useState, useEffect, useCallback } from 'react';
import { 
  ReactFlow, 
  Background, 
  Controls, 
  MiniMap, 
  useNodesState, 
  useEdgesState, 
  addEdge,
  Handle,
  Position,
  type NodeProps,
  type Edge,
  type Connection
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  GitBranch, Users, Shield, TrendingUp, 
  ArrowRight, Activity, Zap, Info, Loader2,
  Building2, MapPin, Target
} from 'lucide-react';
import { TechnicalStatsGrid, TechnicalStat, MetricSlider } from '../components/PalantirWidgets';
import { useStore } from '../store/useStore';
import { fmtCompact } from '../utils/formatters';

/* ─── Custom Node Components ─── */

const EntityNode = ({ data, selected }: NodeProps) => {
  return (
    <div className={`command-panel p-0 overflow-hidden min-w-[200px] transition-all ${selected ? 'border-sky shadow-glow scale-105' : 'border-b1'}`}>
      <div className="flex items-center gap-3 p-3 bg-bg2/50 border-b border-b1">
        <div className={`p-2 rounded ${selected ? 'bg-sky/20 text-sky' : 'bg-bg3 text-dim'}`}>
           <Building2 size={16} />
        </div>
        <div className="flex-1">
          <div className="text-[11px] font-black text-heading uppercase tracking-tighter">{data.label as string}</div>
          <div className="text-[8px] text-dim font-mono">{data.type as string || 'SUBSIDIARY'}</div>
        </div>
        <div className="text-right">
           <div className={`text-[10px] font-bold ${Number(data.health) > 80 ? 'text-emerald' : 'text-amber'}`}>{data.health as string}%</div>
        </div>
      </div>
      <div className="p-3 bg-bg1">
         <div className="grid grid-cols-2 gap-2 mb-3">
            <div>
               <div className="text-[8px] text-dim uppercase">Revenue</div>
               <div className="text-[10px] font-mono text-sky">{data.revenue as string}</div>
            </div>
            <div className="text-right">
               <div className="text-[8px] text-dim uppercase">Control</div>
               <div className="text-[10px] font-mono text-muted">{data.control as string}%</div>
            </div>
         </div>
         <div className="flex items-center gap-2 text-[8px] text-muted">
            <MapPin size={8} /> {data.location as string || 'GEORGIA'}
         </div>
      </div>
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-sky" />
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-sky" />
    </div>
  );
};

const ParentNode = ({ data, selected }: NodeProps) => {
  return (
    <div className={`command-panel p-5 border-2 ${selected ? 'border-sky shadow-glow' : 'border-sky/40'} bg-sky/5 min-w-[240px] flex flex-col items-center`}>
       <NyxLogo size={40} className="mb-3" />
       <div className="text-sm font-black text-heading uppercase tracking-widest">{data.label as string}</div>
       <div className="text-[9px] text-sky font-mono mt-1">PRIMARY_ENTITY_ROOT</div>
       
       <div className="mt-4 w-full grid grid-cols-3 gap-2 text-center text-[9px] font-mono">
          <div className="p-1 bg-bg2 border border-b1">
             <div className="text-dim">SUBS</div>
             <div className="text-sky">12</div>
          </div>
          <div className="p-1 bg-bg2 border border-b1">
             <div className="text-dim">NODES</div>
             <div className="text-sky">48</div>
          </div>
          <div className="p-1 bg-bg2 border border-b1">
             <div className="text-dim">HEALTH</div>
             <div className="text-emerald">98%</div>
          </div>
       </div>
       <Handle type="source" position={Position.Bottom} className="w-3 h-3 !bg-sky" />
    </div>
  );
};

const nodeTypes = {
  entity: EntityNode,
  parent: ParentNode
};

function NyxLogo({ size, className }: { size: number; className?: string }) {
  return <Building2 size={size} className={className} />;
}

/* ─── Main Page ─── */

export default function StructurePage() {
  const { company, balance_sheet } = useStore();
  const [loading, setLoading] = useState(true);

  const initialNodes = [
    { id: 'root', type: 'parent', position: { x: 400, y: 0 }, data: { label: 'NYX CORE THINKER HOLDINGS' } },
    { id: 'sub-1', type: 'entity', position: { x: 100, y: 250 }, data: { label: 'PETROLEUM_LOGISTICS', revenue: '₾82M', control: 100, health: 94, location: 'BATUMI' } },
    { id: 'sub-2', type: 'entity', position: { x: 400, y: 250 }, data: { label: 'RETAIL_OPERATIONS', revenue: '₾145M', control: 100, health: 88, location: 'TBILISI' } },
    { id: 'sub-3', type: 'entity', position: { x: 700, y: 250 }, data: { label: 'ENERGY_TRADING_EU', revenue: '€42M', control: 85, health: 92, location: 'VIENNA' } },
    { id: 'bu-1', type: 'entity', position: { x: 50, y: 450 }, data: { label: 'FLEET_MGMT', type: 'UNIT', revenue: '₾12M', control: 100, health: 91, location: 'BATUMI' } },
    { id: 'bu-2', type: 'entity', position: { x: 250, y: 450 }, data: { label: 'MARINE_TERMINAL', type: 'UNIT', revenue: '₾24M', control: 51, health: 76, location: 'POTI' } },
  ];

  const initialEdges: Edge[] = [
    { id: 'e1', source: 'root', target: 'sub-1', animated: true, style: { stroke: 'var(--sky)', strokeWidth: 2 } },
    { id: 'e2', source: 'root', target: 'sub-2', animated: true, style: { stroke: 'var(--sky)', strokeWidth: 2 } },
    { id: 'e3', source: 'root', target: 'sub-3', animated: true, style: { stroke: 'var(--sky)', strokeWidth: 2 } },
    { id: 'e4', source: 'sub-1', target: 'bu-1', style: { stroke: 'var(--b2)' } },
    { id: 'e5', source: 'sub-1', target: 'bu-2', style: { stroke: 'var(--b2)' } },
  ];

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

  const totalEquity = balance_sheet?.total_equity || 0;
  const totalAssets = balance_sheet?.total_assets || 0;
  const leverage = totalAssets > 0 ? (balance_sheet?.total_liabilities || 0) / totalAssets : 0;

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div className="scanline" />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--sky)' }} />
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2 }}>ORCHESTRATING_STRUCTURAL_HIERARCHY...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, animation: 'slide-up 0.4s ease both', padding: '0 4px', position: 'relative', height: 'calc(100vh - 120px)' }}>
      <div className="scanline" />
      
      {/* ══════ HEADER ══════ */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--b1)', paddingBottom: 16, flexShrink: 0 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, letterSpacing: -0.5 }}>
            <GitBranch size={22} style={{ color: 'var(--sky)' }} />
            ENTITY_RELATIONSHIP_GRAPH
          </h1>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', opacity: 0.8 }}>
            ONTOLOGY_CLUSTER: {typeof company === 'string' ? company : 'NYX_GLOBAL'} | NODES: {nodes.length} | RELATIONS: {edges.length}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
           <button className="btn btn-primary-outline text-[10px]"><Users size={12} /> Manage Stakeholders</button>
           <button className="btn btn-primary text-[10px]"><Zap size={12} /> Sync Hierarchy</button>
        </div>
      </div>

      {/* ══════ ROW 1: KEY METRICS ══════ */}
      <div style={{ flexShrink: 0 }}>
        <TechnicalStatsGrid>
          <TechnicalStat 
            label="CONSOLIDATED_EQUITY" 
            value={fmtCompact(totalEquity)} 
            subValue="CAPITAL_BASE"
            progress={82}
            status="VERIFIED"
          />
          <TechnicalStat 
            label="GROUP_LEVERAGE" 
            value={`${(leverage * 100).toFixed(1)}%`} 
            subValue="GEARING_RATIO"
            progress={leverage * 100}
            color="var(--emerald)"
            status="OPTIMAL"
          />
          <TechnicalStat 
            label="CONTROL_NODES" 
            value={String(nodes.length)} 
            subValue="GRAPH_DENSITY"
            progress={45}
            color="var(--sky)"
            status="SYNCED"
          />
          <TechnicalStat 
            label="AUDIT_SCORE" 
            value="98.4%" 
            subValue="DATA_LINEAGE"
            progress={98}
            color="var(--emerald)"
            status="SECURE"
          />
        </TechnicalStatsGrid>
      </div>

      {/* ══════ INTERACTIVE GRAPH AREA ══════ */}
      <div className="flex-1 command-panel relative overflow-hidden bg-black/40 border-b1" style={{ padding: 0 }}>
         <div className="absolute top-4 left-4 z-10 pointer-events-none">
            <div className="command-panel p-3 bg-bg1/90 border-sky/30 max-w-[280px]">
               <div className="text-[10px] font-bold text-sky flex items-center gap-2 mb-2">
                 <Shield size={12} /> STRUCTURAL_INTEGRITY_CHECK
               </div>
               <div className="text-[10px] text-text leading-relaxed font-mono">
                  ACTIVE_RELATIONS: <span className="text-emerald">VERIFIED</span><br/>
                  OWNERSHIP_OVERLAP: <span className="text-amber">DETECTED_L3</span><br/>
                  CONTROL_FLOW: <span className="text-sky">HIERARCHICAL</span>
               </div>
            </div>
         </div>

         <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          colorMode="dark"
        >
          <Background color="var(--b2)" gap={24} size={1} />
          <Controls className="bg-bg1 border border-b1 fill-sky" />
          <MiniMap 
            nodeColor={(n) => n.type === 'parent' ? 'var(--sky)' : 'var(--b2)'}
            maskColor="rgba(0,0,0,0.6)"
            className="bg-bg2 border border-b1"
          />
        </ReactFlow>

        <div className="absolute bottom-4 right-4 z-10 command-panel p-3 flex gap-6 text-[9px] font-bold uppercase tracking-widest backdrop-blur-md font-mono">
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-sky" />
              <span>Parent Entity</span>
           </div>
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-bg3 border border-b2" />
              <span>Child Entity</span>
           </div>
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-emerald" />
              <span>High Health</span>
           </div>
        </div>
      </div>

      {/* ══════ BOTTOM SLIDERS ══════ */}
      <div className="glass p-5 border-t border-b1" style={{ flexShrink: 0 }}>
         <div className="grid grid-cols-3 gap-12">
            <MetricSlider label="Capital_Mobility" value={85} statusLabel="PRISTINE" statusColor="var(--emerald)" />
            <MetricSlider label="IntraGroup_Risk" value={32} statusLabel="NOMINAL" statusColor="var(--sky)" />
            <MetricSlider label="Governance_Gaps" value={12} statusLabel="MINIMAL" statusColor="var(--emerald)" />
         </div>
      </div>

    </div>
  );
}
