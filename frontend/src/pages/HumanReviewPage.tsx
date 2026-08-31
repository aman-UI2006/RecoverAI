import React, { useState, useEffect, useMemo } from 'react';
import {
  UserCheck,
  ShieldAlert,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  Filter,
  Eye,
  AlertTriangle,
  Zap,
  Check,
  ChevronRight,
  TrendingUp,
  DollarSign
} from 'lucide-react';
import { api } from '../services/api';
import { ReviewModal, HumanReviewItem } from '../components/ReviewModal';

const MOCK_REVIEW_QUEUE: HumanReviewItem[] = [
  {
    id: 'rev_1001_exp_alpha',
    transaction_id: 'tx_alpha_998811',
    merchant_id: 'm_alpha_123',
    status: 'PENDING',
    reason: 'HIGH_VALUE_AMOUNT_CAP_EXCEEDED (₹25,000 > ₹10,000 Cap)',
    reviewer_id: null,
    decision: null,
    notes: null,
    reviewed_at: null,
    created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    amount: 25000.0,
    currency: 'INR',
    scenario_type: 'PAYMENT_FAILURE',
    mode: 'SIMULATION'
  },
  {
    id: 'rev_1002_exp_beta',
    transaction_id: 'tx_beta_445522',
    merchant_id: 'm_alpha_123',
    status: 'PENDING',
    reason: 'ML_PROBABILITY_BELOW_POLICY_FLOOR (P=0.04 < 0.10 Floor)',
    reviewer_id: null,
    decision: null,
    notes: null,
    reviewed_at: null,
    created_at: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    amount: 8500.0,
    currency: 'INR',
    scenario_type: 'CHECKOUT_ABANDONMENT',
    mode: 'SIMULATION'
  },
  {
    id: 'rev_1003_exp_gamma',
    transaction_id: 'tx_gamma_771133',
    merchant_id: 'm_alpha_123',
    status: 'PENDING',
    reason: 'POLICY_REJECTED_NEEDS_HUMAN_APPROVAL (Max Retries Reached)',
    reviewer_id: null,
    decision: null,
    notes: null,
    reviewed_at: null,
    created_at: new Date(Date.now() - 1000 * 60 * 300).toISOString(),
    amount: 14200.0,
    currency: 'INR',
    scenario_type: 'SUBSCRIPTION_LAPSE',
    mode: 'REAL_TEST'
  },
  {
    id: 'rev_1004_exp_delta',
    transaction_id: 'tx_delta_883344',
    merchant_id: 'm_alpha_123',
    status: 'APPROVED',
    reason: 'HIGH_VALUE_THRESHOLD',
    reviewer_id: 'rev_operator_01',
    decision: 'APPROVE_OVERRIDE',
    notes: 'Verified customer identity and account solvency manually.',
    reviewed_at: new Date(Date.now() - 1000 * 60 * 600).toISOString(),
    created_at: new Date(Date.now() - 1000 * 60 * 720).toISOString(),
    amount: 45000.0,
    currency: 'INR',
    scenario_type: 'INSUFFICIENT_FUNDS',
    mode: 'SIMULATION'
  }
];

export const HumanReviewPage: React.FC = () => {
  const [queueItems, setQueueItems] = useState<HumanReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('PENDING');
  const [selectedItem, setSelectedItem] = useState<HumanReviewItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchReviewQueue = async () => {
    setIsRefreshing(true);
    try {
      const res = await api.get('/api/v1/human-review/queue');
      if (res.data && Array.isArray(res.data.items)) {
        setQueueItems(res.data.items);
      } else {
        setQueueItems(MOCK_REVIEW_QUEUE);
      }
    } catch (err: any) {
      console.warn('[HumanReview API Fallback]: Using mock review queue data', err?.message);
      setQueueItems(MOCK_REVIEW_QUEUE);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchReviewQueue();
  }, []);

  const handleOpenInspectModal = (item: HumanReviewItem) => {
    setSelectedItem(item);
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    if (isSubmitting) return;
    setIsModalOpen(false);
    setSelectedItem(null);
    setModalError(null);
  };

  const handleSubmitDecision = async (
    reviewId: string,
    decision: 'APPROVE_OVERRIDE' | 'REJECT_PERMANENT',
    reviewerId: string,
    notes: string
  ) => {
    setIsSubmitting(true);
    setModalError(null);

    try {
      const endpoint = `/api/v1/human-review/items/${reviewId}/decision`;
      await api.post(endpoint, {
        decision,
        reviewer_id: reviewerId,
        notes: notes || undefined
      });

      // Update local state dynamically
      const newStatus = decision === 'APPROVE_OVERRIDE' ? 'APPROVED' : 'REJECTED';
      setQueueItems((prev) =>
        prev.map((item) =>
          item.id === reviewId
            ? {
                ...item,
                status: newStatus,
                decision,
                reviewer_id: reviewerId,
                notes: notes || item.notes,
                reviewed_at: new Date().toISOString()
              }
            : item
        )
      );

      setToastMessage(`Review decision '${decision}' successfully recorded for ${selectedItem?.transaction_id}`);
      setTimeout(() => setToastMessage(null), 5000);
      setIsModalOpen(false);
      setSelectedItem(null);
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Failed to submit reviewer decision';
      console.error('[HumanReview Action Error]:', errMsg);
      setModalError(errMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredItems = useMemo(() => {
    return queueItems.filter((item) => {
      const matchesStatus =
        statusFilter === 'ALL' || item.status === statusFilter;
      const matchesSearch =
        searchTerm === '' ||
        item.transaction_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.merchant_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.reason.toLowerCase().includes(searchTerm.toLowerCase());

      return matchesStatus && matchesSearch;
    });
  }, [queueItems, statusFilter, searchTerm]);

  // KPI Calculations
  const pendingCount = queueItems.filter((i) => i.status === 'PENDING').length;
  const highValueCount = queueItems.filter((i) => i.amount >= 10000).length;
  const approvedCount = queueItems.filter((i) => i.status === 'APPROVED').length;
  const rejectedCount = queueItems.filter((i) => i.status === 'REJECTED').length;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Toast Banner */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-2xl flex items-center space-x-3 backdrop-blur-md animate-fadeIn">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span className="text-sm font-medium">{toastMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">Human Review Queue</h1>
            <span className="text-xs font-mono font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2.5 py-0.5 rounded-full">
              STEP 36
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Process escalated high-value or policy-rejected transactions requiring manual operator authorization
          </p>
        </div>

        <button
          onClick={fetchReviewQueue}
          disabled={isRefreshing}
          className="flex items-center space-x-2 px-4 py-2 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700 transition-colors shadow-md disabled:opacity-50"
        >
          <RotateCcw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>{isRefreshing ? 'Syncing Queue...' : 'Refresh Queue'}</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/80 border border-amber-500/30 backdrop-blur-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Pending Escalations</span>
            <ShieldAlert className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono">{pendingCount}</div>
          <p className="text-[11px] text-slate-500">Requires manual authorization decision</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 backdrop-blur-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>High-Value Items (≥₹10k)</span>
            <DollarSign className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-indigo-400 font-mono">{highValueCount}</div>
          <p className="text-[11px] text-slate-500">Above merchant auto-execution cap</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 backdrop-blur-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Approved Overrides</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">{approvedCount}</div>
          <p className="text-[11px] text-slate-500">Forced execution authorized</p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 backdrop-blur-sm space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Terminated Actions</span>
            <XCircle className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold text-red-400 font-mono">{rejectedCount}</div>
          <p className="text-[11px] text-slate-500">Permanently rejected & terminated</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/80 border border-slate-800">
        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {['PENDING', 'APPROVED', 'REJECTED', 'ALL'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                statusFilter === status
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {status === 'ALL' ? 'ALL STATUSES' : status}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search Tx ID or Escalation Code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Review Queue Cards Grid / List */}
      {isLoading ? (
        <div className="p-12 text-center text-slate-500 space-y-3">
          <RotateCcw className="w-8 h-8 animate-spin mx-auto text-indigo-500" />
          <p className="text-sm">Loading escalated human review items...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="p-12 text-center rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
          <UserCheck className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-base font-semibold text-slate-300">No Escalated Review Items Found</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            There are currently no transactions matching your selected filters requiring manual operator authorization.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className={`p-5 rounded-xl border transition-all flex flex-col justify-between space-y-4 ${
                item.status === 'PENDING'
                  ? 'bg-slate-900/90 border-amber-500/30 hover:border-amber-500/50 shadow-lg shadow-amber-950/20'
                  : 'bg-slate-900/50 border-slate-800 opacity-80'
              }`}
            >
              <div className="space-y-3">
                {/* Card Top Row */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-indigo-400 bg-indigo-500/10 px-2.5 py-0.5 rounded border border-indigo-500/20">
                    Tx: {item.transaction_id}
                  </span>
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                      item.status === 'PENDING'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse'
                        : item.status === 'APPROVED'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                    }`}
                  >
                    {item.status}
                  </span>
                </div>

                {/* Amount & Scenario Row */}
                <div className="flex items-baseline justify-between pt-1">
                  <div>
                    <span className="text-[11px] text-slate-500 block">Amount</span>
                    <span className="text-lg font-bold text-white font-mono">
                      ₹{item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-[11px] text-slate-500 block">Scenario</span>
                    <span className="text-xs text-slate-300 font-medium bg-slate-800 px-2 py-0.5 rounded">
                      {item.scenario_type}
                    </span>
                  </div>
                </div>

                {/* Escalation Code Banner */}
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 space-y-1">
                  <div className="flex items-center space-x-1.5 text-amber-400 text-[11px] font-semibold uppercase tracking-wider">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Escalation Code</span>
                  </div>
                  <p className="text-xs text-amber-200/90 font-mono line-clamp-2">
                    {item.reason}
                  </p>
                </div>
              </div>

              {/* Card Footer Action */}
              <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between text-xs">
                <span className="text-slate-500 font-mono text-[11px]">
                  {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>

                <button
                  onClick={() => handleOpenInspectModal(item)}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    item.status === 'PENDING'
                      ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/30'
                      : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>{item.status === 'PENDING' ? 'INSPECT & ACTION' : 'View Decision Details'}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Review Modal Dialog */}
      <ReviewModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        item={selectedItem}
        onSubmitDecision={handleSubmitDecision}
        isSubmitting={isSubmitting}
        errorAlert={modalError}
      />
    </div>
  );
};

export const HumanReview = HumanReviewPage;
export default HumanReviewPage;
