// ═══════════════════════════════════════════════════════════
// OperationChain.tsx — Reusable process visualization
// ═══════════════════════════════════════════════════════════
// 
// Usage:
//   <OperationChain steps={steps} />
//
// Where steps come from the backend's processing_pipeline or
// are generated client-side for any multi-step operation.
//
// Copy to: frontend/src/components/OperationChain.tsx

import { CheckCircle2, Circle, Loader2, AlertCircle } from 'lucide-react';

export interface ChainStep {
  id: string;
  label: string;
  detail?: string;
  status: 'pending' | 'running' | 'done' | 'error';
  duration_ms?: number;
  result_summary?: string;  // e.g., "38 lines filled", "₾51.2M revenue"
}

interface OperationChainProps {
  title?: string;
  steps: ChainStep[];
  compact?: boolean;  // Horizontal mode for inline use
}

export default function OperationChain({ title, steps, compact }: OperationChainProps) {
  if (!steps.length) return null;

  const completed = steps.filter(s => s.status === 'done').length;
  const total = steps.length;
  const isRunning = steps.some(s => s.status === 'running');
  const hasError = steps.some(s => s.status === 'error');
  const progress = total > 0 ? (completed / total) * 100 : 0;

  if (compact) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0' }}>
        {steps.map((step, i) => (
          <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {step.status === 'done' && <CheckCircle2 size={12} style={{ color: 'var(--emerald)' }} />}
            {step.status === 'running' && <Loader2 size={12} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />}
            {step.status === 'error' && <AlertCircle size={12} style={{ color: 'var(--rose)' }} />}
            {step.status === 'pending' && <Circle size={12} style={{ color: 'var(--dim)' }} />}
            <span style={{ fontSize: 10, color: step.status === 'done' ? 'var(--emerald)' : step.status === 'running' ? 'var(--sky)' : 'var(--dim)' }}>
              {step.label}
            </span>
            {i < steps.length - 1 && <span style={{ color: 'var(--b2)', fontSize: 10 }}>→</span>}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="glass" style={{ padding: 16 }}>
      {/* Header */}
      {title && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--heading)' }}>{title}</div>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: isRunning ? 'var(--sky)' : hasError ? 'var(--rose)' : 'var(--emerald)' }}>
            {isRunning ? `${completed}/${total} running...` : hasError ? 'Error' : `${completed}/${total} complete`}
          </div>
        </div>
      )}

      {/* Progress bar */}
      <div style={{ height: 3, background: 'var(--bg2)', borderRadius: 2, marginBottom: 14, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${progress}%`,
          background: hasError ? 'var(--rose)' : 'var(--emerald)',
          borderRadius: 2,
          transition: 'width 0.5s ease',
        }} />
      </div>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {steps.map((step, i) => (
          <div key={step.id} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '6px 8px',
            borderRadius: 6,
            background: step.status === 'running' ? 'rgba(56,189,248,0.05)' : 'transparent',
            transition: 'background 0.3s',
          }}>
            {/* Step icon */}
            <div style={{ flexShrink: 0, width: 20, display: 'flex', justifyContent: 'center' }}>
              {step.status === 'done' && <CheckCircle2 size={16} style={{ color: 'var(--emerald)' }} />}
              {step.status === 'running' && <Loader2 size={16} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />}
              {step.status === 'error' && <AlertCircle size={16} style={{ color: 'var(--rose)' }} />}
              {step.status === 'pending' && <Circle size={16} style={{ color: 'var(--dim)', opacity: 0.4 }} />}
            </div>

            {/* Step label */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 12,
                fontWeight: step.status === 'running' ? 600 : 400,
                color: step.status === 'pending' ? 'var(--dim)' : 'var(--text)',
              }}>
                {step.label}
              </div>
              {step.detail && step.status !== 'pending' && (
                <div style={{ fontSize: 10, color: 'var(--dim)', marginTop: 1 }}>{step.detail}</div>
              )}
            </div>

            {/* Result / Duration */}
            <div style={{ flexShrink: 0, textAlign: 'right' }}>
              {step.result_summary && step.status === 'done' && (
                <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--emerald)' }}>{step.result_summary}</div>
              )}
              {step.duration_ms != null && step.status === 'done' && (
                <div style={{ fontSize: 9, color: 'var(--dim)', fontFamily: 'var(--mono)' }}>
                  {step.duration_ms < 1000 ? `${step.duration_ms}ms` : `${(step.duration_ms / 1000).toFixed(1)}s`}
                </div>
              )}
            </div>

            {/* Connector line to next step */}
            {i < steps.length - 1 && (
              <div style={{ position: 'absolute', left: 25, top: '100%', width: 1, height: 2, background: 'var(--b1)' }} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════
// Helper: Create chain steps for common operations
// ═══════════════════════════════════════════════════════════

export function createUploadChain(): ChainStep[] {
  return [
    { id: 'detect', label: 'Detecting file type', status: 'pending' },
    { id: 'sheets', label: 'Analyzing sheets', status: 'pending' },
    { id: 'revenue', label: 'Extracting Revenue', status: 'pending' },
    { id: 'cogs', label: 'Extracting COGS', status: 'pending' },
    { id: 'opex', label: 'Extracting Operating Expenses', status: 'pending' },
    { id: 'bs', label: 'Extracting Balance Sheet', status: 'pending' },
    { id: 'validate', label: 'Cross-validating data', status: 'pending' },
    { id: 'store', label: 'Storing in database', status: 'pending' },
  ];
}

export function createMRReportChain(): ChainStep[] {
  return [
    { id: 'load', label: 'Loading financial data', status: 'pending' },
    { id: 'rate', label: 'Fetching exchange rate (NBG)', status: 'pending' },
    { id: 'convert', label: 'Converting GEL → USD thousands', status: 'pending' },
    { id: 'pl', label: 'Filling P&L sheet', status: 'pending' },
    { id: 'bs', label: 'Filling Balance Sheet', status: 'pending' },
    { id: 'opex', label: 'Filling OPEX breakdown', status: 'pending' },
    { id: 'products', label: 'Filling Product Revenue/COGS', status: 'pending' },
    { id: 'clean', label: 'Cleaning template', status: 'pending' },
    { id: 'export', label: 'Generating Excel file', status: 'pending' },
  ];
}

export function createAnalysisChain(): ChainStep[] {
  return [
    { id: 'load', label: 'Loading financial data', status: 'pending' },
    { id: 'ratios', label: 'Computing financial ratios', status: 'pending' },
    { id: 'diagnosis', label: 'Running diagnosis engine', status: 'pending' },
    { id: 'causal', label: 'Causal analysis', status: 'pending' },
    { id: 'benchmark', label: 'Comparing to benchmarks', status: 'pending' },
    { id: 'strategy', label: 'Generating strategy', status: 'pending' },
    { id: 'report', label: 'Building executive summary', status: 'pending' },
  ];
}

// Helper to advance steps (simulate or track real progress)
export function advanceStep(
  steps: ChainStep[],
  stepId: string,
  status: 'running' | 'done' | 'error',
  result?: string,
  duration?: number
): ChainStep[] {
  return steps.map(s =>
    s.id === stepId
      ? { ...s, status, result_summary: result || s.result_summary, duration_ms: duration || s.duration_ms }
      : s
  );
}
