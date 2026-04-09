import { useState, useEffect, useCallback } from 'react';
import {
  FolderOpen, Loader2, Upload, FileSpreadsheet, Calendar, Archive,
  Sparkles, AlertCircle, CheckCircle, Star, Trash2, Search,
  ChevronDown, ChevronUp, Database, Shield, TrendingUp, RefreshCw,
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api } from '../api/client';
import { useToast } from '../components/Toast';
import PipelineVisualization from '../components/PipelineVisualization';

/* ─── Styles ─── */
const label9: React.CSSProperties = { fontSize: 9, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: 'var(--muted)' };

interface OrganizedDataset {
  id: number;
  filename: string;
  original_filename?: string;
  period: string;
  record_count: number;
  quality_tier?: string;     // "gold" | "silver" | "bronze" | "test"
  file_size?: number;
  created_at?: string;
  status?: string;
  is_active?: boolean;
  is_seed?: boolean;
  year?: string;
}

interface Recommendation {
  type: string;           // "cleanup" | "dedup" | "coverage_gap" | "archive"
  message: string;
  severity?: string;      // "info" | "warning" | "critical"
  affected_ids?: number[];
}

interface OrganizedResponse {
  datasets?: OrganizedDataset[];
  groups?: Record<string, OrganizedDataset[]>;
  recommendations?: Recommendation[];
  smart_recommendation?: string;
  current_purpose?: string;
  total_records?: number;
  total_size?: number;
  by_year?: Record<string, { count: number; datasets: any[] }>;
  summary?: { total_records: number; total_size: number };
}

const ACCEPTED = ['.xlsx', '.xls', '.csv'];

function formatSize(bytes: number): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function qualityBadge(tier?: string) {
  const colors: Record<string, { bg: string; fg: string }> = {
    gold: { bg: 'rgba(234,179,8,.1)', fg: '#EAB308' },
    silver: { bg: 'rgba(148,163,184,.1)', fg: '#94A3B8' },
    bronze: { bg: 'rgba(217,119,6,.1)', fg: '#D97706' },
    test: { bg: 'rgba(239,68,68,.06)', fg: 'var(--rose)' },
  };
  const c = colors[tier || ''] || colors.silver;
  return (
    <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 3, background: c.bg, color: c.fg, fontWeight: 600, textTransform: 'uppercase' as const }}>
      {tier || 'standard'}
    </span>
  );
}

function recIcon(type: string) {
  if (type === 'cleanup') return <Trash2 size={12} style={{ color: 'var(--amber, #F59E0B)' }} />;
  if (type === 'dedup') return <RefreshCw size={12} style={{ color: 'var(--sky)' }} />;
  if (type === 'coverage_gap') return <AlertCircle size={12} style={{ color: 'var(--rose)' }} />;
  if (type === 'archive') return <Archive size={12} style={{ color: 'var(--muted)' }} />;
  return <Sparkles size={12} style={{ color: 'var(--sky)' }} />;
}

export default function DataLibraryPage() {
  const { dataset_id } = useStore();
  const { toast } = useToast();
  const [data, setData] = useState<OrganizedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedYear, setExpandedYear] = useState<string | null>(null);

  // Upload state
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const json = await api.organizedData() as OrganizedResponse;
      if (!json) throw new Error('No data');

      // Backend returns { by_year: { "2026": { count, datasets }, ... }, recommendations, ... }
      // Frontend expects { datasets: [...], groups: { "2026": [...] }, recommendations }
      let normalized: OrganizedResponse;
      if (json.by_year && !json.datasets) {
        const flatDatasets: OrganizedDataset[] = [];
        const groups: Record<string, OrganizedDataset[]> = {};
        for (const [year, yearData] of Object.entries<any>(json.by_year)) {
          const dsList = (yearData.datasets || []).map((d: any) => ({
            id: d.id,
            filename: d.name || d.filename || d.original_filename || `Dataset ${d.id}`,
            original_filename: d.original_filename || d.name,
            period: d.period || '',
            record_count: d.record_count || 0,
            quality_tier: d.quality_tier,
            file_size: d.file_size,
            created_at: d.created_at,
            status: d.status,
            is_active: d.is_active,
            is_seed: d.is_test_data,
            year,
          }));
          groups[year] = dsList;
          flatDatasets.push(...dsList);
        }
        normalized = {
          datasets: flatDatasets,
          groups,
          recommendations: json.recommendations || [],
          total_records: json.summary?.total_records,
        };
      } else {
        normalized = json;
      }
      setData(normalized);

      // Auto-expand latest year
      const g = normalized.groups || groupByYear(normalized.datasets || []);
      if (Object.keys(g).length > 0) {
        const years = Object.keys(g).sort().reverse();
        if (years.length > 0) setExpandedYear(years[0]);
      }
    } catch {
      // Fallback: load datasets from existing API
      try {
        const datasets: any = await api.listDatasets();
        const list = Array.isArray(datasets) ? datasets : datasets.datasets || [];
        setData({ datasets: list, recommendations: [], groups: groupByYear(list) });
        if (list.length > 0) {
          const years = Object.keys(groupByYear(list)).sort().reverse();
          if (years.length > 0) setExpandedYear(years[0]);
        }
      } catch {
        toast('Failed to load data library', 'error');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    let success = 0;
    for (const file of Array.from(files)) {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (!ACCEPTED.includes(ext)) {
        toast(`Skipped ${file.name}: unsupported format`, 'error');
        continue;
      }
      try {
        await api.upload(file);
        success++;
      } catch (err: any) {
        toast(`Upload failed: ${file.name}`, 'error');
      }
    }
    if (success > 0) {
      toast(`${success} file(s) uploaded`, 'success');
      loadData();
    }
    setUploading(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const archiveDataset = async (id: number) => {
    try {
      await api.deleteDataset(id);
      toast('Dataset removed', 'success');
      loadData();
    } catch {
      toast('Archive failed', 'error');
    }
  };

  const selectDataset = (id: number) => {
    const ds = (data?.datasets || []).find(d => d.id === id);
    if (ds) {
      useStore.getState().setDatasetId(id);
      useStore.getState().setPeriod(ds.period);
      toast(`Switched to ${ds.filename || ds.original_filename} (${ds.period})`, 'success');
    }
  };

  const groups = data?.groups || groupByYear(data?.datasets || []);
  const recs = data?.recommendations || [];
  const filtered = searchTerm.trim()
    ? (data?.datasets || []).filter(d => (d.filename || d.original_filename || '').toLowerCase().includes(searchTerm.toLowerCase()))
    : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 4px', animation: 'slide-up 0.4s ease both', position: 'relative', overflow: 'hidden' }}>
      <div className="scanline" />
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--b1)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 10, margin: 0, letterSpacing: -0.5 }}>
            <Database size={22} style={{ color: 'var(--sky)' }} /> DATA_LIBRARY_WAREHOUSE
          </h1>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--mono)', opacity: 0.8 }}>
            QUANTITATIVE_DATASET_REGISTRY | STATUS: <span style={{ color: 'var(--emerald)' }}>SYNCHRONIZED</span>
          </p>
        </div>
        <button onClick={loadData} disabled={loading} className="btn-minimal" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px' }}>
          <RefreshCw size={12} className={loading ? 'spin' : ''} /> SYNC_REGISTRY
        </button>
      </div>

      {/* Upload Zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => {
          const input = document.createElement('input');
          input.type = 'file';
          input.multiple = true;
          input.accept = ACCEPTED.join(',');
          input.onchange = () => handleUpload(input.files);
          input.click();
        }}
        className="glass-interactive"
        style={{
          padding: 32, textAlign: 'center', cursor: 'pointer',
          border: dragOver ? '2px dashed var(--sky)' : '1px dashed var(--b2)',
          background: dragOver ? 'rgba(0, 242, 255, 0.05)' : 'rgba(15, 20, 34, 0.3)',
          transition: 'all 0.2s',
        }}
      >
        {uploading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Loader2 size={24} className="spin" style={{ color: 'var(--sky)' }} />
            <span style={{ fontSize: 10, color: 'var(--sky)', fontFamily: 'var(--mono)', fontWeight: 800, letterSpacing: 2 }}>STREAMING_DATA_BITS...</span>
          </div>
        ) : (
          <>
            <Upload size={32} style={{ color: 'var(--sky)', margin: '0 auto 12px', opacity: 0.8 }} />
            <p style={{ fontSize: 12, fontWeight: 800, color: 'var(--heading)', letterSpacing: 1 }}>DROP_FINANCIAL_MATRICES_HERE</p>
            <p style={{ fontSize: 9, color: 'var(--dim)', marginTop: 6, fontFamily: 'var(--mono)' }}>ACCEPTED: .XLSX, .XLS, .CSV | MAX_LIMIT: 50MB</p>
          </>
        )}
      </div>

      {/* Pipeline Visualization */}
      <PipelineVisualization />

      {/* Smart Recommendation */}
      {data?.smart_recommendation && (
        <div className="glass" style={{ padding: 16, display: 'flex', gap: 12, alignItems: 'flex-start', borderLeft: '4px solid var(--sky)', background: 'rgba(0, 242, 255, 0.03)' }}>
          <Sparkles size={18} style={{ color: 'var(--sky)', marginTop: 2, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--sky)', fontFamily: 'var(--mono)', letterSpacing: 2 }}>AGENTIC_INSIGHT</div>
            <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 6, lineHeight: 1.6, fontStyle: 'italic', opacity: 0.9 }}>{data.smart_recommendation}</p>
          </div>
        </div>
      )}

      {loading && (
        <div className="empty-state" style={{ padding: 60 }}>
          <Loader2 size={32} className="spin" style={{ color: 'var(--sky)', marginBottom: 16 }} />
          <div className="empty-state-title">PARSING_OBJECT_MODELS...</div>
        </div>
      )}

      {!loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: 24 }}>
          {/* Left: Datasets grouped by year */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Search */}
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--dim)' }} />
              <input
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                placeholder="SEARCH_REGISTRY_IDS..."
                style={{ 
                  width: '100%', padding: '10px 16px 10px 36px', fontSize: 11, 
                  background: 'var(--bg1)', border: '1px solid var(--b1)', 
                  borderRadius: 2, color: 'var(--text)', boxSizing: 'border-box',
                  fontFamily: 'var(--mono)'
                }}
              />
            </div>

            {/* Search results */}
            {filtered && (
              <div className="glass" style={{ padding: 20 }}>
                <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', marginBottom: 16 }}>MATCH_RESULTS ({filtered.length})</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {filtered.map(ds => <DatasetRow key={ds.id} ds={ds} onArchive={archiveDataset} onSelect={selectDataset} isActive={ds.id === dataset_id} />)}
                </div>
                {filtered.length === 0 && <p style={{ fontSize: 11, color: 'var(--dim)', marginTop: 12, textAlign: 'center', fontFamily: 'var(--mono)' }}>NO_MATCHES_FOUND</p>}
              </div>
            )}

            {/* Grouped by year */}
            {!filtered && Object.keys(groups).sort().reverse().map(year => (
              <div key={year} className="glass" style={{ overflow: 'hidden' }}>
                <button
                  onClick={() => setExpandedYear(expandedYear === year ? null : year)}
                  style={{ 
                    width: '100%', padding: '16px 20px', display: 'flex', alignItems: 'center', 
                    justifyContent: 'space-between', background: 'transparent', border: 'none', 
                    cursor: 'pointer', color: 'var(--heading)' 
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <Calendar size={16} style={{ color: 'var(--sky)' }} />
                    <span style={{ fontSize: 14, fontWeight: 800, letterSpacing: -0.5 }}>{year}</span>
                    <span style={{ fontSize: 10, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>[{groups[year].length}_NODES]</span>
                  </div>
                  {expandedYear === year ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
                {expandedYear === year && (
                  <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {groups[year].map(ds => <DatasetRow key={ds.id} ds={ds} onArchive={archiveDataset} onSelect={selectDataset} isActive={ds.id === dataset_id} />)}
                  </div>
                )}
              </div>
            ))}

            {!filtered && Object.keys(groups).length === 0 && (
              <div className="empty-state">
                <Database size={40} className="empty-state-icon" />
                <div className="empty-state-title">REPOSITORY_EMPTY</div>
                <p className="empty-state-desc">Awaiting initial financial ingestion.</p>
              </div>
            )}
          </div>

          {/* Right: Recommendations panel + Summary */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div className="glass" style={{ padding: 20 }}>
              <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2, marginBottom: 20, borderBottom: '1px solid var(--b1)', paddingBottom: 8 }}>DATA_INTEGRITY_SIGNALS</div>
              {recs.length === 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: 12, background: 'rgba(16, 185, 129, 0.05)', borderRadius: 2 }}>
                  <CheckCircle size={16} style={{ color: 'var(--emerald)' }} />
                  <span style={{ fontSize: 11, color: 'var(--emerald)', fontWeight: 700, fontFamily: 'var(--mono)' }}>REGISTRY_VALIDATED_OK</span>
                </div>
              )}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {recs.map((rec, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, padding: '12px', background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 2, alignItems: 'flex-start' }}>
                    <div style={{ marginTop: 2 }}>{recIcon(rec.type)}</div>
                    <div>
                      <span style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.5, display: 'block', fontWeight: 500 }}>{rec.message}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                        <span style={{ 
                          fontSize: 8, padding: '2px 6px', borderRadius: 2,
                          color: rec.severity === 'critical' ? 'var(--rose)' : rec.severity === 'warning' ? 'var(--amber)' : 'var(--sky)',
                          background: `${rec.severity === 'critical' ? 'var(--rose)' : rec.severity === 'warning' ? 'var(--amber)' : 'var(--sky)'}11`,
                          fontWeight: 800, fontFamily: 'var(--mono)', border: `1px solid ${rec.severity === 'critical' ? 'var(--rose)' : rec.severity === 'warning' ? 'var(--amber)' : 'var(--sky)'}33`
                        }}>
                          {rec.severity?.toUpperCase() || 'INFO'}
                        </span>
                        <span style={{ fontSize: 8, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>TYPE::{rec.type.toUpperCase()}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Summary stats */}
            {data && (
              <div className="glass" style={{ padding: 20 }}>
                <div style={{ fontSize: 10, fontWeight: 900, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 2, marginBottom: 20, borderBottom: '1px solid var(--b1)', paddingBottom: 8 }}>RESOURCES_SUMMARY</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: 'var(--muted)', fontFamily: 'var(--mono)' }}>TOTAL_DATASETS</span>
                    <span style={{ fontWeight: 800, color: 'var(--heading)', fontFamily: 'var(--mono)' }}>{data.datasets?.length || 0}</span>
                  </div>
                  {data.total_records != null && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                      <span style={{ color: 'var(--muted)', fontFamily: 'var(--mono)' }}>TOTAL_RECORDS_MTRX</span>
                      <span style={{ fontWeight: 800, color: 'var(--heading)', fontFamily: 'var(--mono)' }}>{data.total_records.toLocaleString()}</span>
                    </div>
                  )}
                  {data.total_size != null && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                      <span style={{ color: 'var(--muted)', fontFamily: 'var(--mono)' }}>TOTAL_HEURISTIC_SIZE</span>
                      <span style={{ fontWeight: 800, color: 'var(--heading)', fontFamily: 'var(--mono)' }}>{formatSize(data.total_size)}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Dataset Row ─── */
function DatasetRow({ ds, onArchive, onSelect, isActive }: { ds: OrganizedDataset; onArchive: (id: number) => void; onSelect?: (id: number) => void; isActive?: boolean }) {
  return (
    <div 
      className="glass-interactive"
      style={{
        display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px',
        borderLeft: `4px solid ${isActive ? 'var(--sky)' : 'var(--b2)'}`,
        background: isActive ? 'rgba(0, 242, 255, 0.05)' : 'var(--bg1)',
      }}
    >
      <FileSpreadsheet size={16} style={{ color: isActive ? 'var(--sky)' : 'var(--dim)', flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: isActive ? 'var(--sky)' : 'var(--heading)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', letterSpacing: -0.2 }}>
          {ds.filename || ds.original_filename || `Dataset #${ds.id}`}
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 4, opacity: 0.7 }}>
          <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>PER::{ds.period}</span>
          <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>{ds.record_count.toLocaleString()}_ROWS</span>
          {ds.file_size ? <span style={{ fontSize: 9, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>{formatSize(ds.file_size)}</span> : null}
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        {qualityBadge(ds.quality_tier)}
        <div style={{ display: 'flex', gap: 4 }}>
          {onSelect && (
            <button
              onClick={(e) => { e.stopPropagation(); onSelect(ds.id); }}
              className="btn-minimal"
              style={{ padding: '4px 10px', borderColor: isActive ? 'var(--sky)' : 'var(--b2)', color: isActive ? 'var(--sky)' : 'var(--muted)', background: isActive ? 'rgba(0,242,255,0.05)' : 'transparent' }}
            >
              {isActive ? 'ACTIVE' : 'ACTIVATE'}
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); onArchive(ds.id); }}
            className="btn-minimal"
            style={{ padding: '4px 8px', color: 'var(--rose)', borderColor: 'rgba(239, 68, 68, 0.2)' }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Group datasets by year helper ─── */
function groupByYear(datasets: OrganizedDataset[]): Record<string, OrganizedDataset[]> {
  const groups: Record<string, OrganizedDataset[]> = {};
  for (const ds of datasets) {
    const year = ds.year || extractYear(ds.period) || 'Unknown';
    if (!groups[year]) groups[year] = [];
    groups[year].push(ds);
  }
  return groups;
}

function extractYear(period?: string): string {
  if (!period) return '';
  const match = period.match(/20\d{2}/);
  return match ? match[0] : period.substring(0, 4);
}
