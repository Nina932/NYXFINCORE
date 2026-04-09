import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Trash2, Bot, User, Sparkles, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { captainChat, api } from '../api/client';
import type { CaptainResponse } from '../api/client';
import { useUsageMetrics } from '../hooks/useUsageMetrics';

interface ChatMsg {
  role: 'user' | 'ai';
  content: string;
  model?: string;
  reasoning?: string;
  data?: unknown;
}

const SUGGESTIONS = [
  'What is our margin?',
  'Analyze our financial health',
  'What are the biggest risks?',
  'Compare revenue vs costs',
  'Show cost breakdown',
  'Generate a strategy',
  'გამოთვალე EBITDA',
  'რა არის ჩვენი მარჟა?',
];

export default function ChatPage() {
  const navigate = useNavigate();
  const { trackAction } = useUsageMetrics();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [thinkingSeconds, setThinkingSeconds] = useState(0);
  const [currentModel, setCurrentModel] = useState('claude-sonnet-4');
  const endRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Thinking timer
  useEffect(() => {
    if (isTyping) {
      setThinkingSeconds(0);
      timerRef.current = setInterval(() => setThinkingSeconds(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setThinkingSeconds(0);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isTyping]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const send = useCallback(async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg) return;
    trackAction('ai_chat_sent', { message_length: msg.length });
    setInput('');
    setMessages(m => [...m, { role: 'user', content: msg }]);
    setIsTyping(true);

    try {
      // Try Captain hybrid routing first, fall back to command endpoint
      let reply: ChatMsg;
      try {
        const captainResult: CaptainResponse = await captainChat(msg);
        setCurrentModel(captainResult.model);
        reply = {
          role: 'ai',
          content: captainResult.content,
          model: captainResult.model,
          reasoning: captainResult.reasoning,
        };
      } catch {
        // Fallback to existing command endpoint
        const data = await api.command(msg);
        const content = data.response || data.llm_summary || 'No response.';
        reply = { role: 'ai', content, data };
        if (data.navigate) navigate(data.navigate);
      }
      setMessages(m => [...m, reply]);
    } catch {
      setMessages(m => [...m, { role: 'ai', content: 'Error connecting to agent. Make sure the backend is running.' }]);
    } finally {
      setIsTyping(false);
    }
  }, [input, navigate]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)', maxWidth: 860, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 12,
            background: 'var(--gradient-primary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Sparkles size={18} style={{ color: 'var(--heading)' }} />
          </div>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--heading)' }}>FinAI Assistant</h1>
            <p style={{ fontSize: 10, color: 'var(--muted)' }}>Your intelligent financial co-pilot</p>
          </div>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '4px 12px', borderRadius: 20,
          background: 'var(--bg2)', border: '1px solid var(--b2)',
          fontSize: 10, fontFamily: 'var(--mono)',
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--emerald)', animation: 'pulse 2s infinite' }} />
          <span style={{ color: 'var(--muted)' }}>Model:</span>
          <span style={{ color: 'var(--sky)' }}>{currentModel}</span>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 10 }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <Bot size={48} style={{ color: 'var(--sky)', opacity: 0.4, margin: '0 auto 16px', display: 'block' }} />
            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--heading)', marginBottom: 6 }}>
              გამარჯობა, მე ვარ FinAI ასისტენტი
            </h2>
            <p style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 420, margin: '0 auto 24px' }}>
              როგორ შემიძლია დაგეხმაროთ დღეს? შეგიძლიათ მკითხოთ ანგარიშის ანალიზი,
              რეპორტის გენერირება, ან უბრალოდ განიხილოთ ბიზნესის მდგომარეობა.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 6 }}>
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => send(s)} style={{
                  padding: '6px 14px', borderRadius: 16, fontSize: 11,
                  background: 'var(--bg2)', border: '1px solid var(--b2)', color: 'var(--muted)',
                  cursor: 'pointer', transition: 'all .2s',
                }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--sky)'; e.currentTarget.style.color = 'var(--sky)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--b2)'; e.currentTarget.style.color = 'var(--muted)'; }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <div style={{
              width: 30, height: 30, borderRadius: 10, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: m.role === 'user' ? 'rgba(56,189,248,.1)' : 'rgba(167,139,250,.1)',
            }}>
              {m.role === 'user'
                ? <User size={14} style={{ color: 'var(--sky)' }} />
                : <Sparkles size={14} style={{ color: 'var(--violet)' }} />
              }
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)', marginBottom: 3,
                display: 'flex', justifyContent: 'space-between',
              }}>
                <span>{m.role === 'user' ? 'You' : 'FinAI'}</span>
                {m.model && m.role === 'ai' && (
                  <span style={{ color: 'var(--dim)' }}>via {m.model}</span>
                )}
              </div>

              {/* Reasoning trace (Nemotron) */}
              {m.reasoning && (
                <details style={{
                  marginBottom: 6, fontSize: 10, color: 'var(--amber)',
                  background: 'rgba(251,191,36,.05)', borderRadius: 8, padding: '6px 10px',
                  border: '1px solid rgba(251,191,36,.1)',
                }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 500 }}>Reasoning Trace (Nemotron)</summary>
                  <pre style={{ marginTop: 6, whiteSpace: 'pre-wrap', fontSize: 9, opacity: 0.7, fontFamily: 'var(--mono)' }}>
                    {m.reasoning}
                  </pre>
                </details>
              )}

              <div className="glass" style={{
                padding: '12px 16px', fontSize: 12.5, lineHeight: 1.8,
                color: 'var(--text)', whiteSpace: 'pre-wrap',
                borderRadius: 12,
                ...(m.role === 'user' ? { background: 'rgba(56,189,248,.08)', border: '1px solid rgba(56,189,248,.15)' } : {}),
              }}>
                {m.content}
              </div>
            </div>
          </div>
        ))}

        {isTyping && (
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <div style={{
              width: 30, height: 30, borderRadius: 10, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(167,139,250,.1)',
            }}>
              <Sparkles size={14} style={{ color: 'var(--violet)' }} />
            </div>
            <div className="glass" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8, borderRadius: 12 }}>
              <Loader2 size={14} style={{ color: 'var(--sky)', animation: 'spin 1s linear infinite' }} />
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                {thinkingSeconds < 5 ? 'Analyzing...' :
                 thinkingSeconds < 15 ? `Deep reasoning... ${thinkingSeconds}s` :
                 thinkingSeconds < 30 ? `Nemotron processing... ${thinkingSeconds}s` :
                 `Still working... ${thinkingSeconds}s (complex query)`}
              </span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input Bar */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 0', borderTop: '1px solid var(--b1)' }}>
        {messages.length > 0 && (
          <button onClick={() => setMessages([])} style={{
            width: 40, height: 40, borderRadius: 10, border: '1px solid var(--b1)',
            background: 'var(--bg2)', color: 'var(--muted)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Trash2 size={14} />
          </button>
        )}
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="დაწერეთ შეკითხვა ან ბრძანება..."
          disabled={isTyping}
          style={{
            flex: 1, height: 40, padding: '0 14px', borderRadius: 10,
            border: '1px solid var(--b2)', background: 'var(--bg2)',
            color: 'var(--text)', fontSize: 12.5, outline: 'none', fontFamily: 'inherit',
          }}
          onFocus={e => { e.currentTarget.style.borderColor = 'var(--sky)'; }}
          onBlur={e => { e.currentTarget.style.borderColor = 'var(--b2)'; }}
        />
        <button
          onClick={() => send()}
          disabled={!input.trim() || isTyping}
          style={{
            width: 40, height: 40, borderRadius: 10, border: 'none',
            background: input.trim() ? 'var(--gradient-primary)' : 'var(--bg2)',
            color: input.trim() ? '#fff' : 'var(--dim)',
            cursor: input.trim() ? 'pointer' : 'default',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <Send size={14} />
        </button>
      </div>
      <p style={{ textAlign: 'center', fontSize: 9, color: 'var(--dim)', marginTop: 4 }}>
        Claude Sonnet 4 &bull; Nemotron 3 Super 120B &bull; Qwen3 &bull; NeMo Retriever RAG
      </p>
    </div>
  );
}
