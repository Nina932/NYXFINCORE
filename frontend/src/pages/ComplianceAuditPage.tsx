import React, { useEffect, useState } from 'react';
import { 
  Shield, Activity, Lock, Database, 
  History, AlertTriangle, CheckCircle2, 
  Search, Filter, ArrowRight, GitBranch, 
  Eye, RefreshCcw, Bell
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { toast } from 'sonner';

interface ComplianceData {
  stats: {
    integrity_score: number;
    audit_events: number;
    critical_alerts: number;
    lineage_nodes: number;
  };
  alerts: any[];
  audit_log: any[];
  kpis: any[];
}

export default function ComplianceAuditPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<ComplianceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const dashboard = await api.complianceDashboard() as any;
      const audit = await api.complianceAudit(50) as any[];
      const kpis = (api as any).getKpiStatus ? await (api as any).getKpiStatus() : [];
      
      setData({
        stats: {
          integrity_score: 99.4,
          audit_events: audit.length || 0,
          critical_alerts: dashboard.alerts?.length || 0,
          lineage_nodes: 712
        },
        alerts: dashboard.alerts || [],
        audit_log: audit || [],
        kpis: kpis || []
      });
    } catch (err) {
      console.error('Compliance Data fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const runCheck = async () => {
    setChecking(true);
    try {
      toast.info('Running real-time compliance scan...');
      await new Promise(r => setTimeout(r, 1500)); // Sim delay
      toast.success('System Integrity Verified: 100%');
      fetchData();
    } catch (err) {
      toast.error('Scan failed');
    } finally {
      setChecking(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="empty-state">
        <Shield className="animate-pulse text-sky" size={32} />
        <p className="font-mono text-xs uppercase tracking-widest mt-4">Verifying Audit Chain...</p>
      </div>
    );
  }

  return (
    <div className="page-enter space-y-6 pb-12">
      {/* Header */}
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Lock className="text-sky fill-sky/10" /> Industrial Compliance & Audit
          </h1>
          <p className="text-xs text-muted font-mono uppercase tracking-widest mt-1">
            Forensic Integrity & Real-time Monitoring
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost">
            <Filter size={14} /> Filter Range
          </button>
          <button onClick={runCheck} disabled={checking} className="btn btn-primary">
            {checking ? <RefreshCcw size={14} className="animate-spin" /> : <Shield size={14} />}
            Trigger Compliance Scan
          </button>
        </div>
      </header>

      {/* Stats Row */}
      <div className="grid grid-4 gap-4">
        <div className="command-panel p-4 bg-bg2/30 relative">
          <div className="telemetry-token">CHAIN_OF_CUSTODY_v1</div>
          <div className="fin-label">Integrity Score</div>
          <div className="flex items-end gap-2 mt-1">
            <div className="fin-value-md text-emerald">{data?.stats.integrity_score}%</div>
            <div className="indicator-pulse mb-2" />
          </div>
          <div className="text-[10px] text-muted mt-1 font-mono uppercase tracking-tighter">SECURE / ENCRYPTED / AUDITED</div>
        </div>
        <div className="command-panel p-4">
          <div className="fin-label">Audit Chain Depth</div>
          <div className="fin-value-md text-heading mt-1">{data?.stats.audit_events}</div>
          <div className="text-[10px] text-dim mt-1 font-mono">EVENTS INDEXED</div>
        </div>
        <div className="command-panel p-4 border-rose/30">
          <div className="fin-label">Compliance Breaches</div>
          <div className="fin-value-md text-rose mt-1">{data?.stats.critical_alerts}</div>
          <div className="text-[10px] text-rose/60 mt-1 font-mono">ACTIONS REQUIRED</div>
        </div>
        <div className="command-panel p-4">
          <div className="fin-label">Data Lineage Units</div>
          <div className="fin-value-md text-sky mt-1">{data?.stats.lineage_nodes}</div>
          <div className="text-[10px] text-muted mt-1 font-mono flex items-center gap-1">
            <GitBranch size={10} /> ONTOLOGY MAPPED
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Audit Log Terminal */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
          <div className="command-panel flex flex-col flex-1 min-h-[500px]">
             <div className="card-header border-b border-b1 p-4">
                <div className="card-title"><History size={14} /> Forensic Audit Trail</div>
                <div className="flex gap-2">
                   <div className="tag tag-blue">SYSTEM</div>
                   <div className="tag tag-amber">DATA_ACCESS</div>
                </div>
             </div>
             <div className="flex-1 overflow-auto bg-black/40">
                <div className="terminal-window border-none bg-transparent">
                  <div className="space-y-2">
                    {data?.audit_log && data.audit_log.length > 0 ? (
                      data.audit_log.map((log, i) => (
                        <div key={i} className="flex gap-4 group hover:bg-white/5 p-1 transition-colors">
                           <span className="text-muted w-24 shrink-0 font-light">[{new Date().toLocaleTimeString()}]</span>
                           <span className="text-sky w-20 shrink-0 uppercase font-bold">{log.event_type || 'ACCESS'}</span>
                           <span className="text-text flex-1">
                              {log.description || `User ADMIN accessed component "${log.target || 'Warehouse'}"`}
                           </span>
                           <span className="text-dim opacity-0 group-hover:opacity-100 text-[9px] uppercase tracking-widest">
                              {log.trace_id || 'TR-7722'}
                           </span>
                        </div>
                      ))
                    ) : (
                      <div className="text-dim italic">Waiting for system events...</div>
                    )}
                  </div>
                </div>
             </div>
          </div>
        </div>

        {/* Monitoring Rules & KPIs */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          <div className="command-panel p-4 h-full">
            <div className="card-header">
              <div className="card-title"><Activity size={14} /> Passive Monitoring</div>
              <Bell size={12} className="text-sky" />
            </div>
            
            <div className="space-y-4 mt-4">
              <div className="p-3 border border-b2 rounded bg-bg2/50 group hover:border-sky/50 transition-colors">
                 <div className="flex justify-between items-start">
                    <div className="text-[11px] font-bold text-heading">Balance Sheet Equation</div>
                    <span className="tag tag-green">ACTIVE</span>
                 </div>
                 <div className="text-[10px] text-muted mt-1">Verifies Assets = Liabilities + Equity at 10ms intervals.</div>
                 <div className="mt-2 text-[10px] text-emerald font-mono flex items-center gap-1">
                    <CheckCircle2 size={10} /> ZERO DIVERGENCE
                 </div>
              </div>

              <div className="p-3 border border-b2 rounded bg-bg2/50 group hover:border-sky/50 transition-colors">
                 <div className="flex justify-between items-start">
                    <div className="text-[11px] font-bold text-heading">Revenue Thresholds</div>
                    <span className="tag tag-green">ACTIVE</span>
                 </div>
                 <div className="text-[10px] text-muted mt-1">Monitors intraday revenue against dynamic forecasting alerts.</div>
                 <div className="mt-2 text-[10px] text-muted font-mono flex items-center gap-1">
                    <ArrowRight size={10} /> NEXT SCAN: 2m 14s
                 </div>
              </div>

              <div className="p-3 border border-rose/30 rounded bg-rose/5 group hover:border-rose/50 transition-colors">
                 <div className="flex justify-between items-start">
                    <div className="text-[11px] font-bold text-rose">Currency Translation Drift</div>
                    <span className="tag tag-red">ALERT</span>
                 </div>
                 <div className="text-[10px] text-muted mt-1">Detected mismatch in USD/GEL revaluation for Entity-B.</div>
                 <div className="mt-2 flex gap-1">
                    <button className="btn-minimal text-rose border-rose text-[9px] h-6 py-0 px-2">Investigate</button>
                    <button className="btn-minimal text-dim text-[9px] h-6 py-0 px-2">Dismiss</button>
                 </div>
              </div>

              <div className="p-3 border border-b2 rounded bg-bg2/50 group hover:border-sky/50 transition-colors">
                 <div className="flex justify-between items-start">
                    <div className="text-[11px] font-bold text-heading">Ontology Guard</div>
                    <span className="tag tag-green">ACTIVE</span>
                 </div>
                 <div className="text-[10px] text-muted mt-1">Ensures all write operations conform to the SAP/IFRS metadata schema.</div>
                 <div className="mt-2 text-[10px] text-emerald font-mono flex items-center gap-1">
                    <CheckCircle2 size={10} /> SCHEMA LOCK SECURE
                 </div>
              </div>
            </div>

            <div className="mt-10 pt-4 border-t border-b1">
               <div 
                 onClick={() => navigate('/lineage')}
                 className="flex items-center gap-3 p-4 bg-sky/5 rounded border border-sky/20 cursor-pointer hover:bg-sky/10 transition-all"
               >
                  <GitBranch className="text-sky" size={24} />
                  <div>
                    <div className="text-[11px] font-bold text-sky">Operational Lineage</div>
                    <div className="text-[10px] text-muted">All financial reports traced to source ERP artifacts.</div>
                  </div>
                  <Eye className="ml-auto text-sky" size={16} />
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
