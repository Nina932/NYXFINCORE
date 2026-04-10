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

/* ─── Color Palette — Palantir: muted, corporate ─── */
const GOLD       = 'rgba(168, 144, 96, 0.65)';
const EMERALD    = '#3d9970';
const ROSE       = '#c0392b';
const ORANGE     = '#d4a04a';
const SKY        = '#5b8def';
const SLATE_FILL = 'rgba(100, 116, 139, 0.05)';
const BORDER_CLR = 'rgba(148, 163, 184, 0.12)';

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
    className={`px-3 py-1.5 rounded text-[9px] font-bold transition-all text-left flex items-center gap-2 pointer-events-auto backdrop-blur-sm ${active ? 'bg-accent-op/15 text-accent-op border border-accent-op/30' : 'bg-bg3/40 text-muted hover:bg-bg2/60 border border-white/5 opacity-80 hover:opacity-100'}`}
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
                                className="h-full bg-emerald" 
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
                            <div className="w-1.5 h-10 bg-emerald rounded-full " />
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
  const [mapFocus, setMapFocus] = useState<{center: [number, number], zoom: number}>({ center: [38, 41.5], zoom: 5.0 });
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

      // ── Reactive Intent → View Mode Switching ──
      const intent = activeCommand.intent || '';
      if (intent === 'RISK_SCAN')                                    setViewMode('RISK');
      else if (intent === 'PRICE_INTEL')                             setViewMode('MARKET');
      else if (intent === 'COMPETITOR_INTEL')                        setViewMode('COMPETITOR');
      else if (intent === 'SHOW_TRANSITS' || intent === 'LOGISTICS') setViewMode('LOGISTICS');
      else if (intent === 'OIL_DISTRIBUTION' || intent === 'PROCUREMENT') setViewMode('PROCUREMENT');

      // ── Keyword & Context Detection for camera/filter ──
      const lowerRation = activeCommand.rationale?.toLowerCase() || "";
      if (lowerRation.includes('gas') || intent.includes('GAS')) {
          setFilterTarget('gas');
          setMapFocus({ center: [43, 41], zoom: 6.5 }); // Zoom to Caucasus/pipelines
      } else if (lowerRation.includes('crude')) {
          setFilterTarget('crude');
          setMapFocus({ center: [35, 38], zoom: 5.5 });
      } else if (intent === 'COMPETITOR_INTEL') {
          setFilterTarget('all');
          setMapFocus({ center: [36, 41], zoom: 3.8 }); // Wide view to see all competitor routes
      } else if (intent === 'OIL_DISTRIBUTION' || intent === 'PROCUREMENT') {
          setFilterTarget('all');
          setMapFocus({ center: [40, 40], zoom: 3.5 }); // Wide for supplier routes
      } else {
          setFilterTarget('all');
      }

      // Show toast notification for map mode change
      const modeLabels: Record<string, string> = {
        'RISK_SCAN': '🔴 RISK ENGINE',
        'PRICE_INTEL': '💰 MARKET PRICES',
        'COMPETITOR_INTEL': '🎯 RIVALS OVERLAY',
        'SHOW_TRANSITS': '🌐 LOGISTICS',
        'OIL_DISTRIBUTION': '⚡ SOURCING',
      };
      const label = modeLabels[intent];
      if (label) toast.info(`Map: ${label} activated`, { duration: 3000 });

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
    // ── Route type visual encoding ──
    // Pipeline: solid line, thicker    | Maritime: dashed, medium  | Rail: dotted, thin
    const TYPE_STYLE: Record<string, {dash: number[], width: number, symbol: string}> = {
      'crude_pipeline': { dash: [],       width: 2.5, symbol: 'circle' },
      'gas_pipeline':   { dash: [],       width: 2.0, symbol: 'circle' },
      'tanker_route':   { dash: [8, 4],   width: 1.5, symbol: 'triangle' },
      'rail':           { dash: [3, 3],   width: 1.5, symbol: 'diamond' },
    };
    const TYPE_COLOR: Record<string, string> = {
      'crude':  '#5b8def',  // blue for crude pipelines
      'gas':    'rgba(168, 144, 96, 0.8)', // gold for gas
      'cargo':  '#7a8a9e',  // muted steel for maritime
      'rail':   '#8e7cc3',  // subtle purple for rail
    };

    const routesData = (riskData?.infrastructure?.routes || []).filter((r: any) =>
        filterTarget === 'all' || r.commodity === filterTarget
    ).map((r: any) => {
        const isCritical = r.status === 'CRITICAL' || (riskData?.sim_active && r.name.includes('Black Sea'));
        const style = TYPE_STYLE[r.type] || TYPE_STYLE['tanker_route'];
        const baseColor = isCritical ? ROSE : (TYPE_COLOR[r.commodity] || SKY);
        return {
            name: r.name,
            coords: r.coords,
            routeType: r.type,
            commodity: r.commodity,
            throughput: r.throughput_actual || 1.0,
            status: r.status,
            health_score: r.health_score,
            utilization_pct: r.utilization_pct,
            pressure_bar: r.pressure_bar,
            capacity: r.capacity_mbtu,
            lineStyle: {
                color: baseColor,
                width: isCritical ? style.width + 1 : style.width,
                type: style.dash.length ? style.dash : 'solid',
                opacity: isCritical ? 0.9 : 0.65,
            },
        };
    });

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(11, 14, 20, 0.95)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        textStyle: { color: '#c5cdd8', fontSize: 10, fontFamily: 'var(--font-mono)' },
        formatter: (params: any) => {
            if (params.seriesName === 'Assets') {
                const h = params.data;
                const typeLabel: Record<string, string> = { extraction: 'Extraction Hub', refinery: 'Refinery', port: 'Port Terminal', command: 'Command Center' };
                const storage = h.storage_telemetry ? `<br/>Storage: <b>${(h.storage_telemetry.current_fill * 100).toFixed(0)}%</b> of ${(h.storage_telemetry.capacity_bbl/1e6).toFixed(1)}M BBL` : '';
                return `<div style="padding:6px;font-size:10px;font-family:var(--font-mono)"><b>${params.name}</b><br/><span style="color:#8692a2">${typeLabel[h.type] || h.type}</span>${storage}</div>`;
            }
            // Route tooltip — show type, status, throughput
            const d = params.data || {};
            const typeLabel: Record<string, string> = { crude_pipeline: '● Pipeline (crude)', gas_pipeline: '● Pipeline (gas)', tanker_route: '- - Maritime lane', rail: '··· Railway' };
            const statusColors: Record<string, string> = { NOMINAL: '#3d9970', WATCH: '#d4a04a', CRITICAL: '#c0392b' };
            const statusColor = statusColors[d.status] || '#8692a2';
            return `<div style="padding:8px;font-size:10px;font-family:var(--font-mono);min-width:180px">` +
              `<b>${params.name}</b><br/>` +
              `<span style="color:#8692a2">${typeLabel[d.routeType] || d.routeType || ''}</span><br/>` +
              `<span style="color:${statusColor};font-weight:600">Status: ${d.status || '—'}</span>` +
              (d.health_score != null ? ` · Health ${d.health_score}%` : '') +
              (d.throughput ? `<br/>Throughput: ${d.throughput.toFixed(2)} M/d` : '') +
              (d.utilization_pct ? ` · Util: ${d.utilization_pct}%` : '') +
              (d.pressure_bar ? `<br/>Pressure: ${d.pressure_bar} bar` : '') +
              `</div>`;
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
        // Infrastructure routes — type-differentiated rendering (no animation for clean Palantir look)
        {
          name: 'Routes',
          type: 'lines',
          coordinateSystem: 'geo',
          polyline: true,
          zlevel: 5,
          effect: {
            show: false,
          },
          lineStyle: {
            width: 1.8,
            opacity: 0.6,
            color: 'inherit',
          },
          data: routesData,
        },
        {
          name: 'Assets',
          type: 'scatter',
          coordinateSystem: 'geo',
          zlevel: 6,
          symbolSize: (p:any) => p[2] === 100 ? 12 : 9,
          itemStyle: {
            color: (params: any) => {
              const t = params.data.type;
              if (t === 'refinery') return '#c0392b';
              if (t === 'port') return '#5b8def';
              if (t === 'command') return '#3d9970';
              return 'rgba(168, 144, 96, 0.8)';
            },
            borderColor: 'rgba(255,255,255,0.15)',
            borderWidth: 1,
          },
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
          effect: { show: false },
          lineStyle: { color: '#d4a04a', width: 3, curveness: 0.2, opacity: viewMode === 'PROCUREMENT' ? 0.75 : 0 },
          data: (riskData?.strategy?.optimal_procurement?.path) ? [{
            coords: riskData.strategy.optimal_procurement.path,
            name: 'Recommended Corridor'
          }] : []
        },
        {
          name: 'CompetitorRoutes',
          type: 'lines',
          coordinateSystem: 'geo',
          zlevel: 6,
          polyline: true,
          effect: { show: false },
          lineStyle: { type: 'dashed', width: 2, opacity: viewMode === 'COMPETITOR' ? 0.7 : 0 },
          data: viewMode === 'COMPETITOR' ? (riskData?.competitors || []).flatMap((c: any) =>
              (c.routes || []).map((route: any) => {
                  // Use actual multi-waypoint route coords from competitor data
                  const coords = route.coords;
                  if (!coords || coords.length < 2) return null;
                  // For ECharts lines, we need sequential coordinate pairs
                  // Build segments from waypoint chain
                  return {
                      coords: coords,
                      name: `${c.short_name || c.name}: ${route.name}`,
                      lineStyle: {
                          color: c.color,
                          shadowBlur: 0,
                          width: route.type === 'pipeline' ? 3.5 : route.type === 'maritime' ? 2.5 : 2,
                          type: route.type === 'pipeline' ? 'solid' : route.type === 'maritime' ? 'dashed' : 'dotted',
                      }
                  };
              }).filter(Boolean)
          ) : []
        },
        // Competitor supplier origin points (shown as scatter when in COMPETITOR mode)
        {
          name: 'CompetitorSuppliers',
          type: 'scatter',
          coordinateSystem: 'geo',
          zlevel: 7,
          symbol: 'diamond',
          symbolSize: viewMode === 'COMPETITOR' ? 9 : 0,
          itemStyle: { color: ORANGE, borderColor: 'rgba(255,255,255,0.15)', borderWidth: 1 },
          label: {
            show: viewMode === 'COMPETITOR',
            formatter: (p: any) => p.name,
            fontSize: 8, fontWeight: 'bold', color: '#fff',
            position: 'right', distance: 8,
          },
          data: viewMode === 'COMPETITOR' ? (riskData?.competitors || []).flatMap((c: any) =>
              (c.suppliers || []).map((s: any) => ({
                name: `${s.name}`,
                value: [...s.coords, 60],
                itemStyle: { color: c.color },
              }))
          ) : []
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
                <Globe size={14} className="text-accent-op" />
                <span className="text-[9px] font-semibold tracking-[.3em] uppercase text-muted select-none">Strategic Intelligence</span>
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

      {/* ROUTE LEGEND — Explains line types */}
      {viewMode === 'LOGISTICS' && (
        <div className="absolute bottom-20 left-6 z-[80] bg-bg1/90 backdrop-blur-sm px-4 py-3 rounded border border-white/6 pointer-events-none">
          <div className="text-[8px] font-semibold text-muted uppercase tracking-[.15em] mb-2">Route Types</div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2">
              <div className="w-8 h-0 border-t-2 border-solid" style={{ borderColor: '#5b8def' }} />
              <span className="text-[9px] text-dim">Crude Pipeline</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0 border-t-2 border-solid" style={{ borderColor: 'rgba(168, 144, 96, 0.8)' }} />
              <span className="text-[9px] text-dim">Gas Pipeline</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0 border-t-2 border-dashed" style={{ borderColor: '#7a8a9e' }} />
              <span className="text-[9px] text-dim">Maritime Lane</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-0 border-t-2 border-dotted" style={{ borderColor: '#8e7cc3' }} />
              <span className="text-[9px] text-dim">Railway</span>
            </div>
          </div>
        </div>
      )}
      {viewMode === 'COMPETITOR' && (
        <div className="absolute bottom-20 left-6 z-[80] bg-bg1/90 backdrop-blur-sm px-4 py-3 rounded border border-white/6 pointer-events-none">
          <div className="text-[8px] font-semibold text-muted uppercase tracking-[.15em] mb-2">Competitors</div>
          <div className="flex flex-col gap-1.5">
            {(riskData?.competitors || []).map((c: any) => (
              <div key={c.id} className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ background: c.color }} />
                <span className="text-[9px] text-dim">{c.short_name || c.name} ({(c.market_share * 100).toFixed(0)}%)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FOOTER TICKER */}
      <div className="absolute bottom-6 left-6 z-[80] bg-bg1/85 backdrop-blur-sm px-4 py-2 rounded border border-white/6 pointer-events-none flex items-center gap-6 overflow-hidden max-w-[700px]">
          <div className="flex items-center gap-2 pr-3 border-r border-white/8 flex-shrink-0">
              <span className="text-[9px] text-muted font-semibold uppercase tracking-wider font-mono">Market</span>
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
              <div className="w-1.5 h-1.5 rounded-full bg-emerald" />
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
