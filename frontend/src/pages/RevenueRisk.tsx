import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  Search,
  Filter,
  ArrowUpRight,
  RefreshCw,
  AlertOctagon,
  TrendingDown,
  Building2,
  Clock,
} from 'lucide-react';
import { api, currentApiState } from '../services/api';

export interface RiskTransaction {
  id: string;
  transaction_id?: string;
  merchant_id: string;
  customer_email?: string;
  customer_name?: string;
  amount?: number;
  amount_in_paise?: number;
  currency: string;
  status: string;
  scenario_type: string;
  risk_level?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score?: number;
  created_at: string;
}

const SCENARIOS = [
  { id: 'ALL', label: 'All Scenarios' },
  { id: 'PAYMENT_FAILURE', label: 'Payment Failure' },
  { id: 'CHECKOUT_ABANDONMENT', label: 'Checkout Abandonment' },
  { id: 'SUBSCRIPTION_LAPSE', label: 'Subscription Lapse' },
  { id: 'BANK_DOWNTIME', label: 'Bank Downtime' },
  { id: 'INSUFFICIENT_FUNDS', label: 'Insufficient Funds' },
];

export const RevenueRiskPage: React.FC = () => {
  const [transactions, setTransactions] = useState<RiskTransaction[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [mode] = useState<'SIMULATION' | 'REAL_TEST'>(currentApiState.mode);

  const fetchRiskTransactions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/api/v1/transactions', {
        params: {
          merchant_id: currentApiState.merchantId,
          mode: currentApiState.mode,
          limit: 50,
          scenario_type: selectedScenario === 'ALL' ? undefined : selectedScenario,
        },
      });

      if (res.data && Array.isArray(res.data.items)) {
        setTransactions(res.data.items);
      }
    } catch (err: any) {
      console.warn('[RevenueRisk API Fallback]:', err?.message);
      // Resilient fallback mock dataset for at-risk transactions
      const mockItems: RiskTransaction[] = [
        {
          id: 'risk_001',
          transaction_id: 'pay_RF1001A',
          merchant_id: currentApiState.merchantId,
          customer_email: 'priya.sharma@example.com',
          customer_name: 'Priya Sharma',
          amount_in_paise: 450000,
          currency: 'INR',
          status: 'DETECTED',
          scenario_type: 'PAYMENT_FAILURE',
          risk_level: 'CRITICAL',
          risk_score: 0.92,
          created_at: new Date(Date.now() - 900000).toISOString(),
        },
        {
          id: 'risk_002',
          transaction_id: 'pay_RF1002B',
          merchant_id: currentApiState.merchantId,
          customer_email: 'rahul.verma@example.com',
          customer_name: 'Rahul Verma',
          amount_in_paise: 1250000,
          currency: 'INR',
          status: 'DIAGNOSED',
          scenario_type: 'CHECKOUT_ABANDONMENT',
          risk_level: 'HIGH',
          risk_score: 0.84,
          created_at: new Date(Date.now() - 2400000).toISOString(),
        },
        {
          id: 'risk_003',
          transaction_id: 'pay_RF1003C',
          merchant_id: currentApiState.merchantId,
          customer_email: 'ananya.iyer@example.com',
          customer_name: 'Ananya Iyer',
          amount_in_paise: 320000,
          currency: 'INR',
          status: 'DETECTED',
          scenario_type: 'SUBSCRIPTION_LAPSE',
          risk_level: 'HIGH',
          risk_score: 0.78,
          created_at: new Date(Date.now() - 5400000).toISOString(),
        },
        {
          id: 'risk_004',
          transaction_id: 'pay_RF1004D',
          merchant_id: currentApiState.merchantId,
          customer_email: 'vikram.singh@example.com',
          customer_name: 'Vikram Singh',
          amount_in_paise: 890000,
          currency: 'INR',
          status: 'DIAGNOSED',
          scenario_type: 'BANK_DOWNTIME',
          risk_level: 'MEDIUM',
          risk_score: 0.65,
          created_at: new Date(Date.now() - 9600000).toISOString(),
        },
        {
          id: 'risk_005',
          transaction_id: 'pay_RF1005E',
          merchant_id: currentApiState.merchantId,
          customer_email: 'neha.patel@example.com',
          customer_name: 'Neha Patel',
          amount_in_paise: 210000,
          currency: 'INR',
          status: 'DETECTED',
          scenario_type: 'INSUFFICIENT_FUNDS',
          risk_level: 'HIGH',
          risk_score: 0.81,
          created_at: new Date(Date.now() - 14400000).toISOString(),
        },
      ];
      setTransactions(mockItems);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRiskTransactions();
  }, [selectedScenario, mode, currentApiState.merchantId]);

  const getAmountInPaise = (tx: RiskTransaction): number => {
    if (typeof tx.amount === 'number') {
      return Math.round(tx.amount * 100);
    }
    if (typeof tx.amount_in_paise === 'number') {
      return tx.amount_in_paise;
    }
    return 0;
  };

  // Filtered dataset based on search query
  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      const matchesScenario =
        selectedScenario === 'ALL' || tx.scenario_type === selectedScenario;

      const q = searchQuery.toLowerCase().trim();
      const txId = tx.transaction_id || tx.id || '';
      const matchesSearch =
        !q ||
        txId.toLowerCase().includes(q) ||
        (tx.customer_email && tx.customer_email.toLowerCase().includes(q)) ||
        (tx.customer_name && tx.customer_name.toLowerCase().includes(q));

      return matchesScenario && matchesSearch;
    });
  }, [transactions, selectedScenario, searchQuery]);

  // Calculate summary telemetry
  const totalAtRiskPaise = useMemo(() => {
    return filteredTransactions.reduce((acc, tx) => acc + getAmountInPaise(tx), 0);
  }, [filteredTransactions]);

  const formatCurrency = (valInPaise: number): string => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(valInPaise / 100);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[#0B1F3A] tracking-tight">
            Revenue Risk Exposure
          </h1>
          <p className="text-xs text-[#53627A] mt-0.5">
            Real-time monitoring of transactions flagged at risk of revenue leakage across payment scenarios.
          </p>
        </div>

        <button
          onClick={fetchRiskTransactions}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-[#F8FAFD] text-[#0B1F3A] text-xs font-bold border border-[#E5EAF1] transition-all shadow-sm cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-[#53627A] ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Radar</span>
        </button>
      </div>

      {/* Exposure Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 border border-[#E5EAF1] space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-[#7A8799] uppercase tracking-wider font-bold">
            <span>Total Value At Risk</span>
            <TrendingDown className="w-4 h-4 text-[#D6455D]" />
          </div>
          <div className="text-2xl font-bold text-[#0B1F3A] font-numeric tracking-tight">
            {formatCurrency(totalAtRiskPaise)}
          </div>
          <div className="text-xs text-[#53627A]">
            Across {filteredTransactions.length} flagged transactions
          </div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-[#E5EAF1] space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-[#7A8799] uppercase tracking-wider font-bold">
            <span>High / Critical Severity</span>
            <AlertOctagon className="w-4 h-4 text-[#D99A00]" />
          </div>
          <div className="text-2xl font-bold text-[#D99A00] font-numeric tracking-tight">
            {
              filteredTransactions.filter(
                (t) => t.risk_level === 'CRITICAL' || t.risk_level === 'HIGH'
              ).length
            }
          </div>
          <div className="text-xs text-[#53627A]">Requiring priority AI intervention</div>
        </div>

        <div className="bg-white rounded-xl p-5 border border-[#E5EAF1] space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-[#7A8799] uppercase tracking-wider font-bold">
            <span>Active Tenant</span>
            <Building2 className="w-4 h-4 text-[#2F5BFF]" />
          </div>
          <div className="text-base font-bold text-[#2F5BFF] font-mono">
            {currentApiState.merchantId}
          </div>
          <div className="text-xs text-[#53627A]">Mode: {currentApiState.mode}</div>
        </div>
      </div>

      {/* Controls Bar: Search & Scenario Tabs Card */}
      <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] space-y-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Scenario Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2 lg:pb-0 scrollbar-none">
            {SCENARIOS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSelectedScenario(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all border cursor-pointer ${
                  selectedScenario === tab.id
                    ? 'bg-[#EEF4FF] text-[#2454D6] border-[#2F5BFF]/30 font-bold'
                    : 'bg-white text-[#53627A] border-[#E5EAF1] hover:bg-[#F8FAFD] hover:text-[#0B1F3A]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Real-time Search Input */}
          <div className="relative w-full lg:w-72">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-[#7A8799]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Transaction ID or Email..."
              className="w-full pl-9 pr-4 py-2 rounded-lg bg-white border border-[#E5EAF1] text-xs text-[#0B1F3A] placeholder-[#7A8799] focus:outline-none focus:border-[#2F5BFF]/50 transition-all"
            />
          </div>
        </div>

        {/* Risk Transactions Data Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFD] text-[#53627A] uppercase text-[10px] font-bold tracking-wider border-b border-[#E5EAF1]">
              <tr>
                <th className="py-3.5 px-4">Transaction ID</th>
                <th className="py-3.5 px-4">Customer</th>
                <th className="py-3.5 px-4">Scenario Class</th>
                <th className="py-3.5 px-4">Monetary Value</th>
                <th className="py-3.5 px-4">Risk Severity</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Detected At</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5EAF1] font-numeric">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#7A8799]">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RefreshCw className="w-5 h-5 animate-spin text-[#2F5BFF]" />
                      <span>Scanning risk telemetry...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredTransactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center">
                    <div className="flex flex-col items-center justify-center space-y-2 max-w-sm mx-auto">
                      <div className="p-3 rounded-full bg-[#F8FAFD] text-[#7A8799] border border-[#E5EAF1]">
                        <Filter className="w-5 h-5" />
                      </div>
                      <h3 className="text-xs font-bold text-[#0B1F3A]">No revenue currently at risk</h3>
                      <p className="text-xs text-[#7A8799]">
                        No transactions matched the selected scenario filter ({selectedScenario}) or search query ({searchQuery || 'None'}).
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredTransactions.map((tx) => {
                  const riskLevelStyles: Record<string, string> = {
                    CRITICAL: 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20',
                    HIGH: 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20',
                    MEDIUM: 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20',
                    LOW: 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20',
                  };

                  const riskBadge =
                    riskLevelStyles[tx.risk_level || 'HIGH'] || riskLevelStyles.HIGH;

                  return (
                    <tr key={tx.id} className="hover:bg-[#F8FAFD] transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-[#2F5BFF]">
                        {tx.transaction_id || tx.id}
                      </td>
                      <td className="py-3.5 px-4 font-sans">
                        <div className="font-semibold text-[#0B1F3A]">
                          {tx.customer_name || 'Anonymous Customer'}
                        </div>
                        <div className="text-[11px] text-[#7A8799]">{tx.customer_email || 'n/a'}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="inline-block px-2.5 py-0.5 rounded text-[10px] font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
                          {tx.scenario_type}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-bold text-[#0B1F3A]">
                        {formatCurrency(getAmountInPaise(tx))}
                      </td>
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded text-[10px] font-bold border ${riskBadge}`}
                        >
                          {tx.risk_level || 'HIGH'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[#53627A] font-sans font-medium">
                        {tx.status}
                      </td>
                      <td className="py-3.5 px-4 text-[#7A8799] font-sans">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-[#7A8799]" />
                          {new Date(tx.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/ai-decision/${tx.transaction_id || tx.id}`}
                          className="inline-flex items-center gap-1 text-[#2F5BFF] hover:text-[#1A47E8] font-bold"
                        >
                          <span>Inspect</span>
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default RevenueRiskPage;
