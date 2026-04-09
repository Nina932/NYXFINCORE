import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Zap, FileCheck, AlertCircle, Clock, 
  ArrowRight, Search, CheckCircle2, XCircle, 
  Upload, FileText, ShoppingCart, Truck, 
  ArrowDownToLine, RefreshCcw, Info
} from 'lucide-react';
import { api } from '../api/client';
import { toast } from 'sonner';

interface APStats {
  match_rate: number;
  open_exceptions: number;
  pending_approvals: number;
  total_ap: number;
  currency: string;
}

export default function APAutomationPage() {
  const [stats, setStats] = useState<APStats | null>(null);
  const [exceptions, setExceptions] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const s = await api.apStatus() as any;
      const e = await api.apExceptions('open') as any[];
      setStats(s);
      setExceptions(e);
      // Fetch approvals too
      const q = await api.apExceptions('approved') as any[]; // Using this for demo
      setApprovals(q);
    } catch (err) {
      console.error('AP Data fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSeed = async () => {
    try {
      toast.info('Generating synthetic POs and GRNs...');
      await api.apSeed();
      toast.success('System populated with sample transactions');
      fetchData();
    } catch (err) {
      toast.error('Seeding failed');
    }
  };

  const runMatch = async () => {
    setScanning(true);
    toast.info('Scanning invoice payload...');
    
    // Simulate invoice data for demo
    const sampleInvoice = {
      invoice_number: `INV-${Math.floor(Math.random() * 9000) + 1000}`,
      vendor_name: 'Industrial Metals Corp',
      total_amount: 14500.0,
      line_items: [
        { description: 'Steel Girders L4', quantity: 20, unit_price: 725.0 }
      ],
      po_number: 'PO-1001'
    };

    setTimeout(async () => {
      try {
        const res = await api.apMatch(sampleInvoice) as any;
        if (res.status === 'matched') {
          toast.success(`Invoice ${res.invoice_number} MATCHED with PO-1001 / GRN-2001`);
        } else {
          toast.warning(`Exception found in ${res.invoice_number}: ${res.exceptions[0].type}`);
        }
        fetchData();
      } catch (err) {
        toast.error('Matching engine error');
      } finally {
        setScanning(false);
      }
    }, 2000);
  };

  const handleApprove = async (matchId: string) => {
    try {
      // Logic for approval
      toast.success('Invoice approved for payment');
      fetchData();
    } catch (err) {
      toast.error('Approval failed');
    }
  };

  const formatVal = (v: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: stats?.currency || 'USD',
      minimumFractionDigits: 0, maximumFractionDigits: 0
    }).format(v);
  };

  if (loading && !stats) {
    return (
      <div className="empty-state">
        <RefreshCcw className="animate-spin text-sky" />
        <p className="font-mono text-xs uppercase tracking-widest">Waking match engine...</p>
      </div>
    );
  }

  return (
    <div className="page-enter space-y-6">
      {/* Header */}
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Zap className="text-sky fill-sky/20" /> Accounts Payable Command
          </h1>
          <p className="text-xs text-muted font-mono uppercase tracking-widest mt-1">
            Automated 3-Way Match Terminal
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSeed} className="btn-minimal">
            Populate Store
          </button>
          <button className="btn btn-ghost">
            <Search size={14} /> Audit Trail
          </button>
          <button onClick={runMatch} disabled={scanning} className="btn btn-primary relative overflow-hidden">
            {scanning && <motion.div 
              className="absolute inset-0 bg-white/20"
              initial={{ x: '-100%' }}
              animate={{ x: '100%' }}
              transition={{ repeat: Infinity, duration: 1 }}
            />}
            <FileCheck size={14} /> Process New Invoice
          </button>
        </div>
      </header>

      {/* KPI Stats */}
      <div className="grid grid-4 gap-4">
        <div className="command-panel p-4">
          <div className="fin-label">Match Efficiency</div>
          <div className="flex items-end gap-2 mt-1">
            <div className="fin-value-md text-emerald">{stats?.match_rate}%</div>
            <div className="text-[10px] text-muted mb-1 font-mono">AUTOMATED</div>
          </div>
          <div className="progress-bar mt-3">
            <div className="progress-bar-fill bg-emerald" style={{ width: `${stats?.match_rate}%` }} />
          </div>
        </div>
        <div className="command-panel p-4">
          <div className="fin-label">Active Exceptions</div>
          <div className="fin-value-md text-rose mt-1">{stats?.open_exceptions}</div>
          <div className="text-[10px] text-rose/60 mt-1 font-mono flex items-center gap-1">
            <AlertCircle size={10} /> REQUIRES ATTENTION
          </div>
        </div>
        <div className="command-panel p-4">
          <div className="fin-label">Pending Approval</div>
          <div className="fin-value-md text-amber mt-1">{stats?.pending_approvals}</div>
          <div className="text-[10px] text-muted mt-1 font-mono">FINANCE QUEUE</div>
        </div>
        <div className="command-panel p-4">
          <div className="fin-label">Total Liabilities</div>
          <div className="fin-value-md text-heading mt-1">{formatVal(stats?.total_ap || 0)}</div>
          <div className="text-[10px] text-dim mt-1 font-mono flex items-center gap-1">
            <Clock size={10} /> AVG CYCLE: 1.4 DAYS
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Exception Terminal */}
        <div className="col-span-12 lg:col-span-7 command-panel flex flex-col min-h-[450px]">
          <div className="card-header border-b border-b1 p-4">
            <div className="card-title flex items-center gap-2">
              <AlertCircle size={14} className="text-rose" /> Exception Resolution Center
            </div>
            <div className="flex gap-2">
              <span className="tag tag-gray">FILTER: OPEN</span>
              <span className="tag tag-gray">SORT: RISK</span>
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            <table className="data-grid-premium">
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Vendor</th>
                  <th>Exception Type</th>
                  <th>Variance</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.length > 0 ? (
                  exceptions.map((ex, i) => (
                    <tr key={i} className="group">
                      <td className="font-mono text-heading">{ex.invoice_number}</td>
                      <td className="text-muted">{ex.vendor}</td>
                      <td>
                        <div className="flex flex-col gap-1">
                          <span className={`tag ${ex.type === 'Price Mismatch' ? 'tag-red' : 'tag-amber'}`}>
                            {ex.type}
                          </span>
                          <span className="text-[9px] text-dim">{ex.reason}</span>
                        </div>
                      </td>
                      <td className="font-mono text-rose">-{formatVal(ex.variance || 0)}</td>
                      <td className="text-right">
                        <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button className="btn-minimal text-emerald hover:border-emerald">Override</button>
                          <button className="btn-minimal text-rose hover:border-rose">Reject</button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-20 text-center">
                      <CheckCircle2 size={32} className="mx-auto text-emerald opacity-30 mb-2" />
                      <div className="text-muted text-xs">No active exceptions found.</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 3-Way Match Visual */}
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-6">
          <div className="command-panel p-4 flex-1">
            <div className="card-header mb-4">
              <div className="card-title">Live Match Process</div>
              <Info size={12} className="text-dim" />
            </div>
            
            <div className="flex flex-col gap-6 py-4">
              {/* Step 1: Invoice */}
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg border ${scanning ? 'border-sky animate-pulse shadow-glow' : 'border-b2'} bg-bg2`}>
                  <FileText className={scanning ? 'text-sky' : 'text-muted'} />
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-bold text-muted uppercase">Digital Invoice</div>
                  <div className="text-sm font-mono">{scanning ? '[SCANNING_OCRA...]' : 'INV-8822 (Captured)'}</div>
                </div>
                {scanning && <RefreshCcw size={14} className="text-sky animate-spin" />}
                {!scanning && <CheckCircle2 size={16} className="text-emerald" />}
              </div>

              <div className="flex justify-center py-1">
                <ArrowDownToLine size={20} className="text-b3" />
              </div>

              {/* Step 2: PO */}
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg border border-b2 bg-bg2">
                  <ShoppingCart className="text-muted" />
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-bold text-muted uppercase">Purchase Order</div>
                  <div className="text-sm font-mono">PO-1001 (Found)</div>
                </div>
                <CheckCircle2 size={16} className="text-emerald" />
              </div>

              <div className="flex justify-center py-1">
                <ArrowDownToLine size={20} className="text-b3" />
              </div>

              {/* Step 3: GRN */}
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg border border-b2 bg-bg2">
                  <Truck className="text-muted" />
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-bold text-muted uppercase">Goods Receipt</div>
                  <div className="text-sm font-mono">GRN-2001 (Partial)</div>
                </div>
                <XCircle size={16} className="text-rose" />
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-b1 bg-rose/5 p-3 rounded border border-rose/20">
              <div className="text-xs font-bold text-rose flex items-center gap-1">
                <AlertCircle size={12} /> MATCH FAILURE: QUANTITY DISCREPANCY
              </div>
              <div className="text-[11px] text-muted mt-1">
                Invoice shows 50 units, GRN shows 48 units received. 
                Pending warehouse verification.
              </div>
            </div>
          </div>

          <div className="command-panel p-4 bg-bg2/50 border-sky/20">
             <div className="text-[10px] font-bold text-sky uppercase tracking-widest mb-3">AI Recommendation</div>
             <div className="text-xs leading-relaxed text-text">
                "Vendor <span className="text-sky">Industrial Metals</span> has a history of 
                partial shipments. I suggest setting a <span className="text-amber">2% tolerance</span> threshold for 
                this specific vendor to streamline approvals."
             </div>
             <button className="btn-minimal mt-4 w-full justify-center">Apply Smart Rule</button>
          </div>
        </div>
      </div>
    </div>
  );
}
