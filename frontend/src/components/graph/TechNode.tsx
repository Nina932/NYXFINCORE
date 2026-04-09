import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';
import TechIcon from '../TechIcon';
import * as LucideIcons from 'lucide-react';

const TYPE_CONFIG: Record<string, { icon: keyof typeof LucideIcons; color: string }> = {
  Company:            { icon: 'Building2',      color: '#3B82F6' },
  Account:            { icon: 'BookOpen',       color: '#8B5CF6' },
  FinancialPeriod:    { icon: 'Calendar',       color: '#14B8A6' },
  FinancialStatement: { icon: 'FileText',       color: '#10B981' },
  KPI:                { icon: 'Activity',       color: '#F59E0B' },
  RiskSignal:         { icon: 'AlertTriangle',  color: '#EF4444' },
  Forecast:           { icon: 'TrendingUp',     color: '#06B6D4' },
  Action:             { icon: 'Gavel',          color: '#EAB308' },
  Benchmark:          { icon: 'BarChart3',      color: '#14B8A6' },
  Standard:           { icon: 'BookMarked',     color: '#94A3B8' },
};

const TechNode = ({ data: dataRaw, selected }: NodeProps) => {
  const data = dataRaw as any;
  const type = (data.type as string) || 'Unknown';
  const config = TYPE_CONFIG[type] || { icon: 'HelpCircle', color: '#738091' };
  
  return (
    <div className={`tech-node-container ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      
      <div className="industrial-panel tech-node-body" style={{ 
        borderColor: selected ? config.color : 'var(--b2)',
        boxShadow: selected ? `0 0 20px ${config.color}33` : 'none'
      }}>
        <div className="tech-node-header">
            <TechIcon 
              iconName={config.icon as keyof typeof LucideIcons} 
              color={config.color} 
              size={12} 
              glow={selected}
            />
            <span className="tech-node-type" style={{ color: config.color }}>
              {type.toUpperCase()}
            </span>
        </div>
        
        <div className="tech-node-content">
          <div className="tech-node-label">{(data.label as any) || ''}</div>
          {data.keyValue && (
            <div className="tech-node-value" style={{ color: config.color }}>
              {String(data.keyValue)}
            </div>
          )}
        </div>
        
        {/* Tactical status pips */}
        <div className="tech-node-footer">
           <div className="pip" />
           <div className="pip" />
           <div className="pip active" />
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
      
      <style>{`
        .tech-node-container {
          padding: 10px;
          min-width: 160px;
        }
        .tech-node-body {
          padding: 12px;
          border-radius: 4px;
          background: rgba(14, 19, 31, 0.8) !important;
          border-width: 1px;
          transition: all 0.3s ease;
        }
        .tech-node-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
          border-bottom: 1px solid var(--b1);
          padding-bottom: 6px;
        }
        .tech-node-type {
          font-family: var(--mono);
          font-size: 8px;
          font-weight: 800;
          letter-spacing: 1px;
        }
        .tech-node-label {
          font-size: 11px;
          font-weight: 700;
          color: var(--heading);
          margin-bottom: 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .tech-node-value {
          font-family: var(--mono);
          font-size: 10px;
          font-weight: 800;
        }
        .tech-node-footer {
          display: flex;
          gap: 3px;
          margin-top: 8px;
          justify-content: flex-end;
        }
        .tech-node-footer .pip {
          width: 3px;
          height: 3px;
          background: var(--b3);
          border-radius: 50%;
        }
        .tech-node-footer .pip.active {
          background: var(--sky);
          box-shadow: 0 0 4px var(--sky);
        }
        .selected .tech-node-body {
          transform: scale(1.02);
        }
      `}</style>
    </div>
  );
};

export default memo(TechNode);
