import { useState } from 'react';
import { Sparkles, ChevronDown, ChevronUp, Loader2, Brain } from 'lucide-react';
import { captainChat } from '../api/client';
import { useStore } from '../store/useStore';

interface AIInsightPanelProps {
  pageName: string;
  context?: string;
}

export default function AIInsightPanel({ pageName, context }: AIInsightPanelProps) {
  const { lang } = useStore();
  const [insight, setInsight] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [model, setModel] = useState('');

  const getInsight = async () => {
    if (insight) { setExpanded(!expanded); return; }
    setExpanded(true);
    setLoading(true);
    try {
      const prompt = context
        ? `Analyze the ${pageName} data briefly. Context: ${context}`
        : `Analyze the ${pageName} data briefly. Provide 2-3 key insights and one recommendation.`;
      const res = await captainChat(prompt, lang);
      setInsight(res.content);
      setModel(res.model || 'AI');
    } catch {
      setInsight('AI analysis temporarily unavailable.');
      setModel('--');
    }
    setLoading(false);
  };

  return (
    <div className="ai-insight-panel" style={{ marginTop: 8 }}>
      <div
        className="ai-insight-header"
        onClick={getInsight}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={13} style={{ color: 'var(--sky)' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--heading)' }}>
            AI Insight
          </span>
          {model && insight && (
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 8, padding: '1px 6px',
              borderRadius: 3, background: 'rgba(76,144,240,.08)', color: 'var(--sky)',
              border: '1px solid rgba(76,144,240,.12)',
            }}>
              {model}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {loading && <Loader2 size={12} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />}
          {expanded ? <ChevronUp size={14} style={{ color: 'var(--muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--muted)' }} />}
        </div>
      </div>
      {expanded && (
        <div className="ai-insight-body" style={{ animation: 'slide-up 0.2s ease both' }}>
          {loading && !insight ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0' }}>
              <Brain size={14} style={{ color: 'var(--sky)', opacity: 0.5 }} />
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>Analyzing {pageName} data...</span>
            </div>
          ) : (
            insight
          )}
        </div>
      )}
    </div>
  );
}
