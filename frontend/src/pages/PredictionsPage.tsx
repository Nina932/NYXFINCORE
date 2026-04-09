import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Target, Plus, Loader2, CheckCircle } from 'lucide-react';
import { api } from '../api/client';
import { formatPercent } from '../utils/format';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };

export default function PredictionsPage() {
  const [form, setForm] = useState({ metric: '', predicted_value: '', confidence: '0.7', method: 'analyst' });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const { data: accuracy } = useQuery({
    queryKey: ['prediction-accuracy'],
    queryFn: () => api.predictionAccuracy() as Promise<Record<string, unknown>>,
    retry: false,
  });

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await api.recordPrediction({
        prediction_type: 'manual',
        metric: form.metric,
        predicted_value: parseFloat(form.predicted_value),
        confidence: parseFloat(form.confidence),
        source_method: form.method,
      });
      setSubmitted(true);
      setTimeout(() => setSubmitted(false), 3000);
      setForm({ metric: '', predicted_value: '', confidence: '0.7', method: 'analyst' });
    } catch { /* swallow */ }
    finally { setSubmitting(false); }
  };

  const stats = accuracy as Record<string, unknown> | undefined;
  const byMethod = (stats?.by_method as Record<string, { avg_error: number; direction_accuracy: number; count: number }>) ?? {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Target size={20} style={{ color: 'var(--sky)' }} /> Predictions
        </h1>
        <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>Record and track prediction accuracy</p>
      </div>

      {/* Stats */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {[
            { label: 'Total', value: String(stats.total ?? 0), color: 'var(--sky)' },
            { label: 'Resolved', value: String(stats.resolved ?? 0), color: 'var(--emerald)' },
            { label: 'Avg Error', value: formatPercent((stats.avg_error as number) ?? 0), color: 'var(--amber)' },
            { label: 'Direction', value: formatPercent((stats.direction_accuracy as number) ?? 0), color: 'var(--violet)' },
          ].map(s => (
            <div key={s.label} style={{ ...card, padding: 14 }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, textTransform: 'uppercase', letterSpacing: 2, color: 'var(--muted)', marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'var(--mono)' }}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* By Method */}
      {Object.keys(byMethod).length > 0 && (
        <div style={{ ...card, padding: 18 }}>
          <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 10 }}>Accuracy by Method</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
            {Object.entries(byMethod).map(([method, data]) => (
              <div key={method} style={{ background: 'var(--bg3)', borderRadius: 6, padding: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)', textTransform: 'capitalize' }}>{method}</div>
                <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>Error: {data.avg_error?.toFixed(1)}%</div>
                <div style={{ fontSize: 10, color: 'var(--emerald)' }}>Direction: {data.direction_accuracy?.toFixed(0)}%</div>
                <div style={{ fontSize: 9, color: 'var(--dim)' }}>{data.count} predictions</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Record Prediction */}
      <div style={{ ...card, padding: 18 }}>
        <h3 style={{ fontSize: 13, fontWeight: 600, color: 'var(--heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Plus size={14} style={{ color: 'var(--sky)' }} /> Record Prediction
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 8, alignItems: 'end' }}>
          {[
            { label: 'Metric', value: form.metric, key: 'metric', placeholder: 'e.g. revenue' },
            { label: 'Predicted Value', value: form.predicted_value, key: 'predicted_value', placeholder: 'e.g. 50000000' },
            { label: 'Confidence', value: form.confidence, key: 'confidence', placeholder: '0.0-1.0' },
            { label: 'Method', value: form.method, key: 'method', placeholder: 'e.g. analyst' },
          ].map(f => (
            <div key={f.key}>
              <label style={{ display: 'block', fontSize: 9, color: 'var(--muted)', marginBottom: 3, textTransform: 'uppercase', fontFamily: 'var(--mono)', letterSpacing: 1 }}>{f.label}</label>
              <input value={f.value} onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))} placeholder={f.placeholder} style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--b1)', borderRadius: 6, padding: '7px 10px', color: 'var(--heading)', fontSize: 11, outline: 'none' }} />
            </div>
          ))}
          <button onClick={handleSubmit} disabled={submitting || !form.metric || !form.predicted_value} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'linear-gradient(135deg, var(--sky), var(--blue))', color: '#fff', fontWeight: 600, padding: '7px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 11, height: 32 }}>
            {submitting ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : submitted ? <CheckCircle size={12} /> : <Plus size={12} />}
          </button>
        </div>
      </div>
    </div>
  );
}
