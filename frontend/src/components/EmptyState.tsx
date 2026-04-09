import { useNavigate } from 'react-router-dom';
import { Upload, Database } from 'lucide-react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title?: string;
  description?: string;
  showUploadButton?: boolean;
}

export default function EmptyState({
  icon,
  title = 'No Data Available',
  description = 'Upload a financial file to get started.',
  showUploadButton = true,
}: EmptyStateProps) {
  const navigate = useNavigate();
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: 400, gap: 16, textAlign: 'center',
    }}>
      {icon || <Database size={48} style={{ color: 'var(--dim)' }} />}
      <h2 style={{ fontSize: 18, fontWeight: 700, color: '#fff' }}>{title}</h2>
      <p style={{ fontSize: 12, color: 'var(--muted)', maxWidth: 400 }}>{description}</p>
      {showUploadButton && (
        <button
          onClick={() => navigate('/library')}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'linear-gradient(135deg, var(--sky), var(--blue))',
            color: '#000', fontWeight: 600, padding: '8px 18px', borderRadius: 8,
            border: 'none', cursor: 'pointer', fontSize: 12,
          }}
        >
          <Upload size={14} /> Upload Data
        </button>
      )}
    </div>
  );
}
