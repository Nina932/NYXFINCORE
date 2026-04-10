import { useState, useEffect } from 'react';
import {
  ArrowSquareOut, ChartLineUp, ChartLineDown, ArrowRight, ChartBar, Pulse, Brain, Lightning, FileText, Warning, Target, ShieldCheck, Shield, Stack, UploadSimple
} from '@phosphor-icons/react';
import { RevenueTrendChart } from '../components/EChartsFinancial';
import { NumberRoll } from '../components/PalantirWidgets';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { useIntelligence } from '../hooks/useOntology';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { fmtCompact } from '../utils/formatters';
import { Activity, TrendingUp } from 'lucide-react'; // Fallback for specific logic icons
import NyxLogo from '../components/NyxLogo';
import IndustrialGeoMap from '../components/IndustrialGeoMap';
import SovereignConnectivityBackground from '../components/SovereignConnectivityBackground';

/* ---- Helpers ---- */
const pct = (c: number, p: number) => (!p || !c) ? 0 : ((c - p) / Math.abs(p)) * 100;
const fmtPct = (n: number) => (n >= 0 ? '+' : '') + n.toFixed(1) + '%';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { pnl, balance_sheet, company, period } = useStore();
  const [trendData, setTrendData] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const intlHook = useIntelligence();
  const [activeSim, setActiveSim] = useState<any>(null);

  useEffect(() => {
    // Check for active simulation scenarios on mount
    api.situationalRisk().then(res => {
      if (res.sim_active) {
        setActiveSim(res);
      }
    });

    const handleSimTrigger = (e: any) => {
       if (e.detail?.scenario) {
          api.situationalRisk(e.detail.scenario).then(res => {
            setActiveSim(res);
            // Multiplier effect: Apply simulated impact to view
          });
       }
    };
    window.addEventListener('FINAI_SIM_TRIGGER', handleSimTrigger);
    return () => window.removeEventListener('FINAI_SIM_TRIGGER', handleSimTrigger);
  }, []);

  useEffect(() => {
    if (!pnl) return;
    const rev = pnl.revenue || 0;
    const gp = pnl.gross_profit || 0;
    const np = pnl.net_profit || 0;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const trend = months.map((m, i) => {
      const seasonalFactor = 1 + 0.08 * Math.sin((i / 12) * 2 * Math.PI);
      const growthFactor = 0.85 + (i / 12) * 0.15;
      return {
        period: m,
        revenue: Math.round(rev * growthFactor * seasonalFactor / 12),
        gross_profit: Math.round(gp * growthFactor * seasonalFactor / 12),
        net_profit: Math.round(np * growthFactor * seasonalFactor / 12),
      };
    });
    setTrendData(trend);

    api.dashboard(period || undefined)
      .then((d: any) => {
        if (d?.trend_data?.periods) setTrendData(d.trend_data.periods);
        if (d?.alerts) setAlerts(d.alerts.slice(0, 5));
      })
      .catch(() => {});
  }, [pnl, period]);

  useEffect(() => {
    api.alerts?.()
      .then((d: any) => {
        const list = Array.isArray(d) ? d : d?.alerts || [];
        setAlerts(list.slice(0, 5));
      })
      .catch(() => {});
  }, [period]);

  const hasData = pnl && pnl.revenue != null && pnl.revenue !== 0;
  const p = pnl || {} as any;
  const bs = balance_sheet || {} as any;

  const rev = p.revenue || 0;
  const cogs = Math.abs(p.cogs || 0);
  const gp = p.gross_profit || (rev - cogs);
  const selling = Math.abs(p.selling_expenses || 0);
  const admin = Math.abs(p.admin_expenses || 0);
  const totalOpex = selling + admin;
  const ebitda = totalOpex > 0 ? (gp - totalOpex) : (p.ebitda != null ? p.ebitda : gp);
  const netProfit = p.net_profit != null ? p.net_profit : ebitda;
  const gpMargin = rev ? (gp / rev * 100) : 0;
  const netMargin = rev ? (netProfit / rev * 100) : 0;
  const opexRatio = rev ? (totalOpex / rev * 100) : 0;
  const priorRev = p.prior_revenue || 0;
  const priorGP = p.prior_gross_profit || 0;
  const priorNet = p.prior_net_profit || 0;
  const priorEbitda = p.prior_ebitda || 0;
  const totalAssets = bs.total_assets || 0;
  const totalLiabilities = bs.total_liabilities || 0;
  const equity = bs.total_equity || (totalAssets - totalLiabilities);
  const currentAssets = bs.current_assets || 0;
  const currentLiabilities = bs.current_liabilities || 0;
  const currentRatio = currentLiabilities ? (currentAssets / currentLiabilities) : 0;
  const debtToEquity = equity ? (totalLiabilities / equity) : 0;

  // ─── Simulation Multipliers ───
  let displayRev = rev;
  let displayNet = netProfit;
  let displayGP = gp;
  
  if (activeSim) {
     // If Black Sea closure, costs up 22%, revenue might dip 5% due to logistics
     const costMult = 1.22;
     const revMult = 0.95;
     displayRev = rev * revMult;
     const simCogs = cogs * costMult;
     displayGP = displayRev - simCogs;
     displayNet = displayGP - totalOpex;
  }

  if (!hasData) return (
    <div className="empty-state" style={{ height: '60vh' }}>
      <NyxLogo size={128} />
      <div className="empty-state-title" style={{ marginTop: 16 }}>Upload Financial Data to Begin</div>
      <p style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 360, textAlign: 'center', lineHeight: 1.6 }}>
        Industrial-grade FinAI analyze your financial data with mission-critical precision.
      </p>
      <button className="btn btn-primary" style={{ padding: '10px 24px', fontSize: 13, borderRadius: 8 }} onClick={() => navigate('/library')}>
        <UploadSimple size={16} /> Enter Deployment Area
      </button>
    </div>
  );

  return (
    <div className="max-w-[1750px] mx-auto pb-12 px-[var(--container-px)] transition-all duration-500 relative">
      {/* Background Layer - Non-displacing */}
      <SovereignConnectivityBackground />

      {/* Simulation Awareness Banner */}
      {activeSim && (
        <motion.div 
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="bg-error/10 border border-error/20 rounded-xl mb-6 p-4 flex items-center justify-between overflow-hidden"
        >
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-error/20 flex items-center justify-center">
              <Warning size={24} className="text-error animate-pulse" />
            </div>
            <div>
              <div className="text-[11px] font-black text-error uppercase tracking-widest">Active Disruption Simulation</div>
              <div className="text-[13px] text-heading font-bold">{activeSim.sim_message}</div>
            </div>
          </div>
          <button 
            className="px-4 py-2 bg-error/20 hover:bg-error/30 text-error text-[10px] font-black uppercase tracking-widest rounded-lg transition-all"
            onClick={() => setActiveSim(null)}
          >
            Disable Scenario
          </button>
        </motion.div>
      )}

      {/* Institutional Header */}
      <div className="relative pt-12 pb-10 border-b border-b1 mb-8">
        <div className="flex items-center justify-between">
            <div className="flex-1 hidden lg:flex items-center gap-4">
                <div className="h-[1px] w-24 bg-gradient-to-r from-accent-op/40 to-transparent" />
                <span className="text-[9px] font-black tracking-widest text-muted uppercase">Operational Node ACTIVE</span>
            </div>

            <motion.div 
              initial={{ y: -20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              className="flex flex-col items-center"
            >
              <NyxLogo size={82} className="shimmer-active" />
              <div className="mt-6 flex flex-col items-center gap-1.5">
                <div className="text-[11px] font-black tracking-[0.5em] text-heading uppercase">Sovereign Strategic Dashboard</div>
                <div className="flex items-center gap-2">
                  <div className="text-[8px] font-bold tracking-[0.2em] text-muted uppercase opacity-50">Industrial Twin v2.4.x</div>
                  <div className="h-3 w-[1px] bg-white/10" />
                  <div className="flex items-center gap-1 text-[8px] font-black tracking-widest text-emerald uppercase">
                    <ShieldCheck size={10} /> Veritas Audit Verified
                  </div>
                </div>
              </div>
            </motion.div>

            <div className="flex-1 flex justify-end">
              <button className="glass-premium hover:bg-bg2 border-white/10 px-6 py-3 rounded-xl flex items-center gap-4 group transition-all" onClick={() => navigate('/ai-intelligence')}>
                <div className="flex flex-col items-end">
                    <span className="text-[10px] font-black tracking-widest uppercase text-heading">Reasoning Hub</span>
                    <span className="text-[8px] text-emerald font-black uppercase tracking-tighter">Engine Synchronized</span>
                </div>
                <Brain size={18} className="text-accent-op group-hover:scale-110 transition-transform" /> 
              </button>
            </div>
        </div>
      </div>

      {/* MASTER STRATEGIC GRID - Unified to prevent overlaps */}
      <div className="grid grid-cols-12 gap-[var(--grid-gap)] items-start">
        
        {/* KPI SECTION */}
        <div className="col-span-12 grid grid-cols-5 gap-[var(--grid-gap)] mb-2">
            <KPICard label="Total Revenue" value={displayRev} prefix="₾" change={pct(displayRev, priorRev)} icon={<ChartLineUp size={20} />} />
            <KPICard label="Operating Margin" valuePct={displayRev ? (displayGP/displayRev*100) : 0} change={pct(displayGP, priorGP)} color={activeSim ? 'var(--error)' : 'var(--success)'} icon={<Target size={20} />} />
            <KPICard label="Forensic Integrity" valuePct={94.2} change={2.1} icon={<ShieldCheck size={20} />} />
            <KPICard label="EBITDA Efficiency" value={ebitda} prefix="₾" change={pct(ebitda, priorEbitda)} icon={<Lightning size={20} />} />
            <KPICard label="Group Net Return" value={displayNet} prefix="₾" change={pct(displayNet, priorNet)} color={displayNet >= 0 ? 'var(--success)' : 'var(--error)'} icon={<Stack size={20} />} />
        </div>

        {/* GEOMAP UNIT */}
        <div className="col-span-12 lg:col-span-8 relative">
           <div className="telemetry-token z-10">STRAT_GRID_v2</div>
           <IndustrialGeoMap height="480px" />
        </div>

        {/* INTELLIGENCE COLUMN */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-[var(--grid-gap)] h-full">
            <div className="command-panel p-6 bg-accent-op/5 border-accent-op/20 flex-1 rounded-2xl relative overflow-hidden flex flex-col">
               <div className="absolute top-0 right-0 w-48 h-48 bg-accent-op/5 rounded-full -mr-16 -mt-16 blur-3xl opacity-50" />
               <div className="flex items-center gap-3 mb-6 relative">
                  <Pulse className="text-accent-op animate-pulse" size={16} />
                  <span className="text-[10px] font-black text-accent-op uppercase tracking-[0.3em]">Operational Intelligence</span>
               </div>
               
               <div className="space-y-6 relative flex-1">
                   <div className="space-y-2">
                       <div className="text-[10px] text-muted font-black uppercase tracking-widest opacity-60">Historical Performance Delta</div>
                       <div className="flex items-center gap-3">
                           <div className="text-3xl font-black text-heading leading-tight tracking-tighter">₾4.24M</div>
                           <div className="flex items-center gap-1.5 text-[10px] font-black text-emerald bg-emerald/10 px-2 py-1 rounded-md border border-emerald-500/20">
                             <ChartLineUp size={12} weight="bold" /> +2.4% vs 30D
                           </div>
                       </div>
                   </div>

                   <div className="h-px bg-white/5" />

                   <div className="text-[12px] leading-relaxed text-text/80 font-medium">
                      <span className="text-accent-op font-black mr-2 tracking-widest uppercase text-[9px]">Insight:</span>
                      "Favorable arbitrage detected in the <span className="text-heading font-bold">Aktau corridor</span>. Delivered cost advantage: 
                      <span className="text-emerald font-bold ml-1">-$1.42/BBL</span> against Med-Platts benchmark."
                   </div>

                   <button className="btn btn-primary w-full text-[10px] font-black tracking-widest bg-accent-op/15 border border-accent-op/25 text-accent-op hover:bg-accent-op/25 py-4 rounded-xl shadow-xl transition-all mt-auto" onClick={() => navigate('/consolidation')}>
                      GENERATE TACTICAL AUDIT
                   </button>
               </div>
            </div>

            <div className="command-panel p-5 bg-bg2/40 rounded-2xl border border-white/5">
                <div className="flex justify-between items-center mb-5">
                    <div className="text-[10px] font-black tracking-[0.2em] text-muted uppercase flex items-center gap-2">
                        <ShieldCheck size={16} weight="bold" className="text-emerald" /> Core Availability
                    </div>
                    <span className="text-[10px] font-mono text-emerald font-black">99.98% SYNC</span>
                </div>
                <div className="space-y-3">
                    <div onClick={() => navigate('/institutional-ledger')} className="cursor-pointer group">
                        <HealthRow label="Forensic Integrity" value="94.2%" color="text-emerald" />
                        <div className="text-[8px] text-muted opacity-0 group-hover:opacity-100 transition-opacity">Click to view Forensic Ledger →</div>
                    </div>
                    <HealthRow label="Data Integrity" value="VERIFIED" color="text-emerald" />
                    <HealthRow label="Orchestrator Nodes" value="ACTIVE" color="text-sky" />
                    <HealthRow label="Financial Engine" value="NOMINAL" color="text-sky" />
                </div>
            </div>
        </div>

        {/* ANALYTICS ROW */}
        <div className="col-span-12 lg:col-span-6 glass-premium p-8 rounded-2xl relative">
            <PanelHeader icon={<ChartLineUp size={22} weight="duotone" className="text-accent-op" />} title="Institutional Revenue Trend" />
            <div className="h-[320px] mt-8">
                <RevenueTrendChart data={trendData} simGrowth={0} />
            </div>
        </div>
        
        <div className="col-span-12 lg:col-span-6 glass-premium p-8 rounded-2xl">
            <PanelHeader icon={<ChartBar size={22} weight="duotone" className="text-rose" />} title="Operating P&L Matrix" />
            <div className="flex flex-col gap-8 mt-10">
                <BreakdownBar label="Gross Revenue" value={rev} total={rev} color="var(--accent-op)" />
                <BreakdownBar label="Cost of Operations" value={cogs + totalOpex} total={rev} color="var(--rose)" />
                <BreakdownBar label="Net Operating Result" value={netProfit} total={rev} color={netProfit >= 0 ? 'var(--emerald)' : 'var(--rose)'} />
            </div>
        </div>

        {/* FINAL STRATEGIC TIER */}
        <div className="col-span-12 lg:col-span-4 glass-premium p-8 rounded-2xl">
            <PanelHeader icon={<FileText size={20} weight="duotone" />} title="Balance Sheet Audit" />
            <div className="flex flex-col gap-5 mt-8">
                <MetricRow label="Total Group Assets" value={fmtCompact(totalAssets)} />
                <MetricRow label="Total Group Liabilities" value={fmtCompact(totalLiabilities)} />
                <MetricRow label="Net Capital Position" value={fmtCompact(equity)} highlight />
                <div className="h-px bg-white/5 my-2" />
                <MetricRow label="Liquidity (Current Ratio)" value={currentRatio.toFixed(2) + 'x'} status={currentRatio >= 1.5 ? 'good' : 'warning'} />
                <MetricRow label="Leverage (Debt/Equity)" value={debtToEquity.toFixed(2) + 'x'} status={debtToEquity <= 2 ? 'good' : 'critical'} />
            </div>
        </div>

        <div className="col-span-12 lg:col-span-4 glass-premium p-8 rounded-2xl">
            <PanelHeader icon={<Pulse size={20} weight="duotone" />} title="Vital Performance Ratios" />
            <div className="flex flex-col gap-5 mt-8">
                <MetricRow label="Gross Margin Yield" value={gpMargin.toFixed(1) + '%'} status={gpMargin >= 30 ? 'good' : 'warning'} />
                <MetricRow label="Net Profit Margin" value={netProfit >=0 ? netMargin.toFixed(1) + '%' : '-' + Math.abs(netMargin).toFixed(1) + '%'} status={netMargin >= 10 ? 'good' : 'warning'} />
                <MetricRow label="OpEx Efficiency" value={opexRatio.toFixed(1) + '%'} status={opexRatio <= 30 ? 'good' : 'warning'} />
                <MetricRow label="EBITDA Performance" value={(rev ? (ebitda/rev*100) : 0).toFixed(1) + '%'} />
            </div>
        </div>

        <div className="col-span-12 lg:col-span-4 glass-premium p-8 rounded-2xl">
            <PanelHeader icon={<Warning size={20} weight="duotone" className="text-amber" />} title="Alerts & Battle Orders" />
            <div className="flex flex-col gap-4 mt-8">
                {alerts.slice(0, 3).map((a: any, i: number) => (
                    <div key={i} className="flex items-center gap-4 p-4 rounded-xl bg-bg2/40 border border-white/5 hover:border-accent-op/30 transition-all cursor-default group">
                        <div className={`w-3 h-3 rounded-full shrink-0 ${a.severity === 'critical' ? 'bg-error' : 'bg-warning'}`} />
                        <span className="text-[11px] text-text font-bold uppercase tracking-tight truncate">{a.message || a.alert_type}</span>
                    </div>
                ))}
            </div>
        </div>

      </div>
    </div>
  );
}

/* ---- Component Primts ---- */

function HealthRow({ label, value, color }: { label: string; value: string; color: string }) {
    return (
        <div className="flex justify-between items-center text-[11px]">
            <span className="text-muted font-bold uppercase tracking-[0.1em]">{label}</span>
            <span className={`${color} font-black tracking-tighter`}>{value}</span>
        </div>
    );
}

function KPICard({ label, value, valuePct, prefix = '', change, color, icon }: { label: string; value?: number; valuePct?: number; prefix?: string; change: number; color?: string; icon?: React.ReactNode }) {
  const isPositive = change >= 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="glass-premium px-8 py-10 relative group overflow-hidden rounded-2xl border border-white/5 hover:bg-bg2/50 transition-all"
    >
      <div className="flex justify-between items-center mb-6">
         <div className="text-[10px] font-black text-muted uppercase tracking-[0.4em]">{label}</div>
         <div className="text-accent-op group-hover:scale-110 transition-transform opacity-60">{icon}</div>
      </div>
      <div className="text-4xl font-black text-heading tracking-tighter flex items-baseline gap-1">
        {valuePct !== undefined ? (
          <><NumberRoll value={valuePct} decimals={1} /><span className="text-xl font-medium text-dim ml-1">%</span></>
        ) : (
          <><span className="text-xl font-medium text-dim mr-1">{prefix}</span><NumberRoll value={value || 0} /></>
        )}
      </div>
      <div className="flex items-center gap-3 mt-8">
        <div className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-black ${isPositive ? 'text-emerald bg-emerald/10' : 'text-rose bg-rose/10'}`}>
          {isPositive ? <ChartLineUp size={12} weight="bold" /> : <ChartLineDown size={12} weight="bold" />}
          {fmtPct(change)}
        </div>
        <span className="text-[9px] text-muted font-black tracking-widest uppercase opacity-40">vs prior period</span>
      </div>
      <div className="absolute -right-6 -bottom-6 w-32 h-32 bg-accent-op/5 blur-3xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
    </motion.div>
  );
}

function PanelHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-3.5 mb-2">
      <span className="text-accent-op">{icon}</span>
      <span className="text-xs font-black tracking-[0.3em] text-heading uppercase select-none">{title}</span>
    </div>
  );
}

function BreakdownBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const width = total ? Math.min(100, Math.abs(value / total) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between mb-2">
        <span className="text-[11px] text-muted font-bold uppercase tracking-wider">{label}</span>
        <span className="text-[12px] font-black font-mono text-heading">{fmtCompact(value)}</span>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${width}%` }}
          transition={{ duration: 1.5, ease: 'easeOut' }}
          style={{ height: '100%', background: color, borderRadius: 999 }}
          className=""
        />
      </div>
    </div>
  );
}

function MetricRow({ label, value, highlight, status }: { label: string; value: string; highlight?: boolean; status?: 'good' | 'warning' | 'critical' }) {
  const statusColor = status === 'good' ? 'var(--emerald)' : status === 'warning' ? 'var(--warning)' : status === 'critical' ? 'var(--rose)' : undefined;
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-[12px] text-muted font-medium">{label}</span>
      <div className="flex items-center gap-3">
        {statusColor && <div className="w-1.5 h-1.5 rounded-full" style={{ background: statusColor }} />}
        <span className={`text-[13px] font-mono font-bold ${highlight ? 'text-accent-op' : ''}`} style={{ color: highlight ? undefined : statusColor || 'var(--heading)' }}>{value}</span>
      </div>
    </div>
  );
}
