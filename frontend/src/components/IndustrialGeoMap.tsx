import React, { useEffect, useState, useCallback, useMemo } from 'react';
import * as echarts from 'echarts';
import ReactECharts from 'echarts-for-react';
import { Globe, Droplet, Activity, TrendingUp, TrendingDown, AlertTriangle, RefreshCw, Shield, ShieldCheck, Info, CheckCircle2, XCircle, Zap, X, Target, ChevronUp, ChevronDown, DollarSign } from 'lucide-react';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { fmtCompact } from '../utils/formatters';
import { useAgentMapInteraction } from '../hooks/useAgentMapInteraction';
import MapOperatorBriefing from './MapOperatorBriefing';
import SovereignMacroOverlay from './SovereignMacroOverlay';

// Sovereign Custom SVG Icons
const TAX_ICON = 'path://M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z';
const HUB_ICON = 'path://M18 10V7M12 10V4M6 10v3m12 0v7H6v-7';
const PORT_ICON = 'path://M12 21v-4m0 0a4 4 0 100-8 4 4 0 000 8zM5 8h14M12 3v5';

interface GeoMapProps {
  data?: any[];
  title?: string;
  height?: string;
}

/* ─── Color Palette ─── */
const GOLD       = '#d4a953a4';
const EMERALD    = '#10b981';
const ROSE       = '#f43f5e';
const ORANGE     = '#fb923c';
const SKY        = '#00D8FF';
const SLATE_FILL = 'rgba(100, 116, 139, 0.08)';
const BORDER_CLR = 'rgba(148, 163, 184, 0.2)';

/* ─── Types ─── */
interface RegionRisk { risk_score: number; level: string; color: string; border_color: string; primary_driver: string; factors: string[]; }
interface RouteRisk { 
  name: string; 
  id: string; 
  risk_score: number; 
  status: string; 
  color: string; 
  capacity: number; 
  pressure_bar: number;
  throughput_actual: number;
  health_score: number;
  financial_exposure_daily: number;
  potential_loss_daily: number;
  spot_surcharge_est: number;
  type: string;
  coords: number[][];
}
interface RiskData {
  regions: Record<string, RegionRisk>;
  routes: RouteRisk[];
  infrastructure: { routes: any[]; hubs: any[] };
  market_pulse: any[];
  price_signals: any;
  fx_signals: any;
  geo_signals: any;
  supply_fundamentals: any;
  overall_risk_level: string;
  data_quality: string;
  sim_active?: boolean;
  sim_message?: string;
  competitors?: any[];
  strategy?: any;
  telemetry?: any[];
}

const ModeButton = ({ active, icon, label, onClick }: any) => (
  <button 
    onClick={onClick}
    className={`px-3 py-1.5 rounded-lg text-[9px] font-black transition-all text-left flex items-center gap-2 pointer-events-auto shadow-xl backdrop-blur-md ${active ? 'bg-accent-op/30 text-accent-op border border-accent-op/50 shadow-[0_0_20px_rgba(212,168,83,0.2)]' : 'bg-bg3/40 text-muted hover:bg-bg2/60 border border-white/5 opacity-80 hover:opacity-100'}`}
  >
    {icon} {label}
  </button>
);

const TacticalRolloutTray = ({ asset, isOpen, onClose, viewMode }: { asset: any; isOpen: boolean; onClose: () => void; viewMode: string }) => {
  if (!asset) return null;

  return (
    <div className={`absolute bottom-6 left-6 right-[360px] glass-premium border border-accent-op/30 shadow-2xl z-[100] transition-all duration-500 transform ${isOpen ? 'translate-y-0 opacity-100 h-[220px]' : 'translate-y-8 opacity-0 h-0 pointer-events-none'}`}>
        <div className="absolute top-0 left-8 -translate-y-1/2 flex items-center gap-4">
             <div className="bg-bg3 border border-accent-op/30 px-6 py-1.5 rounded-full flex items-center gap-2 shadow-2xl">
                <span className="text-[10px] font-black text-accent-op tracking-[.3em]">TACTICAL ASSET INTEL</span>
                <button onClick={onClose} className="hover:text-rose transition-colors"><X size={14} /></button>
             </div>
        </div>

        <div className="p-8 grid grid-cols-12 gap-8 h-full">
            <div className="col-span-12 lg:col-span-4 border-white/5 lg:border-r pr-8">
                <div className="flex items-center gap-3 mb-5">
                    <Activity size={20} className="text-accent-op" />
                    <div>
                        <div className="text-[10px] font-black text-muted uppercase tracking-[.2em]">{asset.type || 'Operational'} NODE</div>
                        <div className="text-xl font-bold text-heading tracking-tight">{asset.name?.split('(')[0]}</div>
                    </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                        <div className="text-[8px] text-muted font-black uppercase mb-1 tracking-widest">Health</div>
                        <div className="text-sm font-mono font-bold text-emerald">98.4%</div>
                    </div>
                    <div className="bg-white/5 p-3 rounded-lg border border-white/5">
                        <div className="text-[8px] text-muted font-black uppercase mb-1 tracking-widest">Util.</div>
                        <div className="text-sm font-mono font-bold text-sky">92.0%</div>
                    </div>
                </div>
            </div>

            <div className="col-span-12 lg:col-span-5 border-white/5 lg:border-r px-8">
                <div className="text-[10px] font-black text-muted uppercase tracking-[.2em] mb-4">Landed Cost Matrix ($/BBL)</div>
                <div className="space-y-3">
                    <div className="flex justify-between text-[11px] items-center">
                        <span className="text-muted font-medium">FOB Purchase</span>
                        <span className="font-mono text-heading bg-white/5 px-2 py-0.5 rounded">${asset.fob || 74.20}</span>
                    </div>
                    <div className="flex justify-between text-[11px] items-center">
                        <span className="text-dim">Logistics & Transit</span>
                        <span className="font-mono text-heading">+${asset.tax || 2.15}</span>
                    </div>
                    <div className="pt-3 border-t border-white/10 flex justify-between text-xs font-black">
                        <span className="text-accent-op uppercase tracking-widest">Industrial Delivered</span>
                        <span className="text-accent-op text-sm">${(asset.price ? asset.price + 4 : 78.20).toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <div className="col-span-12 lg:col-span-3 pl-8 flex flex-col gap-4">
                <div className="text-[10px] font-black text-muted uppercase tracking-[.2em] mb-1">Signal</div>
                
                {asset.storage_telemetry ? (
                    <div className="p-3 bg-accent-op/10 border border-accent-op/20 rounded-xl relative overflow-hidden">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[8px] font-black text-accent-op uppercase">Storage Fill</span>
                            <ShieldCheck size={12} className="text-emerald" />
                        </div>
                        <div className="text-lg font-black text-heading font-mono">
                            {(asset.storage_telemetry.current_fill * 100).toFixed(1)}%
                        </div>
                        <div className="mt-2 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                            <motion.div 
                                className="h-full bg-emerald shadow-[0_0_8px_rgba(16,185,129,0.5)]" 
                                initial={{ width: 0 }}
                                animate={{ width: `${asset.storage_telemetry.current_fill * 100}%` }}
                                transition={{ duration: 1.2, ease: "easeOut" }}
                            />
                        </div>
                        <div className="mt-2 text-[8px] text-muted font-bold uppercase tracking-tighter">
                            {fmtCompact(asset.storage_telemetry.capacity_bbl / 1000000)}M BBL Capacity
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col gap-4">
                        <div className="flex items-center gap-3">
                            <div className="w-1.5 h-10 bg-emerald rounded-full shadow-[0_0_10px_rgba(16,185,129,0.3)]" />
                            <div>
                                <div className="text-[9px] text-muted font-black uppercase">Margin</div>
                                <div className="text-xs font-bold text-emerald">+1.4%</div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
  );
};

export default function IndustrialGeoMap({ title = 'STRATEGIC ASSETS & SUPPLY CHAIN', height = '500px' }: GeoMapProps) {
  const [mapReady, setMapReady]   = useState(false);
  const [riskData, setRiskData]   = useState<RiskData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [isMaximized, setIsMaximized] = useState(false);
  const [viewMode, setViewMode] = useState<'LOGISTICS' | 'RISK' | 'MARKET' | 'PROCUREMENT' | 'COMPETITOR'>('LOGISTICS');
  const [selectedAsset, setSelectedAsset] = useState<any>(null);
  const [showTray, setShowTray] = useState(false);
  const [filterTarget, setFilterTarget] = useState<string>('all');
  const [mapFocus, setMapFocus] = useState<{center: [number, number], zoom: number}>({ center: [38, 42], zoom: 4.2 });
  const chartRef = React.useRef<any>(null);
  const { activeCommand, clearCommand } = useAgentMapInteraction();

  const fetchLiveData = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/external-data/situational-risk');
      if (resp.ok) {
        const d: RiskData = await resp.json();
        setRiskData(d);
      }
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Risk data fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetch('/assets/world.json')
      .then(res => res.json())
      .then(geoJson => { echarts.registerMap('world', geoJson); setMapReady(true); })
      .catch(() => {
        return fetch('https://raw.githubusercontent.com/apache/echarts/master/test/data/map/json/world.json')
          .then(res => res.json())
          .then(geoJson => { echarts.registerMap('world', geoJson); setMapReady(true); });
      });
    fetchLiveData();
    const interval = setInterval(fetchLiveData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  useEffect(() => {
      if (!activeCommand) return;
      
      // Reactive Intent Handling
      if (activeCommand.intent === 'RISK_SCAN') setViewMode('RISK');
      if (activeCommand.intent === 'PRICE_INTEL') setViewMode('MARKET');
      
      // Keyword & Context Detection for "Live" experience
      const lowerRation = activeCommand.rationale?.toLowerCase() || "";
      if (lowerRation.includes('gas') || activeCommand.intent?.includes('GAS')) {
          setFilterTarget('gas');
          setMapFocus({ center: [43, 41], zoom: 6.5 }); // Zoom to Caucasus/pipelines
      } else if (lowerRation.includes('crude')) {
          setFilterTarget('crude');
          setMapFocus({ center: [35, 38], zoom: 5.5 });
      } else {
          setFilterTarget('all');
      }

      // Cleanup command after transition
      const timer = setTimeout(clearCommand, 8000);
      return () => clearTimeout(timer);
  }, [activeCommand, clearCommand]);

  const regionStyles = useMemo(() => {
    const regions = riskData?.regions || {};
    if (viewMode === 'RISK') {
      return Object.entries(regions).map(([name, r]) => ({
        name,
        itemStyle: {
          areaColor: `${r.color.replace('0.25', '0.4')}`,
          borderColor: r.border_color,
          borderWidth: name === 'Georgia' ? 2.5 : 1,
        }
      }));
    }
    const corridor = ['Georgia', 'Azerbaijan', 'Turkey', 'Kazakhstan'];
    return corridor.map(name => ({
      name,
      itemStyle: {
        areaColor: name === 'Georgia' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(148, 163, 184, 0.04)',
        borderColor: name === 'Georgia' ? EMERALD : 'rgba(148, 163, 184, 0.3)',
        borderWidth: name === 'Georgia' ? 2 : 1,
      }
    }));
  }, [riskData, viewMode]);

  const option = useMemo(() => {
    const routesData = (riskData?.infrastructure?.routes || []).filter((r: any) => 
        filterTarget === 'all' || r.commodity === filterTarget
    ).map((r: any) => ({
        name: r.name,
        coords: r.coords,
        type: r.type,
        commodity: r.commodity,
        throughput: r.throughput_actual || 1.0,
        status: r.status,
        lineStyle: { 
            color: (r.status === 'CRITICAL' || (riskData?.sim_active && r.name.includes('Black Sea'))) ? ROSE : (r.commodity === 'gas' ? GOLD : r.commodity === 'crude' ? EMERALD : r.commodity === 'rail' ? '#a78bfa' : SKY),
            width: r.status === 'CRITICAL' ? 4 : 2,
            opacity: riskData?.sim_active && r.status === 'CRITICAL' ? 0.95 : 0.8
        }
    }));

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(2, 6, 23, 0.95)',
        borderColor: 'rgba(59, 130, 246, 0.3)',
        borderWidth: 1,
        textStyle: { color: '#fff', fontSize: 10, fontFamily: 'var(--font-mono)' },
        formatter: (params: any) => {
            if (params.seriesName === 'Assets') {
                const h = params.data;
                const storage = h.storage_telemetry ? `<br/><span style='color:var(--accent-op)'>STRG: ${(h.storage_telemetry.current_fill * 100).toFixed(0)}%</span>` : '';
                return `<div class="p-2 uppercase tracking-tighter text-[9px] font-mono"><b>${params.name}</b><br/>${h.type}${storage}</div>`;
            }
            return `<div class="p-2 uppercase tracking-tighter text-[9px] font-mono"><b>${params.name}</b><br/>${params.data?.status || 'Active'}</div>`;
        }
      },
      geo: {
        map: 'world',
        roam: true,
        center: mapFocus.center,
        zoom: mapFocus.zoom,
        silent: false,
        itemStyle: { areaColor: SLATE_FILL, borderColor: BORDER_CLR, borderWidth: 0.5 },
        regions: regionStyles,
        emphasis: { itemStyle: { areaColor: 'rgba(59, 130, 246, 0.1)' } }
      },
      series: [
        // LAYER 1: THE GLOW (Broad atmosphere)
        {
          name: 'RoutesGlow',
          type: 'lines',
          coordinateSystem: 'geo',
          polyline: true,
          zlevel: 4,
          silent: true,
          lineStyle: { 
            width: 12, 
            opacity: 0.12, 
            shadowBlur: 25,
            shadowColor: 'inherit',
            color: 'inherit'
          },
          data: routesData
        },
        // LAYER 2: THE CORE (Solid high-tech line)
        {
          name: 'RoutesCore',
          type: 'lines',
          coordinateSystem: 'geo',
          polyline: true,
          zlevel: 5,
          effect: { 
            show: true, 
            period: (params: any) => Math.max(2, 8 / (params.data?.throughput || 1)), 
            trailLength: 0.4, 
            symbol: 'circle', 
            symbolSize: 3, 
            color: '#fff', 
            shadowBlur: 10 
          },
          lineStyle: { 
            width: 2.2, 
            opacity: 0.9, 
            curveness: 0.1, 
            shadowBlur: 8,
            color: 'inherit'
          },
          data: routesData
        },
        {
          name: 'Assets',
          type: 'effectScatter',
          coordinateSystem: 'geo',
          zlevel: 6,
          symbolSize: (p:any) => p[2] === 100 ? 14 : 10,
          rippleEffect: { brushType: 'stroke', scale: 3, period: 4 },
          itemStyle: { color: (params: any) => params.data.type === 'refinery' ? ROSE : GOLD },
          label: {
              show: viewMode === 'MARKET',
              formatter: (params: any) => `$${params.data.price || 74.20}`,
              position: 'top',
              distance: 10,
              color: '#fff',
              backgroundColor: 'rgba(15, 23, 42, 0.8)',
              padding: [4, 6],
              borderRadius: 4,
              fontSize: 10,
              fontFamily: 'monospace',
              fontWeight: 'bold',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1
          },
          data: (riskData?.infrastructure?.hubs || []).map((h: any) => ({
            name: h.name,
            value: [...h.coord, h.id === 'baku' || h.id === 'batumi' ? 100 : 80],
            type: h.type,
            price: h.id === 'batumi' ? 78.4 : h.id === 'baku' ? 74.2 : 75.1,
            storage_telemetry: h.storage_telemetry
          }))
        },
        {
          name: 'StrategyPath',
          type: 'lines',
          coordinateSystem: 'geo',
          zlevel: 10,
          effect: { 
            show: viewMode === 'PROCUREMENT', 
            period: 3, trailLength: 0.5, color: '#fbbf24', symbol: 'arrow', symbolSize: 10 
          },
          lineStyle: { color: '#fbbf24', width: 6, curveness: 0.2, opacity: viewMode === 'PROCUREMENT' ? 0.9 : 0 },
          data: (riskData?.strategy?.optimal_procurement?.path) ? [{
            coords: riskData.strategy.optimal_procurement.path,
            name: 'Recommended Corridor'
          }] : []
        },
        {
          name: 'CompetitorSourcing',
          type: 'lines',
          coordinateSystem: 'geo',
          zlevel: 6,
          lineStyle: { type: 'dashed', width: 2, opacity: viewMode === 'COMPETITOR' ? 0.8 : 0, curveness: 0.2 },
          data: viewMode === 'COMPETITOR' ? (riskData?.competitors || []).map((c: any) => {
              const refinery = riskData?.infrastructure?.hubs?.find((h:any) => h.id === c.refinery_id);
              if (!refinery) return null;
              return {
                  coords: [refinery.coord, [44.82, 41.71]],
                  lineStyle: { color: c.color, shadowBlur: 10, shadowColor: c.color }
              };
          }).filter(Boolean) : []
        }
      ]
    };
  }, [regionStyles, riskData, viewMode, filterTarget, mapFocus]);

  const onEvents = {
    click: (params: any) => {
      if (params.data) {
        setSelectedAsset({ ...params.data, name: params.name });
        setShowTray(true);
      }
    }
  };

  const brentPrice = riskData?.price_signals?.brent?.price || 84.15;
  const wtiPrice = riskData?.price_signals?.wti?.price || 81.20;

  return (
    <div className={`relative ${isMaximized ? 'fixed inset-4 z-[9999] bg-bg overflow-hidden border border-white/10 rounded-2xl shadow-2xl' : 'w-full glass-premium rounded-xl overflow-hidden'}`} style={{ height: isMaximized ? 'calc(100vh - 32px)' : height }}>
      
      {/* HUD HEADER - MODERN HORIZONTAL COMMAND STRIP */}
      <div className="absolute top-6 left-6 right-6 z-[80] flex justify-between items-start pointer-events-none">
          <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2 mb-1">
                <Globe size={14} className="text-accent-op animate-pulse" />
                <span className="text-[10px] font-black tracking-[.4em] uppercase text-accent-op/80 select-none">Strategic Intelligence</span>
              </div>
              <div className="flex items-center gap-2 pointer-events-auto">
                <ModeButton active={viewMode === 'LOGISTICS'} icon={<Globe size={12} />} label="LOGISTICS" onClick={() => setViewMode('LOGISTICS')} />
                <ModeButton active={viewMode === 'RISK'} icon={<Activity size={12} />} label="RISK ENGINE" onClick={() => setViewMode('RISK')} />
                <ModeButton active={viewMode === 'MARKET'} icon={<DollarSign size={12} />} label="PRICES" onClick={() => setViewMode('MARKET')} />
                <ModeButton active={viewMode === 'PROCUREMENT'} icon={<Zap size={12} />} label="SOURCING" onClick={() => setViewMode('PROCUREMENT')} />
                <ModeButton active={viewMode === 'COMPETITOR'} icon={<Target size={12} />} label="RIVALS" onClick={() => setViewMode('COMPETITOR')} />
              </div>
          </div>

          <div className="flex items-center gap-2 pointer-events-auto">
              <button onClick={() => setIsMaximized(!isMaximized)} className="p-2.5 bg-bg3/60 backdrop-blur-xl border border-white/10 rounded-xl text-muted hover:text-white hover:border-accent-op transition-all shadow-xl">
                 {isMaximized ? <X size={18} /> : <Target size={18} />}
              </button>
          </div>
      </div>

      {/* SOVEREIGN MACRO OVERLAY */}
      <SovereignMacroOverlay 
        brent={brentPrice}
        usdGel={riskData?.fx_signals?.usd_gel || 2.68}
        nbgRate={9.0}
        dataQuality="live"
      />

      {mapReady ? (
        <ReactECharts ref={chartRef} option={option} onEvents={onEvents} style={{ height: '100%', width: '100%' }} />
      ) : (
        <div className="h-full flex items-center justify-center text-dim text-xs font-mono uppercase tracking-[0.5em] animate-pulse">Synchronizing Twin...</div>
      )}

      {/* OPERATOR BRIEFING */}
      <div className="absolute bottom-6 right-6 z-[110] pointer-events-none">
          <div className="pointer-events-auto">
              <MapOperatorBriefing 
                isOpen={true} 
                activeCommand={activeCommand} 
                onClose={() => {}} 
              />
          </div>
      </div>

      {/* FOOTER TICKER - UPGRADED WITH LIVE COMMODITY SIGNALS */}
      <div className="absolute bottom-6 left-6 z-[80] glass-premium bg-bg3/70 px-6 py-2.5 rounded-xl border border-white/10 pointer-events-none backdrop-blur-xl flex items-center gap-6 shadow-2xl overflow-hidden max-w-[800px]">
          <div className="flex items-center gap-2 pr-4 border-r border-white/10 flex-shrink-0">
              <span className="text-[10px] text-accent-op font-black uppercase tracking-widest font-mono">LIVE_MARKET_PULSE</span>
          </div>
          
          <div className="flex items-center gap-8 overflow-x-auto no-scrollbar whitespace-nowrap">
              {riskData?.market_pulse && riskData.market_pulse.length > 0 ? (
                  riskData.market_pulse.map((pulse: any, idx: number) => (
                      <div key={idx} className="flex items-center gap-4 animate-in fade-in slide-in-from-right duration-700" style={{ animationDelay: `${idx * 150}ms` }}>
                          <span className="text-[9px] text-muted font-black uppercase tracking-tight">{pulse.exchange?.split(' ')[0]}</span>
                          <div className="text-[11px] font-bold text-heading font-mono">${(pulse.price || 84.15).toFixed(2)}</div>
                          <div className={`flex items-center gap-1 text-[9px] font-black ${(pulse.change || 0) >= 0 ? 'text-emerald' : 'text-rose'}`}>
                              {(pulse.change || 0) >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                              {Math.abs(pulse.change || 0).toFixed(2)}%
                          </div>
                      </div>
                  ))
              ) : (
                  <>
                      <div className="flex items-center gap-3">
                          <span className="text-[9px] text-muted font-black uppercase tracking-tighter">Brent</span>
                          <div className="text-[11px] font-bold text-heading font-mono">${brentPrice.toFixed(2)}</div>
                          <TrendingUp size={12} className="text-emerald" />
                      </div>
                      <div className="flex items-center gap-3">
                          <span className="text-[9px] text-muted font-black uppercase tracking-tighter">WTI</span>
                          <div className="text-[11px] font-bold text-heading font-mono">${wtiPrice.toFixed(2)}</div>
                          <TrendingUp size={12} className="text-emerald" />
                      </div>
                  </>
              )}
          </div>

          <div className="flex items-center gap-3 pl-4 border-l border-white/10 flex-shrink-0">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
              <span className="text-[10px] text-heading font-black font-mono tracking-tighter uppercase">{lastRefresh?.toLocaleTimeString() || 'SYNCING'}</span>
          </div>
      </div>

      <TacticalRolloutTray 
        asset={selectedAsset} 
        isOpen={showTray} 
        onClose={() => setShowTray(false)} 
        viewMode={viewMode}
      />
    </div>
  );
}
