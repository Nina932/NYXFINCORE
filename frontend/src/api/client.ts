const BASE = '/api/agent';

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  
  // Dynamically inject the active language preference for the backend
  const lang = typeof window !== 'undefined' ? localStorage.getItem('finai-lang') || 'en' : 'en';
  if (lang) headers['Accept-Language'] = lang;
  
  return headers;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${BASE}${path}`;
  const options: RequestInit = { method, headers: getHeaders() };
  if (body !== undefined) options.body = JSON.stringify(body);
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function get<T = unknown>(path: string): Promise<T> { return request<T>('GET', path); }
function post<T = unknown>(path: string, body?: unknown): Promise<T> { return request<T>('POST', path, body); }

async function postFile<T = unknown>(path: string, file: File): Promise<T> {
  const url = `${BASE}${path}`;
  const formData = new FormData();
  formData.append('file', file);
  const headers: Record<string, string> = {};
  const token = localStorage.getItem('token');
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const lang = typeof window !== 'undefined' ? localStorage.getItem('finai-lang') || 'en' : 'en';
  if (lang) headers['Accept-Language'] = lang;
  const response = await fetch(url, { method: 'POST', headers, body: formData });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Upload failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postBlob(path: string, body?: unknown): Promise<Blob> {
  const url = `${BASE}${path}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: getHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(`Download failed: ${response.status}`);
  // Check if response is actually JSON error instead of file blob
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    const data = await response.json();
    throw new Error(data.error || data.detail || 'Report generation failed');
  }
  return response.blob();
}

/* ─── API Functions ─── */
export const api = {
  // Upload
  upload: (file: File) => postFile(`/agents/smart-upload`, file),

  // Dashboard
  dashboard: (period?: string) => get(`/agents/dashboard${period ? `?period=${period}` : ''}`),
  comparePeriods: (current?: string, previous?: string) =>
    get(`/agents/dashboard/compare${current ? `?current=${current}` : ''}${previous ? `&previous=${previous}` : ''}`),

  // Chat (ALWAYS use /command, NEVER WebSocket)
  command: (cmd: string) => post<{
    command_type?: string; response?: string; data?: unknown;
    navigate?: string; insights?: unknown[]; llm_summary?: string;
  }>(`/command`, { command: cmd }),

  // Orchestrator
  orchestrate: (current: unknown, balance_sheet: unknown) =>
    post(`/agents/orchestrator/run`, { current, balance_sheet }),
  orchestratorLast: () => get(`/agents/orchestrator/last`),

  // Strategy (backend reads body.get("current", body.get("financials", {})))
  strategy: (financials: unknown, balance_sheet: unknown) =>
    post(`/agents/strategy/generate`, { current: financials, financials, balance_sheet }),
  strategyLast: () => get(`/agents/strategy/last`),
  strategyLearning: () => get(`/agents/strategy/learning`),

  // Sensitivity
  sensitivity: (financials: unknown) =>
    post(`/agents/sensitivity/analyze`, { financials }),
  monteCarlo: (financials: unknown, iterations = 500) =>
    post(`/agents/sensitivity/monte-carlo`, { financials, iterations }),
  multiVariable: (financials: unknown, changes: unknown) =>
    post(`/agents/sensitivity/multi-variable`, { financials, changes }),

  // Decisions (backend reads body.get("current", {}))
  decisions: (financials: unknown, balance_sheet: unknown) =>
    post(`/agents/decisions/generate`, { current: financials, balance_sheet }),
  verdict: () => get(`/agents/decisions/verdict`),

  // Analogies
  analogies: (financials: unknown) =>
    post(`/agents/analogy/search`, { financials }),

  // Alerts
  alerts: () => get<unknown[]>(`/alerts`),
  alertRules: () => get(`/agents/monitoring/rules`),

  // KPI
  kpi: (financials: unknown) =>
    post(`/agents/monitoring/kpi/evaluate`, { financials }),

  // Cash Runway
  runway: (cash: number, revenue: number, expenses: number) =>
    post(`/agents/monitoring/cash-runway`, { cash_balance: cash, monthly_revenue: revenue, monthly_expenses: expenses }),

  // Expense Spikes
  expenseSpikes: (current: unknown, previous: unknown) =>
    post(`/agents/monitoring/expense-spikes`, { current, previous }),

  // Predictions
  recordPrediction: (entry: unknown) => post(`/agents/predictions/record`, entry),
  resolvePrediction: (id: number, actual: number) =>
    post(`/agents/predictions/resolve`, { id, actual_value: actual }),
  predictionAccuracy: () => get(`/agents/predictions/accuracy`),

  // Benchmarks
  industries: () => get(`/agents/benchmarks/industries`),
  benchmarkCompare: (financials: unknown, industry_id: string) => {
    const f = financials as Record<string, number>;
    const rev = f.revenue || 1;
    const metrics: Record<string, number> = {};
    if (f.gross_profit != null) metrics.gross_margin = (f.gross_profit / rev) * 100;
    if (f.net_profit != null) metrics.net_margin = (f.net_profit / rev) * 100;
    if (f.ebitda != null) metrics.ebitda_margin = (f.ebitda / rev) * 100;
    if (f.cogs != null) metrics.cogs_ratio = (Math.abs(f.cogs) / rev) * 100;
    if (f.total_assets && rev) metrics.asset_turnover = rev / f.total_assets;
    if (f.total_liabilities && f.total_equity) metrics.debt_to_equity = f.total_liabilities / (f.total_equity || 1);
    return post(`/agents/benchmarks/compare`, { metrics, industry: industry_id });
  },

  // Forecasts
  forecast: (values: number[], periods: number, forecast_periods = 6) =>
    post(`/agents/forecast/ensemble`, { values, periods, forecast_periods }),
  backtest: (values: number[], periods: number) =>
    post(`/agents/forecast/backtest`, { values, periods }),

  // GL Pipeline
  glPipeline: (transactions: unknown[]) =>
    post(`/agents/gl/full-pipeline`, { transactions }),
  trialBalance: (transactions: unknown[]) =>
    post(`/agents/gl/trial-balance`, { transactions }),

  // Reports
  pdfReport: (payload: unknown) => postBlob(`/agents/orchestrator/pdf`, payload),
  briefReport: (payload: unknown) => postBlob(`/agents/orchestrator/brief`, payload),
  excelReport: (data: unknown) => postBlob(`/agents/export/excel`, data),

  // Datasets
  listDatasets: () => rawGet(`/api/datasets`),
  getDataset: (id: number) => rawGet(`/api/datasets/${id}`),
  deleteDataset: (id: number) => rawDel(`/api/datasets/${id}`),

  // Classification Approvals
  pendingClassifications: () => get(`/agents/classifications/pending`),
  approveClassification: (id: number) => post(`/agents/classifications/${id}/approve`, {}),
  modifyClassification: (id: number, data: Record<string, string>) => post(`/agents/classifications/${id}/modify`, data),
  bulkApproveClassifications: (datasetId?: number) => post(`/agents/classifications/bulk-approve`, { dataset_id: datasetId }),

  // COA Upload
  uploadCOA: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const token = localStorage.getItem('token') || '';
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch('/api/agent/agents/coa/upload', { method: 'POST', headers, body: formData });
    if (!res.ok) throw new Error(`COA upload failed: ${res.status}`);
    return res.json();
  },

  // Modern Email Reports
  sendEmailReport: (data: {
    recipients: string[];
    report_type: string;
    company_name?: string;
    period?: string;
    custom_message?: string;
    dataset_id?: number;
    prior_dataset_id?: number;
  }) => post(`/agents/email-report`, data),

  // System
  status: () => get(`/agents/status`),
  health: () => rawGet<{ status: string; company_name: string; version: string; env: string; agent_mode: string; llm_available: boolean }>(`/health`),
  publicConfig: () => rawGet<{ company_name: string; default_currency: string; default_period: string; app_name: string; app_version: string }>(`/api/config/public`),
  telemetry: () => get(`/agents/telemetry`),
  telemetryRecent: () => get(`/agents/telemetry/recent`),

  // Reasoning
  explain: (metric: string, change: number) =>
    post(`/agents/reasoning/explain`, { metric, change }),
  scenario: (scenario: unknown) =>
    post(`/agents/reasoning/scenario`, scenario),

  // Ingestion
  detect: (file: File) => postFile(`/agents/ingestion/detect`, file),
  parseCoa: (data: unknown) => post(`/agents/ingestion/parse-coa`, data),

  // Learning
  learningAccuracy: () => get(`/agents/learning/accuracy`),
  learningSync: () => post(`/agents/learning/sync`),

  // Evaluation
  evalCases: () => get(`/agents/eval/cases`),
  evalRunAll: () => post(`/agents/eval/run-all`),
  evalRunSingle: (caseId: string) => post(`/agents/eval/run/${caseId}`),

  // Company 360
  company360: (period?: string, companyId?: number) =>
    get(`/company/360${period ? `?period=${period}` : ''}${companyId ? `${period ? '&' : '?'}company_id=${companyId}` : ''}`),

  // Causal Graph
  causalGraph: (financials: unknown, previous?: unknown, healthScore?: number, healthGrade?: string) =>
    post(`/causal/graph`, { financials, previous, health_score: healthScore, health_grade: healthGrade }),

  // Alert Resolution
  resolveAlert: (alertId: number, decision: string, explanation: string, resolutionType: string) =>
    post(`/alerts/${alertId}/resolve`, { decision, explanation, resolution_type: resolutionType }),
  escalateAlert: (alertId: number, explanation: string) =>
    post(`/alerts/${alertId}/escalate`, { explanation }),
  alertResolutionStats: () => get(`/alerts/resolution-stats`),
  alertImpact: (alertId: number) => get(`/alerts/${alertId}/impact`),

  // Translation
  translate: (text: string, targetLang: string = 'ka') =>
    post<{ translated: string }>(`/translate`, { text, target_lang: targetLang }),

  // Auth
  login: (email: string, password: string) =>
    post<{ access_token: string; email: string; role: string }>(`/../auth/login`, { email, password }),

  // ─── System of Record: Journal Entries ───
  journalCreate: (data: {
    posting_date: string; period: string; fiscal_year: number;
    description: string; currency?: string; reference?: string;
    lines: { account_code: string; debit: string; credit: string; description?: string; cost_center?: string }[];
  }) => rawPost('/api/journal/entries', data),

  journalList: (status?: string, period?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (period) params.set('period', period);
    return rawGet(`/api/journal/entries?${params}`);
  },

  journalDetail: (id: number) => rawGet(`/api/journal/entries/${id}`),
  journalPost: (id: number) => rawPost(`/api/journal/entries/${id}/post`),
  journalReverse: (id: number) => rawPost(`/api/journal/entries/${id}/reverse`),
  journalVerify: (id: number) => rawGet(`/api/journal/entries/${id}/verify`),
  journalSubmit: (id: number) => rawPost(`/api/journal/entries/${id}/submit`),
  journalApprove: (id: number) => rawPost(`/api/journal/entries/${id}/approve`),
  journalReject: (id: number, reason: string) => rawPost(`/api/journal/entries/${id}/reject`, { reason }),
  journalPending: () => rawGet('/api/journal/pending-approvals'),
  journalStats: () => rawGet('/api/journal/stats'),
  journalTrialBalance: (period: string) => rawGet(`/api/journal/trial-balance?period=${period}`),

  // ─── Periods ───
  periodList: () => rawGet('/api/periods'),
  periodCreate: (data: { period_name: string; fiscal_year: number; start_date: string; end_date: string }) =>
    rawPost('/api/periods', data),
  periodClose: (name: string, closeType = 'hard_close') =>
    rawPost(`/api/periods/${encodeURIComponent(name)}/close`, { close_type: closeType }),
  periodReopen: (name: string) => rawPost(`/api/periods/${encodeURIComponent(name)}/reopen`),
  periodIntegrity: (name: string) => rawGet(`/api/periods/${encodeURIComponent(name)}/integrity`),

  // ─── Product Profitability ───
  profitability: (datasetId?: number, segment?: string, sortBy = 'margin_pct') => {
    const params = new URLSearchParams({ sort_by: sortBy });
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (segment) params.set('segment', segment);
    return rawGet(`/api/analytics/product-profitability?${params}`);
  },

  // ─── Report Comparisons (with prior year + variance) ───
  plComparison: (datasetId?: number, priorId?: number) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (priorId) params.set('prior_dataset_id', String(priorId));
    return rawGet(`/api/analytics/pl-comparison?${params}`);
  },
  cogsComparison: (datasetId?: number, priorId?: number) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (priorId) params.set('prior_dataset_id', String(priorId));
    return rawGet(`/api/analytics/cogs-comparison?${params}`);
  },
  bsComparison: (datasetId?: number, priorId?: number) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (priorId) params.set('prior_dataset_id', String(priorId));
    return rawGet(`/api/analytics/bs-comparison?${params}`);
  },
  revenueComparison: (datasetId?: number, priorId?: number) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    if (priorId) params.set('prior_dataset_id', String(priorId));
    return rawGet(`/api/analytics/revenue-comparison?${params}`);
  },
  plTrend: (datasetIds?: string) => rawGet(`/api/analytics/pl-trend${datasetIds ? `?dataset_ids=${datasetIds}` : ''}`),
  plExportExcel: async (datasetId?: number) => {
    const params = datasetId ? `?dataset_id=${datasetId}` : '';
    const response = await fetch(`/api/analytics/pl-comparison/export${params}`, { headers: getHeaders() });
    if (!response.ok) throw new Error('Export failed');
    return response.blob();
  },
  bsExportExcel: async (datasetId?: number) => {
    const params = datasetId ? `?dataset_id=${datasetId}` : '';
    const response = await fetch(`/api/analytics/bs-comparison/export${params}`, { headers: getHeaders() });
    if (!response.ok) throw new Error('BS Export failed');
    return response.blob();
  },
  mrExportExcel: async (datasetId?: number) => {
    const response = await fetch('/api/mr/generate-excel', {
      method: 'POST', headers: { ...getHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId }),
    });
    if (!response.ok) throw new Error('MR Export failed');
    return response.blob();
  },

  revenueExportExcel: async (datasetId?: number) => {
    const params = datasetId ? `?dataset_id=${datasetId}` : '';
    const response = await fetch(`/api/analytics/revenue-comparison/export${params}`, { headers: getHeaders() });
    if (!response.ok) throw new Error('Revenue Export failed');
    return response.blob();
  },
  cogsExportExcel: async (datasetId?: number) => {
    const params = datasetId ? `?dataset_id=${datasetId}` : '';
    const response = await fetch(`/api/analytics/cogs-comparison/export${params}`, { headers: getHeaders() });
    if (!response.ok) throw new Error('COGS Export failed');
    return response.blob();
  },

  // ─── GL Reporting (from journal entries) ───
  glPeriods: () => rawGet('/api/gl/periods'),
  glIncomeStatement: (period?: string) => rawGet(`/api/gl/income-statement${period ? `?period=${period}` : ''}`),
  glBalanceSheet: (period?: string) => rawGet(`/api/gl/balance-sheet${period ? `?period=${period}` : ''}`),

  // ─── Intelligent Ingestion (Reasoning Engine) ───
  intelligentIngestPlan: (datasetId: number) =>
    rawPost(`/api/journal/intelligent-ingest/${datasetId}/plan`),
  intelligentIngestExecute: (datasetId: number) =>
    rawPost(`/api/journal/intelligent-ingest/${datasetId}/execute?auto_post=true`),

  // ─── Legacy Ingestion (summary mode) ───
  ingestToJournal: (datasetId: number) =>
    rawPost(`/api/journal/ingest/${datasetId}?auto_post=true`),

  // ─── P&L Lineage / Drill-Down ───
  plLineage: (lineCode: string, datasetId?: number) => {
    const params = new URLSearchParams();
    if (datasetId) params.set('dataset_id', String(datasetId));
    return rawGet(`/api/analytics/lineage/pl/${lineCode}?${params}`);
  },
  lineage: (type: string, id: number) => rawGet(`/api/journal/lineage/${type}/${id}`),

  // ─── Flywheel (note: different base path!) ───
  flywheelStatus: () => fetch('/api/flywheel/status', { headers: getHeaders() }).then(r => r.json()),
  flywheelTrigger: () => fetch('/api/flywheel/trigger-cycle', { method: 'POST', headers: getHeaders() }).then(r => r.json()),
  flywheelCalibrations: () => fetch('/api/flywheel/calibrations', { headers: getHeaders() }).then(r => r.json()),
  finetuneStatus: () => fetch('/api/flywheel/finetune/status', { headers: getHeaders() }).then(r => r.json()),
  finetuneExport: () => fetch('/api/flywheel/finetune/export', { method: 'POST', headers: getHeaders() }).then(r => r.json()),

  // ─── Market Data ───
  marketData: () => get('/agents/market-data'),

  // ─── EIA (Energy Information Administration) ───
  eiaReport: () => rawGet('/api/external-data/eia/petroleum-report'),
  eiaPrices: () => rawGet('/api/external-data/eia/prices'),
  eiaInventories: () => rawGet('/api/external-data/eia/inventories'),

  // ─── Financial Controls / Reconciliation ───
  reconciliation: () => rawGet('/api/analytics/reconciliation').catch(() => null),
  sapFi: () => rawGet('/api/analytics/sap-fi').catch(() => null),

  // ─── Workflow ───
  workflowPipeline: (body?: unknown) => body ? post('/agents/workflow/pipeline', body) : get('/agents/workflow/pipeline'),

  // ─── Structured Report ───
  generateReport: (params: unknown) => post('/agents/report/generate', params),

  // ─── Warehouse / Data Agent ───
  warehouseTables: () => rawGet<{ tables?: unknown[] }>('/api/ontology/warehouse/tables').then(d => (d as any)?.tables || d).catch(() => []),
  warehouseSync: () => rawPost('/api/ontology/warehouse/sync'),
  warehouseQuery: (sql: string) => rawPost('/api/ontology/warehouse/query', { sql }),
  ontologyStats: () => rawGet('/api/ontology/stats').catch(() => null),
  dataAgentQuery: (question: string) => post('/agents/data-agent/query', { question }),
  dataAgentPrebuilt: () => get<{ queries?: unknown[] }>('/agents/data-agent/prebuilt'),

  // ─── Knowledge Graph ───
  knowledgeStats: () => get('/agents/knowledge/stats'),

  // ─── Organized Data ───
  organizedData: () => rawGet('/api/data/organized').catch(() => null),

  // ─── Consolidation ───
  consolidationStatus: () => rawGet<ConsolidationData>('/api/consolidation/status'),
  consolidationRun: (subsidiaries?: any[]) => rawPost<ConsolidationData>('/api/consolidation/run', { subsidiaries }),
  consolidationSeed: () => rawPost('/api/consolidation/seed'),

  // ─── AP Automation ───
  apStatus: () => rawGet('/api/ap/status'),
  apMatch: (invoice: any) => rawPost('/api/ap/match', invoice),
  apExceptions: (status?: string) => rawGet(`/api/ap/exceptions${status ? `?status=${status}` : ''}`),
  apResolve: (index: number, resolution: string) => rawPost(`/api/ap/exceptions/${index}/resolve`, { resolution }),
  apSeed: () => rawPost('/api/ap/seed'),

  // ─── Sub-Ledger ───
  subledgerARaging: () => rawGet('/api/subledger/ar/aging'),
  subledgerAPaging: () => rawGet('/api/subledger/ap/aging'),
  subledgerSummary: () => rawGet('/api/subledger/summary'),
  subledgerSeed: () => rawPost('/api/subledger/seed'),

  // ─── Company 360 ───
  company360Overview: (period?: string, companyId?: number) => {
    const params = new URLSearchParams();
    if (period) params.set('period', period);
    if (companyId) params.set('company_id', String(companyId));
    const qs = params.toString();
    return rawGet(`/api/company-360/overview${qs ? `?${qs}` : ''}`);
  },
  company360Kpis: (period?: string, companyId?: number) => {
    const params = new URLSearchParams();
    if (period) params.set('period', period);
    if (companyId) params.set('company_id', String(companyId));
    const qs = params.toString();
    return rawGet(`/api/company-360/kpis${qs ? `?${qs}` : ''}`);
  },
  company360Health: (period?: string, companyId?: number) => {
    const params = new URLSearchParams();
    if (period) params.set('period', period);
    if (companyId) params.set('company_id', String(companyId));
    const qs = params.toString();
    return rawGet(`/api/company-360/health${qs ? `?${qs}` : ''}`);
  },
  company360Seed: () => rawPost('/api/company-360/seed'),

  // ─── Compliance ───
  complianceDashboard: () => rawGet('/api/compliance/dashboard'),
  complianceAlerts: () => rawGet('/api/compliance/alerts'),
  complianceAudit: (limit?: number) => rawGet(`/api/compliance/audit-log${limit ? `?limit=${limit}` : ''}`),
  complianceLineage: (datasetId?: string) => rawGet(`/api/compliance/lineage${datasetId ? `?dataset_id=${datasetId}` : ''}`),

  // ─── ESG & Sustainability ───
  esgDashboard: () => rawGet('/api/esg/dashboard'),
  esgScores: () => rawGet('/api/esg/scores'),
  esgCarbon: () => rawGet('/api/esg/carbon'),
  esgKpis: () => rawGet('/api/esg/kpis'),
  esgSeed: () => rawPost('/api/esg/seed'),

  // Benchmarks (added back)
  benchmarkIndustries: () => get<unknown[]>('/agents/benchmarks/industries'),

  // Situational Risk & Simulation
  situationalRisk: (scenario?: string) => 
    rawGet<any>(`/api/external-data/situational-risk${scenario ? `?scenario=${scenario}` : ''}`),

  // Competitor Intelligence
  benchmarkCompetitors: (target_a: string, target_b: string) => 
    rawGet<any>(`/api/external-data/logistics/benchmark?target_a=${target_a}&target_b=${target_b}`),

  // Institutional Facts & Writeback
  getInstitutionalLedger: () => rawGet<any[]>('/api/reports/institutional-ledger'),
  postWriteback: (facts: any[]) => rawPost('/api/writeback/push', { facts }),
};

function put<T = unknown>(path: string, body?: unknown): Promise<T> { return request<T>('PUT', path, body); }
function del<T = unknown>(path: string): Promise<T> { return request<T>('DELETE', path); }

// Raw fetch for non-/api/agent endpoints (journal, periods, profitability)
async function rawGet<T = unknown>(path: string): Promise<T> {
  const response = await fetch(path, { headers: getHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
async function rawDel<T = unknown>(path: string): Promise<T> {
  const response = await fetch(path, { method: 'DELETE', headers: getHeaders() });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
async function rawPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  const options: RequestInit = { method: 'POST', headers: getHeaders() };
  if (body !== undefined) options.body = JSON.stringify(body);
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

/* ─── FinAI Captain Chat (Hybrid Routing) ─── */
export interface ConsolidationData {
  summary: {
    total_assets: number;
    total_equity: number;
    nci: number;
    intercompany_eliminated: number;
    currency: string;
    entities: string[];
  };
  eliminations: any[];
  consolidated_financials: Record<string, number>;
  subsidiaries: any[];
}

export interface CaptainResponse {
  content: string;
  model: string;
  language?: string;
  reasoning?: string;
  action?: { type: string; payload: Record<string, unknown> };
}

export const captainChat = async (message: string, lang?: string): Promise<CaptainResponse> => {
  const storeLang = lang || (typeof window !== 'undefined' ? localStorage.getItem('finai-lang') || 'en' : 'en');
  // Captain may use Nemotron (slow) — allow 120s timeout
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120_000);
  try {
    const url = `${BASE}/captain/chat`;
    const response = await fetch(url, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        message,
        use_nemo_retriever: /document|file|upload|search/i.test(message),
        lang: storeLang,
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`Captain error: ${response.status}`);
    return await response.json();
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return { content: 'Request timed out after 2 minutes. Please try a simpler question.', model: 'timeout' };
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
};

export const bsComparison = (datasetId?: number, priorId?: number) => api.bsComparison(datasetId, priorId);
export const bsExportExcel = (datasetId?: number) => api.bsExportExcel(datasetId);
export const plComparison = (datasetId?: number, priorId?: number) => api.plComparison(datasetId, priorId);
export const plExportExcel = (datasetId?: number) => api.plExportExcel(datasetId);
export const revenueComparison = (datasetId?: number, priorId?: number) => api.revenueComparison(datasetId, priorId);
export const revenueExportExcel = (datasetId?: number) => api.revenueExportExcel(datasetId);
export const cogsComparison = (datasetId?: number, priorId?: number) => api.cogsComparison(datasetId, priorId);
export const cogsExportExcel = (datasetId?: number) => api.cogsExportExcel(datasetId);

export { get, post, put, del, postFile, postBlob };
