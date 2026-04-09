import React, { useMemo } from 'react';
import { motion } from 'framer-motion';

export default function SovereignConnectivityBackground() {
  const lineCount = 36;
  
  // Generating jagged "electrical" paths
  const wires = useMemo(() => {
    return Array.from({ length: lineCount }).map((_, i) => {
      const angle = (i * 360) / lineCount;
      const length = 600 + Math.random() * 600;
      const segments = 5 + Math.floor(Math.random() * 4);
      
      let currentX = 0;
      let currentY = 0;
      let pathString = `M 0 0`;
      
      for (let s = 0; s < segments; s++) {
        const segLen = length / segments;
        // Add random jaggedness
        const jitterX = (Math.random() - 0.5) * 30;
        const jitterY = (Math.random() - 0.5) * 30;
        
        currentX += segLen;
        currentY += jitterY;
        
        pathString += ` L ${currentX} ${currentY}`;
      }
      
      return {
        id: i,
        path: pathString,
        angle,
        delay: 0.5 + Math.random() * 2,
        duration: 4 + Math.random() * 4,
        color: i % 7 === 0 ? 'var(--accent-fin)' : '#8cbbc38b',
        opacity: i % 3 === 0 ? 0.4 : 0.2
      };
    });
  }, [lineCount]);

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      <svg className="w-full h-full">
        <defs>
          <filter id="energy-glow">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        
        {/* Central Hub Shadow/Presence */}
        <g transform={`translate(${window.innerWidth / 2}, 80)`}>
          {wires.map((wire) => (
            <motion.g 
              key={wire.id} 
              style={{ rotate: wire.angle }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: wire.delay, duration: 1 }}
            >
              {/* Main Electrical Trace */}
              <motion.path
                d={wire.path}
                fill="none"
                stroke={wire.color}
                strokeWidth={0.8}
                strokeOpacity={wire.opacity}
                filter="url(#energy-glow)"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: [0, 1, 1], opacity: [0, wire.opacity, 0] }}
                transition={{
                  duration: wire.duration,
                  repeat: Infinity,
                  delay: wire.delay,
                  ease: "linear"
                }}
              />
              
              {/* "Data Packet" Pulse */}
              <motion.circle
                r={1.2}
                fill={wire.color}
                initial={{ opacity: 0 }}
                animate={{ 
                  opacity: [0, 1, 0],
                  offsetDistance: ["0%", "100%"]
                }}
                transition={{
                  duration: wire.duration * 0.6,
                  repeat: Infinity,
                  delay: wire.delay,
                  ease: "easeInOut"
                }}
                style={{ offsetPath: `path("${wire.path}")` }}
              />
            </motion.g>
          ))}
        </g>
      </svg>
      
      {/* Background radial gradient to soften the center */}
      <div 
        className="absolute inset-x-0 top-0 h-[500px] pointer-events-none opacity-20"
        style={{ background: 'radial-gradient(circle at 50% 80px, var(--accent-op) 0%, transparent 60%)' }}
      />
    </div>
  );
}
