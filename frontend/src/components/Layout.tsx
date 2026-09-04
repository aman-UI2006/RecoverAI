import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ShieldAlert,
  ListFilter,
  FileText,
  Cpu,
  BarChart3,
  Lock,
  Sliders,
  UserCheck,
  Menu,
  X,
  Building2,
  User,
  Search,
  Bell,
  AlertTriangle,
  CheckCircle2,
  Key,
  Code2,
  Database,
  Activity,
  Shield,
} from 'lucide-react';
import { checkBackendHealth, currentApiState } from '../services/api';
import logoSvg from '../assets/logo.svg';
import { AnimatedBackground } from './AnimatedBackground';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [backendStatus, setBackendStatus] = useState<'online' | 'offline' | 'checking'>('checking');
  const [currentMode, setCurrentMode] = useState<'SIMULATION' | 'REAL_TEST'>(currentApiState.mode);
  const [currentMerchant, setCurrentMerchant] = useState<string>(currentApiState.merchantId);

  useEffect(() => {
    let isMounted = true;
    const verifyHealth = async () => {
      const health = await checkBackendHealth();
      if (isMounted) {
        setBackendStatus(health.status === 'ok' ? 'online' : 'offline');
      }
    };
    verifyHealth();
    const interval = setInterval(verifyHealth, 15000);

    const handleStateChange = () => {
      setCurrentMode(currentApiState.mode);
      setCurrentMerchant(currentApiState.merchantId);
    };
    window.addEventListener('apiStateChanged', handleStateChange);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener('apiStateChanged', handleStateChange);
    };
  }, []);

  const handleModeToggle = () => {
    const nextMode = currentMode === 'SIMULATION' ? 'REAL_TEST' : 'SIMULATION';
    currentApiState.mode = nextMode;
    setCurrentMode(nextMode);

    if (nextMode === 'REAL_TEST' && currentMerchant !== 'm_real_2f9b3a') {
      currentApiState.merchantId = 'm_real_2f9b3a';
      setCurrentMerchant('m_real_2f9b3a');
    } else if (nextMode === 'SIMULATION' && currentMerchant === 'm_real_2f9b3a') {
      currentApiState.merchantId = '';
      setCurrentMerchant('');
    }

    window.dispatchEvent(new CustomEvent('apiStateChanged'));
  };

  const handleMerchantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextMerchant = e.target.value;
    currentApiState.merchantId = nextMerchant;
    setCurrentMerchant(nextMerchant);
    window.dispatchEvent(new CustomEvent('apiStateChanged'));
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/ai-decision?tx=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  // Helper function to check if a route or sub-route is active
  const isPathActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const navSections = [
    {
      category: 'OVERVIEW',
      items: [
        { label: 'Command Center', path: '/', icon: LayoutDashboard },
      ],
    },
    {
      category: 'RECOVERY OPERATIONS',
      items: [
        { label: 'Revenue Risk', path: '/revenue-risk', icon: ShieldAlert },
        { label: 'Recovery Queue', path: '/recovery-queue', icon: ListFilter },
        { label: 'Transaction Detail', path: '/transactions', icon: FileText },
      ],
    },
    {
      category: 'INTELLIGENCE',
      items: [
        { label: 'AI Decision Center', path: '/ai-decision', icon: Cpu },
      ],
    },
    {
      category: 'GOVERNANCE & AUDIT',
      items: [
        { label: 'Policy Manager', path: '/policies', icon: Sliders },
        { label: 'Human Review', path: '/human-review', icon: UserCheck },
        { label: 'Audit Center', path: '/audit', icon: Lock },
      ],
    },
    {
      category: 'ANALYTICS',
      items: [
        { label: 'Recovery Analytics', path: '/analytics', icon: BarChart3 },
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0B1F44] flex flex-col antialiased font-sans relative">
      <AnimatedBackground />
      
      {/* ========================================================= */}
      {/* 1. TOP GLOBAL HEADER BAR — RAZORPAY STYLED HEADER (60px)   */}
      {/* ========================================================= */}
      <header className="bg-black text-white sticky top-0 z-50 h-[60px] shadow-lg border-b border-slate-900">
        <div className="max-w-[1800px] mx-auto px-4 sm:px-6 h-full flex items-center justify-between gap-4 relative">
          
          {/* LEFT: RecoverAI Branding */}
          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg bg-slate-900 text-slate-300 hover:text-white border border-slate-800"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-8 h-8 rounded-lg bg-black border border-slate-800 flex items-center justify-center p-1.5 shadow-sm group-hover:border-blue-500 transition-all">
                <img src={logoSvg} alt="RecoverAI Logo" className="w-full h-full object-contain" />
              </div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg text-white tracking-tight leading-none">
                  RecoverAI
                </span>
                <span className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-blue-950/90 text-blue-400 border border-blue-500/40 tracking-wider">
                  ENTERPRISE
                </span>
              </div>
            </Link>
          </div>

          {/* CENTER: Navigation Links with Glowing Active Spotlight */}
          <nav className="hidden xl:flex items-center gap-2">
            {[
              { label: 'Overview', path: '/', icon: Activity },
              { label: 'Operations', path: '/recovery-queue', icon: Shield },
              { label: 'Intelligence', path: '/ai-decision', icon: Code2 },
              { label: 'Governance', path: '/policies', icon: Database },
              { label: 'Analytics', path: '/analytics', icon: BarChart3 },
            ].map((nav) => {
              const active = isPathActive(nav.path);
              const Icon = nav.icon;
              return (
                <Link
                  key={nav.label}
                  to={nav.path}
                  className={`relative px-3.5 py-2 flex items-center gap-2 text-xs font-bold transition-all ${
                    active ? 'text-white' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  {/* Glowing Spotlight Backdrop for Active Link */}
                  {active && (
                    <>
                      <div className="absolute inset-0 bg-blue-600/40 blur-md rounded-lg -z-10 animate-pulse" />
                      <div className="absolute inset-0 bg-gradient-to-t from-blue-600/30 via-blue-500/10 to-transparent rounded-lg -z-10" />
                      <div className="absolute bottom-0 left-2 right-2 h-[2.5px] bg-white rounded-full shadow-[0_0_8px_rgba(255,255,255,1)]" />
                    </>
                  )}
                  <Icon className={`w-3.5 h-3.5 ${active ? 'text-blue-400' : 'text-slate-400'}`} />
                  <span>{nav.label}</span>
                </Link>
              );
            })}
          </nav>

          {/* RIGHT: Search Box & Utility Buttons */}
          <div className="flex items-center gap-3 shrink-0">
            
            {/* Search Input Box */}
            <form onSubmit={handleSearchSubmit} className="hidden md:block relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search payment products, settings, and more"
                className="pl-8 pr-3 py-1.5 bg-[#121620] border border-slate-800 rounded-lg text-xs text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 w-56 lg:w-72 transition-all"
              />
            </form>

            {/* Merchant Context Dropdown Selector */}
            <div className="flex items-center gap-1.5 bg-[#121620] border border-slate-800 rounded-lg px-2.5 py-1.5">
              <Building2 className="w-3.5 h-3.5 text-blue-400 hidden sm:block" />
              <select
                value={currentMerchant}
                onChange={handleMerchantChange}
                aria-label="Select Merchant Context"
                className="bg-transparent text-xs font-bold text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="" className="bg-[#0B0E14] text-white">All Simulation Merchants (Global Dataset)</option>
                <option value="m54_simulation_3d0201" className="bg-[#0B0E14] text-white">Merchant Simulation (m54_simulation_3d0201)</option>
                <option value="m_alpha_123" className="bg-[#0B0E14] text-white">Merchant Alpha</option>
                <option value="m_real_2f9b3a" className="bg-[#0B0E14] text-white">Merchant REAL_TEST</option>
                <option value="m_beta_456" className="bg-[#0B0E14] text-white">Merchant Beta</option>
                <option value="m_gamma_789" className="bg-[#0B0E14] text-white">Merchant Gamma</option>
              </select>
            </div>

            {/* Telemetry / Pulse Icon Button */}
            <div
              className="w-8 h-8 bg-[#121620] border border-slate-800 rounded-lg flex items-center justify-center text-slate-300 hover:text-white hover:border-slate-700 transition-all cursor-pointer"
              title="Telemetry Status"
            >
              <Activity className="w-3.5 h-3.5 text-slate-300" />
            </div>

            {/* Notifications / Bell Icon Button */}
            <div
              className="w-8 h-8 bg-[#121620] border border-slate-800 rounded-lg flex items-center justify-center relative text-slate-300 hover:text-white hover:border-slate-700 transition-all cursor-pointer"
              title={`API Health Status: ${backendStatus.toUpperCase()}`}
            >
              <Bell className="w-3.5 h-3.5 text-slate-300" />
              <span
                className={`absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full ${
                  backendStatus === 'online'
                    ? 'bg-emerald-400'
                    : backendStatus === 'offline'
                    ? 'bg-rose-500'
                    : 'bg-amber-400'
                }`}
              />
            </div>

            {/* Merchant Avatar Badge */}
            <div
              className="w-8 h-8 bg-[#121620] border border-slate-800 rounded-lg flex items-center justify-center font-extrabold text-xs text-white hover:border-slate-700 transition-all cursor-pointer"
              title="User Profile"
            >
              A
            </div>

          </div>

          {/* HANGING BLACK DROPDOWN CUTOUT TAB FOR EXECUTION MODE */}
          <div className="absolute top-[60px] left-1/2 -translate-x-1/2 z-50 hidden lg:flex items-center gap-3 bg-black border-x border-b border-slate-800 rounded-b-2xl px-5 py-1 shadow-2xl">
            <button
              onClick={handleModeToggle}
              title={
                currentMode === 'REAL_TEST'
                  ? 'REAL_TEST Mode Active (Razorpay Test Sandbox)'
                  : 'SIMULATION Mode Active (Synthetic Evaluation Engine)'
              }
              className="flex items-center gap-2 cursor-pointer focus:outline-none group"
            >
              {/* Toggle Slider Pill */}
              <div
                className={`w-7 h-4 rounded-full p-0.5 transition-colors duration-200 ease-in-out flex items-center ${
                  currentMode === 'REAL_TEST' ? 'bg-emerald-500' : 'bg-blue-600'
                }`}
              >
                <div
                  className={`w-3 h-3 bg-white rounded-full shadow-md transform transition-transform duration-200 ease-in-out ${
                    currentMode === 'REAL_TEST' ? 'translate-x-3' : 'translate-x-0'
                  }`}
                />
              </div>

              {/* Mode Text */}
              <span
                className={`text-[11px] font-extrabold tracking-widest uppercase transition-colors ${
                  currentMode === 'REAL_TEST' ? 'text-emerald-400' : 'text-blue-400'
                }`}
              >
                {currentMode === 'REAL_TEST' ? 'REAL_TEST' : 'SIMULATION'}
              </span>
            </button>

            {/* Vertical Divider */}
            <span className="text-slate-700 text-xs font-light">|</span>

            {/* Quick Action Icons */}
            <div className="flex items-center gap-2.5 text-slate-400">
              <button title="API Keys" className="hover:text-white transition-colors cursor-pointer">
                <Key className="w-3.5 h-3.5" />
              </button>
              <button title="Schemas" className="hover:text-white transition-colors cursor-pointer">
                <Code2 className="w-3.5 h-3.5" />
              </button>
              <button title="Database Nodes" className="hover:text-white transition-colors cursor-pointer">
                <Database className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

        </div>
      </header>

      {/* ========================================================= */}
      {/* 2. BODY SHELL: PERSISTENT SIDEBAR + CENTER CONTENT        */}
      {/* ========================================================= */}
      <div className="flex-1 flex max-w-[1700px] w-full mx-auto relative">
        
        {/* PERSISTENT DESKTOP SIDEBAR — STICKY (260-280px) */}
        <aside className="hidden lg:flex flex-col w-64 xl:w-72 bg-white border-r border-slate-200/80 shrink-0 sticky top-[60px] h-[calc(100vh-60px)] p-4 space-y-6 z-20 shadow-xs overflow-y-auto">
          <nav className="space-y-6 flex-1">
            {navSections.map((sec) => (
              <div key={sec.category} className="space-y-1.5">
                <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest px-3 mb-2">
                  {sec.category}
                </div>
                <div className="space-y-1">
                  {sec.items.map((item) => {
                    const active = isPathActive(item.path);
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.label}
                        to={item.path}
                        className={`flex items-center gap-3 px-3.5 py-2.5 text-xs font-semibold rounded-xl transition-all duration-150 group ${
                          active
                            ? 'bg-[#F0F6FF] text-[#1D4ED8] font-extrabold shadow-xs border-l-4 border-[#2563EB] pl-3'
                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                        }`}
                      >
                        <Icon
                          className={`w-4 h-4 transition-transform group-hover:scale-110 ${
                            active ? 'text-[#2563EB]' : 'text-slate-400 group-hover:text-slate-600'
                          }`}
                        />
                        <span className="tracking-tight">{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>

          {/* Execution Engine Status Footer Card inside Sidebar */}
          <div className="pt-4 border-t border-slate-100 px-2 space-y-2">
            <div className="bg-[#F8FAFC] border border-slate-200/70 rounded-xl p-3 space-y-1.5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Engine Status</span>
                <span
                  className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    currentMode === 'REAL_TEST'
                      ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                      : 'bg-blue-100 text-blue-700 border border-blue-300'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      currentMode === 'REAL_TEST' ? 'bg-emerald-500 animate-pulse' : 'bg-blue-500'
                    }`}
                  />
                  {currentMode}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium leading-tight">
                {currentMode === 'REAL_TEST'
                  ? 'Razorpay Test Sandbox Connected'
                  : 'Synthetic Recovery Evaluation Active'}
              </p>
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-400 font-semibold px-1">
              <span>RecoverAI Engine</span>
              <span>v1.0.0 Enterprise</span>
            </div>
          </div>
        </aside>

        {/* MOBILE MENU DRAWER OVERLAY */}
        {mobileMenuOpen && (
          <div className="lg:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs" onClick={() => setMobileMenuOpen(false)} />
            <div className="relative bg-white w-72 max-w-full h-full p-5 space-y-6 overflow-y-auto shadow-2xl flex flex-col z-50">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div className="flex items-center gap-2">
                  <img src={logoSvg} alt="RecoverAI Logo" className="w-6 h-6 object-contain" />
                  <span className="font-extrabold text-sm text-slate-900">RecoverAI</span>
                </div>
                <button onClick={() => setMobileMenuOpen(false)} className="p-1 rounded-lg hover:bg-slate-100">
                  <X className="w-5 h-5 text-slate-500" />
                </button>
              </div>

              {/* Mobile Search */}
              <form onSubmit={handleSearchSubmit} className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search transactions..."
                  className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-900 placeholder-slate-400 focus:outline-none"
                />
              </form>

              {/* Mobile Navigation */}
              <nav className="space-y-6 flex-1">
                {navSections.map((sec) => (
                  <div key={sec.category} className="space-y-1">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest px-3 mb-1">
                      {sec.category}
                    </div>
                    <div className="space-y-0.5">
                      {sec.items.map((item) => {
                        const active = isPathActive(item.path);
                        const Icon = item.icon;
                        return (
                          <Link
                            key={item.label}
                            to={item.path}
                            onClick={() => setMobileMenuOpen(false)}
                            className={`flex items-center gap-2.5 px-3 py-2 text-xs font-semibold rounded-lg transition-all ${
                              active
                                ? 'bg-[#EFF6FF] text-[#1D4ED8] font-bold border-l-4 border-[#2563EB] pl-2.5'
                                : 'text-slate-700 hover:bg-slate-50'
                            }`}
                          >
                            <Icon className={`w-4 h-4 ${active ? 'text-[#2563EB]' : 'text-slate-400'}`} />
                            <span>{item.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </nav>
            </div>
          </div>
        )}

        {/* CENTER CONTENT WORKSPACE */}
        <main className="flex-1 p-6 lg:p-8 min-w-0 bg-[#F8FAFC] overflow-y-auto">
          {children}
        </main>

      </div>
    </div>
  );
};

export default Layout;
