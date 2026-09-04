import React, { useState, useEffect, useMemo } from 'react';
import {
  UserCheck,
  ShieldAlert,
  RotateCcw,
  CheckCircle2,
  XCircle,
  Search,
  Eye,
  Zap,
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
    <div className="space-y-6 font-sans">
      {/* Toast Banner */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 p-4 rounded-xl bg-[#E6F4ED] border border-[#16A36A]/30 text-[#16A36A] shadow-lg flex items-center space-x-3 backdrop-blur-md font-bold text-xs">
          <CheckCircle2 className="w-5 h-5 shrink-0 text-[#16A36A]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E5EAF1] p-6 rounded-xl shadow-sm">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold text-[#0B1F3A] tracking-tight">Human Review Queue</h1>
            <span className="text-xs font-mono font-bold bg-[#FDF8EC] text-[#D99A00] border border-[#D99A00]/20 px-2.5 py-0.5 rounded">
              STEP 36
            </span>
          </div>
          <p className="text-xs text-[#53627A] mt-1">
            Process escalated high-value or policy-rejected transactions requiring manual operator authorization
          </p>
        </div>

        <button
          onClick={fetchReviewQueue}
          disabled={isRefreshing}
          className="flex items-center space-x-2 px-4 py-2 text-xs font-bold text-[#0B1F3A] bg-white hover:bg-[#F8FAFD] rounded-lg border border-[#E5EAF1] transition-all shadow-sm cursor-pointer disabled:opacity-50"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
          <span>{isRefreshing ? 'Syncing Queue...' : 'Refresh Queue'}</span>
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 font-numeric">
        <div className="p-4 rounded-xl bg-white border border-[#D99A00]/30 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[#7A8799] text-xs font-bold font-sans">
            <span>Pending Escalations</span>
            <ShieldAlert className="w-4 h-4 text-[#D99A00]" />
          </div>
          <div className="text-2xl font-bold text-[#D99A00]">{pendingCount}</div>
          <p className="text-[11px] text-[#7A8799] font-sans">Requires manual authorization decision</p>
        </div>

        <div className="p-4 rounded-xl bg-white border border-[#E5EAF1] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[#7A8799] text-xs font-bold font-sans">
            <span>High-Value Items (≥₹10k)</span>
            <DollarSign className="w-4 h-4 text-[#2F5BFF]" />
          </div>
          <div className="text-2xl font-bold text-[#2454D6]">{highValueCount}</div>
          <p className="text-[11px] text-[#7A8799] font-sans">Above merchant auto-execution cap</p>
        </div>

        <div className="p-4 rounded-xl bg-white border border-[#E5EAF1] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[#7A8799] text-xs font-bold font-sans">
            <span>Approved Overrides</span>
            <CheckCircle2 className="w-4 h-4 text-[#16A36A]" />
          </div>
          <div className="text-2xl font-bold text-[#16A36A]">{approvedCount}</div>
          <p className="text-[11px] text-[#7A8799] font-sans">Forced execution authorized</p>
        </div>

        <div className="p-4 rounded-xl bg-white border border-[#E5EAF1] shadow-sm space-y-2">
          <div className="flex items-center justify-between text-[#7A8799] text-xs font-bold font-sans">
            <span>Terminated Actions</span>
            <XCircle className="w-4 h-4 text-[#D6455D]" />
          </div>
          <div className="text-2xl font-bold text-[#D6455D]">{rejectedCount}</div>
          <p className="text-[11px] text-[#7A8799] font-sans">Permanently rejected & terminated</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 p-4 rounded-xl bg-white border border-[#E5EAF1] shadow-sm">
        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {['PENDING', 'APPROVED', 'REJECTED', 'ALL'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                statusFilter === status
                  ? 'bg-[#2F5BFF] text-white shadow-sm'
                  : 'text-[#53627A] hover:text-[#0B1F3A] hover:bg-[#F8FAFD]'
              }`}
            >
              {status === 'ALL' ? 'ALL STATUSES' : status}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#7A8799]" />
          <input
            type="text"
            placeholder="Search Tx ID or Escalation Code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-white border border-[#E5EAF1] text-xs text-[#0B1F3A] placeholder-[#7A8799] focus:outline-none focus:border-[#2F5BFF]/50"
          />
        </div>
      </div>

      {/* Review Queue Cards Grid / List */}
      {isLoading ? (
        <div className="p-12 text-center text-[#7A8799] space-y-3 bg-white rounded-xl border border-[#E5EAF1]">
          <RotateCcw className="w-8 h-8 animate-spin mx-auto text-[#2F5BFF]" />
          <p className="text-xs font-bold">Loading escalated human review items...</p>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="p-12 text-center rounded-xl bg-white border border-[#E5EAF1] space-y-3 shadow-sm">
          <UserCheck className="w-10 h-10 text-[#7A8799] mx-auto" />
          <h3 className="text-sm font-bold text-[#0B1F3A]">No Escalated Review Items Found</h3>
          <p className="text-xs text-[#53627A] max-w-md mx-auto">
            There are currently no transactions matching your selected filters requiring manual operator authorization.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-numeric">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className={`p-5 rounded-xl border transition-all flex flex-col justify-between space-y-4 shadow-sm ${
                item.status === 'PENDING'
                  ? 'bg-white border-[#D99A00]/40'
                  : 'bg-white border-[#E5EAF1] opacity-80'
              }`}
            >
              <div className="space-y-3">
                {/* Card Top Row */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-[#2454D6] bg-[#EEF4FF] px-2.5 py-0.5 rounded border border-[#2F5BFF]/20">
                    Tx: {item.transaction_id}
                  </span>
                  <span
                    className={`text-[11px] px-2.5 py-0.5 rounded font-bold border font-sans ${
                      item.status === 'PENDING'
                        ? 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20'
                        : item.status === 'APPROVED'
                        ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20'
                        : 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20'
                    }`}
                  >
                    {item.status}
                  </span>
                </div>

                {/* Amount & Scenario Row */}
                <div className="flex items-baseline justify-between pt-1">
                  <div>
                    <span className="text-[10px] text-[#7A8799] uppercase font-bold font-sans block">Amount</span>
                    <span className="text-lg font-bold text-[#0B1F3A]">
                      ₹{item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="text-right font-sans">
                    <span className="text-[10px] text-[#7A8799] uppercase font-bold block">Scenario</span>
                    <span className="text-xs text-[#0B1F3A] font-bold bg-[#F8FAFD] px-2 py-0.5 rounded border border-[#E5EAF1]">
                      {item.scenario_type}
                    </span>
                  </div>
                </div>

                {/* Escalation Code Banner */}
                <div className="p-3 rounded-lg bg-[#F8FAFD] border border-[#E5EAF1] space-y-1 font-sans">
                  <div className="flex items-center space-x-1.5 text-[#D99A00] text-[10px] font-bold uppercase tracking-wider">
                    <Zap className="w-3.5 h-3.5 text-[#D99A00]" />
                    <span>Escalation Code</span>
                  </div>
                  <p className="text-xs text-[#0B1F3A] font-mono font-bold line-clamp-2">
                    {item.reason}
                  </p>
                </div>
              </div>

              {/* Card Footer Action */}
              <div className="pt-3 border-t border-[#E5EAF1] flex items-center justify-between text-xs font-sans">
                <span className="text-[#7A8799] font-mono text-[11px]">
                  {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>

                <button
                  onClick={() => handleOpenInspectModal(item)}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    item.status === 'PENDING'
                      ? 'bg-[#FDF8EC] hover:bg-[#FDF8EC]/80 text-[#D99A00] border border-[#D99A00]/30 shadow-sm'
                      : 'bg-white hover:bg-[#F8FAFD] text-[#0B1F3A] border border-[#E5EAF1] shadow-sm'
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
