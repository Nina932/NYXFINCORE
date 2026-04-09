import { create } from 'zustand';
import { setLang as setTranslationLang } from '../i18n/translations';

/* ─── Types ─── */
export interface PLLineItem {
  code: string;
  label: string;
  amount: number;
  type: string;
  level: number;
}

export interface RevenueItem {
  product: string;
  net_revenue: number;
  category: string;
}

export interface COGSItem {
  product: string;
  amount: number;
}

export interface DataSource {
  type: string;
  hasProductBreakdown: boolean;
  hasCOGSBreakdown: boolean;
  message: string | null;
  sheetsParsed: string[];
}

export interface AlertItem {
  severity: string;
  message: string;
  metric?: string;
  created_at?: string;
  id?: number;
}

export interface LLMInsight {
  severity: string;
  title: string;
  explanation: string;
  action: string;
}

export interface User {
  email: string;
  role: string;
  token: string;
}

/* ─── Dataset record ─── */
export interface DatasetRecord {
  id: number;
  name: string;
  original_filename?: string;
  file_type: string;
  file_size: number;
  record_count: number;
  status: string;
  is_active: boolean;
  period: string;
  currency: string;
  company?: string;
  sheet_count: number;
  created_at: string;
  quality_score?: number;
}

/* ─── State shape ─── */
export interface FinAIState {
  // Auth
  user: User | null;
  setUser: (user: User) => void;
  logout: () => void;

  // Core financial data (ALL from backend)
  dataset_id: number | null;
  company: string | null;
  period: string | null;
  pnl: Record<string, number> | null;
  balance_sheet: Record<string, number> | null;
  revenue_breakdown: RevenueItem[];
  cogs_breakdown: COGSItem[];
  pl_line_items: PLLineItem[];
  revenue_by_category: Record<string, number>;

  // Data quality & upload assessment
  data_quality_score: number | null;
  upload_assessment: Record<string, unknown> | null;

  // Datasets catalogue
  datasets: DatasetRecord[];
  setDatasets: (datasets: DatasetRecord[]) => void;

  // Intelligence
  orchestrator: Record<string, unknown> | null;
  intelligence: Record<string, unknown> | null;
  alerts: AlertItem[];
  llm_insights: LLMInsight[];
  llm_summary: string;

  // Data source info
  dataSource: DataSource | null;

  // Document intelligence
  doc_type: string | null;  // 'trial_balance' | 'pnl_report' | null
  account_classifications: Record<string, unknown>[] | null;
  classification_summary: Record<string, unknown> | null;
  
  // Institutional Marts
  fact_ledger: any[];
  setFactLedger: (facts: any[]) => void;
  fetchInstitutionalLedger: (period?: string) => Promise<void>;
  triggerWriteback: (anomalies: any[]) => Promise<any>;

  // UI state
  lang: 'en' | 'ka';
  theme: 'dark' | 'light';
  isLoading: boolean;
  error: string | null;

  // Actions
  setDatasetId: (id: number | null) => void;
  setPeriod: (period: string | null) => void;
  setFromUpload: (response: Record<string, unknown>) => void;
  setFromDashboard: (response: Record<string, unknown>) => void;
  setAlerts: (alerts: AlertItem[]) => void;
  setOrchestrator: (data: Record<string, unknown>) => void;
  setIntelligence: (data: Record<string, unknown>) => void;
  setLang: (lang: 'en' | 'ka') => void;
  setTheme: (theme: 'dark' | 'light') => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  refreshData: () => void;
  clear: () => void;
  hasData: () => boolean;
}

/* ─── Initial state ─── */
const EMPTY_STATE = {
  lang: 'en' as const,
  theme: (typeof window !== 'undefined' ? localStorage.getItem('finai-theme') as 'dark' | 'light' : null) || 'dark' as const,
  dataset_id: null,
  company: null,
  period: null,
  pnl: null,
  balance_sheet: null,
  revenue_breakdown: [] as RevenueItem[],
  cogs_breakdown: [] as COGSItem[],
  pl_line_items: [] as PLLineItem[],
  revenue_by_category: {} as Record<string, number>,
  data_quality_score: null,
  upload_assessment: null,
  datasets: [] as DatasetRecord[],
  orchestrator: null,
  intelligence: null,
  alerts: [] as AlertItem[],
  llm_insights: [] as LLMInsight[],
  llm_summary: '',
  dataSource: null,
  doc_type: null,
  account_classifications: null,
  classification_summary: null,
  fact_ledger: [] as any[],
  isLoading: false,
  error: null,
};

/* ─── Store ─── */
export const useStore = create<FinAIState>((set, get) => ({
  // Auth — restore from localStorage
  user: (() => {
    const token = localStorage.getItem('token');
    const email = localStorage.getItem('email');
    const role = localStorage.getItem('role');
    if (token && email) return { email, role: role || 'user', token };
    return null;
  })(),

  setUser: (user) => {
    localStorage.setItem('token', user.token);
    localStorage.setItem('email', user.email);
    localStorage.setItem('role', user.role);
    set({ user });
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('email');
    localStorage.removeItem('role');
    set({ user: null });
  },

  // Dataset / period direct setters
  setDatasetId: (id) => set({ dataset_id: id }),
  setPeriod: (period) => set({ period }),

  // Financial data
  ...EMPTY_STATE,

  // Populate from smart-upload response
  setFromUpload: (r) => {
    const pnlData = (r.pnl ?? r.extracted_financials) as Record<string, number> | null;
    set({
      dataset_id: (r.dataset_id as number) ?? null,
      company: (typeof r.company === 'object' && r.company !== null ? (r.company as Record<string, unknown>).name as string : r.company as string) ?? null,
      period: (r.period as string) ?? null,
      pnl: pnlData ? {
        revenue: pnlData.revenue || 0,
        revenue_wholesale: pnlData.revenue_wholesale || 0,
        revenue_retail: pnlData.revenue_retail || 0,
        revenue_other: pnlData.revenue_other || 0,
        cogs: pnlData.cogs || 0,
        cogs_wholesale: pnlData.cogs_wholesale || 0,
        cogs_retail: pnlData.cogs_retail || 0,
        gross_profit: pnlData.gross_profit || 0,
        selling_expenses: pnlData.selling_expenses || 0,
        admin_expenses: pnlData.admin_expenses || 0,
        ga_expenses: pnlData.ga_expenses || 0,
        total_opex: pnlData.total_opex || 0,
        ebitda: pnlData.ebitda ?? 0,
        depreciation: pnlData.depreciation || 0,
        ebit: pnlData.ebit ?? 0,
        non_operating_income: pnlData.non_operating_income || 0,
        non_operating_expense: pnlData.non_operating_expense || 0,
        interest_income: pnlData.interest_income || 0,
        interest_expense: pnlData.interest_expense || 0,
        fx_gain_loss: pnlData.fx_gain_loss || 0,
        profit_before_tax: pnlData.profit_before_tax ?? 0,
        net_profit: pnlData.net_profit ?? 0,
      } : null,
      balance_sheet: (r.balance_sheet as Record<string, number>) ?? null,
      revenue_breakdown: (r.revenue_breakdown as RevenueItem[]) ?? [],
      cogs_breakdown: (r.cogs_breakdown as COGSItem[]) ?? [],
      pl_line_items: (r.pl_line_items as PLLineItem[]) ?? [],
      revenue_by_category: (r.revenue_by_category as Record<string, number>) ?? {},
      data_quality_score: (r.data_quality_score as number) ?? null,
      upload_assessment: (r.upload_assessment as Record<string, unknown>) ?? null,
      orchestrator: (r.orchestrator as Record<string, unknown>) ?? null,
      llm_insights: (r.llm_insights as LLMInsight[]) ?? [],
      llm_summary: (r.llm_summary as string) ?? '',
      dataSource: r.data_source ? {
        type: (r.data_source as Record<string, unknown>).type as string,
        hasProductBreakdown: (r.data_source as Record<string, unknown>).has_product_breakdown as boolean,
        hasCOGSBreakdown: (r.data_source as Record<string, unknown>).has_cogs_breakdown as boolean,
        message: ((r.data_source as Record<string, unknown>).message as string) ?? null,
        sheetsParsed: ((r.data_source as Record<string, unknown>).sheets_parsed as string[]) ?? [],
      } : null,
      doc_type: (r.doc_type as string) ?? null,
      account_classifications: (r.account_classifications as Record<string, unknown>[]) ?? null,
      classification_summary: (r.classification_summary as Record<string, unknown>) ?? null,
      isLoading: false,
      error: null,
    });
  },

  // Populate from dashboard endpoint
  setFromDashboard: (r) => {
    // Dashboard returns financials under 'financials' or 'pnl' key
    // Use || instead of ?? so empty {} falls through to pnl
    const rawFin = r.financials as Record<string, number> | null;
    const fin = (rawFin && Object.keys(rawFin).length > 0 ? rawFin : r.pnl) as Record<string, number> | null;
    const rawBs = r.balance_sheet as Record<string, number> | null;
    const bs = (rawBs && Object.keys(rawBs).length > 0 ? rawBs : r.bs) as Record<string, number> | null;
    set({
      company: (typeof r.company === 'object' && r.company !== null ? (r.company as Record<string, unknown>).name as string : r.company as string) ?? get().company,
      period: (r.period as string) ?? get().period,
      pnl: fin ? {
        revenue: fin.revenue || 0,
        revenue_wholesale: fin.revenue_wholesale || 0,
        revenue_retail: fin.revenue_retail || 0,
        revenue_other: fin.revenue_other || 0,
        cogs: fin.cogs || 0,
        cogs_wholesale: fin.cogs_wholesale || 0,
        cogs_retail: fin.cogs_retail || 0,
        gross_profit: fin.gross_profit || 0,
        selling_expenses: fin.selling_expenses || 0,
        admin_expenses: fin.admin_expenses || fin.ga_expenses || 0,
        ga_expenses: fin.ga_expenses || 0,
        ebitda: fin.ebitda ?? 0,
        depreciation: fin.depreciation || 0,
        ebit: fin.ebit ?? 0,
        non_operating_income: fin.non_operating_income || fin.other_income || 0,
        non_operating_expense: fin.non_operating_expense || fin.other_expense || 0,
        interest_income: fin.interest_income || 0,
        interest_expense: fin.interest_expense || 0,
        fx_gain_loss: fin.fx_gain_loss || 0,
        profit_before_tax: fin.profit_before_tax ?? 0,
        net_profit: fin.net_profit ?? 0,
      } : get().pnl,
      balance_sheet: bs ?? get().balance_sheet,
      revenue_breakdown: (r.revenue_breakdown as RevenueItem[]) ?? get().revenue_breakdown,
      cogs_breakdown: (r.cogs_breakdown as COGSItem[]) ?? get().cogs_breakdown,
      pl_line_items: (r.pl_line_items as PLLineItem[]) ?? get().pl_line_items,
      revenue_by_category: (r.revenue_by_category as Record<string, number>) ?? get().revenue_by_category,
      data_quality_score: (r.data_quality_score as number) ?? get().data_quality_score,
      dataSource: r.data_source ? {
        type: (r.data_source as Record<string, unknown>).type as string,
        hasProductBreakdown: (r.data_source as Record<string, unknown>).has_product_breakdown as boolean,
        hasCOGSBreakdown: (r.data_source as Record<string, unknown>).has_cogs_breakdown as boolean,
        message: ((r.data_source as Record<string, unknown>).message as string) ?? null,
        sheetsParsed: ((r.data_source as Record<string, unknown>).sheets_parsed as string[]) ?? [],
      } : get().dataSource,
      doc_type: (r.doc_type as string) ?? get().doc_type,
      account_classifications: (r.account_classifications as Record<string, unknown>[]) ?? get().account_classifications,
      orchestrator: (r.orchestrator as Record<string, unknown>) ?? get().orchestrator,
      intelligence: (r.intelligence as Record<string, unknown>) ?? get().intelligence,
    });
  },

  setDatasets: (datasets) => set({ datasets }),
  setAlerts: (alerts) => set({ alerts }),
  setOrchestrator: (data) => set({ orchestrator: data }),
  setIntelligence: (data) => set({ intelligence: data }),
  setFactLedger: (fact_ledger) => set({ fact_ledger }),
  
  fetchInstitutionalLedger: async () => {
    set({ isLoading: true });
    try {
      const { api } = await import('../api/client');
      const data = await api.getInstitutionalLedger();
      set({ fact_ledger: data || [] });
    } catch (err) {
      console.error('Failed to fetch ledger:', err);
    } finally {
      set({ isLoading: false });
    }
  },

  triggerWriteback: async (anomalies: any[]) => {
    try {
      const { api } = await import('../api/client');
      await api.postWriteback(anomalies);
    } catch (err) {
      console.error('Writeback failed:', err);
      throw err;
    }
  },

  setLang: (lang) => {
    set({ lang });
    setTranslationLang(lang);
    try { localStorage.setItem('finai-lang', lang); } catch {}
  },
  setTheme: (theme) => {
    set({ theme });
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('finai-theme', theme); } catch {}
  },
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),

  refreshData: () => {
    // Trigger a re-fetch of dashboard data
    import('../api/client').then(({ api }) => {
      api.dashboard().then((data: any) => {
        get().setFromDashboard(data);
      }).catch(() => {});
    });
  },
  clear: () => set(EMPTY_STATE),

  hasData: () => get().pnl !== null,
}));
