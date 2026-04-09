import React from 'react';
import { X, Network, Activity, Zap, HelpCircle, Shield, Target, Play } from 'lucide-react';

interface DiscoveryGuideProps {
  onClose: () => void;
}

export default function DiscoveryGuide({ onClose }: DiscoveryGuideProps) {
  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
      background: 'rgba(5, 8, 18, 0.95)', backdropFilter: 'blur(20px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      padding: 20
    }}>
      <div className="industrial-panel" style={{
        maxWidth: 900, width: '100%', background: 'var(--bg1)',
        border: '1px solid var(--b2)', position: 'relative',
        animation: 'mount-scan 0.5s ease-out',
        boxShadow: '0 0 50px rgba(0, 242, 255, 0.05)'
      }}>
        <div className="scanline-mount" style={{ height: 2, background: 'var(--sky)', opacity: 0.5 }} />

        {/* Header */}
        <div style={{
          padding: '24px 32px', borderBottom: '1px solid var(--b1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: 'rgba(0, 242, 255, 0.02)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ padding: 10, background: 'rgba(0, 242, 255, 0.1)', border: '1px solid rgba(0, 242, 255, 0.2)', borderRadius: 4 }}>
              <Shield size={22} style={{ color: 'var(--sky)' }} />
            </div>
            <div>
              <h2 style={{ fontSize: 20, fontWeight: 900, color: 'var(--heading)', letterSpacing: -0.5, margin: 0 }}>MISSION_BRIEFING: INTELLIGENCE_MATRIX_SHOWCASE</h2>
              <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', marginTop: 4 }}>SECURITY_CLEARANCE: ALPHA_01 | VER_4.2.0_STABLE</div>
            </div>
          </div>
          <button onClick={onClose} className="btn-minimal" style={{ border: 'none', background: 'none' }}>
            <X size={24} style={{ color: 'var(--muted)' }} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '40px', display: 'flex', flexDirection: 'column', gap: 40 }}>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr', gap: 40 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 900, color: 'var(--sky)', letterSpacing: 2, marginBottom: 16, fontFamily: 'var(--mono)' }}>[01] THE_SEMANTIC_LAYER</div>
              <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.7, margin: 0 }}>
                The Intelligence Matrix is not just a viewer—it is a <strong>Command & Control</strong> interface. 
                It maps low-level GL accounts to high-level strategic KPIs using a directed causal graph.
              </p>
              <div style={{ marginTop: 24, padding: '12px 16px', background: 'var(--bg2)', borderLeft: '3px solid var(--sky)' }}>
                 <div style={{ fontSize: 9, color: 'var(--sky)', fontWeight: 900, fontFamily: 'var(--mono)', marginBottom: 4 }}>SYSTEM_TIP:</div>
                 <div style={{ fontSize: 11, color: 'var(--dim)', fontStyle: 'italic' }}>Double-click any node to center the entire matrix on that entity.</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ padding: 20, background: 'var(--bg2)', border: '1px solid var(--b1)', position: 'relative' }}>
                   <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                     <Target size={16} style={{ color: 'var(--amber)' }} />
                     <span style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', letterSpacing: 1 }}>PRECISION_NODES</span>
                   </div>
                   <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6 }}>Companies, Accounts, and Metrics. Every node is an interactive operational object.</div>
                </div>
                <div style={{ padding: 20, background: 'var(--bg2)', border: '1px solid var(--b1)' }}>
                   <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                     <Network size={16} style={{ color: 'var(--sky)' }} />
                     <span style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', letterSpacing: 1 }}>CAUSAL_STREAMS</span>
                   </div>
                   <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6 }}>Animated links (DataStreamEdges) represent the direction of financial influence.</div>
                </div>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 10, fontWeight: 900, color: 'var(--emerald)', letterSpacing: 2, marginBottom: 20, fontFamily: 'var(--mono)' }}>[02] ACTIONABLE_INTELLIGENCE</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }}>
              <div style={{ background: 'rgba(16, 185, 129, 0.03)', padding: 24, border: '1px solid rgba(16, 185, 129, 0.1)' }}>
                 <div style={{ color: 'var(--emerald)', marginBottom: 12 }}><Play size={20} /></div>
                 <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 6 }}>DIRECT_EXECUTION</div>
                 <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.6 }}>Approve or Execute AI-generated tactical actions directly from the Detail Panel.</div>
              </div>
              <div style={{ background: 'rgba(0, 242, 255, 0.03)', padding: 24, border: '1px solid rgba(0, 242, 255, 0.1)' }}>
                 <div style={{ color: 'var(--sky)', marginBottom: 12 }}><Zap size={20} /></div>
                 <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 6 }}>QUICK_EDIT</div>
                 <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.6 }}>Click the "Edit" icon to modify metadata or statuses in real-time. Changes sync to the warehouse.</div>
              </div>
              <div style={{ background: 'rgba(234, 179, 8, 0.03)', padding: 24, border: '1px solid rgba(234, 179, 8, 0.1)' }}>
                 <div style={{ color: 'var(--amber)', marginBottom: 12 }}><Activity size={20} /></div>
                 <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 6 }}>SIMULATION_MODE</div>
                 <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.6 }}>Simulate KPI variances to visualize how a single revenue drop hits your cash reserves.</div>
              </div>
            </div>
          </div>

          <div style={{ padding: '24px 32px', background: 'var(--bg0)', border: '1px solid var(--b2)', display: 'flex', alignItems: 'center', gap: 20 }}>
            <div><Shield size={24} style={{ color: 'var(--sky)', opacity: 0.5 }} /></div>
            <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.7 }}>
               Look for the **"STRATEGIC_BRIEFING"** overlay in the bottom left. 
               It provides tactical context tailored to your current operation mode (Graph, List, or Analytics).
            </div>
          </div>

        </div>

        {/* Footer */}
        <div style={{
          padding: '24px 32px', borderTop: '1px solid var(--b1)', background: 'var(--bg0)',
          display: 'flex', justifyContent: 'flex-end', gap: 16, alignItems: 'center'
        }}>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 1 }}>SYSTEM_STATUS: NOMINAL</div>
          <button 
            onClick={onClose} 
            className="btn-minimal" 
            style={{ 
              background: 'var(--sky)', 
              color: 'var(--bg0)', 
              padding: '10px 32px', 
              fontSize: 12, 
              fontWeight: 900,
              border: 'none',
              boxShadow: '0 0 20px rgba(0, 242, 255, 0.2)'
            }}
          >
            INITIALIZE_MATRIX
          </button>
        </div>

      </div>
    </div>
  );
}
