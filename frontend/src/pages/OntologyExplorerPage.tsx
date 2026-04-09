import { useState, useEffect, useCallback } from 'react';
import { 
  Network, Activity, LayoutGrid, Search, Zap, Loader2, X, ChevronRight, 
  Sparkles, HelpCircle, Shield, Target, Play, CheckCircle2, AlertOctagon, 
  Edit3, Save, Trash2, ChevronUp, ChevronDown, BarChart3, AlertCircle,
  Building2, BookOpen, Calendar, FileText, AlertTriangle, TrendingUp, Gavel, 
  BookMarked
} from 'lucide-react';
import ContextualBriefing from '../components/ContextualBriefing';
import TechIcon from '../components/TechIcon';
import DiscoveryGuide from '../components/DiscoveryGuide';
import ObjectGraph from '../components/ObjectGraph';
import { TYPE_CONFIG } from '../config/ontology';
import { useObjects } from '../hooks/useOntology';

/* ─── Graph Analytics Panel ─── */
function GraphAnalyticsPanel() {
  const [graphStats, setGraphStats] = useState<any>(null);
  const [graphStatsLoading, setGraphStatsLoading] = useState(true);
  const [anomalies, setAnomalies] = useState<any>(null);
  const [anomaliesLoading, setAnomaliesLoading] = useState(true);
  const [impactNodeId, setImpactNodeId] = useState('');
  const [impactChangePct, setImpactChangePct] = useState('10');
  const [impactResult, setImpactResult] = useState<any>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [graphQuery, setGraphQuery] = useState('');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    stats: true, impact: false, query: false, anomalies: false,
  });

  const toggleSection = (key: string) =>
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));

  useEffect(() => {
    fetch('/api/graph/stats').then(r => r.json()).then(d => { setGraphStats(d); setGraphStatsLoading(false); })
      .catch(() => setGraphStatsLoading(false));
    fetch('/api/graph/anomalies').then(r => r.json()).then(d => { setAnomalies(d); setAnomaliesLoading(false); })
      .catch(() => setAnomaliesLoading(false));
  }, []);

  const runImpact = async () => {
    if (!impactNodeId.trim()) return;
    setImpactLoading(true);
    try {
      const res = await fetch(`/api/graph/impact/${encodeURIComponent(impactNodeId)}?change_pct=${impactChangePct}`);
      setImpactResult(await res.json());
    } catch { setImpactResult({ error: 'Failed to fetch impact data' }); }
    setImpactLoading(false);
  };

  const runQuery = async () => {
    if (!graphQuery.trim()) return;
    setQueryLoading(true);
    try {
      const res = await fetch(`/api/graph/query?q=${encodeURIComponent(graphQuery)}`);
      setQueryResult(await res.json());
    } catch { setQueryResult({ error: 'Failed to query graph' }); }
    setQueryLoading(false);
  };

  const severityColor = (sev: string) => {
    if (sev === 'critical' || sev === 'high') return 'var(--rose)';
    if (sev === 'medium' || sev === 'warning') return '#EAB308';
    return 'var(--emerald)';
  };

  const sectionHeader = (key: string, icon: React.ElementType, title: string, badge?: number) => {
    const Icon = icon;
    const open = expandedSections[key];
    return (
      <button onClick={() => toggleSection(key)} style={{
        display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '10px 14px',
        background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8,
        color: 'var(--heading)', fontSize: 12, fontWeight: 600, cursor: 'pointer', marginBottom: open ? 8 : 0,
      }}>
        <Icon size={14} style={{ color: 'var(--sky)' }} />
        {title}
        {badge !== undefined && badge > 0 && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, padding: '1px 6px', borderRadius: 10, background: 'rgba(56,189,248,.1)', color: 'var(--sky)' }}>
            {badge}
          </span>
        )}
        <span style={{ marginLeft: 'auto' }}>
          {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </span>
      </button>
    );
  };

  return (
    <div style={{ padding: 20, overflowY: 'auto', height: '100%' }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', marginBottom: 4, letterSpacing: '-0.5px' }}>
        Graph Analytics
      </h2>
      <p style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 20 }}>
        Analyze the knowledge graph structure, run impact analysis, and detect anomalies.
      </p>

      {/* ── Graph Stats ── */}
      <div style={{ marginBottom: 12 }}>
        {sectionHeader('stats', BarChart3, 'Graph Statistics')}
        {expandedSections.stats && (
          <div style={{ padding: 14, background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 8 }}>
            {graphStatsLoading ? (
              <Loader2 size={16} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
            ) : graphStats?.error ? (
              <div style={{ fontSize: 11, color: 'var(--rose)' }}>Error loading stats</div>
            ) : (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 14 }}>
                  {[
                    { label: 'Total Nodes', value: graphStats?.total_nodes ?? graphStats?.node_count ?? '-', color: 'var(--sky)' },
                    { label: 'Total Edges', value: graphStats?.total_edges ?? graphStats?.edge_count ?? '-', color: 'var(--emerald)' },
                    { label: 'Density', value: typeof graphStats?.density === 'number' ? graphStats.density.toFixed(4) : '-', color: '#EAB308' },
                  ].map(m => (
                    <div key={m.label} style={{ textAlign: 'center', padding: 10, background: 'var(--bg2)', borderRadius: 6, border: '1px solid var(--b1)' }}>
                      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--mono)', color: m.color }}>{m.value}</div>
                      <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>{m.label}</div>
                    </div>
                  ))}
                </div>
                {/* Node types breakdown */}
                {graphStats?.node_types && (
                  <>
                    <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--dim)', fontWeight: 600, marginBottom: 6, fontFamily: 'var(--mono)' }}>
                      NODE TYPES
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                      {Object.entries(graphStats.node_types).map(([type, count]) => (
                        <span key={type} style={{
                          fontSize: 10, padding: '3px 8px', borderRadius: 4,
                          background: 'var(--bg2)', border: '1px solid var(--b1)', color: 'var(--text)',
                          fontFamily: 'var(--mono)',
                        }}>
                          {type}: <strong>{String(count)}</strong>
                        </span>
                      ))}
                    </div>
                  </>
                )}
                {/* Top connected entities */}
                {graphStats?.top_connected && graphStats.top_connected.length > 0 && (
                  <>
                    <div style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--dim)', fontWeight: 600, marginBottom: 6, fontFamily: 'var(--mono)' }}>
                      TOP 10 MOST CONNECTED
                    </div>
                    {graphStats.top_connected.slice(0, 10).map((e: any, i: number) => (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '5px 8px', borderRadius: 4, fontSize: 11,
                        background: i % 2 === 0 ? 'var(--bg2)' : 'transparent',
                      }}>
                        <span style={{ color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                          {e.id || e.node_id || e.name || `Node ${i + 1}`}
                        </span>
                        <span style={{ fontWeight: 600, color: 'var(--sky)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                          {e.connections ?? e.degree ?? e.count ?? '-'}
                        </span>
                      </div>
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Impact Analysis ── */}
      <div style={{ marginBottom: 12 }}>
        {sectionHeader('impact', Target, 'Impact Analysis')}
        {expandedSections.impact && (
          <div style={{ padding: 14, background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 8 }}>
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <input
                value={impactNodeId}
                onChange={e => setImpactNodeId(e.target.value)}
                placeholder="Node ID (e.g. account:1110)"
                style={{
                  flex: 1, height: 30, padding: '0 8px', borderRadius: 'var(--r1)',
                  border: '1px solid var(--b2)', background: 'var(--bg2)',
                  color: 'var(--text)', fontSize: 11, outline: 'none', fontFamily: 'var(--mono)',
                }}
              />
              <input
                value={impactChangePct}
                onChange={e => setImpactChangePct(e.target.value)}
                placeholder="Change %"
                type="number"
                style={{
                  width: 70, height: 30, padding: '0 8px', borderRadius: 'var(--r1)',
                  border: '1px solid var(--b2)', background: 'var(--bg2)',
                  color: 'var(--text)', fontSize: 11, outline: 'none', fontFamily: 'var(--mono)',
                  textAlign: 'center',
                }}
              />
              <button onClick={runImpact} disabled={impactLoading} style={{
                height: 30, padding: '0 12px', borderRadius: 'var(--r1)', border: 'none',
                background: 'var(--sky)', color: 'var(--heading)', cursor: 'pointer', fontSize: 10, fontWeight: 600,
                opacity: impactLoading ? 0.6 : 1,
              }}>
                {impactLoading ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : 'Analyze'}
              </button>
            </div>
            {impactResult && !impactResult.error && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {(impactResult.impacted_entities || impactResult.impacts || impactResult.results || []).map((e: any, i: number) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '6px 10px', borderRadius: 6, fontSize: 11,
                    background: 'var(--bg2)', border: '1px solid var(--b1)',
                    borderLeft: `3px solid ${severityColor(e.severity || e.impact_level || 'low')}`,
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, color: 'var(--heading)', fontSize: 11 }}>
                        {e.entity_id || e.node_id || e.id || e.name}
                      </div>
                      {e.description && <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 1 }}>{e.description}</div>}
                    </div>
                    <span style={{
                      fontSize: 9, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                      color: severityColor(e.severity || e.impact_level || 'low'),
                      background: `color-mix(in srgb, ${severityColor(e.severity || e.impact_level || 'low')} 10%, transparent)`,
                    }}>
                      {e.severity || e.impact_level || e.impact_pct ? `${e.impact_pct}%` : 'affected'}
                    </span>
                  </div>
                ))}
                {(impactResult.impacted_entities || impactResult.impacts || impactResult.results || []).length === 0 && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', padding: 10 }}>No impacted entities found.</div>
                )}
              </div>
            )}
            {impactResult?.error && (
              <div style={{ fontSize: 11, color: 'var(--rose)', padding: 6 }}>{impactResult.error}</div>
            )}
          </div>
        )}
      </div>

      {/* ── Graph Query ── */}
      <div style={{ marginBottom: 12 }}>
        {sectionHeader('query', Search, 'Graph Query')}
        {expandedSections.query && (
          <div style={{ padding: 14, background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 8 }}>
            <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
              <input
                value={graphQuery}
                onChange={e => setGraphQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runQuery()}
                placeholder="Search entities (e.g. revenue, IFRS 15...)"
                style={{
                  flex: 1, height: 30, padding: '0 8px', borderRadius: 'var(--r1)',
                  border: '1px solid var(--b2)', background: 'var(--bg2)',
                  color: 'var(--text)', fontSize: 11, outline: 'none',
                }}
              />
              <button onClick={runQuery} disabled={queryLoading} style={{
                height: 30, padding: '0 12px', borderRadius: 'var(--r1)', border: 'none',
                background: 'var(--blue)', color: 'var(--heading)', cursor: 'pointer', fontSize: 10, fontWeight: 600,
                opacity: queryLoading ? 0.6 : 1,
              }}>
                {queryLoading ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : 'Search'}
              </button>
            </div>
            {queryResult && !queryResult.error && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {(queryResult.results || queryResult.entities || queryResult.matches || []).map((e: any, i: number) => (
                  <div key={i} style={{
                    padding: '8px 10px', borderRadius: 6, fontSize: 11,
                    background: 'var(--bg2)', border: '1px solid var(--b1)',
                  }}>
                    <div style={{ fontWeight: 600, color: 'var(--heading)' }}>
                      {e.id || e.node_id || e.name || e.entity_id}
                    </div>
                    {e.type && <span style={{ fontSize: 9, color: 'var(--sky)', fontFamily: 'var(--mono)' }}>{e.type}</span>}
                    {e.connections !== undefined && (
                      <span style={{ fontSize: 9, color: 'var(--muted)', marginLeft: 8 }}>
                        {e.connections} connections
                      </span>
                    )}
                    {e.description && <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 2 }}>{e.description}</div>}
                  </div>
                ))}
                {(queryResult.results || queryResult.entities || queryResult.matches || []).length === 0 && (
                  <div style={{ fontSize: 11, color: 'var(--muted)', padding: 10 }}>No matching entities found.</div>
                )}
              </div>
            )}
            {queryResult?.error && (
              <div style={{ fontSize: 11, color: 'var(--rose)', padding: 6 }}>{queryResult.error}</div>
            )}
          </div>
        )}
      </div>

      {/* ── Anomalies ── */}
      <div style={{ marginBottom: 12 }}>
        {sectionHeader('anomalies', AlertCircle, 'Structural Anomalies', anomalies?.anomalies?.length || anomalies?.issues?.length || 0)}
        {expandedSections.anomalies && (
          <div style={{ padding: 14, background: 'var(--bg1)', border: '1px solid var(--b1)', borderRadius: 8 }}>
            {anomaliesLoading ? (
              <Loader2 size={16} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {(anomalies?.anomalies || anomalies?.issues || []).map((a: any, i: number) => (
                  <div key={i} style={{
                    padding: '8px 10px', borderRadius: 6, fontSize: 11,
                    background: 'var(--bg2)', border: '1px solid var(--b1)',
                    borderLeft: `3px solid ${severityColor(a.severity || 'warning')}`,
                  }}>
                    <div style={{ fontWeight: 600, color: 'var(--heading)' }}>{a.type || a.anomaly_type || a.title || 'Anomaly'}</div>
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{a.description || a.message || a.detail}</div>
                    {a.affected_nodes && (
                      <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 2, fontFamily: 'var(--mono)' }}>
                        Affected: {Array.isArray(a.affected_nodes) ? a.affected_nodes.join(', ') : a.affected_nodes}
                      </div>
                    )}
                  </div>
                ))}
                {(anomalies?.anomalies || anomalies?.issues || []).length === 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--emerald)', padding: 10 }}>
                    <Zap size={14} /> No structural anomalies detected.
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function OntologyExplorerPage() {
  const [stats, setStats] = useState<any>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedObject, setSelectedObject] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any>(null);
  const [searchObjects, setSearchObjects] = useState<any[]>([]);
  const [viewMode, setViewMode] = useState<'graph' | 'list' | 'analytics'>('graph');
  const [graphSeedId, setGraphSeedId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editProperties, setEditProperties] = useState<Record<string, any>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Set mounted state for animation
  useEffect(() => {
    setMounted(true);
    const timer = setTimeout(() => setMounted(false), 2000);
    return () => clearTimeout(timer);
  }, []);

  // Fetch objects based on type or search using the custom hook
  const {
    objects: typeObjects = [],
    isLoading: typeLoading = false,
  } = useObjects({
    type: selectedType || '',
    limit: 100,
    enabled: !!selectedType && searchObjects.length === 0,
  }) as any;

  // Merge search results or type objects
  const objects = searchObjects.length > 0 ? searchObjects : (typeObjects || []);

  // Load stats
  useEffect(() => {
    fetch('/api/ontology/stats').then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  // Set graph seed when objects load
  useEffect(() => {
    if (objects.length > 0 && !graphSeedId) {
      const withRels = objects.find((o: any) =>
        o.relationships && Object.values(o.relationships).some((v: any) => Array.isArray(v) && v.length > 0)
      );
      setGraphSeedId((withRels || objects[0]).object_id as string);
    }
  }, [objects, graphSeedId]);

  // Reset search state when type changes
  useEffect(() => {
    setGraphSeedId(null);
    setSearchObjects([]);
    setSearchResults(null);
  }, [selectedType]);

  // Natural language search handler
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      const res = await fetch('/api/ontology/query/natural', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }),
      });
      const data = await res.json();
      setSearchResults(data);
      if (data.objects?.length) {
        setSearchObjects(data.objects);
        setGraphSeedId(data.objects[0].object_id);
      }
    } catch { }
  };

  // Object selection handler
  const selectObject = async (objectId: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/ontology/objects/${objectId}`);
      const data = await res.json();
      setSelectedObject(data);
      setEditProperties(data.properties || {});
      setIsEditing(false);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleUpdateProperty = async () => {
    if (!selectedObject) return;
    setActionLoading('update');
    try {
      const res = await fetch(`/api/ontology/objects/${selectedObject.object_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ properties: editProperties })
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedObject(updated);
        setIsEditing(false);
      }
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const handleObjectAction = async (action: string) => {
    if (!selectedObject) return;
    setActionLoading(action);
    try {
      const res = await fetch(`/api/ontology/objects/${selectedObject.object_id}/action?action=${action}`, {
        method: 'POST'
      });
      if (res.ok) {
        await selectObject(selectedObject.object_id);
      }
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const typeCounts = stats?.registry?.by_type || {};

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 64px)', gap: 0, position: 'relative', overflow: 'hidden' }}>
      {mounted && <div className="scanline-mount" />}
      
      {/* Left Panel -- Type Tree + Search */}
      <div className="industrial-panel" style={{
        width: 280, borderRight: '1px solid var(--b1)', background: 'rgba(8, 11, 20, 0.4)',
        display: 'flex', flexDirection: 'column', flexShrink: 0, backdropFilter: 'blur(20px)',
        zIndex: 5,
      }}>
        {/* Search */}
        <div style={{ padding: 16, borderBottom: '1px solid var(--b1)' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--dim)' }} />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="ASK_INTELLIGENCE..."
                style={{
                  width: '100%', height: 34, padding: '0 12px 0 32px', borderRadius: 2,
                  border: '1px solid var(--b2)', background: 'var(--bg2)',
                  color: 'var(--text)', fontSize: 11, outline: 'none', fontFamily: 'var(--mono)',
                }}
              />
            </div>
            <button onClick={handleSearch} style={{
              width: 34, height: 34, borderRadius: 2, border: 'none',
              background: 'var(--sky)', color: 'var(--heading)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Zap size={14} strokeWidth={3} />
            </button>
          </div>
          {searchResults && (
            <div style={{ fontSize: 9, color: 'var(--sky)', marginTop: 8, fontFamily: 'var(--mono)', fontWeight: 700 }}>
              RESULTS: {searchResults.count} | LATENCY: {searchResults.execution_ms?.toFixed(1) || '0.0'}ms
            </div>
          )}
        </div>

        {/* Explanation */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b1)', background: 'rgba(0, 242, 255, 0.02)' }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: 'var(--heading)', marginBottom: 6, letterSpacing: 1 }}>
            INTELLIGENCE_MATRIX
          </div>
          <div style={{ fontSize: 9, color: 'var(--muted)', lineHeight: 1.5 }}>
            Explore causal links and financial flows across entities.
          </div>
        </div>

        {/* Type Tree */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          <div style={{
            fontFamily: 'var(--mono)', fontSize: 9, textTransform: 'uppercase',
            letterSpacing: 2, color: 'var(--dim)', padding: '12px 16px 8px', fontWeight: 800,
          }}>
            REGISTRY_TYPES
          </div>
          {Object.entries(TYPE_CONFIG).map(([typeId, cfg]) => {
            const Icon = cfg.icon;
            const count = typeCounts[typeId] || 0;
            const isSelected = selectedType === typeId;
            return (
              <button
                key={typeId}
                onClick={() => { setSelectedType(typeId); setSelectedObject(null); }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, width: '100%',
                  padding: '8px 16px', border: 'none', cursor: 'pointer', textAlign: 'left',
                  background: isSelected ? 'rgba(0, 242, 255, 0.04)' : 'transparent',
                  borderLeft: `2px solid ${isSelected ? cfg.color : 'transparent'}`,
                  color: isSelected ? 'var(--heading)' : 'var(--muted)',
                  transition: 'all .2s cubic-bezier(0.4, 0, 0.2, 1)',
                }}
              >
                <TechIcon 
                  iconName={cfg.icon.name || cfg.icon} 
                  color={isSelected ? cfg.color : 'var(--dim)'} 
                  size={12} 
                  glow={isSelected}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: isSelected ? 800 : 500, letterSpacing: 0.5 }}>{cfg.label.toUpperCase()}</div>
                </div>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 9, padding: '1px 6px',
                  borderRadius: 2, background: isSelected ? `${cfg.color}22` : 'var(--bg3)',
                  color: isSelected ? cfg.color : 'var(--dim)', fontWeight: 800,
                  border: `1px solid ${isSelected ? cfg.color + '44' : 'transparent'}`
                }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Stats Footer */}
        <div style={{
          padding: '12px 16px', borderTop: '1px solid var(--b1)',
          fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)',
          background: 'var(--bg0)', display: 'flex', justifyContent: 'space-between'
        }}>
          <span>OBJ: {stats?.registry?.objects || 0}</span>
          <span>TYP: {stats?.registry?.types || 0}</span>
          <span style={{ color: 'var(--emerald)' }}>SQL_OK</span>
        </div>
      </div>

      {/* Center Panel -- Graph or List Canvas */}
      <div style={{ flex: 1, position: 'relative', background: 'var(--bg0)', display: 'flex', flexDirection: 'column' }}>
        {/* View mode toggle */}
        {(selectedType || searchResults || viewMode === 'analytics') && (
          <div style={{
            padding: '10px 16px', borderBottom: '1px solid var(--b1)',
            display: 'flex', alignItems: 'center', gap: 12, background: 'var(--bg1)',
          }}>
            <button
              onClick={() => setViewMode('graph')}
              className="btn-minimal"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                borderColor: viewMode === 'graph' ? 'var(--sky)' : 'var(--b2)',
                color: viewMode === 'graph' ? 'var(--sky)' : 'var(--muted)',
                background: viewMode === 'graph' ? 'rgba(0,242,255,0.05)' : 'var(--bg2)',
              }}
              title="Graph View: Discover causal chains and data flow between entities."
            >
              <Network size={12} /> GRAPH_CANVAS
            </button>
            <button
              onClick={() => setViewMode('list')}
              className="btn-minimal"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                borderColor: viewMode === 'list' ? 'var(--sky)' : 'var(--b2)',
                color: viewMode === 'list' ? 'var(--sky)' : 'var(--muted)',
                background: viewMode === 'list' ? 'rgba(0,242,255,0.05)' : 'var(--bg2)',
              }}
              title="List View: High-density tabular review for auditing and verification."
            >
              <LayoutGrid size={12} /> TABULAR_LIST
            </button>
            <button
              onClick={() => setViewMode('analytics')}
              className="btn-minimal"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                borderColor: viewMode === 'analytics' ? 'var(--sky)' : 'var(--b2)',
                color: viewMode === 'analytics' ? 'var(--sky)' : 'var(--muted)',
                background: viewMode === 'analytics' ? 'rgba(0,242,255,0.05)' : 'var(--bg2)',
              }}
              title="Analytics View: System-wide structural health and anomaly detection."
            >
              <Activity size={12} /> STRUCTURAL_ANALYTICS
            </button>
            <button
              onClick={() => setShowGuide(true)}
              className="btn-minimal"
              style={{
                marginLeft: 12, display: 'flex', alignItems: 'center', gap: 6,
                borderColor: 'var(--sky)', color: 'var(--sky)',
                background: 'rgba(0,242,255,0.05)', borderRadius: '50%', width: 28, height: 28, padding: 0, justifyContent: 'center'
              }}
              title="System Briefing"
            >
              <HelpCircle size={14} />
            </button>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', letterSpacing: 1 }}>
              NODES: {objects.length} | SYNC_STATUS: <span style={{ color: 'var(--emerald)' }}>NOMINAL</span>
            </span>
          </div>
        )}

        <div style={{ flex: 1, overflow: 'hidden' }}>
          {viewMode === 'analytics' ? (
            <GraphAnalyticsPanel />
          ) : !selectedType && !searchResults ? (
            <div style={{ padding: 60, overflowY: 'auto', height: '100%', background: 'radial-gradient(circle at 50% 0%, rgba(0,242,255,0.03) 0%, transparent 70%)' }}>
              {/* Mission Briefing */}
              <div style={{ maxWidth: 900, marginBottom: 60 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                  <div className="pixel-node" style={{ width: 8, height: 8 }} />
                  <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--sky)', letterSpacing: 2, fontWeight: 900 }}>SYSTEM_READY // DOMAIN_FINANCIAL_INTELLIGENCE</span>
                </div>
                <h1 style={{ fontSize: 32, fontWeight: 900, color: 'var(--heading)', marginBottom: 20, letterSpacing: -1 }}>
                  THE INTELLIGENCE MATRIX
                </h1>
                <p style={{ fontSize: 15, color: 'var(--muted)', lineHeight: 1.8, marginBottom: 32, maxWidth: 700 }}>
                  This is the <span style={{ color: 'var(--sky)', fontWeight: 700 }}>Knowledge Layer</span> of your organization. It connects disconnected data—Accounts, KPIs, and Risks—into a single, navigable brain. Use this tool to discover <strong>why</strong> numbers are changing, not just <strong>what</strong> they are.
                </p>
                
                {/* Value Pillars */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24, marginBottom: 48 }}>
                  <div className="industrial-panel" style={{ padding: 20, background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ color: 'var(--sky)', marginBottom: 12 }}><Network size={20} /></div>
                    <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 8 }}>CAUSAL DISCOVERY</div>
                    <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.5 }}>Trace variances back to their origin. See which exact account movements triggered a KPI breach.</div>
                  </div>
                  <div className="industrial-panel" style={{ padding: 20, background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ color: 'var(--amber)', marginBottom: 12 }}><Activity size={20} /></div>
                    <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 8 }}>RISK PROPAGATION</div>
                    <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.5 }}>Simulate market shocks. See how a currency fluctuation "flows" through your subsidiary network.</div>
                  </div>
                  <div className="industrial-panel" style={{ padding: 20, background: 'rgba(255,255,255,0.02)' }}>
                    <div style={{ color: 'var(--emerald)', marginBottom: 12 }}><LayoutGrid size={20} /></div>
                    <div style={{ fontSize: 12, fontWeight: 900, color: 'var(--heading)', marginBottom: 8 }}>DATA LINEAGE</div>
                    <div style={{ fontSize: 11, color: 'var(--dim)', lineHeight: 1.5 }}>Maintain perfect audit trails. Every inference the AI makes is backed by a visible path to source data.</div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 16 }}>
                  <button 
                    onClick={() => setShowGuide(true)}
                    className="btn-minimal" 
                    style={{ border: '1px solid var(--sky)', padding: '10px 20px', color: 'var(--sky)' }}
                  >
                    <Sparkles size={14} style={{ marginRight: 8 }} /> START_SYSTEM_TOUR
                  </button>
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)' }}>SYSTEM_LOAD:</div>
                    <div style={{ padding: '4px 12px', background: 'rgba(0, 242, 255, 0.05)', border: '1px solid var(--b2)', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', borderRadius: 2 }}>
                      {stats?.registry?.objects || '...'} ENTITIES
                    </div>
                  </div>
                </div>
              </div>

              {/* Object type grid - Scenario-Driven */}
              <div style={{ fontSize: 10, fontWeight: 900, color: 'var(--dim)', letterSpacing: 2, marginBottom: 20, borderBottom: '1px solid var(--b1)', paddingBottom: 8, fontFamily: 'var(--mono)' }}>
                DISCOVER_BY_DOMAINS
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
                {Object.entries(TYPE_CONFIG).map(([typeId, cfg]) => {
                  const Icon = cfg.icon;
                  const count = typeCounts[typeId] || 0;
                  return (
                    <div
                      key={typeId}
                      onClick={() => { setSelectedType(typeId); setSelectedObject(null); }}
                      className="glass-interactive industrial-panel"
                      style={{ padding: '24px', borderLeft: `2px solid ${cfg.color}`, position: 'relative', overflow: 'hidden' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                        <TechIcon iconName={cfg.icon.name || cfg.icon} color={cfg.color} size={14} />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 900, color: 'var(--heading)' }}>{cfg.label.toUpperCase()}</div>
                          <div style={{ fontSize: 9, color: cfg.color, fontFamily: 'var(--mono)', fontWeight: 800 }}>{count} ACTIVE_NODES</div>
                        </div>
                      </div>
                      
                      <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 16, minHeight: 48 }}>
                        {cfg.desc}
                      </div>

                      <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: 4, marginBottom: 16 }}>
                        <div style={{ fontSize: 8, color: 'var(--dim)', fontWeight: 900, letterSpacing: 1, marginBottom: 8 }}>DISCOVERY_SCENARIOS:</div>
                        <ul style={{ padding: 0, margin: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {cfg.scenarios?.map((s, si) => (
                            <li key={si} style={{ fontSize: 10, color: 'var(--sky)', display: 'flex', alignItems: 'center', gap: 6 }}>
                              <div className="pixel-node" style={{ width: 4, height: 4 }} />
                              {s}
                            </li>
                          ))}
                        </ul>
                      </div>

                      <div style={{ display: 'flex', gap: 4 }}>
                        <span style={{ fontSize: 8, padding: '2px 8px', background: 'var(--bg2)', border: '1px solid var(--b1)', color: 'var(--dim)', fontFamily: 'var(--mono)' }}>SYSTEM_CORE</span>
                        <span style={{ fontSize: 8, padding: '2px 8px', background: 'var(--bg2)', border: '1px solid var(--b1)', color: 'var(--dim)', fontFamily: 'var(--mono)' }}>AUDIT_READY</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Loader2 size={32} className="spin" style={{ color: 'var(--sky)' }} />
            </div>
          ) : viewMode === 'graph' && graphSeedId ? (
            /* Graph View — ObjectGraph component */
            <ObjectGraph
              seedObjectId={graphSeedId}
              seedType={selectedType || 'Unknown'}
              onNavigate={(id) => selectObject(id)}
            />
          ) : (
            /* List View */
            <div style={{ padding: 24, overflowY: 'auto', height: '100%' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {objects.map((obj: any) => {
                  const cfg = TYPE_CONFIG[selectedType || obj.object_type || ''] || { color: '#738091' };
                  const label = obj.properties?.name_en || obj.properties?.code || obj.properties?.metric || obj.object_id;
                  const isActive = graphSeedId === obj.object_id;
                  return (
                    <div
                      key={obj.object_id}
                      onClick={() => {
                        selectObject(obj.object_id);
                        setGraphSeedId(obj.object_id);
                      }}
                      className="glass-interactive"
                      style={{
                        padding: '14px 20px',
                        borderLeft: `4px solid ${isActive ? cfg.color : 'var(--b2)'}`,
                        display: 'flex', alignItems: 'center', gap: 16,
                        background: isActive ? 'rgba(0, 242, 255, 0.03)' : 'var(--bg1)',
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: isActive ? 'var(--sky)' : 'var(--heading)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {label}
                        </div>
                        <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--dim)', marginTop: 4 }}>
                          OBJ_ID: {obj.object_id}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8 }}>
                         {obj.properties?.status && (
                           <span style={{ fontSize: 8, padding: '2px 8px', borderRadius: 2, background: 'var(--bg3)', color: 'var(--muted)', fontFamily: 'var(--mono)' }}>
                             {obj.properties.status.toUpperCase()}
                           </span>
                         )}
                         <ChevronRight size={14} style={{ color: isActive ? 'var(--sky)' : 'var(--b2)' }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Panel -- Object Detail */}
      {selectedObject && (
        <div className="industrial-panel" style={{
          width: 360, borderLeft: '1px solid var(--b1)', background: 'rgba(5, 8, 18, 0.6)', 
          backdropFilter: 'blur(30px)', display: 'flex', flexDirection: 'column', 
          overflow: 'hidden', zIndex: 10,
        }}>
          {/* Header */}
          <div style={{
            padding: '24px', borderBottom: '1px solid var(--b1)',
            background: 'var(--bg1)', position: 'relative'
          }}>
            <div className="scanline-mount" style={{ height: 2, background: 'var(--sky)', opacity: 0.3 }} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <TechIcon 
                  iconName={TYPE_CONFIG[selectedObject.object_type]?.icon.name || TYPE_CONFIG[selectedObject.object_type]?.icon || 'HelpCircle'} 
                  color={TYPE_CONFIG[selectedObject.object_type]?.color || 'var(--sky)'} 
                  size={10} 
                  glow 
                />
                <span style={{ fontSize: 9, fontWeight: 900, fontFamily: 'var(--mono)', color: TYPE_CONFIG[selectedObject.object_type]?.color || 'var(--sky)', letterSpacing: 1 }}>
                  {selectedObject.object_type?.toUpperCase()}
                </span>
              </div>
              <button 
                onClick={() => setSelectedObject(null)} 
                className="btn-minimal" 
                style={{ border: 'none', background: 'none', color: 'var(--muted)' }}
              >
                <X size={16} />
              </button>
            </div>
            
            <h3 style={{ fontSize: 18, fontWeight: 900, color: 'var(--heading)', letterSpacing: -0.5, marginBottom: 4 }}>
              {selectedObject.properties?.name_en || selectedObject.properties?.code || selectedObject.object_id}
            </h3>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: 1 }}>
              REVISION_V{selectedObject.version} | SYNCED_STREAM_OK
            </div>

            {/* ACTION_CONTROL_CENTER */}
            <div style={{ marginTop: 20, display: 'flex', gap: 8 }}>
              {selectedObject.object_type === 'Action' && (
                <>
                  <button 
                    onClick={() => handleObjectAction('approve')}
                    disabled={actionLoading === 'approve'}
                    className="btn-minimal" 
                    style={{ flex: 1, padding: '8px 12px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--emerald)', color: 'var(--emerald)', fontSize: 10, fontWeight: 900 }}
                  >
                    {actionLoading === 'approve' ? <Loader2 size={12} className="spin" /> : <><CheckCircle2 size={12} style={{ marginRight: 6 }} /> APPROVE</>}
                  </button>
                  <button 
                    onClick={() => handleObjectAction('execute')}
                    disabled={actionLoading === 'execute'}
                    className="btn-minimal" 
                    style={{ flex: 1, padding: '8px 12px', background: 'rgba(0, 216, 255, 0.1)', border: '1px solid var(--sky)', color: 'var(--sky)', fontSize: 10, fontWeight: 900 }}
                  >
                    {actionLoading === 'execute' ? <Loader2 size={12} className="spin" /> : <><Play size={12} style={{ marginRight: 6 }} /> EXECUTE</>}
                  </button>
                </>
              )}
              {selectedObject.object_type === 'KPI' && (
                <button 
                  onClick={() => handleObjectAction('simulate')}
                  className="btn-minimal" 
                  style={{ flex: 1, padding: '8px 12px', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid var(--amber)', color: 'var(--amber)', fontSize: 10, fontWeight: 900 }}
                >
                  <Zap size={12} style={{ marginRight: 6 }} /> SIMULATE_IMPACT
                </button>
              )}
              <button 
                onClick={() => setIsEditing(!isEditing)}
                className="btn-minimal" 
                style={{ padding: '8px 12px', border: '1px solid var(--b2)', color: 'var(--muted)' }}
              >
                {isEditing ? <X size={14} /> : <Edit3 size={14} />}
              </button>
            </div>
          </div>

          {/* Properties Grid */}
          <div style={{ flex: 1, overflowY: 'auto', padding: 24 }} className="matrix-grid">
            <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--dim)', letterSpacing: 2, marginBottom: 16, borderBottom: '1px solid var(--b1)', paddingBottom: 8, fontFamily: 'var(--mono)' }}>
              PROPERTY_MATRIX
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 32 }}>
              {Object.entries(selectedObject.properties || {}).map(([key, val]) => (
                <div key={key} style={{ 
                  padding: 10, background: 'var(--bg2)', border: '1px solid var(--b1)', 
                  borderRadius: 2, display: 'flex', flexDirection: 'column', gap: 4 
                }}>
                  <span style={{ fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--muted)', textTransform: 'uppercase' }}>{key}</span>
                  {isEditing ? (
                    <input 
                      value={editProperties[key] || ''} 
                      onChange={(e) => setEditProperties({ ...editProperties, [key]: e.target.value })}
                      style={{ background: 'var(--bg3)', border: 'none', borderBottom: '1px solid var(--sky)', color: 'var(--heading)', fontSize: 11, padding: '2px 0', outline: 'none' }}
                    />
                  ) : (
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--heading)', wordBreak: 'break-all' }}>
                      {typeof val === 'number' ? (val as number).toLocaleString() : String(val || '\u2014')}
                    </span>
                  )}
                </div>
              ))}
            </div>
            
            {isEditing && (
              <button 
                onClick={handleUpdateProperty}
                disabled={actionLoading === 'update'}
                className="btn-minimal"
                style={{ width: '100%', padding: '10px', background: 'var(--sky)', color: 'var(--bg0)', fontSize: 11, fontWeight: 900, marginBottom: 32 }}
              >
                {actionLoading === 'update' ? <Loader2 size={16} className="spin" /> : <><Save size={16} style={{ marginRight: 8 }} /> SAVE_CHANGES</>}
              </button>
            )}

            {/* Computed Fields (Industrial Variant) */}
            {selectedObject.computed && Object.keys(selectedObject.computed).length > 0 && (
              <>
                <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--amber)', letterSpacing: 2, marginBottom: 16, borderBottom: '1px solid var(--b1)', paddingBottom: 8, display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--mono)' }}>
                   <Activity size={12} /> INFERENCE_DATA
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginBottom: 32 }}>
                  {Object.entries(selectedObject.computed).map(([key, val]) => (
                    <div key={key} style={{ 
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                      padding: '8px 12px', background: 'rgba(234, 179, 8, 0.03)', border: '1px solid rgba(234, 179, 8, 0.1)'
                    }}>
                      <span style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--dim)', textTransform: 'uppercase' }}>{key}</span>
                      <span style={{
                        fontSize: 11, fontWeight: 800, fontFamily: 'var(--mono)',
                        color: typeof val === 'number' && (val as number) < 0 ? 'var(--rose)' : 'var(--emerald)',
                      }}>
                        {typeof val === 'number' ? `${(val as number).toFixed(1)}%` : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Relationships */}
            {Object.keys(selectedObject.relationships || {}).length > 0 && (
              <>
                <div style={{ fontSize: 9, fontWeight: 900, color: 'var(--sky)', letterSpacing: 2, marginBottom: 16, borderBottom: '1px solid var(--b1)', paddingBottom: 8, fontFamily: 'var(--mono)' }}>
                  GRAPH_RELATIONS
                </div>
                {Object.entries(selectedObject.relationships || {}).map(([relType, targets]) => (
                  <div key={relType} style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 8, color: 'var(--dim)', fontFamily: 'var(--mono)', marginBottom: 8, opacity: 0.6 }}>{relType.toUpperCase()}</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {(targets as any[]).map((t: any, i: number) => {
                        const tid = t.node_id || t.object_id || t.id;
                        return (
                          <button
                            key={i}
                            onClick={() => {
                              selectObject(tid);
                              setGraphSeedId(tid);
                            }}
                            className="btn-minimal"
                            style={{ 
                              fontSize: 9, padding: '8px 12px', textAlign: 'left', 
                              textTransform: 'none', background: 'var(--bg2)', 
                              border: '1px solid var(--b1)', display: 'flex', 
                              alignItems: 'center', gap: 8, width: '100%',
                              color: 'var(--sky)', fontFamily: 'var(--mono)'
                            }}
                          >
                            <div className="pixel-node" style={{ width: 4, height: 4 }} />
                            {tid}
                            <ChevronRight size={10} style={{ marginLeft: 'auto', opacity: 0.5 }} />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </>
            )}
            
            {/* ID + Meta Footer */}
            <div style={{ marginTop: 'auto', paddingTop: 32 }}>
              <div style={{ fontSize: 8, fontFamily: 'var(--mono)', color: 'var(--dim)', lineHeight: 1.8, padding: 12, background: 'rgba(255,255,255,0.02)', borderTop: '1px solid var(--b1)' }}>
                GLOBAL_UID: {selectedObject.object_id}<br />
                ENGINE_VER: 4.2.0-STABLE<br />
                LAST_SYNC: {new Date().toISOString().split('T')[0]}
              </div>
            </div>
          </div>
        </div>
      )}
      {showGuide && <DiscoveryGuide onClose={() => setShowGuide(false)} />}
      
      {/* Real-time Contextual Briefing */}
      <ContextualBriefing 
        viewMode={selectedObject ? 'graph' : viewMode} 
        selectedType={selectedType}
        selectedObject={selectedObject}
      />
    </div>
  );
}
