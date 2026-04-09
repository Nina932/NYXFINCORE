import React from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { 
  Shield, 
  Cpu, 
  Map, 
  Database, 
  ChevronRight, 
  ArrowRight, 
  Activity, 
  Lock, 
  Globe, 
  Zap, 
  Layers,
  Network
} from 'lucide-react';
// Landing page is standalone — no react-router
import MissionControlSim from '../components/marketing/MissionControlSim';

const LandingPage: React.FC = () => {
  const [requestSent, setRequestSent] = React.useState(false);
  const [email, setEmail] = React.useState('');
  const goToApp = () => { window.location.href = '/app/'; };
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.2], [1, 0.95]);

  return (
    <div className="landing-hero-bg min-h-screen text-text selection:bg-sky/30">
      {/* Premium Sticky Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 landing-nav flex items-center justify-between px-8">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-sky/20 border border-sky/30 flex items-center justify-center animate-pulse">
            <Shield className="w-5 h-5 text-sky" />
          </div>
          <span className="font-bold text-xl tracking-tighter text-heading">NYX <span className="text-sky">CORE</span></span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-[10px] font-bold tracking-[0.2em] uppercase text-muted">
          <a href="#solutions" className="hover:text-sky transition-colors cursor-pointer">Solutions</a>
          <a href="#connections" className="hover:text-sky transition-colors cursor-pointer">Connections</a>
          <a href="#docs" className="hover:text-sky transition-colors cursor-pointer">Documentation</a>
          <a href="#pricing" className="hover:text-sky transition-colors cursor-pointer">Pricing</a>
          <button 
            onClick={() => goToApp()}
            className="ml-4 px-6 py-2.5 rounded-full bg-white/5 border border-white/10 text-heading hover:bg-white/10 transition-all cursor-pointer text-[10px] font-bold tracking-widest uppercase"
          >
            Access Terminal
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <motion.section 
        style={{ opacity, scale }}
        className="relative pt-48 pb-32 px-8 flex flex-col items-center text-center overflow-hidden"
      >
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="max-w-5xl"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky/10 border border-sky/30 text-sky text-[10px] uppercase tracking-[0.2em] font-bold mb-8 animate-float">
            <Zap className="w-3 h-3" /> Mission Critical Strategic Intelligence
          </div>
          <h1 className="text-5xl md:text-8xl font-black text-heading mb-8 tracking-tighter leading-[0.9]">
            Autonomous <br /> 
            <span className="text-glow-cyan">Financial Ops</span>
          </h1>
          <p className="text-muted/80 text-lg md:text-xl max-w-2xl mx-auto mb-12 leading-relaxed font-medium">
            The industrial-grade digital twin for sovereign capital. 
            Real-time logistics, forensic auditing, and cross-border 
            intelligence for mission-critical operations.
          </p>
          <div className="flex flex-wrap justify-center gap-6">
            <button 
              onClick={() => {
                document.getElementById('priority-queue')?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="px-10 py-5 bg-sky text-bg0 font-black rounded-full flex items-center gap-3 hover:scale-105 transition-all group cursor-pointer shadow-xl shadow-sky/20"
            >
              Get Started Free <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button className="px-10 py-5 bg-white/5 border border-white/10 hover:bg-white/10 rounded-full font-bold transition-all flex items-center gap-2 cursor-pointer">
              View Connections <Globe className="w-4 h-4 opacity-50" />
            </button>
          </div>
        </motion.div>

        {/* Floating App Preview Card */}
        <motion.div 
          initial={{ opacity: 0, y: 100 }}
          animate={{ opacity: 1, y: 40 }}
          transition={{ delay: 0.2, duration: 1 }}
          className="relative mt-20 w-full max-w-6xl mx-auto image-reveal-container transform rotate-x-2"
        >
          <div className="absolute inset-0 bg-gradient-to-t from-bg0 via-transparent to-transparent z-10" />
          <img 
            src="/assets/hero_section_1775673701241.png" 
            alt="NYX Core Strategic Map" 
            className="w-full object-cover"
          />
          <div className="absolute top-4 left-4 z-20 flex gap-2">
            <div className="px-2 py-1 rounded bg-rose/20 border border-rose/50 text-[8px] text-rose font-bold animate-pulse uppercase">Live: Territory Alpha</div>
            <div className="px-2 py-1 rounded bg-sky/20 border border-sky/50 text-[8px] text-sky font-bold uppercase tracking-wider">Vector ID: 0x98A1</div>
          </div>
        </motion.div>
      </motion.section>

      {/* Mission Control Simulation Section */}
      <section className="py-24 px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-5xl font-black text-heading mb-4 uppercase tracking-tighter">Live Orchestration Simulator</h2>
            <div className="h-1 w-20 bg-sky mx-auto mb-4" />
            <p className="text-muted max-w-xl mx-auto">Real-time trace of the NYX multi-agent reasoning engine in a cross-border logistics scenario.</p>
          </div>
          <MissionControlSim />
        </div>
      </section>

      {/* Metrics Section */}
      <section className="py-24 border-y border-white/5 bg-bg1/50 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-8 grid grid-cols-2 md:grid-cols-4 gap-12">
          {[
            { label: 'Platform Volume', value: '₾113.8M', detail: 'Gross Processed' },
            { label: 'Intelligence Depth', value: '2.4K+', detail: 'Active Entities' },
            { label: 'Audit Accuracy', value: '99.4%', detail: 'ML Precision' },
            { label: 'System Uptime', value: '99.99%', detail: 'Enterprise SLA' }
          ].map((stat, i) => (
            <motion.div 
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="text-center"
            >
              <div className="text-[10px] text-muted uppercase tracking-widest font-bold mb-2">{stat.label}</div>
              <div className="text-3xl md:text-4xl font-mono font-bold text-heading mb-1">{stat.value}</div>
              <div className="text-[10px] text-sky/60 font-mono font-medium">{stat.detail}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section id="intelligence" className="py-32 px-8 max-w-7xl mx-auto">
        <div className="mb-20">
          <h2 className="text-3xl md:text-5xl font-bold text-heading mb-6 tracking-tight">Sovereign Capabilities</h2>
          <div className="h-1 w-20 bg-sky mb-6" />
          <p className="text-muted text-lg max-w-xl">Deep integration into industrial logistics and financial flows, mapping reality to digital intelligence.</p>
        </div>

        <div className="feature-grid">
          {/* Card 1: Map */}
          <motion.div 
            whileHover={{ y: -5 }}
            className="glass-premium p-8 flex flex-col gap-6 group"
          >
            <div className="w-12 h-12 rounded bg-sky/10 flex items-center justify-center border border-sky/20">
              <Map className="w-6 h-6 text-sky" />
            </div>
            <h3 className="text-xl font-bold text-heading">Industrial Digital Twin</h3>
            <p className="text-muted text-sm leading-relaxed">
              Real-time geospatial mapping of supply chain assets, fuel terminals, and competitor logistics 
              across key territories including Georgia and the Black Sea region.
            </p>
            <div className="mt-4 image-reveal-container h-48">
              <img src="/assets/digital_twin_section_1775673717979.png" className="w-full h-full object-cover grayscale group-hover:grayscale-0" />
            </div>
          </motion.div>

          {/* Card 2: AI Workflow */}
          <motion.div 
            whileHover={{ y: -5 }}
            className="glass-premium p-8 flex flex-col gap-6 group"
          >
            <div className="w-12 h-12 rounded bg-violet/10 flex items-center justify-center border border-violet/20">
              <Cpu className="w-6 h-6 text-violet-400" />
            </div>
            <h3 className="text-xl font-bold text-heading">Cognitive Orchestration</h3>
            <p className="text-muted text-sm leading-relaxed">
              Leveraging a dual-engine architecture powered by Claude 3.5 Sonnet and Gemini 1.5 Pro 
              to perform cross-border reasoning on legacy 1C financial data.
            </p>
            <div className="mt-4 image-reveal-container h-48">
              <img src="/assets/intelligence_section_1775673748028.png" className="w-full h-full object-cover grayscale group-hover:grayscale-0" />
            </div>
          </motion.div>

          {/* Card 3: Entity Graph */}
          <motion.div 
            whileHover={{ y: -5 }}
            className="glass-premium p-8 flex flex-col gap-6 group"
          >
            <div className="w-12 h-12 rounded bg-gold/10 flex items-center justify-center border border-gold/20">
              <Network className="w-6 h-6 text-gold" />
            </div>
            <h3 className="text-xl font-bold text-heading">Structural Intelligence</h3>
            <p className="text-muted text-sm leading-relaxed">
              Automated ontology extraction from raw data sources, building a semantic map of relationships, 
              risk factors, and hidden financial dependencies.
            </p>
            <div className="mt-4 image-reveal-container h-48">
              <img src="/assets/entity_graph_structure_1775674059655.png" className="w-full h-full object-cover grayscale group-hover:grayscale-0" />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Architecture / Trust Section */}
      <section id="architecture" className="py-32 px-8 relative overflow-hidden bg-bg1/30">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center gap-20">
          <div className="flex-1">
            <h2 className="text-3xl md:text-5xl font-bold text-heading mb-8 tracking-tight">Enterprise Defensibility</h2>
            <div className="space-y-8">
              {[
                { icon: <Lock className="w-5 h-5" />, title: 'Zero-Trust Architecture', desc: 'Secure local vector storage and private-cloud LLM deployments ensuring no data leakage.' },
                { icon: <Database className="w-5 h-5" />, title: 'Unified Data Warehouse', desc: 'Sovereign financial warehouse integrating SAP, 1C, and unstructured intelligence into a single truth layer.' },
                { icon: <Globe className="w-5 h-5" />, title: 'Multi-Region Tactical HUD', desc: 'The ability to deploy localized strategic dashboards for regional commanders and CFOs.' }
              ].map((item, i) => (
                <div key={i} className="flex gap-4">
                  <div className="mt-1 w-10 h-10 rounded bg-sky/10 flex items-center justify-center text-sky border border-sky/20 shrink-0">{item.icon}</div>
                  <div>
                    <h4 className="font-bold text-heading mb-1">{item.title}</h4>
                    <p className="text-sm text-muted leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="flex-1 w-full flex justify-center translate-y-10 md:translate-y-0">
             <div className="image-reveal-container glass-premium p-4 max-w-md transform rotate-2">
                <img src="/assets/investor_section_1775673735546.png" alt="Intelligence Panel" className="rounded border border-white/5" />
             </div>
          </div>
        </div>
      </section>

      {/* Footer / CTA */}
      <section className="py-40 px-8 text-center bg-bg0">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            className="max-w-4xl mx-auto glass-premium p-16 relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-64 h-64 bg-sky/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
            <h2 className="text-4xl md:text-6xl font-bold text-heading mb-8">Ready to deploy?</h2>
            <p className="text-muted text-lg mb-12 max-w-xl mx-auto">
              Join the institutional networks leveraging NYX CORE to redefine strategic operations and financial transparency.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <button 
                onClick={() => goToApp()}
                className="px-12 py-5 bg-sky text-bg0 font-bold rounded-lg hover:scale-105 hover:bg-white transition-all shadow-lg shadow-sky/20 cursor-pointer"
              >
                Launch Primary Terminal
              </button>
            </div>

            {/* Request Access Form */}
            <div id="priority-queue" className="mt-20 max-w-md mx-auto relative z-10">
              <div className="text-xs font-bold text-sky uppercase tracking-[0.3em] mb-4">Priority Queue</div>
              {!requestSent ? (
                <form 
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      await fetch('/api/marketing/request', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email })
                      });
                      setRequestSent(true);
                    } catch (err) {
                      console.error("Failed to send request", err);
                      // Still show success to user for UX, or handle error
                      setRequestSent(true);
                    }
                  }}
                  className="flex flex-col gap-4"
                >
                  <input 
                    type="email" 
                    required
                    placeholder="Enter institutional email..."
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all"
                  />
                  <button 
                    type="submit"
                    className="w-full py-4 bg-white/10 hover:bg-white/20 border border-white/10 rounded-lg text-xs font-bold uppercase tracking-widest transition-all"
                  >
                    Request Intelligence Briefing
                  </button>
                </form>
              ) : (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="p-8 rounded-lg bg-emerald/10 border border-emerald/30 text-emerald text-sm font-medium"
                >
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <Shield className="w-4 h-4" /> REQUEST LOGGED
                  </div>
                  System verification in progress. Our team will contact you shortly.
                </motion.div>
              )}
            </div>
            <div className="mt-12 pt-12 border-t border-white/5 flex flex-wrap justify-center gap-8 text-[9px] uppercase tracking-[0.3em] font-bold text-muted">
              <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-emerald shadow-[0_0_6px_#48BB78]" /> SYSTEM STATUS: NOMINAL</div>
              <div className="flex items-center gap-2">ORCHESTRATOR: ACTIVE</div>
              <div className="flex items-center gap-2">VECTOR SYNC: 100%</div>
            </div>
          </motion.div>
      </section>

      <footer className="py-12 border-t border-white/5 text-center text-[10px] text-muted tracking-widest uppercase">
        © 2026 NYX CORE FINANCIAL INTELLIGENCE — PRIVATE ACCESS ONLY
      </footer>
    </div>
  );
};

export default LandingPage;
