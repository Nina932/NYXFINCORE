import { Construction } from 'lucide-react';

interface PlaceholderPageProps {
  title: string;
}

export default function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 400, gap: 14 }}>
      <div style={{
        width: 56, height: 56, borderRadius: 12,
        background: 'rgba(56,189,248,.08)', border: '1px solid rgba(56,189,248,.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Construction size={24} style={{ color: 'var(--sky)' }} />
      </div>
      <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--heading)' }}>{title}</h2>
      <p style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 320, textAlign: 'center', lineHeight: 1.6 }}>
        This module is being developed. Connect your data source or upload financial data to activate this view.
      </p>
      <div style={{
        fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--dim)',
        padding: '4px 10px', borderRadius: 4, background: 'var(--bg2)', border: '1px solid var(--b1)',
      }}>
        COMING SOON
      </div>
    </div>
  );
}
