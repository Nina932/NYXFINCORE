import * as LucideIcons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

interface TechIconProps {
  iconName: keyof typeof LucideIcons;
  color?: string;
  size?: number;
  glow?: boolean;
  className?: string;
}

/**
 * TechIcon wraps a Lucide icon in a premium hexagonal "Command Center" frame.
 */
const TechIcon: React.FC<TechIconProps> = ({ 
  iconName, 
  color = 'var(--sky)', 
  size = 16, 
  glow = false,
  className = '' 
}) => {
  const Icon = LucideIcons[iconName] as React.FC<LucideProps>;

  if (!Icon) return null;

  return (
    <div className={`tech-icon-wrapper ${className}`} style={{ width: size * 2.5, height: size * 2.5 }}>
      <div 
        className="tech-icon-hex" 
        style={{ 
          borderColor: glow ? color : 'var(--b2)',
          boxShadow: glow ? `0 0 15px ${color}44` : 'none'
        }} 
      />
      <div className="tech-icon-inner">
        <Icon size={size} style={{ color }} />
      </div>
    </div>
  );
};

export default TechIcon;
