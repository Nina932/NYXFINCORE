import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

const GlobalNode = ({ data, selected }: NodeProps) => {
  const type = (data.type as string) || 'Unknown';
  const color = data.color as string || 'var(--sky)';
  
  return (
    <div className={`global-node-container ${selected ? 'selected' : ''}`} style={{ 
      width: 12, height: 12, 
      display: 'flex', alignItems: 'center', justifyContent: 'center' 
    }}>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      
      <div 
        className="pixel-node" 
        style={{ 
          background: selected ? color : 'var(--b3)',
          width: selected ? 8 : 4,
          height: selected ? 8 : 4,
          boxShadow: selected ? `0 0 10px ${color}` : 'none',
          borderColor: color,
          borderWidth: 1,
          borderStyle: 'solid'
        }} 
      />
      
      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
      
      <style>{`
        .pixel-node {
          border-radius: 1px;
          transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .global-node-container:hover .pixel-node {
          background: ${color} !important;
          transform: scale(3);
          box-shadow: 0 0 12px ${color} !important;
          z-index: 100;
        }
      `}</style>
    </div>
  );
};

export default memo(GlobalNode);
