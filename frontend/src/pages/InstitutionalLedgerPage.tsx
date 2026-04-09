
import React, { useEffect, useState } from 'react';
import { useStore } from '../store/useStore';
import { 
  Database, 
  ShieldCheck, 
  ArrowUpRight, 
  Search, 
  Filter, 
  RefreshCw, 
  AlertCircle,
  CheckCircle2,
  HardDrive
} from 'lucide-react';
import DataTable from '../components/DataTable';
import KPICard from '../components/KPICard';
import EChartsFinancial from '../components/EChartsFinancial';

const InstitutionalLedgerPage = () => {
  const { fact_ledger, fetchInstitutionalLedger, triggerWriteback, isLoading } = useStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<null | 'success' | 'error'>(null);

  useEffect(() => {
    fetchInstitutionalLedger();
  }, [fetchInstitutionalLedger]);

  const handleWriteback = async () => {
    setIsSyncing(true);
    setSyncStatus(null);
    try {
      const anomalies = fact_ledger.filter(f => f.confidence_score < 0.85);
      await triggerWriteback(anomalies);
      setSyncStatus('success');
      setTimeout(() => setSyncStatus(null), 3000);
    } catch (err) {
      setSyncStatus('error');
    } finally {
      setIsSyncing(false);
    }
  };

  const filteredFacts = fact_ledger.filter(f => 
    f.product_category?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    f.ifrs_line_item?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    f.account_code?.includes(searchTerm)
  );

  const avgConfidence = fact_ledger.length > 0
    ? fact_ledger.reduce((acc, curr) => acc + curr.confidence_score, 0) / fact_ledger.length
    : 1;

  const totalAmount = fact_ledger.reduce((acc, curr) => acc + curr.amount_gel, 0);

  return (
    <div className="p-6 space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-3">
            <Database className="text-sky-500" />
            Institutional Forensic Ledger
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Standardized Fact-Dimension Marts | Singer-Protocol Synchronized
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <button 
            onClick={handleWriteback}
            disabled={isSyncing || fact_ledger.length === 0}
            className={`px-4 py-2 rounded-lg flex items-center gap-2 font-bold text-sm transition-all
              ${syncStatus === 'success' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 
                syncStatus === 'error' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                'bg-sky-500 text-white hover:bg-sky-400 shadow-[0_0_20px_rgba(14,165,233,0.3)]'}
            `}
          >
            {isSyncing ? <RefreshCw className="animate-spin" size={16} /> : 
             syncStatus === 'success' ? <CheckCircle2 size={16} /> :
             syncStatus === 'error' ? <AlertCircle size={16} /> : <ArrowUpRight size={16} />}
            {isSyncing ? 'Syncing to 1C...' : 
             syncStatus === 'success' ? 'Pushed to 1C' :
             syncStatus === 'error' ? 'Sync Failed' : 'Reverse ETL: Push to 1C'}
          </button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <KPICard 
          title="Warehouse Value (GEL)" 
          value={totalAmount.toLocaleString()} 
          icon={HardDrive} 
          badge="+12% vs LY"
          color="var(--sky)"
        />
        <KPICard 
          title="Forensic Integrity" 
          value={`${(avgConfidence * 100).toFixed(1)}%`} 
          icon={ShieldCheck} 
          badge="Institutional Standard"
          color="var(--emerald)"
        />
        <KPICard 
          title="Fact Records" 
          value={fact_ledger.length.toString()} 
          icon={Database} 
          badge="Live Sync Active"
          color="var(--amber)"
        />
        <KPICard 
          title="Staging Status" 
          value="Ready" 
          icon={RefreshCw} 
          badge="Singer STATE: OK"
          color="var(--indigo)"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Table View */}
        <div className="lg:col-span-2 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl overflow-hidden">
          <div className="p-4 border-b border-white/5 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest">General Ledger Facts</h2>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
              <input 
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search ledger..."
                className="bg-black/20 border border-white/5 rounded-lg py-1.5 pl-9 pr-4 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50 transition-colors"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-white/5 text-slate-500 font-bold uppercase tracking-tighter">
                  <th className="p-4">Period</th>
                  <th className="p-4">Account</th>
                  <th className="p-4">Entity</th>
                  <th className="p-4">Category</th>
                  <th className="p-4 text-right">Amount (GEL)</th>
                  <th className="p-4 text-center">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredFacts.map((fact, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="p-4 text-slate-300 font-mono">{fact.period}</td>
                    <td className="p-4">
                      <div className="font-bold text-slate-200">{fact.account_code}</div>
                      <div className="text-[10px] text-slate-500">{fact.ifrs_line_item}</div>
                    </td>
                    <td className="p-4 text-slate-400">{fact.business_unit}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 text-[10px] font-bold">
                        {fact.product_category}
                      </span>
                    </td>
                    <td className="p-4 text-right font-mono font-bold text-slate-200">
                      ₾{fact.amount_gel?.toLocaleString()}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-center gap-2">
                        <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${fact.confidence_score > 0.9 ? 'bg-emerald-500' : fact.confidence_score > 0.8 ? 'bg-amber-500' : 'bg-rose-500'}`}
                            style={{ width: `${fact.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-bold text-slate-500">
                          {(fact.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Sidebar Insights */}
        <div className="space-y-6">
          <div className="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-4">Forensic Analytics</h3>
            <div className="h-[200px]">
              <EChartsFinancial 
                option={{
                  tooltip: { trigger: 'axis' },
                  xAxis: { type: 'category', data: fact_ledger.map(f => f.period).slice(-5) },
                  yAxis: { type: 'value' },
                  series: [{
                    data: fact_ledger.map(f => f.confidence_score * 100).slice(-5),
                    type: 'line',
                    smooth: true,
                    areaStyle: { color: 'rgba(14, 165, 233, 0.1)' },
                    lineStyle: { color: '#0ea5e9', width: 3 }
                  }]
                }}
              />
            </div>
            <p className="text-[10px] text-slate-500 mt-4 leading-relaxed">
              Confidence scores are derived from the autonomous 1C-to-FACT transformation layer. 
              Variations suggest manual baseline shifts or supply chain disruptions.
            </p>
          </div>

          <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-6">
            <h3 className="text-sm font-bold text-amber-500 uppercase tracking-widest mb-2 flex items-center gap-2">
              <RefreshCw size={14} className="animate-spin-slow" />
              Singer State Audit
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">Current Stream</span>
                <span className="text-slate-200 font-mono">1c_export_petroleum</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">Last Watermark</span>
                <span className="text-slate-200 font-mono">2026-04-09</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-slate-400">STATE Continuity</span>
                <span className="text-emerald-500 font-bold uppercase">Healthy</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InstitutionalLedgerPage;
