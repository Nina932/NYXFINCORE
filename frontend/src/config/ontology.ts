import { 
  Building2, BookOpen, Calendar, FileText, Activity, 
  AlertTriangle, TrendingUp, Gavel, BarChart3, BookMarked 
} from 'lucide-react';

export const TYPE_CONFIG: Record<string, { 
  icon: any; 
  color: string; 
  label: string; 
  desc: string; 
  affects: string; 
  actions: string[]; 
  scenarios?: string[] 
}> = {
  Company: { 
    icon: Building2, 
    color: '#3B82F6', 
    label: 'Companies', 
    desc: 'Organize data by legal entity and subsidiary.', 
    affects: 'All reports and risks are grouped by company to ensure legal boundaries are respected.', 
    actions: ['View profile', 'Compare subsidaries'], 
    scenarios: ['Audit single subsidiary', 'Compare performance across regions'] 
  },
  Account: { 
    icon: BookOpen, 
    color: '#8B5CF6', 
    label: 'Accounts', 
    desc: 'The building blocks of your ledger (1C & IFRS).', 
    affects: 'Accounts are the foundation of everything. Changes here flow into P&L and Balance Sheets.', 
    actions: ['Browse chart', 'Review mappings'], 
    scenarios: ['Check IFRS compliance of 1C accounts', 'Trace GL movements'] 
  },
  FinancialPeriod: { 
    icon: Calendar, 
    color: '#14B8A6', 
    label: 'Periods', 
    desc: 'Reporting buckets (Monthly, Quarterly, Annual).', 
    affects: 'Time-based grouping allows for trend analysis and year-over-year growth tracking.', 
    actions: ['Comparison mode', 'Trend analysis'], 
    scenarios: ['Compare Q1 vs Q2', 'Identify seasonal patterns'] 
  },
  FinancialStatement: { 
    icon: FileText, 
    color: '#10B981', 
    label: 'Statements', 
    desc: 'Automated P&L, Balance Sheet, and Cash Flow.', 
    affects: 'Statements summarize millions of transactions into executive-ready financial views.', 
    actions: ['Open P&L', 'Open Balance Sheet'], 
    scenarios: ['Analyze gross margin trends', 'Review equity structure'] 
  },
  KPI: { 
    icon: Activity, 
    color: '#F59E0B', 
    label: 'KPIs', 
    desc: 'High-level health metrics and performance indicators.', 
    affects: 'KPIs monitor the pulse. If a KPI breaches, the system automatically triggers risk signals.', 
    actions: ['Dashboard', 'Set targets'], 
    scenarios: ['Monitor debt-to-equity ratios', 'Track unit cost efficiency'] 
  },
  RiskSignal: { 
    icon: AlertTriangle, 
    color: '#EF4444', 
    label: 'Risk Signals', 
    desc: 'Early warning system for financial distress.', 
    affects: 'Signals identify exactly where a KPI breach occurred and point to the root cause account.', 
    actions: ['View alerts', 'Run investigation'], 
    scenarios: ['Discover why ROE dropped', 'Identify hidden insolvency risks'] 
  },
  Forecast: { 
    icon: TrendingUp, 
    color: '#06B6D4', 
    label: 'Forecasts', 
    desc: 'Predictive modeling for future performance.', 
    affects: 'Forecasts simulate future outcomes based on historical trends and causal links.', 
    actions: ['Run projection', 'View paths'], 
    scenarios: ['Estimate next month cash flow', 'Predict impact of rate hikes'] 
  },
  Action: { 
    icon: Gavel, 
    color: '#EAB308', 
    label: 'Actions', 
    desc: 'AI-generated tactical recommendations.', 
    affects: 'Actions are proposed steps to resolve risks or capture growth opportunities.', 
    actions: ['Review queue', 'Approve steps'], 
    scenarios: ['Optimize OPEX', 'Resolve liquidity bottlenecks'] 
  },
  Benchmark: { 
    icon: BarChart3, 
    color: '#14B8A6', 
    label: 'Benchmarks', 
    desc: 'Industry performance comparisons.', 
    affects: 'Benchmarks provide context. See if your metrics are healthy compared to global industry peers.', 
    actions: ['Compare industry', 'View norms'], 
    scenarios: ['Compare margins to industry average', 'Check liquidity ranking'] 
  },
  Standard: { 
    icon: BookMarked, 
    color: '#94A3B8', 
    label: 'Standards', 
    desc: 'Regulatory compliance layers (IFRS/GAAP).', 
    affects: 'Standards ensure your accounts are compliant with international reporting rules.', 
    actions: ['Check compliance', 'Review rules'], 
    scenarios: ['Verify IFRS 15 revenue alignment', 'Audit reporting standards'] 
  },
};
