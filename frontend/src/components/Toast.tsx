import { useState, useCallback, createContext, useContext } from 'react';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType, duration?: number) => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });
export const useToast = () => useContext(ToastContext);

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, type: ToastType = 'info', duration = 4000) => {
    const id = ++nextId;
    setToasts(prev => [...prev, { id, message, type, duration }]);
    if (duration > 0) {
      setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
    }
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const icons: Record<ToastType, React.ReactNode> = {
    success: <CheckCircle size={16} style={{ color: 'var(--emerald)', flexShrink: 0 }} />,
    error: <AlertCircle size={16} style={{ color: 'var(--rose)', flexShrink: 0 }} />,
    warning: <AlertCircle size={16} style={{ color: 'var(--amber)', flexShrink: 0 }} />,
    info: <Info size={16} style={{ color: 'var(--sky)', flexShrink: 0 }} />,
  };

  const borderColors: Record<ToastType, string> = {
    success: 'rgba(52,211,153,.3)',
    error: 'rgba(248,113,113,.3)',
    warning: 'rgba(251,191,36,.3)',
    info: 'rgba(56,189,248,.3)',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {toasts.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 20, right: 20, zIndex: 9999,
          display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 400,
        }}>
          {toasts.map(t => (
            <div
              key={t.id}
              style={{
                background: 'var(--bg2)', border: `1px solid ${borderColors[t.type]}`,
                borderRadius: 10, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10,
                boxShadow: '0 8px 32px rgba(0,0,0,.4)',
                animation: 'slideIn 0.2s ease-out',
              }}
            >
              {icons[t.type]}
              <span style={{ fontSize: 12, color: '#fff', flex: 1 }}>{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 2, flexShrink: 0 }}
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </ToastContext.Provider>
  );
}
