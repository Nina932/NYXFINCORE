import React, { memo } from 'react';
import { getBezierPath, BaseEdge, EdgeLabelRenderer } from '@xyflow/react';
import type { EdgeProps } from '@xyflow/react';

const DataStreamEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
  selected 
}: EdgeProps) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const color = data?.color as string || 'var(--b2)';
  const label = data?.label as string || '';

  return (
    <>
      {/* Background shadow path for depth */}
      <BaseEdge 
        path={edgePath} 
        markerEnd={markerEnd} 
        style={{ 
          ...style, 
          stroke: 'rgba(0,0,0,0.4)', 
          strokeWidth: selected ? 4 : 2,
          opacity: 0.1
        }} 
      />
      
      {/* Main static path */}
      <BaseEdge 
        path={edgePath} 
        markerEnd={markerEnd} 
        style={{ 
          ...style, 
          stroke: color, 
          strokeWidth: selected ? 2 : 1,
          opacity: selected ? 0.8 : 0.3
        }} 
      />

      {/* Animated data stream path */}
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={color}
        strokeWidth={selected ? 2.5 : 1.5}
        strokeLinecap="round"
        className="data-stream-path"
        style={{ 
           opacity: selected ? 1 : 0.4,
           filter: selected ? `drop-shadow(0 0 3px ${color})` : 'none'
        }}
      />
      
      {/* Relationship label */}
      {label && selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 8,
              pointerEvents: 'none',
              fontFamily: 'var(--mono)',
              textTransform: 'uppercase',
              color: 'var(--heading)',
              background: 'var(--bg2)',
              padding: '2px 6px',
              borderRadius: 2,
              border: `1px solid ${color}`,
              zIndex: 10,
              boxShadow: 'var(--shadow-md)'
            }}
          >
            {label.toUpperCase().replace(/_/g, ' ')}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

export default memo(DataStreamEdge);
