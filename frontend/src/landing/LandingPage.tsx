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
  Briefcase,
  PlayCircle,
  HelpCircle,
  Terminal,
  Clock,
  Fingerprint
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
  { name: '1C:Enterprise', category: 'Financial', desc: 'Deep extraction from Georgian and CIS ERP instances.', status: 'active' },
  { name: 'SAP S/4HANA', category: 'E-commerce & Financial', desc: 'Direct OData and RFC connectivity for global finance.', status: 'active' },
  { name: 'NBG Exchange Rate', category: 'Communication & Collaboration', desc: 'Real-time exchange rate and regulatory feed sync.', status: 'active' },
  { name: 'Amazon S3', category: 'Cloud', desc: 'Efficiently extracts and loads data in your centralized data warehouse.', status: 'active' },
  { name: 'Azure SQL Database', category: 'Data Storage', desc: 'Ensures reliable integration with Microsoft cloud SQL service.', status: 'active' },
  { name: 'Google BigQuery', category: 'Data Storage', desc: 'Enterprise-grade integration with Googles serverless warehouse.', status: 'active' },
  { name: 'PostgreSQL', category: 'Data Storage', desc: 'High-performance data integration for your PostgreSQL databases.', status: 'active' },
  { name: 'Snowflake', category: 'Data Storage', desc: 'Reliable and efficient data integration for Snowflake warehouses.', status: 'beta' },
  { name: 'Oracle ERP Cloud', category: 'E-commerce & Financial', desc: 'Seamless data extraction from cloud-based enterprise systems.', status: 'active' },
  { name: 'Amazon Redshift', category: 'Data Storage', desc: 'Leverages Redshifts parallel processing for incremental extraction.', status: 'active' },
  { name: 'BigCommerce', category: 'E-commerce & Financial', desc: 'Extracts order data, product performance, and customer insights.', status: 'active' },
  { name: 'Salesforce', category: 'Marketing & CRM', desc: 'Intuitive schema structure for Salesforce CRM objects.', status: 'active' },
  { name: 'HubSpot', category: 'Marketing & CRM', desc: 'Extracts, replicates and loads marketing automation data.', status: 'active' },
  { name: 'Jira', category: 'Communication & Collaboration', desc: 'Extracts comprehensive project and issue tracking data.', status: 'active' },
  { name: 'Slack', category: 'Communication & Collaboration', desc: 'Extracts message history and collaborator activity analytics.', status: 'active' },
  { name: 'Microsoft Teams', category: 'Communication & Collaboration', desc: 'Seamless integration with unified communication platforms.', status: 'active' },
  { name: 'Shopify', category: 'E-commerce & Financial', desc: 'Extracts sales, inventory, and customer behavior data.', status: 'beta' },
  { name: 'Stripe', category: 'E-commerce & Financial', desc: 'Full payment terminal tracking and ledger reconciliation.', status: 'active' },
  { name: 'Google Ads', category: 'Marketing & CRM', desc: 'Extracts campaign metrics and performance data.', status: 'active' },
  { name: 'Facebook Ads', category: 'Marketing & CRM', desc: 'Comprehensive social media marketing data extraction.', status: 'active' },
  { name: 'Infor', category: 'E-commerce & Financial', desc: 'Full ERP data extraction for industrial manufacturing.', status: 'beta' },
  { name: 'Customs Terminal', category: 'Logistics', desc: 'Direct telemetry from major Black Sea port terminals.', status: 'beta' },
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
    (activeCategory === 'All' || c.category === activeCategory) &&
    (c.name.toLowerCase().includes(search.toLowerCase()) || c.desc.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="landing-hero-bg min-h-screen text-text selection:bg-sky/30 font-sans leading-relaxed">
      
      {/* Institutional Top Bar */}
      <div className="bg-bg0 border-b border-white/5 py-2 px-8 flex justify-between items-center text-[8px] font-bold tracking-[0.3em] uppercase text-muted/60">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5"><div className="w-1 h-1 rounded-full bg-emerald" /> NYX SYSTEM: NOMINAL</span>
          <span className="flex items-center gap-1.5"><div className="w-1 h-1 rounded-full bg-sky" /> NODES: 2,492 ACTIVE</span>
        </div>
        <div className="flex items-center gap-6">
          <span>LATENCY: 14ms</span>
          <span>SOVEREIGN CLOUD: TBILISI_WEST_1</span>
        </div>
      </div>

      {/* Premium Sticky Nav */}
      <nav className="sticky top-0 z-50 landing-nav flex items-center justify-between px-8 py-4 bg-bg0/80 backdrop-blur-xl border-b border-white/5">
        <div className="flex items-center gap-3">
          <NyxLogo size={28} />
          <span className="font-bold text-xl tracking-tighter text-heading">NYX <span className="text-sky">CORE</span></span>
        </div>
        <div className="hidden lg:flex items-center gap-8 text-[9px] font-bold tracking-[0.2em] uppercase text-muted">
          <a href="#about" className="hover:text-sky transition-colors">What is NYX?</a>
          <a href="#architecture" className="hover:text-sky transition-colors">Architecture</a>
          <a href="#connectors" className="hover:text-sky transition-colors">Connections</a>
          <a href="#pricing" className="hover:text-sky transition-colors">Pricing</a>
          <button 
            onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
            className="ml-4 px-6 py-2.5 rounded-full bg-sky text-bg0 hover:bg-white transition-all cursor-pointer text-[9px] font-black tracking-widest uppercase shadow-lg shadow-sky/20"
          >
            Get Started Free
          </button>
        </div>
      </nav>

      {/* Hero Section: The "Unistream" Promise */}
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
            <Zap className="w-3 h-3" /> Everyone is ready for AI, but not your data
          </div>
          <h1 className="text-6xl md:text-8xl font-black text-heading mb-8 tracking-tighter leading-[0.85]">
            Enterprise Power. <br /> 
            <span className="text-glow-cyan">Sovereign Intel.</span>
          </h1>
          <p className="text-muted/80 text-lg md:text-xl max-w-3xl mx-auto mb-12 leading-relaxed font-medium">
             The enterprise-grade data platform that simplifies complex data processing while offering 
             powerful AI capabilities. Deploy anywhere — Cloud or On-Premise.
          </p>
          <div className="flex flex-wrap justify-center gap-6 mb-20">
            <button 
              onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
              className="px-12 py-5 bg-sky text-bg0 font-black rounded-full flex items-center gap-3 hover:scale-105 transition-all group cursor-pointer shadow-xl shadow-sky/30 text-[11px] uppercase"
            >
              Get Started Free <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </button>
            <button 
               onClick={() => document.getElementById('about')?.scrollIntoView({ behavior: 'smooth' })}
               className="px-12 py-5 bg-white/5 border border-white/10 hover:bg-white/10 rounded-full font-bold transition-all flex items-center gap-2 cursor-pointer text-[11px] uppercase text-muted"
            >
               Learn More <ChevronRight className="w-4 h-4 opacity-50" />
            </button>
          </div>

          <div className="relative w-full max-w-6xl mx-auto rounded-2xl border border-white/10 shadow-2xl shadow-sky/10 overflow-hidden transform perspective-1000 rotate-x-2">
            <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-bg0 to-transparent z-10" />
            <img 
              src="/assets/nyx_executive_command_center_1775748584914.png" 
              alt="NYX Strategic HUD" 
              className="w-full h-auto brightness-90 contrast-125"
            />
          </div>
        </motion.div>
      </motion.section>

      {/* "What is Unistream" Style Section */}
      <section id="about" className="py-32 px-8">
         <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-20 items-center">
            <div>
               <h2 className="text-4xl md:text-5xl font-black text-heading mb-8 tracking-tight uppercase leading-[1.1]">
                 What is NYX CORE?
               </h2>
               <p className="text-muted text-lg mb-8 leading-relaxed font-medium">
                  NYX CORE: One platform replaces dozens of tools, collecting, organizing, and extracting insights 
                  from your business data without specialists.
               </p>
               <p className="text-muted/60 text-base mb-12 leading-relaxed italic">
                  Let AI handle the enormous, boring and routine work while you focus solely on analysis and decision-making. 
                  NYX CORE is setting new standards for what a data platform should be.
               </p>
               <div className="space-y-6">
                  {[
                    "Enterprise-grade power with startup simplicity",
                    "Deploy anywhere — Cloud or On-Premise",
                    "Military-grade security with Zero Data Retention"
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-4 text-heading font-bold uppercase text-[10px] tracking-widest">
                       <CheckCircle2 className="w-5 h-5 text-sky" /> {item}
                    </div>
                  ))}
               </div>
            </div>
            <div className="glass-premium p-1 border border-white/10 rounded-2xl overflow-hidden aspect-video relative group">
               <div className="absolute inset-0 bg-sky/10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-20">
                  <PlayCircle className="w-20 h-20 text-sky fill-sky/20" />
               </div>
               <img 
                 src="/assets/nyx_executive_command_center_1775748584914.png" 
                 alt="System Demo" 
                 className="w-full h-full object-cover grayscale opacity-50"
               />
               <div className="absolute bottom-8 left-8 right-8 text-center z-10">
                  <span className="text-[10px] font-black uppercase tracking-[0.5em] text-white">NYX CORE in Action</span>
               </div>
            </div>
         </div>
      </section>

      {/* Architecture Flow */}
      <section id="architecture" className="py-32 px-8 bg-bg1/20 border-y border-white/5">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24 max-w-3xl mx-auto">
            <h2 className="text-4xl font-black text-heading mb-6 tracking-tight uppercase">Platform Architecture</h2>
            <p className="text-muted text-sm uppercase tracking-widest font-black opacity-60 mb-8">One space from ingestion to analytics</p>
            <p className="text-muted text-base">
              A complete data platform — from data ingestion to final analytics, in one space.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { 
                step: '01', icon: Database, title: '📥 Data Sources',
                desc: 'PostgreSQL, SAP, 1C, Excel, and 600+ more connectors.'
              },
              { 
                step: '02', icon: Layers, title: '🔄 Lake Space',
                desc: 'Centralize data in seconds with Auto Schema Detection and ERD Relations.'
              },
              { 
                step: '03', icon: Cpu, title: '⚙️ Warehouse',
                desc: 'Modeling & transformation with AI-Powered ETL and Auto-Generated Lineage.'
              },
              { 
                step: '04', icon: Zap, title: '📊 Consume & Act',
                desc: 'Agentic AI Data Minds and Browser-Based Query Editors for final analytics.'
              }
            ].map((item, i) => (
              <motion.div 
                key={i}
                className="glass-premium p-8 relative z-10 flex flex-col gap-6 group border border-white/5"
              >
                <div className="w-12 h-12 rounded bg-sky/10 flex items-center justify-center text-sky border border-sky/30">
                  <item.icon className="w-6 h-6" />
                </div>
                <h3 className="text-[11px] font-black text-heading tracking-widest uppercase">{item.title}</h3>
                <p className="text-[11px] text-muted leading-relaxed font-medium">
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>

          <div className="mt-20 grid grid-cols-2 md:grid-cols-5 gap-8 border-t border-white/5 pt-20">
             {[
               { icon: Lock, label: 'Access Control' },
               { icon: FileText, label: 'Data Catalog' },
               { icon: Server, label: 'On-Premise' },
               { icon: Fingerprint, label: 'ZDR Security' },
               { icon: Activity, label: '99.9% SLA' }
             ].map((item, i) => (
               <div key={i} className="flex flex-col items-center gap-3 grayscale opacity-40 hover:grayscale-0 hover:opacity-100 transition-all cursor-default">
                  <div className="w-8 h-8 flex items-center justify-center text-sky">
                    <item.icon className="w-5 h-5" />
                  </div>
                  <span className="text-[9px] font-black uppercase tracking-widest whitespace-nowrap">{item.label}</span>
               </div>
             ))}
          </div>
        </div>
      </section>

      {/* "Unistream" Style Connector Explorer */}
      <section id="connectors" className="py-32 px-8 overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-12">
            <div className="max-w-xl">
              <h2 className="text-4xl font-black text-heading mb-4 uppercase tracking-tighter leading-none">Connect to Everything</h2>
              <p className="text-muted text-sm font-medium">
                 Discover all the data sources you can connect with NYX CORE. Our connectors enable 
                 seamless integration with your specialized industrial ecosystem.
              </p>
            </div>
            
            <div className="flex-1 max-w-md relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input 
                type="text" 
                placeholder="Search connectors (e.g. 1C, SAP, S3)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-full px-12 py-4 text-[10px] font-bold focus:outline-none focus:border-sky/50 transition-all text-heading"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mb-12 border-b border-white/5 pb-8">
            {['All', 'Communication & Collaboration', 'Analytics & BI', 'Data Storage', 'Cloud', 'E-commerce & Financial', 'Marketing & CRM'].map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-5 py-2 rounded-full text-[9px] font-black uppercase tracking-widest transition-all ${
                  activeCategory === cat ? 'bg-sky text-bg0 shadow-lg shadow-sky/20' : 'bg-white/5 text-muted hover:bg-white/10'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 min-h-[400px]">
            <AnimatePresence mode="popLayout">
              {filteredConnectors.slice(0, 12).map((c, i) => (
                <motion.div
                  key={c.name}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="glass-premium p-6 flex flex-col gap-4 group cursor-pointer border border-white/5 hover:border-sky/30 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="w-12 h-12 rounded bg-white/5 flex items-center justify-center border border-white/10 font-black text-sky text-xs uppercase overflow-hidden p-2">
                       {/* Simplified icon fallback */}
                       <div className="w-full h-full rounded bg-sky/5 flex items-center justify-center text-[10px]">
                        {c.name.substring(0, 2)}
                       </div>
                    </div>
                    <div className="text-[7px] font-black uppercase px-2 py-0.5 rounded bg-sky/10 text-sky border border-sky/30">
                      {c.status}
                    </div>
                  </div>
                  <div>
                    <h4 className="font-bold text-heading text-sm mb-1">{c.name}</h4>
                    <span className="text-[8px] text-sky/60 font-black uppercase tracking-widest">{c.category}</span>
                  </div>
                  <p className="text-[10px] text-muted leading-relaxed font-medium">
                    {c.desc}
                  </p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
          
          <div className="mt-16 text-center">
             <button className="px-10 py-4 bg-white/5 border border-white/10 text-[10px] uppercase font-black tracking-widest text-muted hover:bg-sky hover:text-bg0 transition-all rounded-full">
                Explore All 600+ Connections
             </button>
          </div>
        </div>
      </section>

      {/* Detailed Use Case Spotlight */}
      <section className="py-32 px-8 bg-bg0">
         <div className="max-w-6xl mx-auto flex flex-col gap-24">
            <div className="flex flex-col lg:flex-row gap-20 items-center">
               <div className="flex-1 order-2 lg:order-1">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-md bg-emerald/10 border border-emerald/50 text-emerald text-[9px] uppercase tracking-widest font-black mb-6">
                     CASE 01
                  </div>
                  <h3 className="text-4xl font-black text-heading mb-6 leading-tight uppercase">Unified Data Space for Growing Companies</h3>
                  <p className="text-muted text-base mb-8 leading-relaxed font-medium">
                    Your business is growing rapidly, but data is scattered across different systems - Excel, CRM, ERP, online sales platforms. 
                    Decisions are made with fragmented information.
                  </p>
                  <ul className="space-y-4">
                     <li className="flex gap-4 items-start">
                        <div className="w-5 h-5 rounded-full bg-sky/20 flex items-center justify-center text-sky shrink-0 mt-1"><CheckCircle2 className="w-3 h-3" /></div>
                        <span className="text-sm text-muted/80">Collects all data in one system, automatically synchronizes and stores it</span>
                     </li>
                     <li className="flex gap-4 items-start">
                        <div className="w-5 h-5 rounded-full bg-sky/20 flex items-center justify-center text-sky shrink-0 mt-1"><CheckCircle2 className="w-3 h-3" /></div>
                        <span className="text-sm text-muted/80">See your business status from different angles with one click</span>
                     </li>
                  </ul>
                  <button className="mt-10 px-8 py-3 bg-sky text-bg0 font-black text-[10px] uppercase tracking-widest rounded-lg hover:bg-white transition-all">
                     Learn More
                  </button>
               </div>
               <div className="flex-1 order-1 lg:order-2">
                   <div className="relative group">
                      <div className="absolute -inset-4 bg-sky/5 rounded-3xl blur-2xl group-hover:bg-sky/10 transition-all" />
                      <div className="glass-premium p-1 border border-white/5 rounded-2xl relative overflow-hidden">
                        <img 
                          src="/assets/nyx_executive_command_center_1775748584914.png" 
                          alt="Unified Hub Visual" 
                          className="w-full h-auto rounded-xl opacity-80"
                        />
                      </div>
                   </div>
               </div>
            </div>
         </div>
      </section>

      {/* "Zero Data Retention" Spotlight */}
      <section className="py-24 px-8 border-y border-white/5 bg-sky/[0.02]">
         <div className="max-w-4xl mx-auto text-center">
            <Lock className="w-12 h-12 text-sky mx-auto mb-8 animate-pulse" />
            <h2 className="text-3xl md:text-4xl font-black text-heading mb-6 tracking-tighter uppercase">Zero Data Retention (ZDR)</h2>
            <p className="text-muted text-lg leading-relaxed mb-8 font-medium">
               ZDR means not storing any data intentionally after it has served its immediate purpose. 
               NYX CORE's AI operates with ZDR, meaning your data is never stored on external servers. 
            </p>
            <div className="p-8 glass-premium border border-white/10 rounded-2xl bg-bg0/40 inline-flex flex-col gap-4 text-left max-w-2xl">
               <div className="flex items-center gap-3 text-emerald text-[11px] font-black uppercase tracking-widest">
                  <Shield className="w-4 h-4" /> Military Grade Security
               </div>
               <p className="text-[11px] text-muted leading-relaxed font-bold">
                  Data is deleted immediately after serving its purpose, ensuring complete privacy and security. 
                  This means your sensitive information never leaves your control when using NYX CORE's AI capabilities.
               </p>
            </div>
         </div>
      </section>

      {/* Pricing Table (Unistream Specs) */}
      <section id="pricing" className="py-32 px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-24 max-w-3xl mx-auto">
            <h2 className="text-4xl md:text-5xl font-black text-heading mb-4 tracking-tight uppercase leading-none">Choose Your NYX Plan</h2>
            <p className="text-muted text-base uppercase tracking-widest font-black opacity-60 mb-8">A unified data platform for every scale</p>
            <p className="text-muted text-sm font-medium">Transparent pricing for mission-critical strategic intelligence.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { 
                name: 'Essentials', price: '899', desc: 'Perfect for small teams getting started.', 
                specs: ['8 vCPU, 32GB RAM', '1TB Premium SSD', '128K IOPS', '50 Pre-built Connectors', '1 AI Mind', 'Daily Backups'] 
              },
              { 
                name: 'Plus', price: '3,999', desc: 'Advanced data needs and warehouse capabilities.', 
                specs: ['16 vCPU, 64GB RAM', '3TB Premium SSD', '256K IOPS', '60 Pre-built Connectors', '10 AI Minds', 'Data Lake & Warehouse'],
                popular: true
              },
              { 
                name: 'Premium', price: '5,499', desc: 'Full-featured solution for data-driven orgs.', 
                specs: ['32 vCPU, 128GB RAM', '15TB Premium SSD', '512K IOPS', '100+ Pre-built Connectors', 'Unlimited AI Minds', 'Data Writeback'] 
              },
              { 
                name: 'Enterprise', price: 'Custom', desc: 'Specific needs and on-premise deployments.', 
                specs: ['Custom Infrastructure', 'On-Premise Option', 'SSO Integration', 'Dedicated Success Manager', '24/7 Premium Support', 'Custom LLM Integration'] 
              }
            ].map((p, i) => (
              <div 
                key={i} 
                className={`glass-premium p-10 flex flex-col gap-8 relative border transition-all hover:border-sky/50 ${
                  p.popular ? 'border-sky shadow-2xl shadow-sky/10' : 'border-white/5'
                }`}
              >
                {p.popular && <div className="absolute top-0 right-10 -translate-y-1/2 bg-sky text-bg0 px-4 py-1 text-[8px] font-black uppercase tracking-widest rounded-full shadow-lg">Popular Choice</div>}
                <div>
                   <h3 className="text-lg font-black text-heading uppercase tracking-widest mb-4">{p.name}</h3>
                   <div className="flex items-baseline gap-1">
                      {p.price !== 'Custom' && <span className="text-muted text-sm font-bold">$</span>}
                      <span className="text-4xl font-black text-heading">{p.price}</span>
                      {p.price !== 'Custom' && <span className="text-muted text-[10px] font-black">/MONTH</span>}
                   </div>
                   <p className="mt-6 text-[10px] text-muted leading-relaxed font-bold uppercase tracking-widest">{p.desc}</p>
                </div>
                <div className="space-y-4 pt-4 border-t border-white/5">
                   {p.specs.map((s, j) => (
                     <div key={j} className="flex items-start gap-3 text-[9px] font-black uppercase tracking-wider text-muted">
                        <CheckCircle2 className="w-3.5 h-3.5 text-sky shrink-0" /> {s}
                     </div>
                   ))}
                </div>
                <button 
                   onClick={() => document.getElementById('enrollment')?.scrollIntoView({ behavior: 'smooth' })}
                   className={`w-full py-4 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${
                  p.popular ? 'bg-sky text-bg0 hover:bg-white' : 'border border-white/10 hover:bg-white/5'
                }`}
                >
                  {p.price === 'Custom' ? 'Contact Advisory' : 'Start Trial'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ: Unistream Questions */}
      <section className="py-24 px-8 bg-bg1/10">
         <div className="max-w-4xl mx-auto">
            <h2 className="text-center text-3xl font-black text-heading mb-16 uppercase tracking-tight">Frequently Asked Questions</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
               {[
                 { q: "What kind of support is included?", a: "Standard access includes email support. Premium tiers receive priority and 24/7 designated support." },
                 { q: "Can I upgrade my plan anytime?", a: "Absolutely. You can scale your infrastructure (vCPU/RAM) or upgrade your plan instantly via the dashboard." },
                 { q: "How does the free trial work?", a: "Start with full access to either Essentials or Plus for up to 60 days to verify your data flows." },
                 { q: "Can we deploy on-premise?", a: "Enterprise clients can opt for a full binary deployment on local servers within their own firewalls." }
               ].map((item, i) => (
                 <div key={i} className="glass-premium p-8 border border-white/5">
                    <h4 className="text-[11px] font-black text-heading uppercase tracking-widest mb-4 flex items-center gap-2"><HelpCircle className="w-4 h-4 text-sky" /> {item.q}</h4>
                    <p className="text-[11px] text-muted leading-relaxed font-medium">{item.a}</p>
                 </div>
               ))}
            </div>
         </div>
      </section>

      {/* Inquiry Form */}
      <section id="enrollment" className="py-40 px-8 bg-bg0 relative overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[600px] bg-sky/5 blur-[120px] rounded-full pointer-events-none" />
        
        <div className="max-w-5xl mx-auto relative z-10">
          <div className="glass-premium p-12 md:p-20 border border-white/10 shadow-3xl">
            <div className="text-center mb-16">
              <h2 className="text-4xl md:text-5xl font-black text-heading mb-6 tracking-tighter uppercase leading-none">Contact NYX Advisory</h2>
              <p className="text-muted text-lg max-w-xl mx-auto font-medium">
                Have questions or want to learn more? Reach out to us and we will get back to you as soon as possible.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-16">
               <div className="lg:col-span-3">
                  {!requestSent ? (
                    <form 
                      onSubmit={async (e) => {
                        e.preventDefault();
                        setRequestSent(true);
                      }}
                      className="space-y-6"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                           <label className="text-[9px] font-black text-muted uppercase tracking-[0.2em]">Full Name</label>
                           <input 
                             type="text" required placeholder="Your full name"
                             className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium text-heading"
                             onChange={e => setForm({...form, fullName: e.target.value})}
                           />
                        </div>
                        <div className="space-y-2">
                           <label className="text-[9px] font-black text-muted uppercase tracking-[0.2em]">Email Address</label>
                           <input 
                             type="email" required placeholder="your@email.com"
                             className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium text-heading"
                             onChange={e => setForm({...form, email: e.target.value})}
                           />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <label className="text-[9px] font-black text-muted uppercase tracking-[0.2em]">Company / Institution (Optional)</label>
                        <input 
                          type="text" placeholder="Your company name"
                          className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium text-heading"
                          onChange={e => setForm({...form, company: e.target.value})}
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-[9px] font-black text-muted uppercase tracking-[0.2em]">How can we help you?</label>
                        <textarea 
                          required rows={4} placeholder="Tell us about your data needs..."
                          className="w-full bg-white/5 border border-white/10 rounded-lg px-6 py-4 text-sm focus:outline-none focus:border-sky/50 transition-all font-medium resize-none text-heading"
                          onChange={e => setForm({...form, message: e.target.value})}
                        />
                      </div>
                      
                      <button 
                        type="submit"
                        className="w-full py-5 bg-sky text-bg0 rounded-xl text-xs font-black uppercase tracking-widest transition-all hover:bg-white shadow-xl shadow-sky/20"
                      >
                        Send Message
                      </button>
                    </form>
                  ) : (
                    <motion.div 
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="h-full flex flex-col items-center justify-center p-12 rounded-2xl bg-emerald/10 border border-emerald/30 text-center"
                    >
                      <CheckCircle2 className="w-20 h-20 text-emerald mb-6 animate-bounce" />
                      <h3 className="text-2xl font-black text-heading mb-4 uppercase tracking-tighter">Inquiry Received</h3>
                      <p className="text-muted text-sm font-medium">Our strategic advisory team will contact you at {form.email} within 24 hours.</p>
                    </motion.div>
                  )}
               </div>

               <div className="lg:col-span-2 flex flex-col gap-10 justify-center">
                  <div className="flex gap-6 items-start">
                     <div className="w-12 h-12 rounded bg-sky/10 flex items-center justify-center text-sky shrink-0"><Shield className="w-6 h-6" /></div>
                     <div>
                        <h4 className="text-sm font-black text-heading uppercase mb-1">Zero Data Retention</h4>
                        <p className="text-[10px] text-muted font-medium leading-relaxed">Your sensitive information never leaves your control when using NYX Core AI.</p>
                     </div>
                  </div>
                  <div className="flex gap-6 items-start">
                     <div className="w-12 h-12 rounded bg-sky/10 flex items-center justify-center text-sky shrink-0"><Globe className="w-6 h-6" /></div>
                     <div>
                        <h4 className="text-sm font-black text-heading uppercase mb-1">99.9% Uptime SLA</h4>
                        <p className="text-[10px] text-muted font-medium leading-relaxed">Guaranteed reliability for mission-critical institutional operations.</p>
                     </div>
                  </div>
                  <div className="flex gap-6 items-start">
                     <div className="w-12 h-12 rounded bg-sky/10 flex items-center justify-center text-sky shrink-0"><Terminal className="w-6 h-6" /></div>
                     <div>
                        <h4 className="text-sm font-black text-heading uppercase mb-1">Industrial Pedigree</h4>
                        <p className="text-[10px] text-muted font-medium leading-relaxed">Built specialized connectors for SAP, 1C, and Oracle ERP systems.</p>
                     </div>
                  </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-24 border-t border-white/5 bg-bg0">
        <div className="max-w-7xl mx-auto px-8 flex flex-col md:flex-row justify-between items-start gap-12">
           <div className="max-w-sm">
              <div className="flex items-center gap-3 mb-6">
                <NyxLogo size={24} />
                <span className="font-bold text-lg tracking-tighter text-heading">NYX <span className="text-sky">CORE</span></span>
              </div>
              <p className="text-[10px] text-muted leading-relaxed uppercase tracking-widest font-black opacity-60">
                 The enterprise-grade data platform that simplifies complex data processing while offering powerful AI capabilities.
              </p>
           </div>
           
           <div className="grid grid-cols-2 md:grid-cols-3 gap-16">
              <div>
                 <h5 className="text-[10px] font-black text-heading uppercase tracking-widest mb-6 border-b border-sky/20 pb-2">Resources</h5>
                 <div className="flex flex-col gap-4 text-[9px] font-black text-muted uppercase tracking-widest">
                    <a href="#" className="hover:text-sky transition-colors">Pricing</a>
                    <a href="#" className="hover:text-sky transition-colors">Use Cases</a>
                    <a href="#" className="hover:text-sky transition-colors">Docs</a>
                    <a href="#" className="hover:text-sky transition-colors">Blog</a>
                 </div>
              </div>

              <div>
                 <h5 className="text-[10px] font-black text-heading uppercase tracking-widest mb-6 border-b border-sky/20 pb-2">Company</h5>
                 <div className="flex flex-col gap-4 text-[9px] font-black text-muted uppercase tracking-widest">
                    <a href="#" className="hover:text-sky transition-colors">About Us</a>
                    <a href="#" className="hover:text-sky transition-colors">Contact</a>
                    <a href="#" className="hover:text-sky transition-colors">Terms</a>
                    <a href="#" className="hover:text-sky transition-colors">Privacy</a>
                 </div>
              </div>
           </div>
        </div>
        <div className="mt-24 pt-12 border-t border-white/5 text-center text-[9px] text-muted tracking-[0.4em] uppercase font-black">
          © 2026 NYX CORE STRATEGIC INTELLIGENCE — DATA SOVEREIGNTY ENSURED
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
