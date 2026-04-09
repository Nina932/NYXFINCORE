import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  compact?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorKey: number;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorKey: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error.message, info.componentStack?.substring(0, 200));
  }

  handleRetry = () => {
    this.setState(prev => ({ hasError: false, error: null, errorKey: prev.errorKey + 1 }));
  };

  render() {
    if (this.state.hasError) {
      const { compact, fallbackTitle } = this.props;

      if (compact) {
        return (
          <div style={{
            padding: '12px 16px', borderRadius: 8,
            background: 'rgba(248,113,113,.04)', border: '1px solid rgba(248,113,113,.12)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <AlertTriangle size={14} style={{ color: 'var(--rose)', flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: 'var(--rose)', flex: 1 }}>
              {fallbackTitle || 'Widget failed to load'}
            </span>
            <button onClick={this.handleRetry} style={{
              display: 'flex', alignItems: 'center', gap: 4, fontSize: 10,
              padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
              background: 'rgba(248,113,113,.08)', color: 'var(--rose)',
              border: '1px solid rgba(248,113,113,.15)',
            }}>
              <RefreshCw size={10} /> Retry
            </button>
          </div>
        );
      }

      return (
        <div style={{
          padding: 32, borderRadius: 12, textAlign: 'center',
          background: 'var(--bg2)', border: '1px solid var(--b1)',
        }}>
          <AlertTriangle size={32} style={{ color: 'var(--rose)', margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: 16, fontWeight: 700, color: '#fff', marginBottom: 6 }}>
            {fallbackTitle || 'Something went wrong'}
          </h3>
          <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16, maxWidth: 400, margin: '0 auto 16px' }}>
            {this.state.error?.message || 'An unexpected error occurred in this component.'}
          </p>
          <button onClick={this.handleRetry} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '8px 20px', borderRadius: 8, fontSize: 12, fontWeight: 600,
            background: 'linear-gradient(135deg, var(--sky), var(--blue))',
            color: '#000', border: 'none', cursor: 'pointer',
          }}>
            <RefreshCw size={14} /> Try Again
          </button>
        </div>
      );
    }

    return <div key={this.state.errorKey}>{this.props.children}</div>;
  }
}
