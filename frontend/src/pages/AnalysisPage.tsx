import { useNavigate } from 'react-router-dom';
import { Activity } from 'lucide-react';

const card: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--b1)', borderRadius: 8 };
export default function AnalysisPage() {
  const navigate = useNavigate();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Activity size={20} style={{ color: 'var(--sky)' }} /> Analysis
      </h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {[
          { label: 'Orchestrator', desc: '7-stage pipeline', path: '/orchestrator' },
          { label: 'Sensitivity', desc: 'Tornado + Monte Carlo', path: '/sensitivity' },
          { label: 'Strategy', desc: 'AI recommendations', path: '/strategy' },
          { label: 'Decisions', desc: 'CFO verdict', path: '/decisions' },
          { label: 'Analogies', desc: 'Pattern matching', path: '/analogies' },
          { label: 'Benchmarks', desc: 'Industry comparison', path: '/benchmarks' },
        ].map(item => (
          <div key={item.label} style={{ ...card, padding: 16, cursor: 'pointer' }} onClick={() => navigate(item.path)}>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--heading)', marginBottom: 4 }}>{item.label}</h3>
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
