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
            <div className="flex items-center gap-2 mb-3 bg-bg1/90 backdrop-blur-sm border border-white/6 rounded px-3 py-1.5 w-fit">
                <Globe size={12} className="text-muted" />
                <span className="text-[9px] font-semibold text-muted tracking-[.2em] uppercase">Macro Pulse</span>
            </div>

            {indicators.map((ind, idx) => (
                <div key={idx} className="group pointer-events-auto bg-bg1/80 backdrop-blur-sm border border-white/5 rounded-lg p-3 hover:border-white/10 transition-all duration-200">
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
