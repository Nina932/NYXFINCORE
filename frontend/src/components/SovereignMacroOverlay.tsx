import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Activity, Globe, Zap, Shield, BarChart3 } from 'lucide-react';

interface MacroIndicator {
    label: string;
    value: string;
    change: string;
    isPositive: boolean;
    icon: any;
    color: string;
}
interface SovereignMacroProps {
    brent: number;
    usdGel: number;
    nbgRate: number;
    dataQuality: string;
}

const SovereignMacroOverlay = ({ brent: propBrent, usdGel: propUsdGel, nbgRate: propNbgRate, dataQuality }: SovereignMacroProps) => {
    const [indicators, setIndicators] = React.useState<MacroIndicator[]>([]);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        setIndicators([
            { 
                label: 'USD/GEL Spot', 
                value: `${propUsdGel.toFixed(3)}`, 
                change: '+0.12%', 
                isPositive: false, 
                icon: Activity, 
                color: 'text-sky-400' 
            },
            { 
                label: 'Brent Velocity', 
                value: `$${propBrent.toFixed(2)}`, 
                change: '-1.2%', 
                isPositive: false, 
                icon: Zap, 
                color: 'text-amber-400' 
            }
        ]);
        setLoading(false);
    }, [propBrent, propUsdGel, propNbgRate]);

    if (loading) return null;

    return (
        <div className="absolute top-20 right-6 z-[60] w-52 space-y-2 pointer-events-none">
            <div className="flex items-center gap-2 mb-3 bg-slate-950/80 backdrop-blur-2xl border border-white/10 rounded px-3 py-1.5 w-fit shadow-2xl">
                <Globe size={12} className="text-sky-500 animate-pulse" />
                <span className="text-[9px] font-black text-sky-200 tracking-[.2em] uppercase">Macro Pulse</span>
            </div>

            {indicators.map((ind, idx) => (
                <div key={idx} className="group pointer-events-auto bg-slate-900/60 backdrop-blur-xl border border-white/5 rounded-xl p-3 hover:bg-slate-800/80 transition-all duration-300 shadow-xl">
                    <div className="flex items-start justify-between">
                        <div className="space-y-1">
                            <div className="text-[8px] font-bold text-slate-500 uppercase tracking-widest">{ind.label}</div>
                            <div className={`text-base font-black tracking-tighter ${ind.color}`}>
                                {ind.value}
                            </div>
                        </div>
                        <div className={`p-1.5 rounded-lg bg-white/5 border border-white/10 ${ind.color}`}>
                            <ind.icon size={12} />
                        </div>
                    </div>
                </div>
            ))}
            
            <div className="mt-4 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg pointer-events-auto">
                <div className="flex items-center gap-2">
                    <BarChart3 size={10} className="text-emerald-500" />
                    <span className="text-[8px] font-black text-emerald-200 uppercase tracking-tighter">Margin: 8.2% Nominal</span>
                </div>
            </div>
        </div>
    );
};

export default SovereignMacroOverlay;
