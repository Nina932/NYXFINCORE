import React from 'react';
import { motion, useScroll, useTransform, AnimatePresence } from 'framer-motion';
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
  Network,
  Search,
  CheckCircle2,
  ExternalLink,
  Users,
  BarChart3,
  Server,
  Cloud,
  FileText,
  Briefcase
} from 'lucide-react';
import MissionControlSim from './MissionControlSim';
import NyxLogo from '../components/NyxLogo';

// --- Types & Data ---

type Connector = {
  name: string;
  category: string;
  desc: string;
  status: 'active' | 'beta' | 'planned';
};

const CONNECTORS: Connector[] = [
  { name: '1C:Enterprise', category: 'Enterprise/ERP', desc: 'Deep extraction from Georgian and CIS instances.', status: 'active' },
  { name: 'SAP S/4HANA', category: 'Enterprise/ERP', desc: 'Direct OData and RFC connectivity for global finance.', status: 'active' },
  { name: 'Oracle ERP Cloud', category: 'Enterprise/ERP', desc: 'Seamless integration with Oracles cloud ecosystem.', status: 'active' },
  { name: 'NBG (National Bank)', category: 'Regulatory', desc: 'Real-time exchange rate and regulatory feed sync.', status: 'active' },
  { name: 'Customs Terminal', category: 'Logistics', desc: 'Direct telemetry from major Black Sea port terminals.', status: 'beta' },
  { name: 'Maersk Logistics', category: 'Logistics', desc: 'Global shipping and container tracking integration.', status: 'active' },
  { name: 'SWIFT Network', category: 'Banking', desc: 'Cross-border payment and ledger reconciliation.', status: 'beta' },
  { name: 'Bank of Georgia API', category: 'Banking', desc: 'Full corporate account transaction mirroring.', status: 'active' },
  { name: 'AWS S3 / Vector', category: 'Cloud/Data', desc: 'Sovereign storage for unstructured intelligence.', status: 'active' },
  { name: 'Google Cloud PubSub', category: 'Cloud/Data', desc: 'High-volume telemetry bus integration.', status: 'active' },
  { name: 'Microsoft Dynamics', category: 'Enterprise/ERP', desc: 'Full suite CRM and financial data extraction.', status: 'active' },
  { name: 'Fuel Terminal HUD', category: 'Logistics', desc: 'IoT integration for real-time fuel inventory.', status: 'planned' },
];

const LandingPage: React.FC = () => {
  const [requestSent, setRequestSent] = React.useState(false);
  const [form, setForm] = React.useState({ fullName: '', email: '', company: '', message: '', interest: 'Investor' });
  const [search, setSearch] = React.useState('');
  const [activeCategory, setActiveCategory] = React.useState('All');

  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.1], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.1], [1, 0.98]);

  const filteredConnectors = CONNECTORS.filter(c => 
    (activeCategory === 'All' || c.category.includes(activeCategory)) &&
    (c.name.toLowerCase().includes(search.toLowerCase()) || c.desc.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="landing-hero-bg min-h-screen text-text selection:bg-sky/30 font-sans">
      
      {/* Institutional Top Bar */}
      <div className="bg-bg0 border-b border-white/5 py-2 px-8 flex justify-between items-center text-[8px] font-bold tracking-[0.3em] uppercase text-muted/60">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><div className="w-1 h-1 rounded-full bg-emerald" /> SYSTEM: NOMINAL</span>
          <span className="flex items-center gap-1.5"><div className="w-1 h-1 rounded-full bg-sky" /> NODES: 2,492 ACTIVE</span>
        </div>
        <div className="flex items-center gap-6">
          <span>LATENCY: 14ms</span>
          <span>SOVEREIGN CLOUD: GEORGIA_WEST_1</span>
        </div>
      </div>

      {/* Premium Sticky Nav */}
      <nav className="sticky top-0 z-50 landing-nav flex items-center justify-between px-8 py-4 bg-bg0/80 backdrop-blur-xl border-b border-white/5">
        <div className="flex items-center gap-3">
          <NyxLogo size={28} />
          <span className="font-bold text-xl tracking-tighter text-heading">NYX <span className="text-sky">CORE</span></span>
        </div>
        <div className="hidden lg:flex items-center gap-8 text-[9px] font-bold tracking-[0.2em] uppercase text-muted">
          <a href="#architecture" className="hover:text-sky transition-colors">Architecture</a>
          <a href="#connectors" className="hover:text-sky transition-colors">Connectivity</a>
          <a href="#solutions" className="hover:text-sky transition-colors">Solutions</a>
          <a href="#pricing" className="hover:text-sky transition-colors">Pricing</a>
          <button 
            onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
            className="ml-4 px-6 py-2.5 rounded-full bg-sky text-bg0 hover:bg-white transition-all cursor-pointer text-[9px] font-black tracking-widest uppercase shadow-lg shadow-sky/20"
          >
            Priority Access
          </button>
        </div>
      </nav>

      {/* Hero Section: Strategic Command */}
      <motion.section 
        style={{ opacity, scale }}
        className="relative pt-32 pb-24 px-8 flex flex-col items-center text-center overflow-hidden"
      >
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="max-w-6xl w-full"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky/10 border border-sky/30 text-sky text-[9px] uppercase tracking-[0.3em] font-bold mb-8">
            <Zap className="w-3 h-3" /> Industrial Strategic Intelligence
          </div>
          <h1 className="text-6xl md:text-8xl font-black text-heading mb-8 tracking-tighter leading-[0.85]">
            Sovereign <br /> 
            <span className="text-glow-cyan">Strategic Intel</span>
          </h1>
          <p className="text-muted/80 text-lg md:text-xl max-w-3xl mx-auto mb-12 leading-relaxed font-medium">
             NYX CORE: The enterprise-grade data platform that replaces fragmented tools with a single, unified environment for analytics, 
             AI auditing, and sovereign strategic command.
          </p>
          <div className="flex flex-wrap justify-center gap-6 mb-20">
            <button 
              onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
              className="px-12 py-5 bg-sky text-bg0 font-black rounded-full flex items-center gap-3 hover:scale-105 transition-all group cursor-pointer shadow-xl shadow-sky/30"
            >
              Get Started Free <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button 
               onClick={() => document.getElementById('architecture')?.scrollIntoView({ behavior: 'smooth' })}
               className="px-12 py-5 bg-white/5 border border-white/10 hover:bg-white/10 rounded-full font-bold transition-all flex items-center gap-2 cursor-pointer"
            >
              System Overview <Globe className="w-4 h-4 opacity-50" />
            </button>
          </div>

          {/* Large Command Preview */}
          <div className="relative w-full max-w-7xl mx-auto image-reveal-container rounded-2xl border border-white/10 shadow-2xl shadow-sky/10 overflow-hidden transform perspective-1000 rotate-x-2">
            <div className="absolute inset-0 bg-gradient-to-t from-bg0 via-transparent to-transparent z-10" />
            <img 
              src="/assets/nyx_executive_command_center_1775748584914.png" 
              alt="NYX Strategic HUD" 
              className="w-full h-auto"
            />
            <div className="absolute top-6 left-6 z-20 flex flex-col gap-2">
              <div className="px-3 py-1.5 rounded-md bg-rose/30 border border-rose/50 text-[10px] text-rose font-black animate-pulse flex items-center gap-2 backdrop-blur-xl">
                 <Activity className="w-3 h-3" /> LIVE: TACTICAL HUD
              </div>
              <div className="px-3 py-1.5 rounded-md bg-sky/30 border border-sky/50 text-[10px] text-sky font-black flex items-center gap-2 backdrop-blur-xl">
                 <Shield className="w-3 h-3" /> ZERO DATA RETENTION (ZDR) ACTIVE
              </div>
            </div>
          </div>
        </motion.div>
      </motion.section>

      {/* "Unistream" Style Architecture Flow */}
      <section id="architecture" className="py-32 px-8 bg-bg1/30 relative">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-5xl font-black text-heading mb-6 tracking-tight uppercase">Platform Architecture</h2>
            <div className="h-1.5 w-24 bg-sky mx-auto mb-8" />
            <p className="text-muted text-lg max-w-2xl mx-auto">
              Institutional-grade power with startup simplicity. NYX CORE simplifies the enormous, routine work of data orchestration, allowing you to focus on analysis and strategic decision-making.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative">
             {/* Flow Lines (Desktop) */}
            <div className="hidden md:block absolute top-1/2 left-0 right-0 h-0.5 bg-gradient-to-r from-sky/5 via-sky/20 to-sky/5 -translate-y-1/2 z-0" />
            
            {[
              { 
                step: '01', icon: Database, title: '📥 STRATEGIC INGESTION', color: 'sky',
                desc: 'Consolidate 100+ sources including SAP, 1C, and Bank APIs into a secure, sovereign Lake Space.'
              },
              { 
                step: '02', icon: Cpu, title: '🔄 PROCESSING ENGINE', color: 'violet-400',
                desc: 'Auto-schema detection and AI-powered ETL transforms raw logistics data into actionable financial models.'
              },
              { 
                step: '03', icon: Network, title: '⚙️ INTELLIGENCE LAYER', color: 'emerald',
                desc: 'Agentic SQL Mind generates complex reports, detects variances, and performs forensic audits in seconds.'
              },
              { 
                step: '04', icon: Zap, title: '📊 STRATEGIC COMMAND', color: 'gold',
                desc: 'Final tactical insights delivered via browser-based HUD, Mobile, or direct API writeback.'
              }
            ].map((item, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
                className="glass-premium p-8 relative z-10 flex flex-col gap-6 group hover:border-sky/40 transition-all border border-white/5"
              >
                <div className="text-4xl font-black text-white/5 absolute top-4 right-4">{item.step}</div>
                <div className={`w-12 h-12 rounded bg-white/5 flex items-center justify-center text-sky border border-white/10 group-hover:scale-110 transition-transform`}>
                  <item.icon className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-bold text-heading tracking-widest uppercase">{item.title}</h3>
                <p className="text-xs text-muted leading-relaxed font-medium">
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* "Unistream" Style Connector Explorer */}
      <section id="connectors" className="py-32 px-8 overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-16">
            <div className="max-w-xl">
              <h2 className="text-4xl font-black text-heading mb-4 uppercase tracking-tighter">Strategic Connectivity</h2>
              <p className="text-muted text-sm">
                Everyone is ready for AI, but not your data. NYX CORE links virtually any data source to your command center with military-grade security.
              </p>
            </div>
            
            <div className="flex-1 max-w-md relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input 
                type="text" 
                placeholder="Search 100+ connectors (e.g. 1C, SAP, Customs)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-full px-12 py-4 text-xs font-bold focus:outline-none focus:border-sky/50 transition-all"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mb-12">
            {['All', 'Enterprise/ERP', 'Logistics', 'Banking', 'Regulatory', 'Cloud/Data'].map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-6 py-2 rounded-full text-[9px] font-bold uppercase tracking-widest transition-all ${
                  activeCategory === cat ? 'bg-sky text-bg0' : 'bg-white/5 text-muted hover:bg-white/10'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 min-h-[400px]">
            <AnimatePresence mode="popLayout">
              {filteredConnectors.map((c, i) => (
                <motion.div
                  key={c.name}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.2 }}
                  className="glass-premium p-6 flex flex-col gap-4 group cursor-help border border-white/5"
                >
                  <div className="flex items-center justify-between">
                    <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center border border-white/10 font-black text-sky text-xs">
                      {c.name.substring(0, 2)}
                    </div>
                    <div className={`text-[7px] font-black uppercase px-2 py-0.5 rounded border ${
                      c.status === 'active' ? 'bg-emerald/10 border-emerald/30 text-emerald' : 
                      c.status === 'beta' ? 'bg-sky/10 border-sky/30 text-sky' : 'bg-white/5 border-white/10 text-muted'
                    }`}>
                      {c.status}
                    </div>
                  </div>
                  <div>
                    <h4 className="font-bold text-heading text-sm mb-1">{c.name}</h4>
                    <span className="text-[8px] text-sky/60 font-black uppercase tracking-widest">{c.category}</span>
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed flex-1">
                    {c.desc}
                  </p>
                  <div className="pt-4 mt-auto border-t border-white/5 flex items-center justify-between">
                     <span className="text-[8px] font-bold text-muted uppercase">Latency: Nominal</span>
                     <ExternalLink className="w-3 h-3 text-muted/30 group-hover:text-sky transition-colors" />
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </section>

      {/* Real-World Use Cases */}
      <section id="solutions" className="py-32 px-8 bg-bg1/20">
        <div className="max-w-7xl mx-auto">
          <div className="mb-20 text-center max-w-3xl mx-auto">
             <h2 className="text-4xl font-black text-heading mb-6 tracking-tight uppercase">Strategic Use Cases</h2>
             <p className="text-muted text-sm leading-relaxed">
               Discover how sovereign capital and industrial leaders leverage NYX CORE to transform data operations into tactical advantages.
             </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                title: 'Forensic Audit & Anti-Fraud',
                icon: Shield,
                desc: 'Real-time analysis of 1C and SAP ledgers to detect invoice anomalies, tax variances, and unauthorized reversals across regional territories.'
              },
              {
                title: 'Cross-Border Supply Chain AI',
                icon: Globe,
                desc: 'Global logistics tracking of fuel shipments, container vessels, and port inventory with predictive risk scoring for geopolitical volatility.'
              },
              {
                title: 'Executive Liquidity Pulse',
                icon: BarChart3,
                desc: 'Consolidated CFO-level visibility into group-wide cash positions, debt structure, and real-time revenue performance in Georgia and beyond.'
              }
            ].map((useCase, i) => (
              <motion.div 
                key={i}
                whileHover={{ y: -5 }}
                className="glass-premium p-10 flex flex-col gap-6 border border-white/5"
              >
                <div className="w-14 h-14 rounded-xl bg-sky/10 border border-sky/30 flex items-center justify-center text-sky">
                  <useCase.icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold text-heading">{useCase.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{useCase.desc}</p>
                <button className="mt-4 text-[10px] font-black uppercase tracking-widest text-sky flex items-center gap-2 hover:gap-3 transition-all">
                   Explore Strategy <ArrowRight className="w-4 h-4" />
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* "Unistream" Style Pricing Table */}
      <section id="pricing" className="py-32 px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24">
            <h2 className="text-4xl md:text-5xl font-black text-heading mb-6 tracking-tight uppercase">Institutional Plans</h2>
            <div className="h-1.5 w-24 bg-sky mx-auto mb-8" />
            <p className="text-muted text-sm">Transparent pricing for mission-critical strategic intelligence.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { 
                name: 'Tactical', price: '1,200', desc: 'For growing teams starting with basic 1C/audit needs.', 
                specs: ['8 vCPU, 32GB RAM', '2TB SSD Storage', '5 Pre-built Connectors', '1 Strategic AI Mind', 'Daily Backups'] 
              },
              { 
                name: 'Operational', price: '4,500', desc: 'Advanced analytics for industrial entities with SAP requirements.', 
                specs: ['16 vCPU, 64GB RAM', '10TB SSD Storage', '20+ Connectors', '10 Strategic AI Minds', 'Hourly Backups'],
                popular: true
              },
              { 
                name: 'Sovereign', price: '8,500', desc: 'Full-featured strategic command for institutional capital.', 
                specs: ['32 vCPU, 128GB RAM', '50TB SSD Storage', 'Unlimited Connectors', 'Tactical Map HUD', 'Real-time Sync'] 
              },
              { 
                name: 'Enterprise', price: 'Custom', desc: 'Hybrid and On-Premise deployments for maximum security.', 
                specs: ['Custom Compute Specs', 'On-Premise Deployment', 'Dedicated Support', 'White Label Theme', 'SSO / Jira Sync'] 
              }
            ].map((p, i) => (
              <div 
                key={i} 
                className={`glass-premium p-10 flex flex-col gap-8 relative border transition-all hover:scale-[1.02] ${
                  p.popular ? 'border-sky shadow-2xl shadow-sky/10' : 'border-white/5'
                }`}
              >
                {p.popular && <div className="absolute top-0 right-10 -translate-y-1/2 bg-sky text-bg0 px-4 py-1 text-[8px] font-black uppercase tracking-widest rounded-full">Recommended</div>}
                <div>
                   <h3 className="text-lg font-black text-heading uppercase tracking-widest mb-2">{p.name}</h3>
                   <div className="flex items-baseline gap-1">
                      {p.price !== 'Custom' && <span className="text-muted text-sm">$</span>}
                      <span className="text-4xl font-black text-heading">{p.price}</span>
                      {p.price !== 'Custom' && <span className="text-muted text-[10px] font-bold">/MONTH</span>}
                   </div>
                   <p className="mt-4 text-[10px] text-muted leading-relaxed font-medium">{p.desc}</p>
                </div>
                <div className="space-y-4">
                   {p.specs.map((s, j) => (
                     <div key={j} className="flex items-center gap-3 text-[10px] font-medium text-muted">
                        <CheckCircle2 className="w-3 h-3 text-sky shrink-0" /> {s}
                     </div>
                   ))}
                </div>
                <button 
                   onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
                   className={`w-full py-4 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
                  p.popular ? 'bg-sky text-bg0 hover:bg-white' : 'bg-white/5 border border-white/10 hover:bg-white/10'
                }`}
                >
                  {p.price === 'Custom' ? 'Contact Advisory' : 'Start Institutional Trial'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final "Unistream" Style Professional Inquiry Form */}
      <section id="enrollment" className="py-40 px-8 bg-bg0 relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[600px] bg-sky/5 blur-[120px] rounded-full pointer-events-none" />
        
        <div className="max-w-5xl mx-auto relative z-10">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            className="glass-premium p-16 border border-white/10"
          >
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-6xl font-black text-heading mb-6 tracking-tighter uppercase">Inquiry Advisory</h2>
              <p className="text-muted text-lg max-w-xl mx-auto">
                Have questions or want to learn more? Reach out to our strategic advisory team and we will get back to you as soon as possible.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
               {/* Left Side: Form */}
               {!requestSent ? (
                <form 
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setRequestSent(true);
                  }}
                  className="space-y-6"
                >
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                       <label className="text-[10px] font-black text-muted uppercase tracking-widest">Full Name</label>
                       <input 
                         type="text" required placeholder="John Doe"
                         className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium"
                         onChange={e => setForm({...form, fullName: e.target.value})}
                       />
                    </div>
                    <div className="space-y-2">
                       <label className="text-[10px] font-black text-muted uppercase tracking-widest">Email Address</label>
                       <input 
                         type="email" required placeholder="john@institution.com"
                         className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium"
                         onChange={e => setForm({...form, email: e.target.value})}
                       />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-muted uppercase tracking-widest">Company / Institution (Optional)</label>
                    <input 
                      type="text" placeholder="NYX Global Partners"
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium"
                      onChange={e => setForm({...form, company: e.target.value})}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-muted uppercase tracking-widest">Primary Interest</label>
                    <select 
                       className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium appearance-none"
                       onChange={e => setForm({...form, interest: e.target.value})}
                    >
                      <option value="Investor" className="bg-bg0 text-text">Strategic Investor</option>
                      <option value="Partner" className="bg-bg0 text-text">Industrial Partner</option>
                      <option value="User" className="bg-bg0 text-text">Early Access User</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black text-muted uppercase tracking-widest">Your Message</label>
                    <textarea 
                      required rows={4} placeholder="Tell us how we can help you..."
                      className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium resize-none"
                      onChange={e => setForm({...form, message: e.target.value})}
                    />
                  </div>
                  
                  <button 
                    type="submit"
                    className="w-full py-5 bg-sky text-bg0 rounded-xl text-xs font-black uppercase tracking-widest transition-all hover:bg-white shadow-xl shadow-sky/20"
                  >
                    Send Advisory Message
                  </button>
                </form>
               ) : (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="h-full flex flex-col items-center justify-center p-8 rounded-2xl bg-emerald/10 border border-emerald/30 text-center"
                >
                  <CheckCircle2 className="w-16 h-16 text-emerald mb-6 animate-bounce" />
                  <h3 className="text-2xl font-black text-heading mb-2">INQUIRY LOGGED</h3>
                  <p className="text-muted text-sm font-medium">System verification in progress. Our strategic advisory team will contact you at {form.email} within 24 hours.</p>
                </motion.div>
               )}

               {/* Right Side: Trust Info */}
               <div className="flex flex-col gap-8 justify-center border-l border-white/5 pl-12">
                  <div className="space-y-2">
                     <h4 className="text-sm font-bold text-heading flex items-center gap-2"><Lock className="w-4 h-4 text-sky" /> Zero Data Retention</h4>
                     <p className="text-[10px] text-muted leading-relaxed font-medium">NYX Core AI operates with ZDR protocols. Your sensitive information never leaves your sovereign control when using our AI capabilities.</p>
                  </div>
                  <div className="space-y-2">
                     <h4 className="text-sm font-bold text-heading flex items-center gap-2"><Globe className="w-4 h-4 text-sky" /> Multi-Region S3</h4>
                     <p className="text-[10px] text-muted leading-relaxed font-medium">Deploy anywhere — Sovereign Cloud or On-Premise. 99.9% SLA guaranteed for institutional operations.</p>
                  </div>
                  <div className="space-y-2">
                     <h4 className="text-sm font-bold text-heading flex items-center gap-2"><Users className="w-4 h-4 text-sky" /> Legacy 1C Support</h4>
                     <p className="text-[10px] text-muted leading-relaxed font-medium">Built-in specialized connectors for legacy 1C and SAP versions used in developing markets.</p>
                  </div>
               </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Enterprise Style Footer */}
      <footer className="py-24 border-t border-white/5 bg-bg0">
        <div className="max-w-7xl mx-auto px-8 grid grid-cols-1 md:grid-cols-4 gap-12">
           <div className="col-span-1 md:col-span-1">
              <div className="flex items-center gap-3 mb-6">
                <NyxLogo size={24} />
                <span className="font-bold text-lg tracking-tighter text-heading">NYX <span className="text-sky">CORE</span></span>
              </div>
              <p className="text-[10px] text-muted leading-relaxed uppercase tracking-widest font-bold">
                 Sovereign Intelligence. <br />
                 Cross-Border Connectivity. <br />
                 Mission Critical Strategy.
              </p>
           </div>
           
           <div>
              <h5 className="text-[10px] font-black text-heading uppercase tracking-widest mb-6">Resources</h5>
              <div className="flex flex-col gap-4 text-[10px] font-bold text-muted uppercase tracking-widest">
                 <a href="#" className="hover:text-sky transition-colors">Documentation</a>
                 <a href="#" className="hover:text-sky transition-colors">Security Whitepaper</a>
                 <a href="#" className="hover:text-sky transition-colors">API Reference</a>
                 <a href="#" className="hover:text-sky transition-colors">Vulnerability Disclosure</a>
              </div>
           </div>

           <div>
              <h5 className="text-[10px] font-black text-heading uppercase tracking-widest mb-6">Capabilities</h5>
              <div className="flex flex-col gap-4 text-[10px] font-bold text-muted uppercase tracking-widest">
                 <a href="#" className="hover:text-sky transition-colors">Forensic Audit</a>
                 <a href="#" className="hover:text-sky transition-colors">Tactical HUD</a>
                 <a href="#" className="hover:text-sky transition-colors">AI Orchestration</a>
                 <a href="#" className="hover:text-sky transition-colors">Logistics Real-time</a>
              </div>
           </div>

           <div>
              <h5 className="text-[10px] font-black text-heading uppercase tracking-widest mb-6">Compliance</h5>
              <div className="flex flex-col gap-4 text-[10px] font-bold text-muted uppercase tracking-widest">
                 <a href="#" className="hover:text-sky transition-colors">GDPR / ZDR Policy</a>
                 <a href="#" className="hover:text-sky transition-colors">Terms of Service</a>
                 <a href="#" className="hover:text-sky transition-colors">Privacy Framework</a>
                 <a href="#" className="hover:text-sky transition-colors">Ethics & Sovereignty</a>
              </div>
           </div>
        </div>
        <div className="mt-24 pt-12 border-t border-white/5 text-center text-[10px] text-muted tracking-[0.4em] uppercase font-black">
          © 2026 NYX CORE STRATEGIC INTELLIGENCE — SECURE SOVEREIGN SPACE
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
