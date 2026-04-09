import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileSpreadsheet, BookOpen, Layers, BarChart3,
  CheckCircle, Loader2,
} from 'lucide-react';

/* ── types ── */
interface StageData {
  key: string;
  label: string;
  sublabel: string;
  count: number | null;
  detail: string;
  icon: React.ReactNode;
  path: string;
  color: string;
}

/* ── currency formatter ── */
function fmtCurrency(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `\u20BE${(n / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `\u20BE${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `\u20BE${(n / 1e3).toFixed(0)}K`;
  return `\u20BE${n.toFixed(0)}`;
}

/* ── SVG arrow between stages ── */
function Arrow() {
  return (
    <svg width="36" height="24" viewBox="0 0 36 24" style={{ flexShrink: 0, margin: '0 -4px' }}>
      <defs>
        <linearGradient id="arrow-grad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--sky, #38BDF8)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--sky, #38BDF8)" stopOpacity="0.8" />
        </linearGradient>
      </defs>
      <line x1="2" y1="12" x2="28" y2="12" stroke="url(#arrow-grad)" strokeWidth="2" />
      <polygon points="28,6 36,12 28,18" fill="var(--sky, #38BDF8)" opacity="0.8" />
    </svg>
  );
}

/* ── single stage card ── */
function StageCard({ stage, onClick }: { stage: StageData; onClick: () => void }) {
  const hasData = stage.count !== null && stage.count > 0;

  return (
    <div
      onClick={onClick}
      style={{
        flex: '1 1 0',
        minWidth: 130,
        maxWidth: 200,
        background: 'var(--bg2, #1a2332)',
        border: `1px solid ${hasData ? stage.color + '44' : 'var(--b1, #2a3a4a)'}`,
        borderRadius: 10,
        padding: '14px 12px 12px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative' as const,
        display: 'flex',
        flexDirection: 'column' as const,
        alignItems: 'center',
        gap: 6,
        textAlign: 'center' as const,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = stage.color;
        (e.currentTarget as HTMLElement).style.boxShadow = `0 0 16px ${stage.color}22`;
        (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = hasData ? stage.color + '44' : 'var(--b1, #2a3a4a)';
        (e.currentTarget as HTMLElement).style.boxShadow = 'none';
        (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
      }}
    >
      {/* Status indicator */}
      {hasData && (
        <div style={{ position: 'absolute', top: 6, right: 6 }}>
          <CheckCircle size={12} style={{ color: '#10B981' }} />
        </div>
      )}

      {/* Icon */}
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: stage.color + '18',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {stage.icon}
      </div>

      {/* Label */}
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--heading, #e2e8f0)' }}>
        {stage.label}
      </div>

      {/* Count */}
      <div style={{ fontSize: 16, fontWeight: 800, color: hasData ? stage.color : 'var(--muted, #64748b)' }}>
        {stage.count !== null ? stage.count.toLocaleString() : '--'}
      </div>

      {/* Sublabel */}
      <div style={{ fontSize: 9, color: 'var(--muted, #64748b)', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>
        {stage.sublabel}
      </div>

      {/* Detail line */}
      {stage.detail && (
        <div style={{ fontSize: 10, color: hasData ? stage.color : 'var(--muted, #64748b)', marginTop: 2 }}>
          {stage.detail}
        </div>
      )}
    </div>
  );
}


/* ── main component ── */
export default function PipelineVisualization() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stages, setStages] = useState<StageData[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function fetchCounts() {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      const token = localStorage.getItem('token');
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const safeFetch = async (url: string) => {
        try {
          const res = await fetch(url, { headers });
          if (!res.ok) return null;
          return await res.json();
        } catch { return null; }
      };

      // Fetch all pipeline stage data in parallel
      const [datasetsRes, journalRes, glRes, plRes] = await Promise.all([
        safeFetch('/api/agent/agents/datasets'),
        safeFetch('/api/journal/entries?limit=1'),
        safeFetch('/api/gl/periods'),
        safeFetch('/api/analytics/pl-comparison'),
      ]);

      if (cancelled) return;

      // Parse counts
      const dsCount = datasetsRes?.datasets?.length ?? datasetsRes?.count ?? null;
      const jeCount = journalRes?.total ?? journalRes?.entries?.length ?? null;
      const postingCount = journalRes?.total_lines ?? null;
      const periodCount = glRes?.periods?.length ?? glRes?.count ?? null;
      const plRowCount = plRes?.rows?.length ?? null;
      const revenue = plRes?.summary?.revenue ?? null;

      setStages([
        {
          key: 'upload',
          label: 'Upload File',
          sublabel: 'datasets',
          count: dsCount,
          detail: dsCount ? `.xlsx files loaded` : 'No files yet',
          icon: <Upload size={18} style={{ color: '#38BDF8' }} />,
          path: '/library',
          color: '#38BDF8',
        },
        {
          key: 'classify',
          label: 'Parse & Classify',
          sublabel: 'accounts mapped',
          count: 406,
          detail: '17 products',
          icon: <FileSpreadsheet size={18} style={{ color: '#A78BFA' }} />,
          path: '/intelligent-ingest',
          color: '#A78BFA',
        },
        {
          key: 'journal',
          label: 'Journal Entries',
          sublabel: 'entries',
          count: jeCount,
          detail: jeCount ? `${jeCount} created` : 'No entries yet',
          icon: <BookOpen size={18} style={{ color: '#F59E0B' }} />,
          path: '/journal',
          color: '#F59E0B',
        },
        {
          key: 'posting',
          label: 'Posting Lines',
          sublabel: 'lines',
          count: postingCount,
          detail: periodCount ? `${periodCount} periods` : '',
          icon: <Layers size={18} style={{ color: '#10B981' }} />,
          path: '/gl-pipeline',
          color: '#10B981',
        },
        {
          key: 'statements',
          label: 'Financial Statements',
          sublabel: 'P&L / BS / CF',
          count: plRowCount,
          detail: revenue ? fmtCurrency(revenue) + ' revenue' : '',
          icon: <BarChart3 size={18} style={{ color: '#EC4899' }} />,
          path: '/pnl',
          color: '#EC4899',
        },
      ]);
      setLoading(false);
    }

    fetchCounts();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="glass" style={{
        padding: '20px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        color: 'var(--muted)',
      }}>
        <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
        <span style={{ fontSize: 12 }}>Loading pipeline...</span>
      </div>
    );
  }

  return (
    <div className="glass" style={{ padding: '16px 20px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
        Data Pipeline
      </div>

      {/* Pipeline stages with arrows */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        overflowX: 'auto',
        paddingBottom: 4,
      }}>
        {stages.map((stage, i) => (
          <div key={stage.key} style={{ display: 'flex', alignItems: 'center' }}>
            <StageCard stage={stage} onClick={() => navigate(stage.path)} />
            {i < stages.length - 1 && <Arrow />}
          </div>
        ))}
      </div>
    </div>
  );
}
