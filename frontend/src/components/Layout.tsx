import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
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
  CheckCircle2,
  AlertTriangle,
  Menu,
  X,
  Building2,
  Activity,
  Layers,
} from 'lucide-react';
import { checkBackendHealth, currentApiState } from '../services/api';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { label: 'Command Center', path: '/', icon: LayoutDashboard },
    { label: 'Revenue Risk', path: '/revenue-risk', icon: ShieldAlert },
    { label: 'Recovery Queue', path: '/recovery-queue', icon: ListFilter },
    { label: 'Transaction Detail', path: '/transactions/tx_demo_001', icon: FileText },
    { label: 'AI Decision Center', path: '/ai-decision', icon: Cpu },
    { label: 'Recovery Analytics', path: '/analytics', icon: BarChart3 },
    { label: 'Audit Center', path: '/audit', icon: Lock },
    { label: 'Policy Manager', path: '/policies', icon: Sliders },
    { label: 'Human Review', path: '/human-review', icon: UserCheck },
  ];

  const handleModeToggle = () => {
    const nextMode = currentMode === 'SIMULATION' ? 'REAL_TEST' : 'SIMULATION';
    currentApiState.mode = nextMode;
    setCurrentMode(nextMode);
  };

  const handleMerchantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const nextMerchant = e.target.value;
    currentApiState.merchantId = nextMerchant;
    setCurrentMerchant(nextMerchant);
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col md:flex-row">
      {/* Mobile Top Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg">
            RAI
          </div>
          <span className="font-bold text-lg text-slate-100 tracking-tight">RecoverAI</span>
        </div>
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-lg bg-slate-800 text-slate-300 hover:text-white border border-slate-700"
          aria-label="Toggle menu"
        >
          {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Global Navigation Sidebar */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 w-64 bg-slate-900/90 backdrop-blur-xl border-r border-slate-800/80 flex flex-col justify-between transition-transform duration-300 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-5 space-y-6">
          {/* Logo & Branding */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-blue-600 to-purple-600 flex items-center justify-center font-bold text-white text-lg shadow-lg glow-cyan">
              RAI
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-xl text-white tracking-tight">RecoverAI</span>
                <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
                  Buildathon
                </span>
              </div>
              <p className="text-xs text-slate-400">Razorpay AI Recovery Engine</p>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="space-y-1">
            <div className="px-3 text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Dashboard & Systems
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive =
                item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path.split('/')[1] ? `/${item.path.split('/')[1]}` : item.path);

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/10 text-cyan-400 border-l-4 border-cyan-500 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer: System Status */}
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/40 space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-slate-400" />
              API Server
            </span>
            <span
              className={`flex items-center gap-1 font-medium ${
                backendStatus === 'online'
                  ? 'text-emerald-400'
                  : backendStatus === 'offline'
                  ? 'text-rose-400'
                  : 'text-amber-400'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  backendStatus === 'online'
                    ? 'bg-emerald-500 animate-pulse'
                    : backendStatus === 'offline'
                    ? 'bg-rose-500'
                    : 'bg-amber-500'
                }`}
              />
              {backendStatus.toUpperCase()}
            </span>
          </div>

          <div className="text-[11px] text-slate-500 text-center border-t border-slate-800/50 pt-2">
            RecoverAI System v1.0.0 • Step 27
          </div>
        </div>
      </aside>

      {/* Main Content Workspace */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="h-16 bg-slate-900/60 backdrop-blur-md border-b border-slate-800/80 px-6 flex items-center justify-between gap-4 sticky top-0 z-40">
          {/* Breadcrumb / Title Context */}
          <div className="flex items-center gap-3">
            <Layers className="w-5 h-5 text-cyan-400 hidden sm:block" />
            <span className="text-sm font-semibold text-slate-300">
              Razorpay Revenue Recovery Workspace
            </span>
          </div>

          {/* Header Action Badges & Toggles */}
          <div className="flex items-center gap-4">
            {/* Mode Badge Indicator / Switcher */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 hidden lg:inline">Mode:</span>
              <button
                onClick={handleModeToggle}
                title="Click to toggle execution mode"
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold transition-all border shadow-sm ${
                  currentMode === 'REAL_TEST'
                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/30 hover:bg-rose-500/20 glow-rose'
                    : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/20 glow-cyan'
                }`}
              >
                {currentMode === 'REAL_TEST' ? (
                  <>
                    <AlertTriangle className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
                    REAL_TEST
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    SIMULATION
                  </>
                )}
              </button>
            </div>

            {/* Merchant Context Selector */}
            <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700/80 rounded-lg px-2.5 py-1">
              <Building2 className="w-3.5 h-3.5 text-slate-400 hidden sm:block" />
              <select
                value={currentMerchant}
                onChange={handleMerchantChange}
                className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
              >
                <option value="m_alpha_123" className="bg-slate-900 text-slate-200">
                  Merchant Alpha (m_alpha_123)
                </option>
                <option value="m_real_2f9b3a" className="bg-slate-900 text-slate-200">
                  Merchant REAL_TEST (m_real_2f9b3a)
                </option>
                <option value="m_beta_456" className="bg-slate-900 text-slate-200">
                  Merchant Beta (m_beta_456)
                </option>
                <option value="m_gamma_789" className="bg-slate-900 text-slate-200">
                  Merchant Gamma (m_gamma_789)
                </option>
              </select>
            </div>
          </div>
        </header>

        {/* Page Content Container */}
        <main className="flex-1 p-6 md:p-8 max-w-7xl mx-auto w-full">{children}</main>
      </div>
    </div>
  );
};
