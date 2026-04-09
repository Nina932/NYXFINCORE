import React, { useState } from 'react';
import { Terminal, Shield, Target, Info, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface BriefingProps {
  viewMode: 'graph' | 'list' | 'analytics' | 'welcome';
  selectedType?: string | null;
  selectedObject?: any | null;
}

const BRIEFING_DATA: Record<string, { title: string; subtitle: string; content: string; icon: any; color: string }> = {
  welcome: {
    title: 'COLD_START_READY',
    subtitle: 'INTELLIGENCE_MATRIX_V4.2',
    content: 'The Intelligence Matrix is a multi-dimensional semantic layer. It connects your raw financial accounts to high-level KPIs and Risk Signals. Select a domain below to begin discovery.',
    icon: Terminal,
    color: 'var(--sky)'
  },
  graph: {
    title: 'SPATIAL_INTELLIGENCE_ACTIVE',
    subtitle: 'KNOWLEDGE_GRAPH_EXPLORER',
    content: 'Navigating causal relationships. The animated streams (DataStreamEdges) show directed influence. Double-click any node to pivot the entire matrix around that entity.',
    icon: Zap,
    color: 'var(--sky)'
  },
  list: {
    title: 'REGISTRY_INTEGRITY_AUDIT',
    subtitle: 'TABULAR_LINEAGE_VIEW',
    content: 'Auditing flat entities. This view ensures structural consistency and strict property governance. Every object here is backed by an immutable ledger entry.',
    icon: Shield,
    color: 'var(--emerald)'
  },
  analytics: {
    title: 'STRATEGIC_SIMULATION',
    subtitle: 'STRUCTURAL_HEALTH_ANALYTICS',
    content: 'Evaluating global graph metrics. This mode simulates market shocks and identifies systemic bottlenecks where small variances could cause major KPI breaches.',
    icon: Target,
    color: 'var(--amber)'
  }
};

export default function ContextualBriefing({ viewMode, selectedType, selectedObject }: BriefingProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  // Decide which briefing to show
  let mode: string = viewMode;
  if (viewMode === 'list' && !selectedType) mode = 'welcome';
  
  const config = BRIEFING_DATA[mode] || BRIEFING_DATA.welcome;
  const Icon = config.icon;

  return (
    <motion.div 
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="industrial-panel"
      style={{
        position: 'fixed',
        bottom: 24,
        left: 304, // Offset from sidebar (280 + padding)
        width: 320,
        zIndex: 100,
        background: 'rgba(5, 8, 18, 0.8)',
        backdropFilter: 'blur(10px)',
        border: '1px solid var(--b2)',
        padding: 0,
        overflow: 'hidden',
        pointerEvents: 'auto'
      }}
    >
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        style={{ 
          padding: '10px 14px', 
          background: 'rgba(0, 242, 255, 0.03)', 
          borderBottom: isExpanded ? '1px solid var(--b1)' : 'none',
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          cursor: 'pointer'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon size={14} style={{ color: config.color }} />
          <span style={{ fontSize: 10, fontWeight: 900, color: 'var(--heading)', letterSpacing: 1, fontFamily: 'var(--mono)' }}>
            STRATEGIC_BRIEFING
          </span>
        </div>
        <div>
          {isExpanded ? <ChevronDown size={14} style={{ color: 'var(--dim)' }} /> : <ChevronUp size={14} style={{ color: 'var(--dim)' }} />}
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            style={{ padding: '16px', overflow: 'hidden' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <div className="pixel-node" style={{ width: 4, height: 4, background: config.color }} />
              <div style={{ fontSize: 11, fontWeight: 900, color: 'var(--heading)' }}>{config.title}</div>
            </div>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: config.color, marginBottom: 12, opacity: 0.8 }}>
              {config.subtitle}
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
              {config.content}
            </p>
            
            {selectedType && (
              <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px dashed var(--b1)' }}>
                <div style={{ fontSize: 8, color: 'var(--dim)', fontWeight: 900, marginBottom: 6 }}>ACTIVE_TARGET_DOMAIN:</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ padding: '2px 8px', background: 'var(--bg2)', border: '1px solid var(--b1)', color: config.color, fontSize: 10, fontWeight: 800 }}>
                    {selectedType.toUpperCase()}
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div style={{ height: 2, background: `linear-gradient(90deg, transparent, ${config.color}, transparent)`, opacity: 0.3 }} />
    </motion.div>
  );
}
