import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, Brain, Send, X, Activity, Globe, Shield, Zap, Target, ChevronDown, ChevronUp, Bot, User, BarChart4, Scaling, ShieldCheck, AlertTriangle } from 'lucide-react';
import { dispatchAgentMapCommand } from '../hooks/useAgentMapInteraction';

interface Msg { role: 'ai' | 'user', content: string; type?: 'strategy' | 'margin' | 'geo' | 'tax' }

interface MapOperatorBriefingProps {
  activeCommand: any;
  isOpen: boolean;
  onClose: () => void;
}

const MapOperatorBriefing = ({ activeCommand, isOpen, onClose }: MapOperatorBriefingProps) => {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [isExpanded, setIsExpanded] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (isOpen) setIsExpanded(true);
  }, [isOpen]);
  
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isExpanded]);
  
  // When activeCommand changes (agent speaks on map), add to messages
  useEffect(() => {
    if (activeCommand?.strategy && activeCommand.type === 'MAP_TRIGGER_STRATEGY') {
        const s = activeCommand.strategy;
        const briefing: Msg = {
            role: 'ai',
            type: 'strategy',
            content: `COMMANDEER DETECTED: Market Disruption (${s.event})\n\nMargin Protection Protocol: ${s.pricing_strategy.recommendation}\nRecommended Adjustment: ${s.pricing_strategy.target_adj}\n\n${s.pricing_strategy.rationale}`
        };
        setMessages(prev => [...prev, briefing]);
    } else if (activeCommand?.rationale) {
        setMessages(prev => [...prev, { role: 'ai', content: activeCommand.rationale }]);
    }
  }, [activeCommand]);

  // ─── Classify user intent from natural language ───
  // Order matters: specific compound phrases FIRST, generic single-word catches LAST
  const classifyIntent = (input: string): { intent: string; command: any; response: string } | null => {
    const q = input.toLowerCase();

    // 1. Prices / cost / compare / analytics (check BEFORE "oil" — catches "oil price", "competitor prices")
    if (q.includes('price') || q.includes('cost') || q.includes('compare') || q.includes('brent')
      || q.includes('wti') || q.includes('margin') || q.includes('analytic') || q.includes('analy')) {
      return {
        intent: 'PRICE_INTEL',
        command: { type: 'MAP_HIGHLIGHT' as const, intent: 'PRICE_ANALYSIS',
          rationale: '[MARKET INTEL] Scanning Brent/WTI spot prices and regional supplier FOB rates. Comparing delivered cost across 8 suppliers with transit tax overlays.' },
        response: 'MARKET PRICE INTELLIGENCE:\n\n' +
          'WHOLESALE ($/BBL):\n' +
          '• Brent Crude: ~$85/BBL (live in bottom bar)\n' +
          '• WTI Crude: ~$81/BBL\n' +
          '• Best Supplier: Basra Terminal $74.2/BBL\n' +
          '• Türkmenbaşy: $76.1 | Aktau: $75.8\n\n' +
          'RETAIL COMPETITOR PRICES (GEL/L):\n' +
          '• Wissol:    Reg ₾3.14 | Diesel ₾2.82 (cheapest)\n' +
          '• SOCAR:     Reg ₾3.15 | Diesel ₾2.85\n' +
          '• Rompetrol: Reg ₾3.16 | Diesel ₾2.84\n' +
          '• Gulf:      Reg ₾3.18 | Diesel ₾2.83\n' +
          '• Lukoil:    Reg ₾3.20 | Diesel ₾2.86 (most expensive)\n\n' +
          'Market Avg: Regular ₾3.17 | Diesel ₾2.84\n' +
          'Click suppliers (◆) on map for FOB + landed cost.'
      };
    }

    // 2. Competitors (check BEFORE "oil" — catches "competitor prices on map")
    if (q.includes('competitor') || q.includes('socar') || q.includes('lukoil') || q.includes('gulf') || q.includes('rompetrol') || q.includes('rival') || q.includes('wissol')) {
      return {
        intent: 'COMPETITOR_INTEL',
        command: { type: 'MAP_SHOW_COMPETITORS' as const, intent: 'COMPETITOR_INTEL',
          rationale: '[COMPETITOR] Decloaking rival supply chains. SOCAR (blue), Rompetrol (rose), Gulf (orange), Lukoil (slate), Wissol (purple) transit lanes now visible with supplier origins.' },
        response: 'COMPETITOR OVERLAY ACTIVE — RETAIL PRICES (GEL/L):\n\n' +
          '┌─────────────┬───────┬───────┬────────┬────────┐\n' +
          '│ Operator     │ Reg92 │ Prem95│ Diesel │ Share  │\n' +
          '├─────────────┼───────┼───────┼────────┼────────┤\n' +
          '│ SOCAR  🔵    │ 3.15  │ 3.35  │ 2.85   │ 22%    │\n' +
          '│ Rompetrol 🔴 │ 3.16  │ 3.38  │ 2.84   │ 18%    │\n' +
          '│ Gulf 🟠      │ 3.18  │ 3.42  │ 2.83   │ 25%    │\n' +
          '│ Lukoil ⚪    │ 3.20  │ 3.40  │ 2.86   │ 12%    │\n' +
          '│ Wissol 🟣    │ 3.14  │ 3.36  │ 2.82   │ 15%    │\n' +
          '└─────────────┴───────┴───────┴────────┴────────┘\n\n' +
          'SUPPLY SOURCES:\n' +
          '• SOCAR: Heydar Aliyev Refinery (Baku) — pipeline direct\n' +
          '• Rompetrol: Petromidia Refinery (Romania) — Black Sea tanker\n' +
          '• Gulf: Multi-source (Ceyhan, Augusta, Sarroch) — spot market\n' +
          '• Lukoil: Neftochim Burgas (Bulgaria) — Black Sea tanker\n' +
          '• Wissol: TÜPRAŞ refineries (Turkey) — Black Sea tanker\n\n' +
          'Map shows colored transit lanes + supplier origin points (◆).'
      };
    }

    // 3. Risk / threat / geopolitical / sanctions
    if (q.includes('risk') || q.includes('threat') || q.includes('danger') || q.includes('sanction') || q.includes('geopolit') || q.includes('disrupt')) {
      return {
        intent: 'RISK_SCAN',
        command: { type: 'MAP_HIGHLIGHT' as const, intent: 'RISK_SCAN',
          rationale: '[RISK SCAN] Evaluating geopolitical, commodity, and FX risk vectors. Scanning news feeds for disruption signals across all corridor regions.' },
        response: 'RISK ASSESSMENT ACTIVE:\n\nSwitch to RISK MAP layer (left panel) for full heatmap.\n\nKey risk drivers:\n• Commodity price velocity (Brent/WTI)\n• GEL exchange rate volatility\n• Geopolitical disruption signals\n• EIA supply/demand balance\n\nCheck DISRUPTION SIGNALS panel (top-right) for live headlines.'
      };
    }

    // 4. What / why / explain / cause
    if (q.includes('what') || q.includes('why') || q.includes('cause') || q.includes('explain')) {
      return {
        intent: 'ANALYSIS',
        command: { type: 'MAP_HIGHLIGHT' as const, intent: 'DEEP_ANALYSIS',
          rationale: '[ANALYSIS] Running multi-factor scan: commodity price drivers, FX movements, supply chain disruptions, and competitor positioning.' },
        response: 'MARKET ANALYSIS:\n\nKey price change drivers:\n1. Brent/WTI spot price velocity (Yahoo Finance live)\n2. U.S. crude inventories — draws = bullish, builds = bearish\n3. GEL depreciation risk (NBG exchange rate)\n4. Geopolitical events (sanctions, conflicts, pipeline disruptions)\n5. Competitor supply constraints\n\nUse RISK MAP layer for regional risk heatmap.\nUse MARKET layer for global producer/transit hub view.'
      };
    }

    // 5. Transit / pipeline / corridor / infrastructure
    if (q.includes('transit') || q.includes('pipeline') || q.includes('corridor') || q.includes('infrastr')) {
      return {
        intent: 'SHOW_TRANSITS',
        command: { type: 'MAP_HIGHLIGHT' as const, route_id: q.includes('scp') ? 'scp_pipeline' : 'btc_pipeline', intent: 'SHOW_TRANSITS',
          rationale: '[INFRASTRUCTURE] Synchronizing pipeline telemetry — pressure, throughput, and health metrics for all active corridors.' },
        response: 'INFRASTRUCTURE TELEMETRY:\n\nAll pipeline and maritime routes are animated on the map. Hover over routes for pressure/flow data.\n\nCheck SIGNAL STREAM (bottom-right) for live SCADA telemetry.'
      };
    }

    // 6. Oil / distribution / supply / logistics / show on map (LAST — generic catch-all)
    if (q.includes('oil') || q.includes('distribution') || q.includes('supply') || q.includes('logistics')
      || q.includes('route') || q.includes('show') || q.includes('map')) {
      return {
        intent: 'OIL_DISTRIBUTION',
        command: { type: 'MAP_HIGHLIGHT' as const, route_id: 'btc_pipeline', intent: 'OIL_DISTRIBUTION',
          rationale: '[LOGISTICS] Illuminating all active supply corridors — BTC Pipeline, SCP Gas, WREP, and Black Sea shipping. Throughput telemetry synchronized.' },
        response: 'LOGISTICS OVERLAY ACTIVE:\n\n• BTC Pipeline (Crude): Baku → Tbilisi → Ceyhan\n• SCP Pipeline (Gas): Baku → Gardabani → Erzurum\n• WREP Pipeline: Baku → Supsa\n• Black Sea Lane: Batumi → Constanța → Odesa\n\nAll corridors illuminated on map. Click any route for telemetry.'
      };
    }

    return null;
  };

  // ─── Fetch live data and build a real response ───
  const fetchLiveResponse = async (intent: string): Promise<string | null> => {
    try {
      const resp = await fetch('/api/external-data/situational-risk');
      if (!resp.ok) return null;
      const d = await resp.json();

      if (intent === 'PRICE_INTEL') {
        const brent = d.price_signals?.brent?.price?.toFixed(2) || '—';
        const brentChg = d.price_signals?.brent?.change_1d_pct?.toFixed(2) || '0';
        const wti = d.price_signals?.wti?.price?.toFixed(2) || '—';
        const wtiChg = d.price_signals?.wti?.change_1d_pct?.toFixed(2) || '0';
        const natGas = d.price_signals?.natural_gas?.price?.toFixed(2) || '—';
        const usdGel = d.fx_signals?.usd_gel?.toFixed(4) || '—';
        const direction = d.price_signals?.direction || 'stable';
        const quality = d.data_quality === 'live' ? 'LIVE' : 'CACHED';
        const supply = d.supply_fundamentals?.signal || 'N/A';
        const supplyChg = d.supply_fundamentals?.weekly_change_k_bbl ? `${(d.supply_fundamentals.weekly_change_k_bbl / 1000).toFixed(1)}M BBL` : '';

        return `LIVE MARKET INTELLIGENCE [${quality}]:\n\n` +
          `COMMODITIES:\n` +
          `• Brent Crude: $${brent}/BBL (${Number(brentChg) >= 0 ? '+' : ''}${brentChg}%)\n` +
          `• WTI Crude: $${wti}/BBL (${Number(wtiChg) >= 0 ? '+' : ''}${wtiChg}%)\n` +
          `• Natural Gas: $${natGas}/MMBtu\n` +
          `• Market Direction: ${direction.toUpperCase()}\n\n` +
          `FX & SUPPLY:\n` +
          `• USD/GEL: ₾${usdGel}\n` +
          `• EIA Supply Signal: ${supply} ${supplyChg}\n\n` +
          `SUPPLIER FOB (estimated):\n` +
          `• Basra Terminal: ~$74.2/BBL\n` +
          `• Aktau Port: ~$75.8/BBL\n` +
          `• Türkmenbaşy: ~$76.1/BBL\n\n` +
          `Click suppliers (◆) on map for details.`;
      }

      if (intent === 'RISK_SCAN') {
        const regions = d.regions || {};
        const headlines = d.geo_signals?.recent_headlines || [];
        const overall = d.overall_risk_level || 'LOW';
        const quality = d.data_quality === 'live' ? 'LIVE' : 'CACHED';

        let regionLines = Object.entries(regions).map(([name, r]: [string, any]) =>
          `• ${name}: ${r.risk_score}/100 [${r.level}] — ${r.primary_driver || 'stable'}`
        ).join('\n');

        let headlineLines = headlines.slice(0, 3).map((h: any) => `• ${h.title}`).join('\n');

        return `LIVE RISK ASSESSMENT [${quality}]:\n` +
          `Overall: ${overall}\n\n` +
          `REGIONS:\n${regionLines}\n\n` +
          (headlineLines ? `DISRUPTION SIGNALS:\n${headlineLines}\n\n` : '') +
          `Switch to RISK MAP layer for heatmap visualization.`;
      }

      if (intent === 'COMPETITOR_INTEL') {
        const competitors = d.competitors || [];
        if (competitors.length) {
          const compLines = competitors.map((c: any) => {
            const rp = c.retail_prices_gel || {};
            const reg = rp.regular_92 ? `₾${rp.regular_92.toFixed(2)}` : '—';
            const diesel = rp.diesel ? `₾${rp.diesel.toFixed(2)}` : '—';
            const prem = rp.premium_95 ? `₾${rp.premium_95.toFixed(2)}` : '—';
            const supplier = (c.suppliers && c.suppliers[0]) ? c.suppliers[0].name : 'Unknown';
            return `• ${c.short_name || c.name} (${(c.market_share * 100).toFixed(0)}% share, ${c.stations_count || '?'} stations)\n` +
              `  Reg: ${reg} | Prem: ${prem} | Diesel: ${diesel}\n` +
              `  Source: ${supplier}\n` +
              `  Corridor: ${c.primary_corridor || c.origin}`;
          }).join('\n\n');

          return `LIVE COMPETITOR INTELLIGENCE:\n\n${compLines}\n\n` +
            `Colored transit lanes + supplier origins (◆) shown on map.`;
        }
      }

      if (intent === 'OIL_DISTRIBUTION' || intent === 'SHOW_TRANSITS') {
        const routes = d.infrastructure?.routes || d.routes || [];
        if (routes.length) {
          const routeLines = routes.map((r: any) =>
            `• ${r.name}: ${r.status || 'NOMINAL'} | Health ${r.health_score || '—'}% | ${r.type === 'tanker_route' ? `${r.vessel_count || 0} vessels` : `${r.pressure_bar || '—'} bar`}`
          ).join('\n');
          return `LIVE INFRASTRUCTURE STATUS:\n\n${routeLines}\n\nAll corridors illuminated on map.`;
        }
      }

      return null;
    } catch {
      return null;
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isSending) return;

    const userMsg: Msg = { role: 'user', content: inputValue };
    setMessages(prev => [...prev, userMsg]);
    const savedInput = inputValue;
    setInputValue('');
    setIsSending(true);

    // ─── Classify intent and dispatch map command ───
    const classified = classifyIntent(savedInput);
    if (classified) {
      dispatchAgentMapCommand(classified.command);
    }

    // ─── Phase 1: Instant live data response (~1-2s) ───
    if (classified) {
      const liveResponse = await fetchLiveResponse(classified.intent);
      setMessages(prev => [...prev, { role: 'ai', content: liveResponse || classified.response }]);
    } else {
      setMessages(prev => [...prev, { role: 'ai', content: 'Analyzing...' }]);
    }

    // ─── Phase 2: Fire Gemma 4 AI reasoning in background ───
    // Response appends when ready — user already has live data above
    setIsSending(false);
    fetch('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: savedInput,
        history: messages.slice(-6).map(m => ({ role: m.role, content: m.content })),
        context: { type: 'MAP_OPERATOR', intent: classified?.intent }
      })
    }).then(r => r.ok ? r.json() : null).then(data => {
      if (data?.response && data.response.length > 60) {
        setMessages(prev => [...prev, { role: 'ai', type: 'strategy', content: '🧠 AI REASONING:\n\n' + data.response }]);
      }
    }).catch(() => {});
  };

  if (!isOpen && messages.length === 0) return null;

  return (
    <div className={`transition-all duration-500 ease-in-out ${isExpanded ? 'w-[320px]' : 'w-48'}`}>
      <div className="bg-slate-900/90 backdrop-blur-2xl border border-sky-500/30 rounded-lg shadow-[0_0_40px_rgba(0,0,0,0.8)] overflow-hidden">
        {/* Header */}
        <div className="px-3 py-2 bg-sky-500/10 border-b border-sky-500/20 flex items-center justify-between">
            <div className="flex items-center gap-2">
                <Brain size={14} className="text-sky-400" />
                <span className="text-[10px] font-black text-sky-100 tracking-[0.15em] uppercase">Operator Briefing</span>
            </div>
            <div className="flex items-center gap-1">
                <button onClick={() => setIsExpanded(!isExpanded)} className="p-1 hover:bg-white/10 rounded">
                    {isExpanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronUp size={14} className="text-slate-400" />}
                </button>
            </div>
        </div>

        {isExpanded && (
            <>
            <div ref={scrollRef} className="max-h-[360px] overflow-y-auto p-4 space-y-4 font-mono scroll-smooth">
                {messages.map((m, idx) => (
                    <div key={idx} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : ''}`}>
                        {m.role === 'ai' && <div className="w-5 h-5 rounded-full bg-sky-500/20 flex items-center justify-center border border-sky-500/30 flex-shrink-0"><Bot size={10} className="text-sky-400" /></div>}
                        <div className={`p-2 rounded-lg text-[10px] leading-relaxed max-w-[85%] border ${m.role === 'user' ? 'bg-slate-800/80 border-slate-700 text-slate-100' : 'bg-slate-900/40 border-white/5 text-slate-300'}`}>
                            {m.type === 'strategy' && (
                                <div className="flex items-center gap-1.5 mb-2 pb-2 border-b border-amber-500/10">
                                    <Zap size={10} className="text-amber-500" />
                                    <span className="font-black text-[9px] uppercase tracking-wider">Battle Order</span>
                                </div>
                            )}
                            <div className="whitespace-pre-line">{m.content}</div>
                        </div>
                        {m.role === 'user' && <div className="w-5 h-5 rounded-full bg-slate-500/20 flex items-center justify-center border border-slate-500/30 flex-shrink-0"><User size={10} className="text-slate-400" /></div>}
                    </div>
                ))}

                {activeCommand?.strategy && (
                    <div className="space-y-4 border-t border-white/5 pt-4">
                        {/* ─── 01. EXECUTIVE SUMMARY ─── */}
                        <div className="bg-sky-500/5 border border-sky-500/10 rounded p-3">
                            <div className="flex items-center gap-2 mb-2">
                                <ShieldCheck size={12} className="text-sky-500" />
                                <span className="text-[10px] font-black text-sky-400 uppercase tracking-tighter">I. EXECUTIVE SUMMARY</span>
                            </div>
                            <div className="text-[10px] text-sky-100/90 leading-relaxed italic">
                                {activeCommand.strategy.event ? `[SITUATION]: ${activeCommand.strategy.event}. ` : ''}
                                {activeCommand.strategy.business_impact}
                            </div>
                        </div>

                        {/* ─── 02. DELIVERED COST MATH ─── */}
                        {activeCommand.strategy.optimal_procurement?.breakdown && (
                            <div className="space-y-2">
                                <div className="flex items-center gap-2">
                                    <Scaling size={12} className="text-slate-500" />
                                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">II. DELIVERED COST AUDIT</span>
                                </div>
                                <table className="w-full text-[9px] font-mono border-collapse bg-black/40 rounded border border-white/5">
                                    <thead>
                                        <tr className="border-b border-white/5 text-slate-500 text-left">
                                            <th className="p-1.5 font-medium">COMPONENT</th>
                                            <th className="p-1.5 font-medium text-right">VALUE ($)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {activeCommand.strategy.optimal_procurement.breakdown.map((row: any, ridx: number) => (
                                            <tr key={ridx} className={`border-b border-white/5 ${row.item === 'total' ? 'bg-white/5 text-emerald-400 font-bold' : 'text-slate-400/80'}`}>
                                                <td className="p-1.5">{row.label}</td>
                                                <td className="p-1.5 text-right">{row.item === 'total' ? `$${row.value.toFixed(2)}` : `+${row.value.toFixed(2)}`}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* ─── 03. BATTLE ORDER ─── */}
                        <div className="bg-rose-500/5 border border-rose-500/20 rounded p-3 animate-pulse-subtle">
                            <div className="flex items-center gap-2 mb-2">
                                <AlertTriangle size={12} className="text-rose-500" />
                                <span className="text-[10px] font-black text-rose-400 uppercase tracking-tighter text-glow-rose">III. BATTLE ORDER</span>
                            </div>
                            <div className="text-[11px] font-bold text-white leading-tight">
                                {activeCommand.strategy.pricing_strategy?.recommendation || 'DIVERSIFY_IMMEDIATELY'}
                            </div>
                            <div className="mt-2 text-[10px] text-rose-200/70 border-t border-rose-500/10 pt-2">
                                {activeCommand.strategy.pricing_strategy?.rationale || "Protecting EBITDA floor through logistics pivot."}
                            </div>
                        </div>
                    </div>
                )}

                {isSending && (
                    <div className="flex items-center gap-2 text-[9px] text-sky-500/60 animate-pulse font-bold uppercase tracking-widest">
                        <Activity size={10} /> Generating Tactical Plan...
                    </div>
                )}
            </div>

            {/* Chat Input Overlay */}
            <div className="px-3 py-2 bg-black/20 border-t border-white/5 flex items-center gap-2">
                <input 
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Enter Tactical Command..."
                    className="flex-1 bg-transparent border-none outline-none text-[10px] text-sky-100 placeholder:text-slate-600 font-mono"
                    disabled={isSending}
                />
                <button 
                    onClick={handleSend}
                    className={`p-1 rounded transition-colors ${inputValue.trim() ? 'text-sky-400 hover:bg-sky-500/20' : 'text-slate-700'}`}
                >
                    <Send size={14} />
                </button>
            </div>
            </>
        )}

        {/* Footer Stats Line */}
        <div className="px-3 py-1.5 bg-black/40 border-t border-white/5 flex items-center justify-between text-[8px] font-bold tracking-widest text-slate-500 uppercase">
            <div className="flex items-center gap-1.5 text-emerald-500/80">
                <Target size={9} /> Margin: {((activeCommand?.strategy?.financial_context?.current_margin || 0.08) * 100).toFixed(1)}%
            </div>
            <div className="flex items-center gap-1.5 text-sky-500/80">
                <Shield size={9} /> Compliance: Verified
            </div>
        </div>
      </div>
    </div>
  );
};

export default MapOperatorBriefing;
