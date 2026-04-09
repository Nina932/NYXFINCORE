import { useState, useRef, useEffect } from 'react';
import { Download, ChevronDown, Filter, Columns, ArrowUpDown, Loader2 } from 'lucide-react';
import { t } from '../i18n/translations';

/* ─── Types ─── */
export type ExportFormat = 'pdf' | 'excel' | 'csv';
export type ViewMode = 'summary' | 'detailed';

interface DropdownOption { value: string; label: string }

interface ActionBarProps {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  // Export
  exports?: ExportFormat[];
  onExport?: (format: ExportFormat) => void;
  exportLoading?: string | null;
  // Segment filter
  segments?: DropdownOption[];
  activeSegment?: string;
  onSegmentChange?: (value: string) => void;
  // Sort
  sortOptions?: DropdownOption[];
  activeSort?: string;
  onSortChange?: (value: string) => void;
  // View mode
  showViewMode?: boolean;
  viewMode?: ViewMode;
  onViewModeChange?: (mode: ViewMode) => void;
  // Extra action buttons
  children?: React.ReactNode;
}

/* ─── Dropdown helper ─── */
function MiniDropdown({ trigger, options, value, onChange }: {
  trigger: React.ReactNode;
  options: DropdownOption[];
  value?: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 11, gap: 4 }}>
        {trigger}
        <ChevronDown size={10} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: 32, right: 0, zIndex: 50,
          background: 'var(--bg3)', border: '1px solid var(--b2)', borderRadius: 8,
          padding: 4, minWidth: 140, boxShadow: 'var(--shadow-lg)',
        }}>
          {options.map(opt => (
            <button
              key={opt.value}
              onClick={() => { onChange(opt.value); setOpen(false); }}
              style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '6px 10px',
                fontSize: 11, borderRadius: 4, border: 'none', cursor: 'pointer',
                background: opt.value === value ? 'rgba(56,189,248,.08)' : 'transparent',
                color: opt.value === value ? 'var(--sky)' : 'var(--text)',
                fontWeight: opt.value === value ? 600 : 400,
              }}
              onMouseEnter={e => { if (opt.value !== value) e.currentTarget.style.background = 'rgba(255,255,255,.03)'; }}
              onMouseLeave={e => { if (opt.value !== value) e.currentTarget.style.background = 'transparent'; }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── ActionBar ─── */
export default function ActionBar({
  title, subtitle, icon,
  exports, onExport, exportLoading,
  segments, activeSegment, onSegmentChange,
  sortOptions, activeSort, onSortChange,
  showViewMode, viewMode, onViewModeChange,
  children,
}: ActionBarProps) {
  const formatLabels: Record<string, string> = {
    pdf: 'PDF', excel: 'Excel', csv: 'CSV',
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
      {/* Left: Title */}
      <div style={{ flex: 1, minWidth: 200 }}>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
          {icon}
          {title}
        </h1>
        {subtitle && <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{subtitle}</p>}
      </div>

      {/* Right: Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        {/* Segment filter */}
        {segments && segments.length > 0 && onSegmentChange && (
          <MiniDropdown
            trigger={<><Filter size={11} /> {segments.find(s => s.value === activeSegment)?.label || t('action.all_segments')}</>}
            options={segments}
            value={activeSegment}
            onChange={onSegmentChange}
          />
        )}

        {/* Sort */}
        {sortOptions && sortOptions.length > 0 && onSortChange && (
          <MiniDropdown
            trigger={<><ArrowUpDown size={11} /> {sortOptions.find(s => s.value === activeSort)?.label || 'Sort'}</>}
            options={sortOptions}
            value={activeSort}
            onChange={onSortChange}
          />
        )}

        {/* View mode */}
        {showViewMode && onViewModeChange && (
          <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--b2)' }}>
            {(['summary', 'detailed'] as ViewMode[]).map(mode => (
              <button
                key={mode}
                onClick={() => onViewModeChange(mode)}
                style={{
                  padding: '4px 10px', fontSize: 10, border: 'none', cursor: 'pointer',
                  background: viewMode === mode ? 'rgba(56,189,248,.1)' : 'transparent',
                  color: viewMode === mode ? 'var(--sky)' : 'var(--muted)',
                  fontWeight: viewMode === mode ? 600 : 400, fontFamily: 'var(--mono)',
                }}
              >
                <Columns size={10} style={{ marginRight: 3, display: 'inline' }} />
                {mode === 'summary' ? t('action.view_summary') : t('action.view_detailed')}
              </button>
            ))}
          </div>
        )}

        {/* Export dropdown */}
        {exports && exports.length > 0 && onExport && (
          exports.length === 1 ? (
            <button
              onClick={() => onExport(exports[0])}
              disabled={!!exportLoading}
              className="btn btn-ghost"
              style={{ padding: '5px 10px', fontSize: 11, gap: 4 }}
            >
              {exportLoading === exports[0] ? <Loader2 size={11} style={{ animation: 'spin 1s linear infinite' }} /> : <Download size={11} />}
              {formatLabels[exports[0]]}
            </button>
          ) : (
            <MiniDropdown
              trigger={<>{exportLoading ? <Loader2 size={11} style={{ animation: 'spin 1s linear infinite' }} /> : <Download size={11} />} Export</>}
              options={exports.map(f => ({ value: f, label: formatLabels[f] }))}
              onChange={(v) => onExport(v as ExportFormat)}
            />
          )
        )}

        {/* Extra action buttons */}
        {children}
      </div>
    </div>
  );
}
