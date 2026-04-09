import React from 'react';
import { motion } from 'framer-motion';
import NyxLogo from './NyxLogo';

export default function LoadingScreen({ onComplete }: { onComplete?: () => void }) {
  React.useEffect(() => {
    const timer = setTimeout(() => {
      if (onComplete) onComplete();
    }, 4500);
    return () => clearTimeout(timer);
  }, [onComplete]);

  // Generate 24 distributed vector lines spreading from center
  const lines = Array.from({ length: 24 }).map((_, i) => ({
    id: i,
    angle: (i * 360) / 24,
    delay: Math.random() * 2,
    duration: 2 + Math.random() * 2,
    length: 300 + Math.random() * 400
  }));

  return (
    <motion.div 
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 1 }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: '#080B14',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden'
      }}
    >
      {/* Background Vector Scheme Grid */}
      <div style={{
        position: 'absolute',
        inset: 0,
        opacity: 0.03,
        backgroundImage: `radial-gradient(#00D8FF 1px, transparent 0)`,
        backgroundSize: '40px 40px'
      }} />

      {/* Distributing Lines Vector Animation */}
      <svg style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none'
      }}>
        <defs>
          <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#00D8FF" stopOpacity="0" />
            <stop offset="50%" stopColor="#00D8FF" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#00D8FF" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g transform={`translate(${window.innerWidth / 2}, ${window.innerHeight / 2})`}>
          {lines.map((line) => (
            <g key={line.id}>
              <motion.line
                x1="60"
                y1="0"
                x2={line.length}
                y2="0"
                stroke="url(#line-grad)"
                strokeWidth="1"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ 
                  pathLength: [0, 1, 1], 
                  opacity: [0, 1, 0],
                  rotate: line.angle 
                }}
                transition={{ 
                  duration: line.duration, 
                  repeat: Infinity, 
                  delay: line.delay,
                  ease: "easeInOut" 
                }}
                style={{ transformOrigin: '0 0' }}
              />
            </g>
          ))}
        </g>
      </svg>

      {/* Central Logo with Fade-in Scale */}
      <motion.div
        initial={{ scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.5, ease: "easeOut" }}
        style={{ position: 'relative', zIndex: 10, textAlign: 'center' }}
      >
        <NyxLogo size={160} />
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1, duration: 1 }}
          style={{ marginTop: 32 }}
        >
          <div style={{ 
            fontSize: '10px', 
            fontWeight: 900, 
            letterSpacing: '0.4em', 
            color: 'rgba(0, 216, 255, 0.6)', 
            textTransform: 'uppercase' 
          }}>
            Sovereign Protocol Initiated
          </div>
          <div style={{ 
            marginTop: 8, 
            height: '1px', 
            width: '192px', 
            marginInline: 'auto',
            background: 'linear-gradient(to right, transparent, rgba(0, 216, 255, 0.4), transparent)' 
          }} />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
