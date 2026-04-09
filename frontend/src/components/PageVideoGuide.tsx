import React, { useState, useEffect } from 'react';
import { PlayCircle, X, Maximize, Play, Pause, FastForward, Info } from 'lucide-react';
import { useStore } from '../store/useStore';
import { t } from '../i18n/translations';

interface GuideStep {
  titleEn: string;
  titleKa: string;
  descEn: string;
  descKa: string;
  animationState: number;
}

const PAGE_GUIDES: Record<string, GuideStep[]> = {
  default: [
    {
      titleEn: "Welcome to FinAI OS", titleKa: "მოგესალმებით FinAI OS-ში",
      descEn: "This is your intelligent financial command center. From here, you can command AI agents and access holistic insights.",
      descKa: "ეს არის თქვენი ინტელექტუალური ფინანსური მართვის ცენტრი, სადაც მართავთ ხელოვნურ ინტელექტს.",
      animationState: 1
    },
    {
      titleEn: "Dynamic Navigation", titleKa: "დინამიური ნავიგაცია",
      descEn: "Use the sidebar to explore deep reasoning, budgets, consolidation, and entity graphs instantly.",
      descKa: "გამოიყენეთ პანელი რათა მყისიერად გადახვიდეთ ანალიზსა და ბიუჯეტზე.",
      animationState: 2
    }
  ]
};

export default function PageVideoGuide({ pageKey = "default" }: { pageKey?: string }) {
  const [isOpen, setIsOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const { lang, theme } = useStore();

  const steps = PAGE_GUIDES[pageKey] || PAGE_GUIDES["default"];
  const isKa = lang === 'ka';

  useEffect(() => {
    let interval: any;
    if (playing) {
      interval = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev >= steps.length - 1) {
            setPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [playing, steps.length]);

  return (
    <>
      <button 
        onClick={() => { setIsOpen(true); setPlaying(true); setCurrentStep(0); }}
        className="glass"
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 16px', borderRadius: 8, cursor: 'pointer',
          border: '1px solid var(--sky)', color: 'var(--sky)',
          background: 'color-mix(in srgb, var(--sky) 10%, transparent)',
          fontWeight: 600, fontSize: 13,
          transition: 'all 0.2sease'
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--sky) 20%, transparent)'}
        onMouseLeave={(e) => e.currentTarget.style.background = 'color-mix(in srgb, var(--sky) 10%, transparent)'}
      >
        <PlayCircle size={16} />
        {isKa ? "ვიდეო ინსტრუქცია" : "Video Guide"}
      </button>

      {isOpen && (
        <div style={{
          position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
          background: 'rgba(0,0,0,0.8)', zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backdropFilter: 'blur(5px)'
        }}>
          <div style={{
            width: '80%', maxWidth: 1000, height: '80%', maxHeight: 600,
            background: 'var(--bg1)', borderRadius: 24,
            border: '1px solid var(--b1)',
            boxShadow: '0 30px 60px rgba(0,0,0,0.5)',
            display: 'flex', flexDirection: 'column',
            overflow: 'hidden', position: 'relative'
          }}>
            {/* Header */}
            <div style={{ 
              display: 'flex', justifyContent: 'space-between', padding: '16px 24px',
              borderBottom: '1px solid var(--b1)', background: 'var(--bg2)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--heading)' }}>
                <Info size={18} style={{ color: 'var(--sky)' }} />
                <span style={{ fontWeight: 700 }}>{isKa ? "სასწავლო მოდული" : "Interactive Guide Module"}</span>
              </div>
              <button onClick={() => setIsOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            {/* Video Area (Animated Mock) */}
            <div style={{ 
              flex: 1, position: 'relative', background: 'var(--bg0)', 
              display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'
            }}>
              <div className="glass" style={{
                position: 'absolute', width: 400, height: 250, borderRadius: 20, 
                border: '1px solid var(--sky)', 
                boxShadow: '0 0 30px rgba(0,242,255,0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 1s cubic-bezier(0.4, 0, 0.2, 1)',
                transform: steps[currentStep].animationState === 1 ? 'scale(1)' : 'scale(1.1) translateY(-20px)',
                opacity: 0.8
              }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ width: 60, height: 60, borderRadius: '50%', background: 'var(--sky)', margin: '0 auto 16px', opacity: 0.2, animation: 'pulse 2s infinite' }} />
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--sky)' }}>
                    DEMO SIMULATION {currentStep + 1}
                  </div>
                </div>
              </div>
              
              {/* Playback Overlay */}
              {!playing && (
                <button onClick={() => setPlaying(true)} style={{
                  position: 'absolute', width: 80, height: 80, borderRadius: '50%',
                  background: 'rgba(0,0,0,0.5)', border: '2px solid var(--sky)',
                  color: 'var(--sky)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', zIndex: 10
                }}>
                  <Play size={40} style={{ marginLeft: 6 }} />
                </button>
              )}
            </div>

            {/* Subtitles & Controls */}
            <div style={{ 
              height: 120, background: 'var(--bg2)', padding: '20px 40px',
              borderTop: '1px solid var(--b1)', display: 'flex', alignItems: 'center', gap: 32
            }}>
              <button 
                onClick={() => setPlaying(!playing)}
                style={{ 
                  width: 50, height: 50, borderRadius: '50%', background: 'var(--sky)', color: '#fff', 
                  border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' 
                }}
              >
                {playing ? <Pause size={24} /> : <Play size={24} style={{ marginLeft: 4 }} />}
              </button>
              
              <div style={{ flex: 1 }}>
                <div style={{ 
                  fontSize: 18, fontWeight: 700, color: 'var(--heading)', marginBottom: 8,
                  transition: 'all 0.3s'
                }}>
                  {isKa ? steps[currentStep].titleKa : steps[currentStep].titleEn}
                </div>
                <div style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.5 }}>
                  {isKa ? steps[currentStep].descKa : steps[currentStep].descEn}
                </div>
              </div>

              <div style={{ color: 'var(--dim)', fontSize: 12, fontWeight: 600 }}>
                {currentStep + 1} / {steps.length}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
