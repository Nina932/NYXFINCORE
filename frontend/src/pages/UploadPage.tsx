import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileSpreadsheet, CheckCircle, AlertCircle, X, Loader2,
  ArrowRight, Sparkles, Database, Calendar, Clock,
  ChevronRight, HardDrive, RefreshCw, Download, Search, Trash2,
  ChevronDown, Edit3, Check, XCircle, Eye, EyeOff,
} from 'lucide-react';
import { useStore } from '../store/useStore';
import { api, captainChat } from '../api/client';
import { t } from '../i18n/translations';
import { useToast } from '../components/Toast';

const ACCEPTED = ['.xlsx', '.xls', '.csv'];
const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
const btnPrimary: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 6, background: 'linear-gradient(135deg, var(--sky), var(--blue))', color: 'var(--heading)', fontWeight: 600, padding: '10px 22px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 12 };

const CLASSIFICATION_OPTIONS = [
  'Revenue', 'COGS', 'Gross Profit', 'Selling Expenses', 'Admin Expenses',
  'Depreciation', 'Other Income', 'Other Expense', 'Financial Income',
  'Financial Expense', 'Tax', 'Asset', 'Liability', 'Equity',
];

interface DatasetRecord {
  id: number;
  name: string;
  original_filename?: string;
  file_type: string;
  file_size: number;
  extension?: string;
  record_count: number;
  status: string;
  is_active: boolean;
  is_seed?: boolean;
  period: string;
  currency: string;
  company?: string;
  sheet_count: number;
  parse_metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at?: string | null;
  entity_counts?: Record<string, number>;
  parsed_sheets?: string[];
}

interface PendingApproval {
  id?: number;
  code: string;
  name?: string;
  pl_line?: string;
  section?: string;
  confidence?: number;
  method?: string;
  explanation?: string;
  override?: string; // user-selected override
  status?: 'pending' | 'approved' | 'modified' | 'rejected';
}

interface MultiUploadProgress {
  total: number;
  current: number;
  fileName: string;
  results: { file: string; success: boolean; error?: string; period?: string }[];
}

function formatSize(bytes: number): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function confidenceColor(c: number): string {
  if (c >= 0.8) return 'var(--emerald)';
  if (c >= 0.5) return 'var(--amber)';
  return 'var(--rose)';
}

function confidenceLabel(c: number): string {
  if (c >= 0.8) return 'High';
  if (c >= 0.5) return 'Medium';
  return 'Low';
}

/* ─── Classification Review Modal ─── */
function ClassificationModal({
  items, onClose, onSave,
}: {
  items: PendingApproval[];
  onClose: () => void;
  onSave: (items: PendingApproval[]) => void;
}) {
  const [rows, setRows] = useState<PendingApproval[]>(
    items.map(i => ({ ...i, status: 'pending', override: '' }))
  );
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const updateRow = (idx: number, patch: Partial<PendingApproval>) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, ...patch } : r));
  };

  const approveAll = () => {
    setRows(prev => prev.map(r => r.status === 'pending' ? { ...r, status: 'approved' } : r));
  };

  const pendingCount = rows.filter(r => r.status === 'pending').length;
  const approvedCount = rows.filter(r => r.status === 'approved').length;
  const modifiedCount = rows.filter(r => r.status === 'modified').length;
  const rejectedCount = rows.filter(r => r.status === 'rejected').length;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,.7)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{
        background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 12,
        width: '90%', maxWidth: 900, maxHeight: '85vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 25px 60px rgba(0,0,0,.5)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid var(--b1)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={18} style={{ color: 'var(--violet)' }} /> AI Classification Review
            </h2>
            <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 10 }}>
              <span style={{ color: 'var(--muted)' }}>Pending: <b style={{ color: 'var(--amber)' }}>{pendingCount}</b></span>
              <span style={{ color: 'var(--muted)' }}>Approved: <b style={{ color: 'var(--emerald)' }}>{approvedCount}</b></span>
              <span style={{ color: 'var(--muted)' }}>Modified: <b style={{ color: 'var(--sky)' }}>{modifiedCount}</b></span>
              <span style={{ color: 'var(--muted)' }}>Rejected: <b style={{ color: 'var(--rose)' }}>{rejectedCount}</b></span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button onClick={approveAll} style={{
              fontSize: 11, padding: '7px 16px', borderRadius: 6,
              background: 'rgba(52,211,153,.1)', color: 'var(--emerald)',
              border: '1px solid rgba(52,211,153,.2)', cursor: 'pointer', fontWeight: 600,
            }}>
              <Check size={12} style={{ marginRight: 4, verticalAlign: -2 }} /> Accept All
            </button>
            <button onClick={onClose} style={{
              background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 4,
            }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Table body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                <th style={{ padding: '8px 16px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Code</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Account Name</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>AI Suggestion</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Confidence</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Override</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500, width: 160 }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((pa, idx) => {
                const conf = pa.confidence ?? 0;
                const isExpanded = expandedIdx === idx;
                const statusBg = pa.status === 'approved'
                  ? 'rgba(52,211,153,.04)' : pa.status === 'modified'
                  ? 'rgba(56,189,248,.04)' : pa.status === 'rejected'
                  ? 'rgba(248,113,113,.04)' : 'transparent';
                return (
                  <tr key={idx} style={{ borderBottom: '1px solid var(--b1)', background: statusBg, transition: 'background .15s' }}>
                    <td style={{ padding: '10px 16px', fontFamily: 'var(--mono)', color: 'var(--sky)', fontWeight: 600, fontSize: 12 }}>
                      {pa.code}
                    </td>
                    <td style={{ padding: '10px 12px', maxWidth: 200 }}>
                      <div style={{ color: 'var(--heading)', fontWeight: 500 }}>{(pa.name || '').substring(0, 50)}</div>
                      {pa.method && <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>Method: {pa.method}</div>}
                      {isExpanded && pa.explanation && (
                        <div style={{
                          fontSize: 10, color: 'var(--muted)', marginTop: 6, padding: 8,
                          background: 'var(--bg3)', borderRadius: 6, fontStyle: 'italic',
                          border: '1px solid var(--b1)', lineHeight: 1.5,
                        }}>
                          {pa.explanation}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{
                        padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 600,
                        background: 'rgba(251,191,36,.08)', color: 'var(--amber)', border: '1px solid rgba(251,191,36,.15)',
                      }}>
                        {pa.pl_line || pa.section || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                        <span style={{
                          fontSize: 13, fontWeight: 700, fontFamily: 'var(--mono)',
                          color: confidenceColor(conf),
                        }}>
                          {Math.round(conf * 100)}%
                        </span>
                        <span style={{ fontSize: 8, color: confidenceColor(conf), textTransform: 'uppercase', letterSpacing: 1 }}>
                          {confidenceLabel(conf)}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <select
                        value={pa.override || ''}
                        onChange={e => updateRow(idx, {
                          override: e.target.value,
                          status: e.target.value ? 'modified' : 'pending',
                        })}
                        style={{
                          width: '100%', height: 30, borderRadius: 6,
                          border: '1px solid var(--b2)', background: 'var(--bg3)',
                          color: pa.override ? 'var(--sky)' : 'var(--muted)',
                          fontSize: 10, padding: '0 8px', fontFamily: 'inherit', outline: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        <option value="">Keep AI suggestion</option>
                        {CLASSIFICATION_OPTIONS.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                        <button
                          onClick={() => updateRow(idx, { status: 'approved', override: '' })}
                          style={{
                            fontSize: 9, padding: '4px 10px', borderRadius: 5, cursor: 'pointer', fontWeight: 600,
                            background: pa.status === 'approved' ? 'rgba(52,211,153,.15)' : 'transparent',
                            color: 'var(--emerald)', border: '1px solid rgba(52,211,153,.25)',
                          }}
                          title="Accept AI suggestion"
                        >
                          <Check size={10} />
                        </button>
                        <button
                          onClick={() => updateRow(idx, { status: 'rejected' })}
                          style={{
                            fontSize: 9, padding: '4px 10px', borderRadius: 5, cursor: 'pointer', fontWeight: 600,
                            background: pa.status === 'rejected' ? 'rgba(248,113,113,.15)' : 'transparent',
                            color: 'var(--rose)', border: '1px solid rgba(248,113,113,.25)',
                          }}
                          title="Reject classification"
                        >
                          <XCircle size={10} />
                        </button>
                        <button
                          onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                          style={{
                            fontSize: 9, padding: '4px 10px', borderRadius: 5, cursor: 'pointer',
                            background: 'transparent', color: 'var(--muted)', border: '1px solid var(--b2)',
                          }}
                          title={isExpanded ? "Hide explanation" : "Show explanation"}
                        >
                          {isExpanded ? <EyeOff size={10} /> : <Eye size={10} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--b1)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 10, color: 'var(--muted)' }}>
            {rows.length} accounts &middot; {pendingCount} need review
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{
              padding: '8px 16px', borderRadius: 6, border: '1px solid var(--b2)',
              background: 'transparent', color: 'var(--muted)', cursor: 'pointer', fontSize: 11,
            }}>
              Cancel
            </button>
            <button
              onClick={async () => {
                setSaving(true);
                await onSave(rows);
                setSaving(false);
              }}
              disabled={saving}
              style={{
                ...btnPrimary, padding: '8px 20px', fontSize: 11,
                opacity: saving ? 0.7 : 1,
              }}
            >
              {saving ? <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> Saving...</> : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { setFromUpload, setFromDashboard, setLoading, company, period } = useStore();
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [progress, setProgress] = useState('');
  const [multiProgress, setMultiProgress] = useState<MultiUploadProgress | null>(null);

  // Dataset list
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(true);
  const [switchingId, setSwitchingId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [askingCaptainId, setAskingCaptainId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [classificationSummary, setClassificationSummary] = useState<any>(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkAction, setBulkAction] = useState<string | null>(null);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };
  const selectAll = () => {
    if (selectedIds.size === filteredDatasets.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(filteredDatasets.map(d => d.id)));
  };
  const bulkDelete = async () => {
    if (!confirm(`Delete ${selectedIds.size} dataset(s)? This cannot be undone.`)) return;
    setBulkAction('deleting');
    for (const id of selectedIds) {
      try { await api.deleteDataset(id); } catch {}
    }
    setDatasets(prev => prev.filter(d => !selectedIds.has(d.id)));
    setSelectedIds(new Set());
    setBulkAction(null);
    toast?.(`Deleted ${selectedIds.size} datasets`, 'success');
  };
  const bulkAnalyze = async () => {
    setBulkAction('analyzing');
    const selected = datasets.filter(d => selectedIds.has(d.id));
    const periods = selected.map(d => d.period).join(', ');
    try {
      const res = await captainChat(`Compare and analyze these periods: ${periods}. What trends do you see?`);
      toast?.(res.content.substring(0, 100) + '...', 'info');
    } catch {}
    setBulkAction(null);
  };

  const filteredDatasets = datasets.filter(ds =>
    ds.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (ds.company || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (ds.period || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const askCaptainAboutDataset = async (ds: DatasetRecord) => {
    setAskingCaptainId(ds.id);
    try {
      const question = `Analyze dataset "${ds.name}" from period ${ds.period || 'unknown'} for ${ds.company || 'this company'}. Provide key financial insights and recommendations.`;
      const res = await captainChat(question);
      toast(res.content.substring(0, 200), 'info', 8000);
    } catch {
      toast('AI assistant is temporarily unavailable.', 'warning');
    } finally {
      setAskingCaptainId(null);
    }
  };

  const deleteDataset = async (ds: DatasetRecord) => {
    const confirmed = window.confirm(
      `Delete "${ds.name}" (${ds.company || 'Unknown'} \u2022 ${ds.period || '?'})?\n\nThis will remove all snapshots and orchestrator data for this dataset. This cannot be undone.`
    );
    if (!confirmed) return;
    setDeletingId(ds.id);
    try {
      await api.deleteDataset(ds.id);
      setDatasets(prev => prev.filter(d => d.id !== ds.id));
    } catch {
      toast('Failed to delete dataset. Please try again.', 'error');
    } finally {
      setDeletingId(null);
    }
  };

  const fetchDatasets = async () => {
    setLoadingDatasets(true);
    try {
      const res = await api.listDatasets() as { datasets: DatasetRecord[] };
      setDatasets(res.datasets || []);
    } catch { setDatasets([]); }
    finally { setLoadingDatasets(false); }
  };

  useEffect(() => { fetchDatasets(); }, []);

  const switchToDataset = async (ds: DatasetRecord) => {
    setSwitchingId(ds.id);
    try {
      const data = await api.getDataset(ds.id) as Record<string, unknown>;
      if (data) setFromDashboard(data);
    } catch { /* swallow */ }
    finally { setSwitchingId(null); }
  };

  const handleFiles = (newFiles: File[]) => {
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      const unique = newFiles.filter(f => !existing.has(f.name + f.size));
      return [...prev, ...unique];
    });
    setError('');
    setSuccess(false);
    setProgress('');
    setMultiProgress(null);
  };

  const removeFile = (idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter(f =>
      ACCEPTED.some(ext => f.name.toLowerCase().endsWith(ext))
    );
    if (dropped.length) handleFiles(dropped);
  }, []);

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files ? Array.from(e.target.files) : [];
    if (selected.length) handleFiles(selected);
    e.target.value = ''; // allow re-selecting same files
  };

  const uploadSingleFile = async (file: File): Promise<{ success: boolean; data?: any; error?: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const token = localStorage.getItem('token') || '';
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch('/api/agent/agents/smart-upload', {
      method: 'POST', headers, body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      return { success: false, error: err.detail || `Upload failed: ${res.status}` };
    }
    const data = await res.json();
    return { success: true, data };
  };

  const handleUpload = async () => {
    if (!files.length) return;
    setUploading(true);
    setError('');
    setLoading(true);

    const allPending: PendingApproval[] = [];
    let lastData: any = null;
    let lastSummary: any = null;

    if (files.length === 1) {
      // Single file — original flow
      setProgress('Processing financial data with AI... (this may take 10-40 seconds)');
      try {
        const result = await uploadSingleFile(files[0]);
        if (!result.success) throw new Error(result.error);
        lastData = result.data;
        setFromUpload(result.data);
        if (result.data.pending_approvals?.length > 0) {
          allPending.push(...result.data.pending_approvals);
        }
        if (result.data.classification_summary) lastSummary = result.data.classification_summary;
        setSuccess(true);
        setProgress('');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed');
        setProgress('');
      }
    } else {
      // Multi-file upload — sequential with progress
      const tracker: MultiUploadProgress = {
        total: files.length, current: 0, fileName: '', results: [],
      };
      setMultiProgress({ ...tracker });

      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        tracker.current = i + 1;
        tracker.fileName = f.name;
        setMultiProgress({ ...tracker });
        setProgress(`Uploading ${i + 1}/${files.length}: ${f.name}...`);

        try {
          const result = await uploadSingleFile(f);
          if (result.success) {
            tracker.results.push({ file: f.name, success: true, period: result.data?.period });
            lastData = result.data;
            if (result.data?.pending_approvals?.length > 0) {
              allPending.push(...result.data.pending_approvals);
            }
            if (result.data?.classification_summary) lastSummary = result.data.classification_summary;
          } else {
            tracker.results.push({ file: f.name, success: false, error: result.error });
          }
        } catch (err) {
          tracker.results.push({ file: f.name, success: false, error: String(err) });
        }
        setMultiProgress({ ...tracker });
      }

      // Use last successful upload data
      if (lastData) {
        setFromUpload(lastData);
        setSuccess(true);
      } else {
        setError('All uploads failed. Check file formats and try again.');
      }
      setProgress('');
    }

    if (allPending.length > 0) setPendingApprovals(allPending);
    if (lastSummary) setClassificationSummary(lastSummary);
    fetchDatasets();
    setUploading(false);
    setLoading(false);
  };

  const handleSaveClassifications = async (rows: PendingApproval[]) => {
    let approvedCount = 0;
    let modifiedCount = 0;

    for (const row of rows) {
      try {
        if (row.status === 'approved' && row.id) {
          await api.approveClassification(row.id);
          approvedCount++;
        } else if (row.status === 'modified' && row.id && row.override) {
          await api.modifyClassification(row.id, { pl_line: row.override });
          modifiedCount++;
        }
        // Rejected items are simply not approved — backend keeps them as-is
      } catch { /* swallow individual errors */ }
    }

    setPendingApprovals([]);
    setShowApprovalModal(false);
    toast(`Classifications saved: ${approvedCount} approved, ${modifiedCount} modified`, 'success');
  };

  const downloadExcel = async () => {
    const s = useStore.getState();
    if (!s.pnl) return;
    try {
      const blob = await api.excelReport({
        pnl: s.pnl, balance_sheet: s.balance_sheet,
        revenue_breakdown: s.revenue_breakdown, cogs_breakdown: s.cogs_breakdown,
        pl_line_items: s.pl_line_items,
        company: s.company ?? 'Company', period: s.period ?? '',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${s.company ?? 'finai'}_report.xlsx`.replace(/ /g, '_');
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* swallow */ }
  };

  if (success) {
    const { company: co, period: pe, pnl } = useStore.getState();
    const successfulCount = multiProgress?.results.filter(r => r.success).length ?? 1;
    const failedCount = multiProgress?.results.filter(r => !r.success).length ?? 0;
    const periods = multiProgress?.results
      .filter(r => r.success && r.period)
      .map(r => r.period!)
      .sort();

    return (
      <div style={{ maxWidth: 700, margin: '40px auto', textAlign: 'center' }}>
        <div style={{ ...card, padding: 32, borderColor: 'rgba(52,211,153,.2)' }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(52,211,153,.08)', border: '2px solid var(--emerald)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <CheckCircle size={28} style={{ color: 'var(--emerald)' }} />
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--heading)', marginBottom: 6 }}>Upload Complete</h2>
          <p style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 12 }}>
            {co ?? 'Company'} {pe ? `\u2022 ${pe}` : ''} — data processed successfully.
          </p>

          {/* Multi-file summary */}
          {multiProgress && multiProgress.total > 1 && (
            <div style={{ background: 'var(--bg3)', borderRadius: 8, padding: 12, marginBottom: 16, textAlign: 'left' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 8 }}>
                Batch Upload Summary
              </div>
              <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>
                <span>Total: <b style={{ color: 'var(--heading)' }}>{multiProgress.total}</b></span>
                <span>Success: <b style={{ color: 'var(--emerald)' }}>{successfulCount}</b></span>
                {failedCount > 0 && <span>Failed: <b style={{ color: 'var(--rose)' }}>{failedCount}</b></span>}
              </div>
              {periods && periods.length > 1 && (
                <div style={{ fontSize: 10, color: 'var(--sky)' }}>
                  Periods: {periods[0]} to {periods[periods.length - 1]}
                </div>
              )}
              {/* Individual results */}
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3 }}>
                {multiProgress.results.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10 }}>
                    {r.success
                      ? <CheckCircle size={10} style={{ color: 'var(--emerald)' }} />
                      : <AlertCircle size={10} style={{ color: 'var(--rose)' }} />
                    }
                    <span style={{ color: r.success ? 'var(--text)' : 'var(--rose)' }}>{r.file}</span>
                    {r.period && <span style={{ color: 'var(--muted)', fontFamily: 'var(--mono)' }}>{r.period}</span>}
                    {r.error && <span style={{ color: 'var(--rose)', fontSize: 9 }}>{r.error.substring(0, 60)}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {pnl && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 24 }}>
              {[
                ['Revenue', pnl.revenue ?? pnl.total_revenue ?? 0],
                ['COGS', pnl.cogs ?? pnl.total_cogs ?? 0],
                ['Net Profit', pnl.net_profit ?? 0],
              ].map(([label, value]) => (
                <div key={label as string} style={{ background: 'var(--bg3)', borderRadius: 8, padding: 12 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--muted)', marginBottom: 4 }}>{label as string}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--heading)', fontFamily: 'var(--mono)' }}>
                    {'\u20BE'}{((value as number) / 1_000_000).toFixed(1)}M
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Classification Summary */}
          {classificationSummary && (
            <div style={{ background: 'var(--bg3)', borderRadius: 8, padding: 12, marginBottom: 16, textAlign: 'left' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Sparkles size={12} style={{ color: 'var(--violet)' }} /> AI Classification Summary
              </div>
              <div style={{ display: 'flex', gap: 12, fontSize: 10, color: 'var(--muted)' }}>
                <span>Total: <b style={{ color: 'var(--heading)' }}>{classificationSummary.total}</b></span>
                <span>Auto-accepted: <b style={{ color: 'var(--emerald)' }}>{classificationSummary.auto_accepted}</b></span>
                {classificationSummary.pending_review > 0 && (
                  <span>Needs review: <b style={{ color: 'var(--amber)' }}>{classificationSummary.pending_review}</b></span>
                )}
              </div>
              {classificationSummary.methods && (
                <div style={{ display: 'flex', gap: 8, marginTop: 6, fontSize: 9, color: 'var(--muted)' }}>
                  {Object.entries(classificationSummary.methods).map(([method, count]) => (
                    <span key={method} style={{ padding: '1px 6px', borderRadius: 4, background: 'var(--bg2)', border: '1px solid var(--b1)' }}>
                      {method}: {count as number}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Pending Approvals — now opens modal */}
          {pendingApprovals.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <button
                onClick={() => setShowApprovalModal(true)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, margin: '0 auto',
                  padding: '10px 24px', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                  background: 'rgba(251,191,36,.08)', color: 'var(--amber)',
                  border: '1px solid rgba(251,191,36,.2)',
                }}
              >
                <AlertCircle size={14} />
                Review {pendingApprovals.length} Classifications
                <ChevronRight size={14} />
              </button>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
            <button onClick={() => navigate('/')} style={btnPrimary}>
              Dashboard <ArrowRight size={14} />
            </button>
            <button onClick={() => navigate('/pnl')} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--bg2)', color: 'var(--text)', padding: '8px 14px', borderRadius: 8, border: '1px solid var(--b1)', cursor: 'pointer', fontSize: 11 }}>
              View P&L
            </button>
            <button onClick={() => { setFiles([]); setSuccess(false); setMultiProgress(null); }} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'var(--bg2)', color: 'var(--text)', padding: '8px 14px', borderRadius: 8, border: '1px solid var(--b1)', cursor: 'pointer', fontSize: 11 }}>
              Upload More
            </button>
          </div>
        </div>

        {/* Classification Modal */}
        {showApprovalModal && (
          <ClassificationModal
            items={pendingApprovals}
            onClose={() => setShowApprovalModal(false)}
            onSave={handleSaveClassifications}
          />
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Database size={20} style={{ color: 'var(--sky)' }} /> {t('page.data_library')}
          </h1>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
            Upload, manage, and switch between financial datasets
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {company && (
            <button onClick={downloadExcel} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'rgba(52,211,153,.08)', color: 'var(--emerald)',
              padding: '8px 14px', borderRadius: 8, border: '1px solid rgba(52,211,153,.15)',
              cursor: 'pointer', fontSize: 11, fontWeight: 500,
            }}>
              <Download size={13} /> Export Excel
            </button>
          )}
          <button onClick={fetchDatasets} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'var(--bg2)', color: 'var(--text)',
            padding: '8px 14px', borderRadius: 8, border: '1px solid var(--b1)',
            cursor: 'pointer', fontSize: 11,
          }}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* Upload Section */}
      <div style={{ ...card, padding: 20 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
          <Upload size={16} style={{ color: 'var(--sky)' }} /> Upload New Dataset
        </h2>

        {error && (
          <div style={{ background: 'rgba(248,113,113,.06)', border: '1px solid rgba(248,113,113,.15)', color: 'var(--rose)', fontSize: 12, borderRadius: 8, padding: '8px 14px', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
            <AlertCircle size={14} /> {error}
          </div>
        )}

        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          style={{
            border: `2px dashed ${dragOver ? 'var(--sky)' : 'var(--b2)'}`,
            borderRadius: 10, padding: 32, textAlign: 'center',
            transition: 'all 0.2s',
            background: dragOver ? 'rgba(56,189,248,.03)' : 'transparent',
          }}
        >
          <Upload size={32} style={{ margin: '0 auto 10px', color: 'var(--muted)' }} />
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 4 }}>
            Drag & drop your financial files here
          </p>
          <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
            Select one or multiple files at once
          </p>
          <p style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 12, opacity: 0.7 }}>
            Supports batch upload — e.g. Jan through Dec in one go
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginBottom: 12 }}>
            {ACCEPTED.map(ext => (
              <span key={ext} style={{ padding: '2px 8px', borderRadius: 10, fontSize: 9, background: 'var(--bg3)', color: 'var(--text)', border: '1px solid var(--b1)' }}>
                {ext}
              </span>
            ))}
          </div>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--bg3)', color: 'var(--heading)', padding: '7px 16px', borderRadius: 8, border: '1px solid var(--b2)', cursor: 'pointer', fontSize: 11, fontWeight: 500 }}>
            Browse Files
            <input type="file" accept=".xlsx,.xls,.csv" multiple onChange={onFileInput} style={{ display: 'none' }} />
          </label>
        </div>

        {/* Selected files list */}
        {files.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{files.length} file{files.length > 1 ? 's' : ''} selected</span>
              {files.length > 1 && !uploading && (
                <button onClick={() => setFiles([])} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: 10, textDecoration: 'underline' }}>
                  Clear all
                </button>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {files.map((f, idx) => {
                const mp = multiProgress;
                const result = mp?.results.find(r => r.file === f.name);
                const isCurrent = mp && mp.current === idx + 1 && !result;
                return (
                  <div key={f.name + f.size} style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                    background: result?.success ? 'rgba(52,211,153,.04)' : result && !result.success ? 'rgba(248,113,113,.04)' : isCurrent ? 'rgba(56,189,248,.04)' : 'var(--bg3)',
                    borderRadius: 6, border: `1px solid ${isCurrent ? 'rgba(56,189,248,.15)' : 'transparent'}`,
                  }}>
                    {result?.success
                      ? <CheckCircle size={13} style={{ color: 'var(--emerald)' }} />
                      : result && !result.success
                      ? <AlertCircle size={13} style={{ color: 'var(--rose)' }} />
                      : isCurrent
                      ? <Loader2 size={13} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
                      : <FileSpreadsheet size={13} style={{ color: 'var(--muted)' }} />
                    }
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: 11, color: 'var(--heading)' }}>{f.name}</span>
                      <span style={{ fontSize: 9, color: 'var(--muted)', marginLeft: 8 }}>{formatSize(f.size)}</span>
                      {result?.period && <span style={{ fontSize: 9, color: 'var(--sky)', marginLeft: 8, fontFamily: 'var(--mono)' }}>{result.period}</span>}
                      {result?.error && <span style={{ fontSize: 9, color: 'var(--rose)', marginLeft: 8 }}>{result.error.substring(0, 50)}</span>}
                    </div>
                    {!uploading && (
                      <button onClick={() => removeFile(idx)} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 2 }}>
                        <X size={12} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Upload button */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10, gap: 8 }}>
              <button onClick={handleUpload} disabled={uploading} style={{ ...btnPrimary, padding: '10px 24px', fontSize: 12, opacity: uploading ? 0.7 : 1 }}>
                {uploading
                  ? <><Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> {multiProgress ? `${multiProgress.current}/${multiProgress.total}` : 'Processing...'}</>
                  : <><Sparkles size={14} /> {files.length > 1 ? `Upload ${files.length} Files` : 'Upload & Analyze'}</>
                }
              </button>
            </div>
          </div>
        )}

        {progress && !multiProgress && (
          <div style={{ marginTop: 12, padding: 10, background: 'rgba(56,189,248,.04)', border: '1px solid rgba(56,189,248,.1)', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Loader2 size={14} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: 11, color: 'var(--sky)' }}>{progress}</span>
          </div>
        )}
      </div>

      {/* Dataset History */}
      <div style={{ ...card, overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--b1)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <h2 style={{ fontSize: 14, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <HardDrive size={15} style={{ color: 'var(--sky)' }} /> Data Catalogue
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)', fontWeight: 400 }}>({filteredDatasets.length})</span>
          </h2>
          <div style={{ position: 'relative', width: 240 }}>
            <Search size={12} style={{ position: 'absolute', left: 10, top: 9, color: 'var(--muted)' }} />
            <input
              type="text"
              placeholder="Search datasets..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              style={{
                width: '100%', height: 32, paddingLeft: 28, paddingRight: 10,
                borderRadius: 8, border: '1px solid var(--b2)', background: 'var(--bg3)',
                color: 'var(--text)', fontSize: 11, outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>
        </div>

        {loadingDatasets ? (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Loader2 size={20} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite', margin: '0 auto' }} />
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>Loading datasets...</p>
          </div>
        ) : filteredDatasets.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Database size={32} style={{ color: 'var(--b2)', margin: '0 auto 8px' }} />
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>No datasets uploaded yet. Upload a file above to get started.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            {/* Bulk actions bar */}
            {selectedIds.size > 0 && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', marginBottom: 8,
                background: 'color-mix(in srgb, var(--sky) 8%, transparent)',
                border: '1px solid color-mix(in srgb, var(--sky) 20%, transparent)',
                borderRadius: 8,
              }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--sky)' }}>
                  {selectedIds.size} selected
                </span>
                <div style={{ flex: 1 }} />
                <button onClick={bulkAnalyze} disabled={bulkAction === 'analyzing'} style={{
                  padding: '5px 14px', borderRadius: 6, border: '1px solid var(--sky)', background: 'transparent',
                  color: 'var(--sky)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                }}>
                  {bulkAction === 'analyzing' ? 'Analyzing...' : 'Compare & Analyze'}
                </button>
                <button onClick={bulkDelete} disabled={bulkAction === 'deleting'} style={{
                  padding: '5px 14px', borderRadius: 6, border: '1px solid var(--rose)', background: 'transparent',
                  color: 'var(--rose)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                }}>
                  {bulkAction === 'deleting' ? 'Deleting...' : 'Delete Selected'}
                </button>
                <button onClick={() => setSelectedIds(new Set())} style={{
                  padding: '5px 10px', borderRadius: 6, border: '1px solid var(--b2)', background: 'transparent',
                  color: 'var(--muted)', fontSize: 11, cursor: 'pointer',
                }}>
                  Clear
                </button>
              </div>
            )}
            <thead>
              <tr style={{ borderBottom: '1px solid var(--b1)' }}>
                <th style={{ padding: '8px 6px', width: 30 }}>
                  <input type="checkbox" checked={selectedIds.size === filteredDatasets.length && filteredDatasets.length > 0} onChange={selectAll} style={{ cursor: 'pointer', accentColor: 'var(--sky)' }} />
                </th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>File</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Company</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Period</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Type</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Currency</th>
                <th style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Records</th>
                <th style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Size</th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Uploaded</th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--muted)', fontWeight: 500 }}>Status</th>
                <th style={{ padding: '8px 12px', width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {filteredDatasets.map(ds => {
                const isActive = ds.period === period && (ds.company === company || !company);
                return (
                  <tr
                    key={ds.id}
                    style={{
                      borderBottom: '1px solid var(--b1)',
                      background: isActive ? 'rgba(56,189,248,.04)' : 'transparent',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,.02)'; }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                  >
                    <td style={{ padding: '10px 6px', width: 30 }}>
                      <input type="checkbox" checked={selectedIds.has(ds.id)} onChange={() => toggleSelect(ds.id)} style={{ cursor: 'pointer', accentColor: 'var(--sky)' }} />
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <FileSpreadsheet size={14} style={{ color: isActive ? 'var(--sky)' : 'var(--muted)', flexShrink: 0 }} />
                        <div>
                          <div style={{ fontWeight: 500, color: isActive ? '#fff' : 'var(--text)', fontSize: 12 }}>
                            {ds.name}
                          </div>
                          {ds.sheet_count > 0 && (
                            <div style={{ fontSize: 9, color: 'var(--muted)' }}>{ds.sheet_count} sheets</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--text)', fontSize: 11 }}>
                      {ds.company || '\u2014'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text)', fontSize: 11 }}>
                        <Calendar size={11} style={{ color: 'var(--muted)' }} />
                        {ds.period || '\u2014'}
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ padding: '2px 7px', borderRadius: 4, fontSize: 9, fontFamily: 'var(--mono)', background: 'rgba(56,189,248,.08)', color: 'var(--sky)', border: '1px solid rgba(56,189,248,.12)' }}>
                        .{ds.extension || 'xlsx'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text)' }}>
                      {ds.currency || 'GEL'}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text)' }}>
                      {ds.record_count || '\u2014'}
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--muted)' }}>
                      {formatSize(ds.file_size)}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--muted)', fontSize: 10 }}>
                        <Clock size={10} />
                        {formatDate(ds.created_at)}
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      {isActive ? (
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 9, fontWeight: 600, background: 'rgba(56,189,248,.1)', color: 'var(--sky)', border: '1px solid rgba(56,189,248,.2)' }}>
                          ACTIVE
                        </span>
                      ) : (
                        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 9, background: 'var(--bg3)', color: 'var(--muted)' }}>
                          {ds.status}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button
                          onClick={() => askCaptainAboutDataset(ds)}
                          disabled={askingCaptainId === ds.id}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 3,
                            background: 'rgba(167,139,250,.08)', color: 'var(--violet)',
                            padding: '5px 8px', borderRadius: 6,
                            border: '1px solid rgba(167,139,250,.15)',
                            cursor: 'pointer', fontSize: 9, fontWeight: 500,
                          }}
                          title="Ask AI about this dataset"
                        >
                          {askingCaptainId === ds.id
                            ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />
                            : <><Sparkles size={10} /> Ask</>
                          }
                        </button>
                        {!isActive && (
                          <button
                            onClick={() => switchToDataset(ds)}
                            disabled={switchingId === ds.id}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 4,
                              background: 'rgba(56,189,248,.08)', color: 'var(--sky)',
                              padding: '5px 10px', borderRadius: 6,
                              border: '1px solid rgba(56,189,248,.15)',
                              cursor: switchingId === ds.id ? 'default' : 'pointer',
                              fontSize: 10, fontWeight: 500,
                            }}
                          >
                            {switchingId === ds.id ? (
                              <Loader2 size={11} style={{ animation: 'spin 1s linear infinite' }} />
                            ) : (
                              <>Load <ChevronRight size={11} /></>
                            )}
                          </button>
                        )}
                        <button
                          onClick={() => deleteDataset(ds)}
                          disabled={deletingId === ds.id}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 3,
                            background: 'rgba(248,113,113,.08)', color: 'var(--rose)',
                            padding: '5px 8px', borderRadius: 6,
                            border: '1px solid rgba(248,113,113,.15)',
                            cursor: deletingId === ds.id ? 'default' : 'pointer',
                            fontSize: 9, fontWeight: 500,
                          }}
                          title="Delete this dataset"
                        >
                          {deletingId === ds.id
                            ? <Loader2 size={10} style={{ animation: 'spin 1s linear infinite' }} />
                            : <Trash2 size={10} />
                          }
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* How it works */}
      <div>
        <h3 style={{ fontSize: 11, fontWeight: 600, color: 'var(--muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>How it works</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          {[
            { step: '01', title: 'Upload', desc: 'Drop one or multiple Excel files' },
            { step: '02', title: 'AI Processing', desc: 'Auto-detects structure, extracts P&L, BS' },
            { step: '03', title: 'Insights', desc: 'Health score, strategy, alerts generated' },
          ].map(s => (
            <div key={s.step} style={{ ...card, padding: 12 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--sky)', fontWeight: 600 }}>{s.step}</span>
              <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', marginTop: 3 }}>{s.title}</p>
              <p style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
