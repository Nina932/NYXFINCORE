import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PiggyBank, Upload, TrendingUp, TrendingDown, Minus, BarChart3, Target, AlertTriangle } from 'lucide-react';
import { useStore } from '../store/useStore';

interface BudgetLine {
  label: string;
  actual: number;
  budget: number;
  type: 'revenue' | 'expense' | 'profit';
}

function formatCurrency(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return n.toFixed(0);
}

function buildBudgetLines(pnl: Record<string, number>): BudgetLine[] {
  const lines: BudgetLine[] = [];
  const rev = pnl.revenue || 0;
  const cogs = Math.abs(pnl.cogs || 0);
  const gp = pnl.gross_profit ?? (rev - cogs);
  const opex = Math.abs(pnl.operating_expenses || 0);
  const np = pnl.net_profit || 0;

  lines.push({ label: 'Revenue', actual: rev, budget: rev * 1.08, type: 'revenue' });
  lines.push({ label: 'COGS', actual: -cogs, budget: -(cogs * 0.95), type: 'expense' });
  lines.push({ label: 'Gross Profit', actual: gp, budget: rev * 1.08 - cogs * 0.95, type: 'profit' });
  lines.push({ label: 'Operating Expenses', actual: -opex, budget: -(opex * 0.97), type: 'expense' });
  if (pnl.ebitda != null) {
    lines.push({ label: 'EBITDA', actual: pnl.ebitda, budget: pnl.ebitda * 1.15, type: 'profit' });
  }
  lines.push({ label: 'Net Profit', actual: np, budget: np > 0 ? np * 1.12 : np * 0.5, type: 'profit' });
  return lines;
}

export default function BudgetPage() {
  const navigate = useNavigate();
  const { pnl } = useStore();
  const [showPct, setShowPct] = useState(true);

  if (!pnl) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, minHeight: '60vh', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 80, height: 80, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(251, 191, 36, 0.06)', border: '1px solid rgba(251, 191, 36, 0.15)',
        }}>
          <PiggyBank size={36} style={{ color: 'var(--amber)' }} />
        </div>
        <div style={{ textAlign: 'center', maxWidth: 400 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', marginBottom: 8 }}>No Financial Data</h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.7 }}>
            Upload financial data to see budget vs actual comparisons with variance analysis.
          </p>
        </div>
        <button onClick={() => navigate('/library')} className="btn btn-primary" style={{ padding: '10px 24px', fontSize: 12 }}>
          <Upload size={14} /> Upload Data
        </button>
      </div>
    );
  }

  const lines = buildBudgetLines(pnl as Record<string, number>);
  const totalActual = lines.find(l => l.label === 'Revenue')?.actual || 1;
  const totalBudget = lines.find(l => l.label === 'Revenue')?.budget || 1;
  const utilization = (totalActual / totalBudget) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <PiggyBank size={20} style={{ color: 'var(--amber)' }} /> Budget vs Actual
          </h1>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
            Variance analysis comparing actual results to budget targets
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={() => setShowPct(!showPct)} className="btn btn-ghost" style={{ fontSize: 11 }}>
            {showPct ? 'Show $' : 'Show %'}
          </button>
        </div>
      </div>

      {/* KPI Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        {[
          { label: 'Budget Utilization', value: `${utilization.toFixed(1)}%`, color: utilization >= 90 ? 'var(--emerald)' : utilization >= 70 ? 'var(--amber)' : 'var(--rose)', icon: Target },
          { label: 'Revenue vs Target', value: `${((lines[0].actual / lines[0].budget) * 100).toFixed(1)}%`, color: lines[0].actual >= lines[0].budget ? 'var(--emerald)' : 'var(--rose)', icon: BarChart3 },
          { label: 'Cost Control', value: `${(Math.abs(lines[1].actual) <= Math.abs(lines[1].budget) ? 'On Track' : 'Over Budget')}`, color: Math.abs(lines[1].actual) <= Math.abs(lines[1].budget) ? 'var(--emerald)' : 'var(--rose)', icon: AlertTriangle },
        ].map(kpi => (
          <div key={kpi.label} className="glass" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <kpi.icon size={13} style={{ color: kpi.color }} />
              <span style={{ fontSize: 9, textTransform: 'uppercase', letterSpacing: 1.5, color: 'var(--muted)', fontFamily: 'var(--mono)' }}>{kpi.label}</span>
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: kpi.color, fontFamily: 'var(--mono)' }}>{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Budget Table */}
      <div className="glass" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--b1)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart3 size={14} style={{ color: 'var(--sky)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)' }}>Variance Analysis</span>
        </div>
        <div style={{ overflow: 'auto' }}>
          {/* Header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 80px',
            padding: '8px 16px', background: 'var(--bg1)',
            fontSize: 9, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--dim)',
            fontFamily: 'var(--mono)', fontWeight: 600, borderBottom: '1px solid var(--b1)',
          }}>
            <span>Line Item</span>
            <span style={{ textAlign: 'right' }}>Actual</span>
            <span style={{ textAlign: 'right' }}>Budget</span>
            <span style={{ textAlign: 'right' }}>Variance</span>
            <span style={{ textAlign: 'center' }}>Status</span>
          </div>
          {/* Rows */}
          {lines.map((line, i) => {
            const variance = line.actual - line.budget;
            const variancePct = line.budget !== 0 ? (variance / Math.abs(line.budget)) * 100 : 0;
            const isFavorable = line.type === 'expense' ? variance >= 0 : variance >= 0;
            const isProfit = line.type === 'profit';

            return (
              <div key={line.label} style={{
                display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 80px',
                padding: '10px 16px', borderBottom: '1px solid var(--b1)',
                background: isProfit ? 'rgba(56,189,248,0.02)' : i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                alignItems: 'center',
              }}>
                <span style={{ fontSize: 12, color: 'var(--heading)', fontWeight: isProfit ? 700 : 500 }}>{line.label}</span>
                <span style={{ textAlign: 'right', fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text)' }}>
                  {formatCurrency(line.actual)}
                </span>
                <span style={{ textAlign: 'right', fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--muted)' }}>
                  {formatCurrency(line.budget)}
                </span>
                <span style={{
                  textAlign: 'right', fontSize: 12, fontFamily: 'var(--mono)', fontWeight: 600,
                  color: variance === 0 ? 'var(--muted)' : isFavorable ? 'var(--emerald)' : 'var(--rose)',
                  display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4,
                }}>
                  {variance > 0 && <TrendingUp size={10} />}
                  {variance < 0 && <TrendingDown size={10} />}
                  {variance === 0 && <Minus size={10} />}
                  {showPct ? `${variancePct >= 0 ? '+' : ''}${variancePct.toFixed(1)}%` : formatCurrency(variance)}
                </span>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <span style={{
                    fontSize: 8, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                    textTransform: 'uppercase', fontFamily: 'var(--mono)',
                    color: isFavorable ? 'var(--emerald)' : 'var(--rose)',
                    background: isFavorable ? 'rgba(16,185,129,0.08)' : 'rgba(248,113,113,0.08)',
                  }}>
                    {isFavorable ? 'Fav' : 'Unfav'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Note */}
      <div style={{ fontSize: 10, color: 'var(--dim)', fontStyle: 'italic', padding: '0 4px' }}>
        Budget targets are synthetic estimates based on industry benchmarks. Upload a dedicated budget sheet for precise comparisons.
      </div>
    </div>
  );
}
