import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import PnLPage from './pages/PnLPage';

import BalanceSheetPage from './pages/BalanceSheetPage';
import AnalysisPage from './pages/AnalysisPage';
import ReportsPage from './pages/ReportsPage';
import ChatPage from './pages/ChatPage';
import SettingsPage from './pages/SettingsPage';
import DeepReasoningPage from './pages/DeepReasoningPage';
import DataLibraryPage from './pages/DataLibraryPage';
import MonitoringPage from './pages/MonitoringPage';
import AlertsPage from './pages/AlertsPage';
import PredictionsPage from './pages/PredictionsPage';
import PlaceholderPage from './pages/PlaceholderPage';
import RevenuePage from './pages/RevenuePage';
import CostsPage from './pages/CostsPage';
import BudgetPage from './pages/BudgetPage';
import BenchmarksPage from './pages/BenchmarksPage';
import ForecastsPage from './pages/ForecastsPage';
import GLPipelinePage from './pages/GLPipelinePage';
import TransactionsPage from './pages/TransactionsPage';
import MarketDataPage from './pages/MarketDataPage';
import SystemPage from './pages/SystemPage';
import EvalPage from './pages/EvalPage';
import WorkflowPage from './pages/WorkflowPage';
import StructuredReportPage from './pages/StructuredReportPage';
import OntologyExplorerPage from './pages/OntologyExplorerPage';
import WarehousePage from './pages/WarehousePage';
import WorkshopPage from './pages/WorkshopPage';
import FlywheelPage from './pages/FlywheelPage';
import JournalPage from './pages/JournalPage';
import PeriodClosePage from './pages/PeriodClosePage';
import ProductProfitabilityPage from './pages/ProductProfitabilityPage';
import IngestionPlanPage from './pages/IngestionPlanPage';
import FinancialControlsPage from './pages/FinancialControlsPage';
import StructurePage from './pages/StructurePage';
import ConsolidationPage from './pages/ConsolidationPage';
import APAutomationPage from './pages/APAutomationPage';
import ComplianceAuditPage from './pages/ComplianceAuditPage';
import ESGPage from './pages/ESGPage';
import DataLineagePage from './pages/DataLineagePage';
import AnalyticsCenterPage from './pages/AnalyticsCenterPage';
import SensitivityPage from './pages/SensitivityPage';
import SubledgerPage from './pages/SubledgerPage';
import Company360Page from './pages/Company360Page';
import LandingPage from './pages/LandingPage';
import React from 'react';
import LoadingScreen from './components/LoadingScreen';
import { AnimatePresence } from 'framer-motion';
import { ToastProvider } from './components/Toast';
import { skeletonStyles } from './components/Skeleton';
import { FilterProvider } from './hooks/useReactiveFilter';
import ErrorBoundary from './components/ErrorBoundary';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const [loading, setLoading] = React.useState(true);

  return (
    <QueryClientProvider client={queryClient}>
      <AnimatePresence>
        {loading && <LoadingScreen onComplete={() => setLoading(false)} />}
      </AnimatePresence>
      <FilterProvider>
      <ToastProvider>
        <style>{skeletonStyles}</style>
        <ErrorBoundary fallbackTitle="Application Error">
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<ErrorBoundary compact fallbackTitle="Dashboard"><DashboardPage /></ErrorBoundary>} />
              <Route path="/structure" element={<ErrorBoundary compact fallbackTitle="Structure"><StructurePage /></ErrorBoundary>} />
              <Route path="/ontology" element={<ErrorBoundary compact fallbackTitle="Ontology Explorer"><OntologyExplorerPage /></ErrorBoundary>} />
              <Route path="/warehouse" element={<ErrorBoundary compact fallbackTitle="Warehouse"><WarehousePage /></ErrorBoundary>} />
              <Route path="/library" element={<ErrorBoundary compact fallbackTitle="Data Library"><DataLibraryPage /></ErrorBoundary>} />
              <Route path="/pnl" element={<ErrorBoundary compact fallbackTitle="P&L"><PnLPage /></ErrorBoundary>} />
              <Route path="/balance-sheet" element={<ErrorBoundary compact fallbackTitle="Balance Sheet"><BalanceSheetPage /></ErrorBoundary>} />
              <Route path="/revenue" element={<ErrorBoundary compact fallbackTitle="Revenue"><RevenuePage /></ErrorBoundary>} />
              <Route path="/costs" element={<ErrorBoundary compact fallbackTitle="Costs"><CostsPage /></ErrorBoundary>} />
              <Route path="/budget" element={<ErrorBoundary compact fallbackTitle="Budget"><BudgetPage /></ErrorBoundary>} />
              <Route path="/mr-reports" element={<ErrorBoundary compact fallbackTitle="Reports"><ReportsPage /></ErrorBoundary>} />
              <Route path="/cash-runway" element={<ErrorBoundary compact fallbackTitle="Cash Runway"><MonitoringPage /></ErrorBoundary>} />
              <Route path="/kpi-monitor" element={<ErrorBoundary compact fallbackTitle="KPI Monitor"><MonitoringPage /></ErrorBoundary>} />
              <Route path="/ai-intelligence" element={<ErrorBoundary compact fallbackTitle="AI Intelligence"><ChatPage /></ErrorBoundary>} />
              <Route path="/benchmarks" element={<ErrorBoundary compact fallbackTitle="Benchmarks"><BenchmarksPage /></ErrorBoundary>} />
              <Route path="/forecasts" element={<ErrorBoundary compact fallbackTitle="Forecasts"><ForecastsPage /></ErrorBoundary>} />
              <Route path="/gl-pipeline" element={<ErrorBoundary compact fallbackTitle="GL Pipeline"><GLPipelinePage /></ErrorBoundary>} />
              <Route path="/reasoning" element={<ErrorBoundary compact fallbackTitle="Deep Reasoning"><DeepReasoningPage /></ErrorBoundary>} />
              <Route path="/alerts" element={<ErrorBoundary compact fallbackTitle="Alerts"><AlertsPage /></ErrorBoundary>} />
              <Route path="/predictions" element={<ErrorBoundary compact fallbackTitle="Predictions"><PredictionsPage /></ErrorBoundary>} />
              <Route path="/transactions" element={<ErrorBoundary compact fallbackTitle="Transactions"><TransactionsPage /></ErrorBoundary>} />
              <Route path="/market" element={<ErrorBoundary compact fallbackTitle="Market Data"><MarketDataPage /></ErrorBoundary>} />
              <Route path="/system" element={<ErrorBoundary compact fallbackTitle="System"><SystemPage /></ErrorBoundary>} />
              <Route path="/workflow" element={<ErrorBoundary compact fallbackTitle="Workflow"><WorkflowPage /></ErrorBoundary>} />
              <Route path="/ai-report" element={<ErrorBoundary compact fallbackTitle="AI Report"><StructuredReportPage /></ErrorBoundary>} />
              <Route path="/eval" element={<ErrorBoundary compact fallbackTitle="Evaluation"><EvalPage /></ErrorBoundary>} />
              <Route path="/workshop" element={<ErrorBoundary compact fallbackTitle="Workshop"><WorkshopPage /></ErrorBoundary>} />
              <Route path="/flywheel" element={<ErrorBoundary compact fallbackTitle="Data Flywheel"><FlywheelPage /></ErrorBoundary>} />
              <Route path="/journal" element={<ErrorBoundary compact fallbackTitle="Journal Entries"><JournalPage /></ErrorBoundary>} />
              <Route path="/periods" element={<ErrorBoundary compact fallbackTitle="Period Close"><PeriodClosePage /></ErrorBoundary>} />
              <Route path="/profitability" element={<ErrorBoundary compact fallbackTitle="Product Profitability"><ProductProfitabilityPage /></ErrorBoundary>} />
              <Route path="/intelligent-ingest" element={<ErrorBoundary compact fallbackTitle="Intelligent Ingestion"><IngestionPlanPage /></ErrorBoundary>} />
              <Route path="/controls" element={<ErrorBoundary compact fallbackTitle="Financial Controls"><FinancialControlsPage /></ErrorBoundary>} />
              <Route path="/consolidation" element={<ErrorBoundary compact fallbackTitle="Consolidation"><ConsolidationPage /></ErrorBoundary>} />
              <Route path="/ap-automation" element={<ErrorBoundary compact fallbackTitle="AP Automation"><APAutomationPage /></ErrorBoundary>} />
              <Route path="/compliance" element={<ErrorBoundary compact fallbackTitle="Compliance"><ComplianceAuditPage /></ErrorBoundary>} />
              <Route path="/esg" element={<ErrorBoundary compact fallbackTitle="ESG & Sustainability"><ESGPage /></ErrorBoundary>} />
              <Route path="/lineage" element={<ErrorBoundary compact fallbackTitle="Data Lineage"><DataLineagePage /></ErrorBoundary>} />
              <Route path="/analytics" element={<ErrorBoundary compact fallbackTitle="Analytics Center"><AnalyticsCenterPage /></ErrorBoundary>} />
              <Route path="/sensitivity" element={<ErrorBoundary compact fallbackTitle="Sensitivity"><SensitivityPage /></ErrorBoundary>} />
              <Route path="/subledger" element={<ErrorBoundary compact fallbackTitle="Sub-Ledger"><SubledgerPage /></ErrorBoundary>} />
              <Route path="/company-360" element={<ErrorBoundary compact fallbackTitle="Company 360"><Company360Page /></ErrorBoundary>} />
              <Route path="/tools" element={<PlaceholderPage title="Tools" />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>

        </ErrorBoundary>
      </ToastProvider>
      </FilterProvider>
    </QueryClientProvider>
  );
}

export default App;
