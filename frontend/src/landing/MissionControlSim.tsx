import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, Shield, Cpu, Activity, Zap, CheckCircle2, Database } from 'lucide-react';
import NyxLogo from '../components/NyxLogo';

interface TraceStep {
  agent: string;
  action: string;
  status: 'pending' | 'active' | 'complete';
  icon: any;
}

const TRACE_STEPS: TraceStep[] = [
  { agent: 'Ingestion Controller', action: 'Extracting GL Data from sftp://1c-server/exports...', status: 'complete', icon: Database },
  { agent: 'Sovereign Auditor', action: 'Verifying VAT compliance on 12,402 transactions...', status: 'complete', icon: Shield },
  { agent: 'Logistics Intel', action: 'Cross-referencing Brent Crude @ $82.4 with BTC Pipeline flow rates...', status: 'complete', icon: Activity },
  { agent: 'NYX Orchestrator', action: 'Synthesizing multi-vector risk map for Georgia-Turkey corridor...', status: 'active', icon: NyxLogo },
  { agent: 'Strategic Captain', action: 'Drafting executive mandate: Re-calibrate supply hedge by 14.2%...', status: 'pending', icon: Zap },
];

const MissionControlSim: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev < TRACE_STEPS.length - 1 ? prev + 1 : prev));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-full max-w-4xl mx-auto glass-premium overflow-hidden border border-white/5 bg-bg0/40 shadow-2xl shadow-sky/10">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-white/5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-sky" />
          <span className="text-[10px] font-bold tracking-[0.3em] uppercase text-sky">NYX Orchestration Trace—v2.2</span>
        </div>
        <div className="flex gap-1.5">
          <div className="w-2 h-2 rounded-full bg-rose/40" />
          <div className="w-2 h-2 rounded-full bg-amber/40" />
          <div className="w-2 h-2 rounded-full bg-emerald/40" />
        </div>
      </div>

      {/* Terminal Body */}
      <div className="p-8 font-mono overflow-y-auto max-h-[400px]">
        <div className="flex flex-col gap-6">
          {TRACE_STEPS.map((step, idx) => {
            const isActive = idx === activeStep;
            const isComplete = idx < activeStep;
            const Icon = step.icon;

            return (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ 
                  opacity: idx <= activeStep ? 1 : 0.2, 
                  x: 0,
                  transition: { duration: 0.5 }
                }}
                className={`flex gap-6 items-start relative ${isActive ? 'text-sky' : 'text-muted'}`}
              >
                {/* Connector Line */}
                {idx < TRACE_STEPS.length - 1 && (
                  <div className={`absolute left-4 top-8 w-[1px] h-12 ${isComplete ? 'bg-sky/40' : 'bg-white/5'}`} />
                )}

                <div className={`relative z-10 w-8 h-8 rounded bg-bg3 border ${isActive ? 'border-sky shadow-[0_0_15px_rgba(0,216,255,0.3)]' : isComplete ? 'border-emerald/30' : 'border-white/5'} flex items-center justify-center shrink-0`}>
                  {isComplete ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald" />
                  ) : (
                      <Icon size={16} className={`w-4 h-4 ${isActive ? 'animate-pulse' : 'opacity-40'}`} />
                  )}
                </div>

                <div className="flex-1 pt-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold uppercase tracking-widest ${isActive ? 'text-sky' : isComplete ? 'text-emerald/70' : ''}`}>
                      {step.agent}
                    </span>
                    {isActive && (
                      <span className="text-[8px] bg-sky/10 px-2 py-0.5 rounded animate-pulse">PROCESSING</span>
                    )}
                  </div>
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: idx <= activeStep ? '100%' : 0 }}
                    className="text-xs leading-relaxed overflow-hidden whitespace-nowrap"
                  >
                    {step.action}
                  </motion.div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Ticker Status */}
      <div className="px-4 py-2 bg-emerald/5 border-t border-white/5 flex items-center gap-4">
        <div className="flex items-center gap-2">
           <Activity className="w-3 h-3 text-emerald animate-pulse" />
           <span className="text-[9px] font-bold text-emerald/80 tracking-widest uppercase">System Stability: Nominal</span>
        </div>
        <div className="h-3 w-[1px] bg-white/10" />
        <div className="text-[9px] font-mono text-muted">
          LOG_STREAM: CLUSTER_ID_0x7FB ... OK
        </div>
      </div>
    </div>
  );
};

export default MissionControlSim;
