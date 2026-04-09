import React, { useState, useCallback } from 'react';
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
  Database, Zap, Layers, FileText, 
  GitBranch, Search, Shield, Activity, 
  ArrowRight, Info
} from 'lucide-react';

/* ─── Custom Node Components ─── */

const PipelineNode = ({ data, selected }: NodeProps) => {
  const Icon = data.icon as React.ElementType;
  return (
    <div className={`command-panel p-0 overflow-hidden min-w-[180px] ${selected ? 'border-sky shadow-glow' : 'border-b1'}`}>
      <div className="flex items-center gap-3 p-3 bg-bg2/50 border-b border-b1">
        <div className={`p-1.5 rounded-md ${selected ? 'bg-sky/20 text-sky' : 'bg-bg3 text-dim'}`}>
          <Icon size={14} />
        </div>
        <div className="flex-1">
          <div className="text-[10px] font-bold text-heading uppercase tracking-widest">{data.label as string}</div>
          <div className="text-[8px] text-dim font-mono uppercase">{data.status as string || 'CONNECTED'}</div>
        </div>
        {data.health !== undefined && (
          <div className={`w-1.5 h-1.5 rounded-full ${Number(data.health) > 90 ? 'bg-emerald' : 'bg-amber'} animate-pulse`} />
        )}
      </div>
      <div className="p-3 bg-bg1">
        <div className="text-[9px] text-muted leading-tight">{data.description as string}</div>
        <div className="mt-2 flex justify-between items-center text-[8px] font-mono text-dim">
           <span>DEPTH: {data.depth as string || '0.4s'}</span>
           <span className="text-sky">{data.records as string || '---'} REC</span>
        </div>
      </div>
      
      <Handle type="target" position={Position.Left} className="w-2 h-2 !bg-sky" />
      <Handle type="source" position={Position.Right} className="w-2 h-2 !bg-sky" />
    </div>
  );
};

const DataSourceNode = ({ data, selected }: NodeProps) => {
  return (
    <div className={`command-panel p-3 border-dashed ${selected ? 'border-sky shadow-glow' : 'border-b2'} bg-bg2/20 flex flex-col items-center justify-center min-w-[120px]`}>
       <Database size={20} className="text-dim mb-2" />
       <div className="text-[9px] font-bold text-dim uppercase tracking-wider">{data.label as string}</div>
       <div className="text-[8px] text-muted font-mono mt-1">{data.format as string || 'JSON/CSV'}</div>
       <Handle type="source" position={Position.Right} className="w-2 h-2 !bg-dim" />
    </div>
  );
};

const StatementNode = ({ data, selected }: NodeProps) => {
  return (
    <div className={`command-panel p-4 border-emerald ${selected ? 'border-emerald shadow-glow' : 'border-emerald/40'} bg-emerald/5 min-w-[200px]`}>
       <div className="flex items-center gap-2 mb-3">
          <FileText size={16} className="text-emerald" />
          <div className="text-[11px] font-black text-emerald uppercase tracking-widest">Financial Statement</div>
       </div>
       <div className="text-xs font-bold text-heading mb-1">{data.label as string}</div>
       <div className="text-[10px] text-muted italic">"Final IFRS output for group audit"</div>
       <div className="mt-4 flex flex-col gap-1">
          <div className="grid grid-2 text-[9px] font-mono">
             <span className="text-dim">INTEGRITY:</span>
             <span className="text-emerald text-right">99.9%</span>
          </div>
          <div className="grid grid-2 text-[9px] font-mono">
             <span className="text-dim">LINEAGE:</span>
             <span className="text-emerald text-right">VERIFIED</span>
          </div>
       </div>
       <Handle type="target" position={Position.Left} className="w-2 h-2 !bg-emerald" />
    </div>
  );
};

const nodeTypes = {
  pipeline: PipelineNode,
  source: DataSourceNode,
  statement: StatementNode
};

/* ─── Page Component ─── */

export default function DataLineagePage() {
  const initialNodes = [
    { 
      id: 'src-1', type: 'source', position: { x: 50, y: 150 }, 
      data: { label: 'ERP_RAW_FEED', format: 'SAP_S4HANA' } 
    },
    { 
      id: 'src-2', type: 'source', position: { x: 50, y: 300 }, 
      data: { label: 'SUBSIDIARY_EXPORT', format: 'EXCEL_XL' } 
    },
    { 
      id: 'pipe-ap', type: 'pipeline', position: { x: 250, y: 100 }, 
      data: { 
        label: 'AP_AUTOMATION', icon: Zap, status: 'PROCESSING', 
        description: '3-way match engine validating invoices vs PO/GRN.',
        health: 98, records: '1.2K'
      } 
    },
    { 
      id: 'pipe-class', type: 'pipeline', position: { x: 500, y: 200 }, 
      data: { 
        label: 'COA_CLASSIFIER', icon: Search, status: 'SYNCED', 
        description: 'Auto-mapping raw GL entries to group ontology.',
        health: 94, records: '4.8K'
      } 
    },
    { 
      id: 'pipe-cons', type: 'pipeline', position: { x: 750, y: 200 }, 
      data: { 
        label: 'CONSOLIDATION', icon: Layers, status: 'IDLE', 
        description: 'IFRS 10 multi-entity elimination and roll-up.',
        health: 100, records: '12 Subs'
      } 
    },
    { 
      id: 'final-pl', type: 'statement', position: { x: 1050, y: 200 }, 
      data: { label: 'Consolidated Income Statement' } 
    }
  ];

  const initialEdges: Edge[] = [
    { id: 'e1', source: 'src-1', target: 'pipe-ap', animated: true, style: { stroke: 'var(--sky)' } },
    { id: 'e2', source: 'src-1', target: 'pipe-class', style: { stroke: 'var(--b2)' } },
    { id: 'e3', source: 'src-2', target: 'pipe-class', animated: true, style: { stroke: 'var(--sky)' } },
    { id: 'e4', source: 'pipe-ap', target: 'pipe-class', animated: true, style: { stroke: 'var(--sky)' } },
    { id: 'e5', source: 'pipe-class', target: 'pipe-cons', animated: true, style: { stroke: 'var(--sky)' } },
    { id: 'e6', source: 'pipe-cons', target: 'final-pl', animated: true, style: { stroke: 'var(--emerald)' } },
  ];

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div className="page-enter flex flex-col h-[calc(100vh-140px)] space-y-6">
      {/* Header */}
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GitBranch className="text-sky" /> Operational Data Lineage
          </h1>
          <p className="text-xs text-muted font-mono uppercase tracking-widest mt-1">
            End-to-End Financial Traceability & Provenance
          </p>
        </div>
        <div className="flex gap-2">
          <div className="command-panel py-1.5 px-4 bg-bg2 flex items-center gap-4">
             <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald animate-pulse" />
                <span className="text-[10px] font-bold text-emerald">LIVE_SYNC</span>
             </div>
             <div className="h-4 w-px bg-b2" />
             <div className="text-[10px] text-muted font-mono uppercase">Nodes: {nodes.length} | Edges: {edges.length}</div>
          </div>
          <button className="btn btn-primary"><Activity size={14} /> Run Validation Trace</button>
        </div>
      </header>

      {/* Main Graph Area */}
      <div className="flex-1 command-panel relative overflow-hidden bg-black/50 p-0 border-b1">
        <div className="absolute top-4 left-4 z-10 space-y-2 pointer-events-none">
           <div className="command-panel p-3 bg-bg1/90 backdrop-blur-md border-sky/30 max-w-[240px]">
              <div className="text-[10px] font-bold text-sky flex items-center gap-2 mb-2">
                <Shield size={12} /> PROVENANCE_GUARD_ACTIVE
              </div>
              <div className="text-[10px] text-text leading-relaxed">
                 "All financial artifacts in the current workspace are linked to 
                 auditable ERP source identifiers with <span className="text-emerald">zero variance</span> detected."
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
          colorMode={document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'}
        >
          <Background color="var(--b2)" gap={24} size={1} />
          <Controls className="bg-bg1 border border-b1 fill-sky" />
          <MiniMap 
            nodeColor={(n) => n.type === 'statement' ? 'var(--emerald)' : 'var(--sky)'}
            maskColor="rgba(0,0,0,0.4)"
            className="bg-bg2 border border-b1"
          />
        </ReactFlow>

        {/* Legend Overlay */}
        <div className="absolute bottom-4 right-4 z-10 command-panel p-3 flex gap-6 text-[9px] font-bold uppercase tracking-tighter backdrop-blur-md">
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 border border-dashed border-dim" />
              <span className="text-dim">Source Artifact</span>
           </div>
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-sky/30 border border-sky/60" />
              <span className="text-sky">Process Unit</span>
           </div>
           <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-emerald/30 border border-emerald/60" />
              <span className="text-emerald">Statement Output</span>
           </div>
        </div>
      </div>

      {/* Bottom Insights */}
      <div className="grid grid-3 gap-6">
        <div className="command-panel p-4">
           <div className="flex items-center gap-2 mb-3">
              <Info size={14} className="text-sky" />
              <span className="text-[10px] font-bold uppercase">Lineage Depth Analysis</span>
           </div>
           <div className="text-[10px] text-muted">
              Traceability depth of <span className="text-heading font-bold">4.2 levels</span> achieved. 
              Sub-ledger transparency is 100% for AP and 82% for general expenses.
           </div>
        </div>
        <div className="command-panel p-4">
           <div className="flex items-center gap-2 mb-3">
              <Shield size={14} className="text-emerald" />
              <span className="text-[10px] font-bold uppercase">Audit Readiness</span>
           </div>
           <div className="text-[10px] text-muted">
              Certificate generated for <span className="text-emerald font-bold">FY2026_CLOSE</span>. 
              Hash-chain verified by Ontology write-guard.
           </div>
        </div>
        <div className="command-panel p-4 flex items-center justify-between">
           <div>
              <div className="text-[10px] font-bold uppercase mb-1">Trace Latency</div>
              <div className="text-lg font-mono text-heading">42ms</div>
           </div>
           <button className="btn-minimal">Recalculate Mesh</button>
        </div>
      </div>
    </div>
  );
}
