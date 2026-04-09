import { useState, useEffect, useCallback, useRef } from 'react';
import { Play, ChevronRight, X, Sparkles, LayoutGrid, Search, Bookmark, Layers, Zap, GripVertical, Settings } from 'lucide-react';

/* ─── Tour Step Definition ─── */
interface TourStep {
  id: string;
  title: string;
  description: string;
  targetSelector?: string;       // CSS selector to spotlight
  action?: () => void;           // Side-effect to run when step activates
  position?: 'top' | 'bottom' | 'left' | 'right' | 'center';
  duration?: number;             // ms before auto-advance (default 4000)
  icon?: React.ReactNode;
}

interface WorkshopTourProps {
  active: boolean;
  onEnd: () => void;
  onSwitchTab: (tab: 'builder' | 'query' | 'saved' | 'templates') => void;
  onAddWidget: () => void;
  onBuildQuery: () => void;
  onRunTemplate: (id: string) => void;
  onSelectDataSource?: (ds: string) => void;
  onSelectMetric?: (m: string) => void;
  onSelectChartType?: (ct: 'bar' | 'line' | 'table' | 'kpi') => void;
}

export default function WorkshopTour({
  active, onEnd, onSwitchTab, onAddWidget, onBuildQuery, onRunTemplate,
  onSelectDataSource, onSelectMetric, onSelectChartType,
}: WorkshopTourProps) {
  const [step, setStep] = useState(0);
  const [typedText, setTypedText] = useState('');
  const [spotlightRect, setSpotlightRect] = useState<DOMRect | null>(null);
  const [isTyping, setIsTyping] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const STEPS: TourStep[] = [
    {
      id: 'welcome',
      title: 'Welcome to the Workshop',
      description: 'Your custom analytics workbench. Build dashboards, run queries, save tools, and use pre-built templates — all powered by your financial data. Let me show you around.',
      position: 'center',
      duration: 5000,
      icon: <Sparkles size={20} style={{ color: 'var(--gold)' }} />,
    },
    {
      id: 'tabs',
      title: '4 Powerful Tools',
      description: 'The Workshop has four tabs: Dashboard Builder for drag-and-drop layouts, Query Builder for custom analytics, Saved Tools for your library, and Templates for instant analysis.',
      targetSelector: '[data-tour="tab-bar"]',
      position: 'bottom',
      duration: 5000,
      icon: <LayoutGrid size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'builder-intro',
      title: 'Dashboard Builder',
      description: 'Create custom dashboard layouts by dragging widgets onto a grid canvas. Each widget connects to your live financial data.',
      targetSelector: '[data-tour="tab-builder"]',
      action: () => onSwitchTab('builder'),
      position: 'bottom',
      duration: 4500,
      icon: <LayoutGrid size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'widget-palette',
      title: 'Widget Palette',
      description: '6 widget types available: Metric Cards for KPIs, Charts for visualization, KPI Lists for status dashboards, Data Tables, Pivot Tables for cross-tab analysis, and Alert Feeds for live monitoring.',
      targetSelector: '[data-tour="widget-palette"]',
      position: 'right',
      duration: 5500,
      icon: <GripVertical size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'add-widget',
      title: 'Adding a Widget',
      description: 'Click any widget type or drag it onto the canvas. Watch — I\'ll add a Metric Card for you now...',
      targetSelector: '[data-tour="widget-palette"]',
      action: () => setTimeout(() => onAddWidget(), 1200),
      position: 'right',
      duration: 4000,
      icon: <Zap size={18} style={{ color: 'var(--gold)' }} />,
    },
    {
      id: 'config-panel',
      title: 'Widget Configuration',
      description: 'Click any widget to configure it. Change the label, connect a data source (P&L, Balance Sheet, Knowledge Graph), and set the display format. Real-time preview updates instantly.',
      targetSelector: '[data-tour="config-panel"]',
      position: 'left',
      duration: 5000,
      icon: <Settings size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'query-intro',
      title: 'Query Builder',
      description: 'Build custom analytics queries from 5 data sources: P&L, Revenue, COGS, Balance Sheet, and Knowledge Graph. Select a metric, choose a visualization, and get instant results.',
      targetSelector: '[data-tour="tab-query"]',
      action: () => onSwitchTab('query'),
      position: 'bottom',
      duration: 5000,
      icon: <Search size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'query-build',
      title: 'Building a Query',
      description: 'Select your data source, pick a metric, choose bar/line/table/KPI view, and hit Build. Let me demonstrate with a P&L Revenue bar chart...',
      targetSelector: '[data-tour="query-controls"]',
      action: () => {
        onSelectDataSource?.('pnl');
        onSelectMetric?.('revenue');
        onSelectChartType?.('bar');
        setTimeout(() => onBuildQuery(), 1500);
      },
      position: 'bottom',
      duration: 5500,
      icon: <Zap size={18} style={{ color: 'var(--gold)' }} />,
    },
    {
      id: 'query-save',
      title: 'Save & Reuse',
      description: 'Name your query and save it to your library. Saved queries persist across sessions and can be re-run instantly from the Saved Tools tab.',
      targetSelector: '[data-tour="query-save"]',
      position: 'bottom',
      duration: 4500,
      icon: <Bookmark size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'saved-intro',
      title: 'Saved Tools',
      description: 'Your personal library of saved queries. One-click Run to re-execute any query, or delete queries you no longer need. All queries show their last run timestamp.',
      targetSelector: '[data-tour="tab-saved"]',
      action: () => onSwitchTab('saved'),
      position: 'bottom',
      duration: 4500,
      icon: <Bookmark size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'templates-intro',
      title: 'Pre-built Templates',
      description: '4 ready-to-use analysis templates: Revenue Waterfall, Profitability Matrix, Period Comparison, and KPI Dashboard. Click any template to instantly generate analysis from your data.',
      targetSelector: '[data-tour="tab-templates"]',
      action: () => onSwitchTab('templates'),
      position: 'bottom',
      duration: 5000,
      icon: <Layers size={18} style={{ color: 'var(--sky)' }} />,
    },
    {
      id: 'template-run',
      title: 'Running a Template',
      description: 'Watch — I\'ll run the KPI Dashboard template. It instantly generates cards with status indicators, targets, and color-coded health for all key metrics.',
      targetSelector: '[data-tour="template-grid"]',
      action: () => setTimeout(() => onRunTemplate('kpi_dashboard'), 1000),
      position: 'top',
      duration: 5500,
      icon: <Zap size={18} style={{ color: 'var(--gold)' }} />,
    },
    {
      id: 'complete',
      title: 'You\'re Ready!',
      description: 'Start building your custom analytics. Drag widgets, build queries, save your favorite tools, and use templates for instant analysis. The Workshop is your playground.',
      position: 'center',
      duration: 5000,
      icon: <Sparkles size={20} style={{ color: 'var(--gold)' }} />,
    },
  ];

  const currentStep = STEPS[step];
  const totalSteps = STEPS.length;

  // Run step action
  useEffect(() => {
    if (!active) return;
    const s = STEPS[step];
    if (s?.action) {
      const t = setTimeout(() => s.action!(), 400);
      return () => clearTimeout(t);
    }
  }, [step, active]);

  // Update spotlight position
  useEffect(() => {
    if (!active || !currentStep?.targetSelector) {
      setSpotlightRect(null);
      return;
    }
    const updateRect = () => {
      const el = document.querySelector(currentStep.targetSelector!);
      if (el) {
        setSpotlightRect(el.getBoundingClientRect());
      } else {
        setSpotlightRect(null);
      }
    };
    // Delay to allow tab switch animation
    const t = setTimeout(updateRect, 500);
    window.addEventListener('resize', updateRect);
    return () => {
      clearTimeout(t);
      window.removeEventListener('resize', updateRect);
    };
  }, [step, active, currentStep?.targetSelector]);

  // Typing animation
  useEffect(() => {
    if (!active) return;
    setTypedText('');
    setIsTyping(true);
    const text = currentStep?.description || '';
    let i = 0;
    typingRef.current = setInterval(() => {
      i++;
      setTypedText(text.slice(0, i));
      if (i >= text.length) {
        if (typingRef.current) clearInterval(typingRef.current);
        setIsTyping(false);
      }
    }, 18);
    return () => { if (typingRef.current) clearInterval(typingRef.current); };
  }, [step, active]);

  // Auto-advance timer
  useEffect(() => {
    if (!active) return;
    const dur = currentStep?.duration || 4000;
    timerRef.current = setTimeout(() => {
      if (step < totalSteps - 1) {
        setStep(s => s + 1);
      } else {
        onEnd();
      }
    }, dur);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [step, active, totalSteps]);

  const goNext = useCallback(() => {
    clearTimeout(timerRef.current || undefined);
    clearInterval(typingRef.current || undefined);
    if (step < totalSteps - 1) {
      setStep(s => s + 1);
    } else {
      onEnd();
    }
  }, [step, totalSteps, onEnd]);

  const skip = useCallback(() => {
    clearTimeout(timerRef.current || undefined);
    clearInterval(typingRef.current || undefined);
    setStep(0);
    onEnd();
  }, [onEnd]);

  // Reset on activation
  useEffect(() => {
    if (active) setStep(0);
  }, [active]);

  if (!active) return null;

  const isCenter = currentStep?.position === 'center' || !currentStep?.targetSelector;

  // Calculate tooltip position
  let tooltipStyle: React.CSSProperties = {};
  if (isCenter) {
    tooltipStyle = {
      position: 'fixed',
      top: '50%', left: '50%',
      transform: 'translate(-50%, -50%)',
    };
  } else if (spotlightRect) {
    const pad = 16;
    const pos = currentStep.position || 'bottom';
    if (pos === 'bottom') {
      tooltipStyle = {
        position: 'fixed',
        top: spotlightRect.bottom + pad,
        left: Math.max(20, spotlightRect.left + spotlightRect.width / 2 - 200),
      };
    } else if (pos === 'top') {
      tooltipStyle = {
        position: 'fixed',
        bottom: window.innerHeight - spotlightRect.top + pad,
        left: Math.max(20, spotlightRect.left + spotlightRect.width / 2 - 200),
      };
    } else if (pos === 'right') {
      tooltipStyle = {
        position: 'fixed',
        top: Math.max(20, spotlightRect.top),
        left: spotlightRect.right + pad,
      };
    } else if (pos === 'left') {
      tooltipStyle = {
        position: 'fixed',
        top: Math.max(20, spotlightRect.top),
        right: window.innerWidth - spotlightRect.left + pad,
      };
    }
  }

  return (
    <>
      {/* Overlay backdrop with spotlight cutout */}
      <div className="tour-overlay" onClick={(e) => e.stopPropagation()}>
        {spotlightRect && !isCenter && (
          <div
            className="tour-spotlight"
            style={{
              top: spotlightRect.top - 8,
              left: spotlightRect.left - 8,
              width: spotlightRect.width + 16,
              height: spotlightRect.height + 16,
            }}
          />
        )}
      </div>

      {/* Tooltip */}
      <div className="tour-tooltip" style={{ ...tooltipStyle, zIndex: 10002 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          {currentStep.icon}
          <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--heading)', flex: 1 }}>
            {currentStep.title}
          </span>
          <span style={{ fontSize: 10, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>
            {step + 1}/{totalSteps}
          </span>
        </div>

        {/* Description with typing effect */}
        <p style={{ fontSize: 12, lineHeight: 1.7, color: 'var(--text)', margin: '0 0 16px', minHeight: 40 }}>
          {typedText}
          {isTyping && <span className="tour-typing-cursor">|</span>}
        </p>

        {/* Progress bar */}
        <div style={{ width: '100%', height: 3, background: 'var(--b2)', borderRadius: 2, marginBottom: 14, overflow: 'hidden' }}>
          <div style={{
            width: `${((step + 1) / totalSteps) * 100}%`,
            height: '100%',
            background: 'linear-gradient(90deg, var(--sky), var(--gold))',
            borderRadius: 2,
            transition: 'width 0.4s ease',
          }} />
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <button onClick={skip} className="tour-btn-skip">
            Skip Tour
          </button>

          <div style={{ display: 'flex', gap: 4 }}>
            {STEPS.map((_, i) => (
              <div key={i} style={{
                width: i === step ? 16 : 6, height: 6, borderRadius: 3,
                background: i === step ? 'var(--sky)' : i < step ? 'var(--gold)' : 'var(--b3)',
                transition: 'all 0.3s ease',
              }} />
            ))}
          </div>

          <button onClick={goNext} className="tour-btn-next">
            {step === totalSteps - 1 ? 'Finish' : 'Next'}
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </>
  );
}

/* ─── Watch Demo Button ─── */
export function WatchDemoButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 7,
        padding: '8px 16px', borderRadius: 8,
        background: 'linear-gradient(135deg, rgba(0,242,255,0.08), rgba(201,169,110,0.08))',
        border: '1px solid rgba(201,169,110,0.25)',
        color: 'var(--gold)', cursor: 'pointer',
        fontSize: 11, fontWeight: 600, fontFamily: 'var(--font)',
        transition: 'all 0.2s',
        letterSpacing: 0.3,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'linear-gradient(135deg, rgba(0,242,255,0.12), rgba(201,169,110,0.14))';
        e.currentTarget.style.borderColor = 'rgba(201,169,110,0.45)';
        e.currentTarget.style.boxShadow = '0 0 16px rgba(201,169,110,0.15)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'linear-gradient(135deg, rgba(0,242,255,0.08), rgba(201,169,110,0.08))';
        e.currentTarget.style.borderColor = 'rgba(201,169,110,0.25)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <Play size={13} fill="currentColor" />
      Watch Demo
    </button>
  );
}
