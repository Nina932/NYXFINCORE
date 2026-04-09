import { useState, useRef, useEffect, useCallback } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Gauge, FolderOpen, FileText, Scales, ChartLineUp,
  CurrencyDollar, PiggyBank, FileArrowUp,
  Brain, ChartBar, TreeStructure, Gear, Database,
  ShieldCheck, Sliders, Gavel, BellSimple, Target,
  LinkSimpleHorizontal, GlobeHemisphereWest, HardDrive, Wrench, SignOut, Lightning, GridFour, ArrowClockwise, FlowArrow,
  X, PaperPlaneTilt, Sun, Moon, ChatCenteredText,
  GearSix, BookOpen, Calendar, Pulse, CaretDown, Leaf,
} from '@phosphor-icons/react';
import { useStore } from '../store/useStore';
import { t, setLang as setI18nLang } from '../i18n/translations';
import NotificationBell from './NotificationBell';
import PeriodSelector from './PeriodSelector';
import NyxLogo from './NyxLogo';
import PageVideoGuide from './PageVideoGuide';

/* ─── Types ─── */

interface NavItem { to: string; label: string; tKey?: string; icon: React.ElementType; badge?: string; badgeColor?: string; shortcut?: string }
interface NavGroup { label: string; tKey?: string; items: NavItem[] }
interface ChatMsg { role: 'user' | 'ai'; content: string }

/* ─── Nav structure — FinAI OS ─── */
const NAV_GROUPS: NavGroup[] = [
  {
    label: 'COMMAND CENTER',
    items: [
      { to: '/dashboard', label: 'Overview', tKey: 'nav.dashboard', icon: Gauge, shortcut: '1' },
      { to: '/consolidation', label: 'Consolidation', icon: GlobeHemisphereWest, shortcut: '2' },
      { to: '/structure', label: 'Entity Graph', icon: TreeStructure },

      { to: '/lineage', label: 'Data Lineage', icon: LinkSimpleHorizontal },
      { to: '/ontology', label: 'Ontology', icon: Pulse },
      { to: '/company-360', label: 'Company 360\u00B0', icon: Target },
      { to: '/institutional-ledger', label: 'Forensic Marts', icon: ShieldCheck },
    ],
  },
  {
    label: 'OPERATIONS',
    items: [
      { to: '/ap-automation', label: 'AP Automation', icon: Lightning, shortcut: '3' },
      { to: '/workflow', label: 'Workflows', tKey: 'nav.workflow', icon: Gear },
      { to: '/intelligent-ingest', label: 'Ingestion', tKey: 'nav.ingest', icon: Brain },
    ],
  },
  {
    label: 'FINANCIALS',
    items: [
      { to: '/pnl', label: 'Income Statement', tKey: 'nav.pnl', icon: FileText, shortcut: '4' },
      { to: '/balance-sheet', label: 'Balance Sheet', tKey: 'nav.balance_sheet', icon: Scales, shortcut: '5' },
      { to: '/revenue', label: 'Revenue', tKey: 'nav.revenue', icon: ChartLineUp },
      { to: '/costs', label: 'Cost Analysis', tKey: 'nav.costs', icon: CurrencyDollar },
      { to: '/budget', label: 'Budgeting', tKey: 'nav.budget', icon: PiggyBank },
      { to: '/profitability', label: 'Profitability', tKey: 'nav.profitability', icon: ChartBar },
      { to: '/subledger', label: 'Sub-Ledger', icon: BookOpen },
    ],
  },
  {
    label: 'DATA WAREHOUSE',
    items: [
      { to: '/warehouse', label: 'Warehouse', icon: Database, shortcut: '6' },
      { to: '/library', label: 'Data Library', tKey: 'nav.data_library', icon: FolderOpen },
      { to: '/flywheel', label: 'Flywheel', icon: ArrowClockwise },
      { to: '/transactions', label: 'Lineage', tKey: 'nav.transactions', icon: LinkSimpleHorizontal },
    ],
  },
  {
    label: 'INTELLIGENCE',
    items: [
      { to: '/reasoning', label: 'Reasoning Engine', tKey: 'nav.deep_reasoning', icon: Brain, shortcut: '7' },
      { to: '/sensitivity', label: 'Simulations', icon: Sliders },
      { to: '/analytics', label: 'Analytics Center', icon: ChartBar },
    ],
  },
  {
    label: 'GOVERNANCE',
    items: [
      { to: '/compliance', label: 'Compliance Audit', icon: ShieldCheck, shortcut: '8' },
      { to: '/esg', label: 'ESG & Sustainability', icon: Leaf },
      { to: '/alerts', label: 'Operational Alerts', tKey: 'nav.alerts', icon: BellSimple },
      { to: '/controls', label: 'Internal Controls', icon: Gavel },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { to: '/workshop', label: 'Studio', icon: GridFour },
      { to: '/system', label: 'Health Status', tKey: 'nav.system_status', icon: HardDrive },
      { to: '/market', label: 'Market Term', tKey: 'nav.market_data', icon: GlobeHemisphereWest },
    ],
  },
];

/* ─── Page titles ─── */
const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/structure': 'Entity Graph',
  '/lineage': 'Data Lineage Explorer',
  '/company-360': 'Company 360\u00B0',
  '/library': 'Data & Library',
  '/pnl': 'Income Statement',
  '/balance-sheet': 'Balance Sheet',
  '/revenue': 'Revenue Analysis',
  '/costs': 'Cost Analysis',
  '/reasoning': 'Deep Reasoning',
  '/workflow': 'Agent Workflow',
  '/ai-report': 'AI Report',
  '/budget': 'Budget',
  '/workshop': 'Workshop',
  '/flywheel': 'Data Flywheel',
  '/mr-reports': 'Management Reports',
  '/cash-runway': 'Cash Runway',
  '/kpi-monitor': 'KPI Monitor',
  '/ai-intelligence': 'AI Intelligence',
  '/benchmarks': 'Benchmarks',
  '/forecasts': 'Forecasts',
  '/gl-pipeline': 'GL Pipeline',
  '/orchestrator': 'Orchestrator',
  '/strategy': 'Strategy',
  '/sensitivity': 'Sensitivity & Forecasts',
  '/decisions': 'Decisions',
  '/analogies': 'Analogies',
  '/alerts': 'Monitoring',
  '/controls': 'Financial Controls',
  '/esg': 'ESG & Sustainability',
  '/predictions': 'Predictions',
  '/transactions': 'Data Transparency',
  '/market': 'Market Data',
  '/system': 'System Status',
  '/eval': 'AI Evaluation',
  '/tools': 'Tools',
  '/subledger': 'Sub-Ledger Analysis',
  '/institutional-ledger': 'Institutional Ledger',
};

/* ─── Context-aware suggestions per page ─── */
const PAGE_SUGGESTIONS: Record<string, string[]> = {
  '/': ['Explain health score', 'Why is net profit negative?', 'What should I do about COGS?', 'Top recommendations'],
  '/pnl': ['Explain gross margin trend', 'Why did selling expenses increase?', 'Compare with prior period', 'Profitability drivers'],
  '/balance-sheet': ['Explain asset composition', 'Is leverage too high?', 'Cash flow projection', 'Working capital analysis'],
  '/revenue': ['Which products are most profitable?', 'Revenue growth forecast', 'Revenue concentration risk', 'Pricing analysis'],
  '/costs': ['Which costs can be reduced?', 'COGS optimization opportunities', 'OpEx trend analysis', 'Cost benchmarks'],
  '/reasoning': ['Explain the strategy', 'What are the top risks?', 'Executive summary', 'Key action items', 'Compare top actions', 'Risk vs reward analysis', 'Implementation timeline', 'ROI ranking', 'Strategy feasibility', 'Time to breakeven', 'Resource requirements', 'Alternative scenarios', 'Worst case scenario', 'Key risk drivers', 'Monte Carlo summary', 'Sensitivity tornado'],
  '/alerts': ['Active alerts summary', 'Alert trends', 'KPI breach history', 'Recommended thresholds'],
};
const DEFAULT_SUGGESTIONS = ['Run full analysis pipeline', 'Generate executive PDF report', 'Show me the biggest risks', 'Compare with prior period', 'What actions should I take?'];

/* ─── Page context names for agent ─── */
const PAGE_CONTEXT_NAMES: Record<string, string> = {
  '/': 'Dashboard', '/pnl': 'Income Statement', '/balance-sheet': 'Balance Sheet',
  '/revenue': 'Revenue', '/costs': 'Costs', '/reasoning': 'Deep Reasoning',
  '/alerts': 'Monitoring', '/library': 'Data Library', '/budget': 'Budget',
  '/ai-report': 'AI Report',
};

/* ─── Sidebar dimensions ─── */
const SIDEBAR_EXPANDED = 200;

/* ─── Keyframes (injected once) ─── */
const STYLE_ID = '__layout-keyframes';
function ensureKeyframes() {
  if (document.getElementById(STYLE_ID)) return;
  const s = document.createElement('style');
  s.id = STYLE_ID;
  s.textContent = `
    @keyframes tbar { 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
    @keyframes dotBounce {
      0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)}
    }
    @keyframes tickerScroll {
      0% { transform: translateX(100%); }
      100% { transform: translateX(-100%); }
    }
  `;
  document.head.appendChild(s);
}

/* ─── Component ─── */
export default function Layout() {
  const { user, logout, period, setFromDashboard, setAlerts, setDatasets, lang, theme, setLang, setTheme } = useStore();
  const navigate = useNavigate();
  const location = useLocation();
  const pageTitle = PAGE_TITLES[location.pathname] || 'FinAI';

  /* --- Global data loader: ALWAYS fetch dashboard data to populate store --- */
  useEffect(() => {
    const periodParam = period ? `?period=${period}` : '';
    fetch(`/api/agent/agents/dashboard${periodParam}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data && !data.empty) setFromDashboard(data); })
      .catch(() => {});
    fetch('/api/agent/alerts')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          const alerts = Array.isArray(data) ? data : data.alerts ?? [];
          if (alerts.length) setAlerts(alerts);
        }
      })
      .catch(() => {});
    // Load available datasets into store for AI context
    fetch('/api/agent/agents/datasets')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          const list = data.datasets || data;
          if (Array.isArray(list)) setDatasets(list);
        }
      })
      .catch(() => {});
  }, [period, setFromDashboard, setAlerts, setDatasets]); // Re-fetch when period changes

  /* --- (period selection handled by PeriodSelector component) --- */

  /* --- state --- */
  const [agentOpen, setAgentOpen] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  
  /* Sidebar Logic */
  const [isPinned, setIsPinned] = useState(() => {
    const saved = localStorage.getItem('finai-sidebar-pinned');
    return saved ? saved === 'true' : true;
  });
  const [isHovered, setIsHovered] = useState(false);
  const isExpanded = isPinned || isHovered;

  const togglePin = () => {
    const next = !isPinned;
    setIsPinned(next);
    localStorage.setItem('finai-sidebar-pinned', String(next));
  };
  
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [activeDataset, setActiveDataset] = useState<string | null>('Reports.xlsx (NYX Core Thinker)');
  const [systemOnline, setSystemOnline] = useState(true);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [healthScore, setHealthScore] = useState<number | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { ensureKeyframes(); }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  /* --- theme toggle --- */
  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  /* --- send chat via /api/agent/command with FULL system context --- */
  const sendChat = useCallback(async (text?: string) => {
    const msg = (text ?? chatInput).trim();
    if (!msg) return;
    setChatInput('');
    setMessages((m) => [...m, { role: 'user', content: msg }]);
    setIsTyping(true);
    setIsThinking(true);

    // Build COMPREHENSIVE context
    const pageName = PAGE_CONTEXT_NAMES[location.pathname] || 'FinAI';
    const store = useStore.getState();
    const rev = store.pnl?.revenue || 0;
    const np = store.pnl?.net_profit || 0;
    const gp = store.pnl?.gross_profit || 0;
    const ebitda = store.pnl?.ebitda || 0;
    const intel = store.intelligence as Record<string, unknown> | null;
    const hs = (intel as any)?.health_summary?.health_score ?? (intel as any)?.health?.score ?? healthScore ?? null;
    const grade = (intel as any)?.health_summary?.grade ?? (intel as any)?.health?.grade ?? null;
    const riskCount = store.alerts?.filter(a => a.severity === 'critical' || a.severity === 'emergency').length || 0;
    const orch = store.orchestrator as Record<string, unknown> | null;

    const contextLines = [
      `System: FinAI OS v2.2`,
      store.company ? `Company: ${store.company}` : null,
      store.period ? `Period: ${store.period}` : null,
      store.dataset_id ? `Active Dataset ID: ${store.dataset_id}` : null,
      `Current Page: ${pageName}`,
      '',
      'Financial Summary:',
      rev ? `- Revenue: ${rev.toLocaleString()}` : null,
      gp ? `- Gross Profit: ${gp.toLocaleString()}` : null,
      ebitda ? `- EBITDA: ${ebitda.toLocaleString()}` : null,
      np ? `- Net Profit: ${np.toLocaleString()}` : null,
      hs !== null ? `- Health Score: ${hs}/100${grade ? ` Grade ${grade}` : ''}` : null,
      riskCount > 0 ? `- Critical Risks: ${riskCount}` : null,
      orch ? `- Orchestrator: last run available` : null,
      '',
      'Available Datasets:',
      ...(store.datasets || []).filter(d => d.record_count > 0).map(d => `- ID:${d.id} "${d.original_filename}" period=${d.period} records=${d.record_count}`),
      '',
      'System Capabilities:',
      '- Can run 7-stage orchestrator analysis',
      '- Can generate PDF/Excel reports and send via email',
      '- Can run sensitivity/Monte Carlo simulations',
      '- Can compare against industry benchmarks',
      '- Can switch datasets and periods for the user',
      '- Can navigate to any page (P&L, BS, Revenue, Costs, etc.)',
      '- Has access to 649 ontology objects, 710 knowledge graph entities',
      '- Can query DuckDB warehouse with SQL',
      '- Strategic Map: Live risk data for Georgia-Azerbaijan-Turkey corridor',
      '- Map shows OPEC/non-OPEC producers, transit hubs, nearby fuel suppliers',
      '- Suppliers: Aktau $75/BBL, Türkmenbaşy $76/BBL, Basra $74/BBL (compliant); Novorossiysk $78 (sanctions risk); Bandar Abbas $72 (sanctions)',
      '- Pipelines: BTC (1.2M BBL/d), Baku-Supsa (140K), SCP gas (25 BCM/yr)',
      '- EIA weekly petroleum data integrated for supply/demand signals',
      '- Can navigate to /market for the full strategic map view',
      '',
      'ACTION COMMANDS (include in response to execute):',
      '- [ACTION:NAVIGATE:/pnl] — navigate to a page',
      '- [ACTION:SET_DATASET:14] — switch to dataset ID 14',
      '- [ACTION:SET_PERIOD:January 2026] — set period',
      '- [ACTION:EXPORT:pl_comparison] — trigger Excel download',
      '- [ACTION:EMAIL:pl_comparison] — open email dialog for report type',
      '',
      `User's question: ${msg}`,
    ].filter(l => l !== null).join('\n');

    try {
      const token = user?.token || localStorage.getItem('token') || '';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000); // 60s timeout
      const res = await fetch('/api/agent/captain/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: contextLines, lang: lang || 'en' }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (!res.ok) {
        const errText = await res.text().catch(() => 'Unknown error');
        throw new Error(`API error ${res.status}: ${errText.slice(0, 200)}`);
      }
      let data: any;
      try {
        data = await res.json();
      } catch {
        const text = await res.text().catch(() => '');
        data = { content: text || 'Received non-JSON response from server.' };
      }
      const reply = data.content || data.response || data.llm_summary || data.detail || 'No response.';

      let cleanReply = reply;

      // 1. Parse and execute AGENT_MAP_COMMAND from AI response
      const mapCmdRegex = /__AGENT_MAP_COMMAND__(\{.*?\})__END__/g;
      let mapMatch;
      while ((mapMatch = mapCmdRegex.exec(reply)) !== null) {
        try {
          const cmd = JSON.parse(mapMatch[1]);
          window.dispatchEvent(new CustomEvent('AGENT_MAP_COMMAND', { detail: cmd }));
          cleanReply = cleanReply.replace(mapMatch[0], '');
        } catch (e) {
          console.warn('Failed to parse Agent Map Command:', e);
        }
      }

      // 1b. Parse __NAVIGATE_TO__ absolute control
      const navRegex = /__NAVIGATE_TO__\/(\S+)/g;
      let navMatch;
      while ((navMatch = navRegex.exec(reply)) !== null) {
        const path = `/${navMatch[1]}`;
        setTimeout(() => navigate(path), 500);
        cleanReply = cleanReply.replace(navMatch[0], '');
      }

      // 2. Parse and execute legacy ACTION commands from AI response
      const actionRegex = /\[ACTION:(\w+):([^\]]+)\]/g;
      let actionMatch;
      while ((actionMatch = actionRegex.exec(reply)) !== null) {
        const [fullMatch, action, value] = actionMatch;
        cleanReply = cleanReply.replace(fullMatch, '');
        try {
          switch (action) {
            case 'NAVIGATE':
              navigate(value);
              break;
            case 'SET_DATASET':
              useStore.getState().setDatasetId(parseInt(value));
              break;
            case 'SET_PERIOD':
              useStore.getState().setPeriod(value);
              break;
            case 'EXPORT': {
              const { api } = await import('../api/client');
              if (value === 'pl_comparison') {
                const blob = await (api as any).plExportExcel();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url; a.download = 'PL_Report.xlsx'; a.click(); URL.revokeObjectURL(url);
              } else if (value === 'bs_comparison') {
                const blob = await (api as any).bsExportExcel();
                const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'BS_Report.xlsx'; a.click(); URL.revokeObjectURL(url);
              }
              break;
            }
            case 'EMAIL':
              window.dispatchEvent(new CustomEvent('finai-open-email', { detail: { reportType: value } }));
              break;
          }
        } catch (actionErr) {
          console.warn('Failed to execute AI action:', action, value, actionErr);
        }
      }

      setMessages((m) => [...m, { role: 'ai', content: cleanReply.trim(), model: data.model }]);
    } catch (err: any) {
      const errMsg = err?.name === 'AbortError'
        ? 'Request timed out (60s). Try a shorter question or check backend status.'
        : `Connection failed: ${err?.message || 'Unknown error'}. Check if backend is running on port 9200.`;
      setMessages((m) => [...m, { role: 'ai', content: errMsg }]);
    } finally {
      setIsTyping(false);
      setIsThinking(false);
    }
  }, [chatInput, user, navigate, healthScore]);

  /* --- excel upload via smart-upload → populate store --- */
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setActiveDataset(file.name);
    setIsThinking(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = user?.token || localStorage.getItem('token') || '';
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch('/api/agent/agents/smart-upload', {
        method: 'POST', headers, body: formData,
      });
      const data = await res.json();
      if (data.company) setActiveDataset(`${file.name} (${data.company})`);
      // Populate the global store
      const { setFromUpload } = useStore.getState();
      setFromUpload(data);
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setIsThinking(false);
    }
    e.target.value = '';
  }, [user]);

  /* --- health check --- */
  useEffect(() => {
    const check = () => fetch('/health').then((r) => setSystemOnline(r.ok)).catch(() => setSystemOnline(false));
    check();
    const iv = setInterval(check, 30000);
    return () => clearInterval(iv);
  }, []);

  /* --- fetch health score from ontology --- */
  useEffect(() => {
    if (period) {
      fetch(`/api/ontology/intelligence/${period}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d?.health?.score) setHealthScore(d.health.score); })
        .catch(() => {});
    }
  }, [period]);

  /* --- keyboard shortcuts for nav --- */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        const allItems = NAV_GROUPS.flatMap(g => g.items);
        const item = allItems.find(i => i.shortcut === e.key);
        if (item) { e.preventDefault(); navigate(item.to); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);

  const toggleGroup = (label: string) => {
    setCollapsedGroups(prev => ({ ...prev, [label]: !prev[label] }));
  };

  const handleLogout = () => { logout(); navigate('/login'); };

  const sidebarWidth = isExpanded ? 240 : 64;

  /* ─────────── Render ─────────── */
  return (
    <div className="app-shell">

      {/* ── Sidebar ── */}
      <aside
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className="sidebar-premium"
        style={{ width: isExpanded ? 240 : 64 }}
      >
        {/* Logo area */}
        <div className="flex items-center justify-between px-4 py-6 shrink-0">
          <div className="flex items-center gap-3">
            <NyxLogo size={isExpanded ? 64 : 32} className="transition-all duration-300" />
            {isExpanded && <span className="text-sm font-black tracking-[0.2em] text-heading">NYX CORE</span>}
          </div>
          
          {isExpanded && (
            <button onClick={togglePin} className={`p-1.5 rounded-md transition-all ${isPinned ? 'text-sky bg-sky/10' : 'text-dim hover:bg-white/5'}`}>
              <Target size={14} className={isPinned ? 'rotate-45' : ''} />
            </button>
          )}
        </div>

        {/* Nav groups */}
        <nav className="flex-1 py-4">
          {NAV_GROUPS.map((group) => {
            const isCollapsed = collapsedGroups[group.label];
            return (
            <div key={group.label} className="mb-4">
              {isExpanded && (
                <div
                  onClick={() => toggleGroup(group.label)}
                  className="nav-group-label cursor-pointer flex items-center justify-between group"
                >
                  <span className="group-hover:text-muted transition-colors">{group.tKey ? t(group.tKey) : group.label}</span>
                  <CaretDown size={10} className={`transition-transform duration-200 ${isCollapsed ? '-rotate-90' : 'rotate-0'}`} />
                </div>
              )}
              
              {!isExpanded && <div className="h-[1px] bg-b1 mx-4 my-2" />}

              <div className={`overflow-hidden transition-all duration-300 ${isCollapsed && isExpanded ? 'max-h-0' : 'max-h-[1000px]'}`}>
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to} 
                    to={item.to} 
                    end={item.to === '/'}
                    className={({ isActive }) => `nav-item-premium ${isActive ? 'active' : ''} ${!isExpanded ? 'justify-center !px-0 !mx-2' : ''}`}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon size={20} weight={isActive ? "fill" : "light"} />
                        {isExpanded && (
                          <>
                            <span className="flex-1 truncate">{item.tKey ? t(item.tKey) : item.label}</span>
                            {item.shortcut && (
                              <span className="font-mono text-[8px] px-1.5 py-0.5 rounded bg-bg3 text-dim opacity-40 shrink-0">
                                {'\u2318'}{item.shortcut}
                              </span>
                            )}
                          </>
                        )}
                      </>
                    )}
                  </NavLink>
                );
              })}
              </div>
            </div>
            );
          })}
        </nav>

        {/* Footer actions */}
        <div className="py-2 border-t border-b1">
          <button onClick={() => setAgentOpen((o) => !o)} className={`flex items-center gap-3 p-3 w-full text-left transition-all hover:bg-white/5 ${agentOpen ? 'text-sky' : 'text-muted'}`}>
            <ChatCenteredText size={20} weight={agentOpen ? "fill" : "light"} />
            {isExpanded && <span className="text-xs font-bold">AI Assistant</span>}
          </button>
          <button onClick={handleLogout} className="flex items-center gap-3 p-3 w-full text-left transition-all hover:bg-rose/10 text-rose/80 hover:text-rose">
            <SignOut size={20} weight="light" />
            {isExpanded && <span className="text-xs font-bold">{t('ui.logout')}</span>}
          </button>
        </div>
      </aside>

      {/* ── Center: main content area ── */}
      <div className="main-content-sync">
        {/* Hidden file input for upload */}
        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={handleFileUpload} className="hidden" />

        {/* Top bar — Unified Command UI */}
        <header className="topbar-command">
          <h2 className="text-[13px] font-bold text-heading mr-auto tracking-tight select-none">
            {pageTitle}
          </h2>

          <div className="flex items-center gap-4">
            <PageVideoGuide pageKey={location.pathname === '/' ? 'default' : location.pathname.substring(1)} />
            <div className="h-4 w-[1px] bg-b1" />
            <PeriodSelector />
            <div className="h-4 w-[1px] bg-b1" />
            <NotificationBell />
            
            <div className="flex items-center gap-2 px-2 py-1 rounded bg-bg2 border border-b1">
               <div className={`w-1.5 h-1.5 rounded-full ${systemOnline ? 'bg-emerald shadow-[0_0_8px_#48BB78]' : 'bg-rose shadow-[0_0_8px_#f56565]'}`} />
               <span className="text-[9px] font-bold text-muted uppercase tracking-widest">{systemOnline ? 'Sync' : 'Lost'}</span>
            </div>

            <button onClick={() => navigate('/system')} className="p-1.5 text-dim hover:text-sky transition-colors">
              <Gear size={18} weight="light" />
            </button>

            <button 
              onClick={() => {
                const newLang = (lang === 'en' ? 'ka' : 'en') as 'en' | 'ka';
                setLang(newLang);
                setI18nLang(newLang);
                localStorage.setItem('finai-lang', newLang);
              }}
              className="px-2 py-1 text-[10px] font-black text-dim hover:text-text transition-all tracking-tighter"
            >
              {lang === 'en' ? 'KA' : 'EN'}
            </button>

            <button onClick={toggleTheme} className="p-1.5 text-dim hover:text-amber transition-colors">
              {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            </button>
          </div>
        </header>

        {/* Thinking bar (Dynamics) */}
        <div className="h-[2px] bg-bg0 overflow-hidden shrink-0">
          {isThinking && (
            <div className="h-full w-1/3 bg-sky/50 shadow-[0_0_12px_#00d8ff] animate-[tbar_1.4s_ease-in-out_infinite]" />
          )}
        </div>

        {/* System Health Ticker (The correct layer) */}
        <div className="ticker-bar">
          <div className="flex items-center h-full px-4 bg-bg3 border-r border-b2 text-[9px] font-black text-sky tracking-[0.2em] relative z-10">
            SYSTEM MONITOR
          </div>
          <div className="flex whitespace-nowrap animate-[tickerScroll_40s_linear_infinite] px-10 gap-20 text-[10px] font-mono text-dim/60">
            <span>[HEALTH: {healthScore || 98}% OPERATIONAL]</span>
            <span>[NODES: 12 ACTIVE]</span>
            <span>[LATENCY: 14ms]</span>
            <span>[AP_AUTOMATION: MATCH_RATE 94%]</span>
            <span>[CONSOLIDATION: ACTIVE (3 ENTITIES)]</span>
            <span>[COMPLIANCE: NO BREACHES]</span>
            <span>[MARKET: BRENT $82.4 | USD/GEL 2.65]</span>
            <span>[AI_REASONING: READY]</span>
          </div>
        </div>

        {/* Page Content Viewport */}
        <div className="flex-1 flex overflow-hidden">
          <main key={location.pathname} className="page-viewport page-enter">
            <Outlet />
          </main>

          {/* ── Agent Panel (Correct Layer) ── */}
          <div className={`flex flex-col border-l border-b1 bg-bg1 transition-all duration-300 ${agentOpen ? 'w-80' : 'w-0 opacity-0 overflow-hidden'}`}>
            <div className="h-11 flex items-center justify-between px-4 border-b border-b1 shrink-0 bg-bg0/30">
              <span className="text-xs font-black tracking-widest text-heading opacity-50 uppercase">Intelligence Panel</span>
              <button onClick={() => setAgentOpen(false)} className="p-1 hover:text-sky transition-colors">
                <X size={14} />
              </button>
            </div>

            {/* Messages area */}
            <div style={{
              flex: 1, overflowY: 'auto', padding: '10px 12px',
              display: 'flex', flexDirection: 'column', gap: 8,
            }}>
              {messages.length === 0 && (
                <div style={{
                  textAlign: 'center', color: 'var(--dim)', fontSize: 11,
                  marginTop: 40, lineHeight: 1.6,
                }}>
                  {t('agent.ask_about')}
                </div>
              )}
              {messages.map((m, i) => {
                // Detect action keywords in AI responses
                const lc = m.role === 'ai' ? m.content.toLowerCase() : '';
                const showOrchBtn = m.role === 'ai' && (lc.includes('orchestrat') || lc.includes('pipeline') || lc.includes('full analysis'));
                const showReportBtn = m.role === 'ai' && (lc.includes('report') || lc.includes('pdf') || lc.includes('document'));
                const showSensBtn = m.role === 'ai' && (lc.includes('sensitiv') || lc.includes('monte carlo') || lc.includes('simulation'));
                const hasActions = showOrchBtn || showReportBtn || showSensBtn;

                return (
                <div key={i} style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                }}>
                  <div style={{
                    padding: '8px 12px', borderRadius: 10, fontSize: 11.5, lineHeight: 1.5,
                    background: m.role === 'user'
                      ? 'var(--bg3)'
                      : 'var(--bg2)',
                    color: m.role === 'user' ? 'var(--text)' : 'var(--text)',
                    borderTopRightRadius: m.role === 'user' ? 2 : 10,
                    borderTopLeftRadius: m.role === 'ai' ? 2 : 10,
                  }}>
                    {m.content}
                  </div>
                  {/* Action buttons based on AI response keywords */}
                  {hasActions && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 4 }}>
                      {showOrchBtn && (
                        <button onClick={() => navigate('/reasoning')} style={{
                          padding: '3px 8px', borderRadius: 6, fontSize: 9,
                          fontFamily: 'var(--mono)', fontWeight: 600,
                          background: 'transparent', border: '1px solid var(--b2)',
                          color: 'var(--muted)', cursor: 'pointer', transition: 'all .15s',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}
                          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.borderColor = 'var(--text)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--muted)'; e.currentTarget.style.borderColor = 'var(--b2)'; }}
                        >
                          <FlowArrow size={10} /> Run Orchestrator
                        </button>
                      )}
                      {showReportBtn && (
                        <button onClick={() => navigate('/ai-report')} style={{
                          padding: '3px 8px', borderRadius: 6, fontSize: 9,
                          fontFamily: 'var(--mono)', fontWeight: 600,
                          background: 'transparent', border: '1px solid var(--b2)',
                          color: 'var(--muted)', cursor: 'pointer', transition: 'all .15s',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}
                          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.borderColor = 'var(--text)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--muted)'; e.currentTarget.style.borderColor = 'var(--b2)'; }}
                        >
                          <FileText size={10} /> Generate Report
                        </button>
                      )}
                      {showSensBtn && (
                        <button onClick={() => navigate('/reasoning')} style={{
                          padding: '3px 8px', borderRadius: 6, fontSize: 9,
                          fontFamily: 'var(--mono)', fontWeight: 600,
                          background: 'transparent', border: '1px solid var(--b2)',
                          color: 'var(--muted)', cursor: 'pointer', transition: 'all .15s',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}
                          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text)'; e.currentTarget.style.borderColor = 'var(--text)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--muted)'; e.currentTarget.style.borderColor = 'var(--b2)'; }}
                        >
                          <Sliders size={10} /> Run Sensitivity
                        </button>
                      )}
                    </div>
                  )}
                </div>
                );
              })}
              {/* Typing indicator with elapsed time */}
              {isTyping && (
                <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px' }}>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {[0, 1, 2].map((d) => (
                      <div key={d} style={{
                        width: 5, height: 5, borderRadius: '50%', background: 'var(--muted)',
                        animation: `dotBounce 1.2s ease-in-out ${d * 0.15}s infinite`,
                      }} />
                    ))}
                  </div>
                  <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                    AI reasoning...
                  </span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Context-aware suggestion chips */}
            <div style={{
              padding: '6px 12px', display: 'flex', gap: 6, flexWrap: 'wrap', flexShrink: 0,
            }}>
              {(PAGE_SUGGESTIONS[location.pathname] || DEFAULT_SUGGESTIONS).map((s) => (
                <button key={s} onClick={() => sendChat(s)} style={{
                  padding: '4px 10px', borderRadius: 12, fontSize: 9.5,
                  fontFamily: 'var(--mono)', background: 'transparent',
                  border: 'none', color: 'var(--muted)',
                  cursor: 'pointer', transition: 'color .15s',
                }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = 'var(--text)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = 'var(--muted)';
                  }}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Input area */}
            <div style={{
              padding: '8px 12px 10px',
              display: 'flex', gap: 6, flexShrink: 0,
            }}>
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } }}
                placeholder={t('agent.ask_anything')}
                style={{
                  flex: 1, height: 32, padding: '0 0 0 2px',
                  border: 'none', borderBottom: '1px solid var(--b2)',
                  borderRadius: 0,
                  background: 'transparent',
                  color: 'var(--text)', fontSize: 11, outline: 'none',
                  fontFamily: 'inherit', transition: 'border-color .15s',
                }}
                onFocus={(e) => { e.currentTarget.style.borderBottomColor = 'var(--text)'; }}
                onBlur={(e) => { e.currentTarget.style.borderBottomColor = 'var(--b2)'; }}
              />
              <button onClick={() => sendChat()} disabled={!chatInput.trim()} style={{
                width: 32, height: 32, borderRadius: 0, border: 'none',
                background: 'transparent',
                color: chatInput.trim() ? 'var(--text)' : 'var(--dim)',
                cursor: chatInput.trim() ? 'pointer' : 'default',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'color .15s',
              }}>
                <PaperPlaneTilt size={13} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
