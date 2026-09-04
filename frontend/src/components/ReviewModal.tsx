import React, { useState } from 'react';
import {
  X,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  User,
  FileText,
  ShieldAlert,
  Zap,
  ExternalLink
} from 'lucide-react';
import { Link } from 'react-router-dom';

export interface HumanReviewItem {
  id: string;
  transaction_id: string;
  merchant_id: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED' | string;
  reason: string;
  reviewer_id?: string | null;
  decision?: 'APPROVE_OVERRIDE' | 'REJECT_PERMANENT' | string | null;
  notes?: string | null;
  reviewed_at?: string | null;
  created_at: string;
  amount: number;
  currency: string;
  scenario_type: string;
  mode: 'SIMULATION' | 'REAL_TEST' | string;
}

interface ReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: HumanReviewItem | null;
  onSubmitDecision: (
    reviewId: string,
    decision: 'APPROVE_OVERRIDE' | 'REJECT_PERMANENT',
    reviewerId: string,
    notes: string
  ) => Promise<void>;
  isSubmitting: boolean;
  errorAlert?: string | null;
}

export const ReviewModal: React.FC<ReviewModalProps> = ({
  isOpen,
  onClose,
  item,
  onSubmitDecision,
  isSubmitting,
  errorAlert
}) => {
  const [reviewerId, setReviewerId] = useState('rev_operator_01');
  const [notes, setNotes] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  if (!isOpen || !item) return null;

  const handleAction = async (decision: 'APPROVE_OVERRIDE' | 'REJECT_PERMANENT') => {
    if (!reviewerId.trim()) {
      setValidationError('Reviewer ID is required for audit authorization');
      return;
    }
    setValidationError(null);
    await onSubmitDecision(item.id, decision, reviewerId.trim(), notes.trim());
  };

  const isResolved = item.status !== 'PENDING';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#0B1F3A]/40 backdrop-blur-sm font-sans">
      <div className="relative w-full max-w-2xl bg-white border border-[#E5EAF1] rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E5EAF1] bg-white">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-[#FDF8EC] border border-[#D99A00]/20 text-[#D99A00]">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#0B1F3A]">Inspect & Action Review</h2>
              <p className="text-xs text-[#53627A]">Authorization & Manual Decision Control</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#7A8799] hover:text-[#0B1F3A] hover:bg-[#F8FAFD] transition-colors cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Error Alert Display */}
          {(errorAlert || validationError) && (
            <div className="p-4 rounded-lg bg-[#FDF2F4] border border-[#D6455D]/20 flex items-start space-x-3 text-[#D6455D] text-xs font-bold">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Action Submission Error</p>
                <p className="text-xs text-[#D6455D] mt-0.5 font-normal">{errorAlert || validationError}</p>
              </div>
            </div>
          )}

          {/* Transaction Metadata Card */}
          <div className="p-4 rounded-lg bg-[#F8FAFD] border border-[#E5EAF1] space-y-3 font-numeric">
            <div className="flex flex-wrap items-center justify-between gap-2 font-sans">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-bold text-[#2454D6] bg-[#EEF4FF] px-2.5 py-0.5 rounded border border-[#2F5BFF]/20">
                  Tx: {item.transaction_id}
                </span>
                <span className="text-xs font-bold text-[#53627A]">
                  Merchant: <span className="text-[#0B1F3A] font-mono">{item.merchant_id}</span>
                </span>
              </div>
              <span className={`text-[11px] px-2.5 py-0.5 rounded font-bold border ${
                item.mode === 'REAL_TEST'
                  ? 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20'
                  : 'bg-[#EEF4FF] text-[#2454D6] border-[#2F5BFF]/20'
              }`}>
                {item.mode}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-2 border-t border-[#E5EAF1] text-xs">
              <div>
                <span className="text-[10px] text-[#7A8799] uppercase font-bold font-sans block">Amount</span>
                <span className="text-base font-bold text-[#0B1F3A]">
                  ₹{item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="font-sans">
                <span className="text-[10px] text-[#7A8799] uppercase font-bold block">Scenario Type</span>
                <span className="text-xs font-bold text-[#D99A00] bg-[#FDF8EC] px-2 py-0.5 rounded border border-[#D99A00]/20 inline-block mt-0.5 font-mono">
                  {item.scenario_type}
                </span>
              </div>
              <div className="font-sans">
                <span className="text-[10px] text-[#7A8799] uppercase font-bold block">Escalated At</span>
                <span className="text-xs text-[#0B1F3A] font-bold">
                  {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Escalation Reason Box */}
          <div className="p-4 rounded-lg bg-[#FDF8EC] border border-[#D99A00]/20 space-y-2">
            <div className="flex items-center space-x-2 text-[#D99A00] text-[10px] font-bold uppercase tracking-wider">
              <Zap className="w-3.5 h-3.5" />
              <span>Escalation Reason Code</span>
            </div>
            <p className="text-xs font-bold text-[#0B1F3A] font-mono bg-white p-2.5 rounded border border-[#D99A00]/20">
              {item.reason}
            </p>
          </div>

          {/* Deep Inspection Links */}
          <div className="flex items-center space-x-4 text-xs font-bold">
            <Link
              to={`/transactions/${item.transaction_id}`}
              target="_blank"
              className="flex items-center space-x-1.5 text-[#2F5BFF] hover:text-[#1A47E8] transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>View Full Lifecycle Stepper</span>
            </Link>
            <Link
              to={`/ai-decision/${item.transaction_id}`}
              target="_blank"
              className="flex items-center space-x-1.5 text-[#2F5BFF] hover:text-[#1A47E8] transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Inspect AI Diagnosis & ENRV Rationale</span>
            </Link>
          </div>

          {/* Decision Form Controls (Only active if PENDING) */}
          {!isResolved ? (
            <div className="space-y-4 pt-2 border-t border-[#E5EAF1]">
              <div>
                <label htmlFor="reviewerId" className="block text-xs font-bold text-[#0B1F3A] mb-1 flex items-center space-x-1">
                  <User className="w-3.5 h-3.5 text-[#7A8799]" />
                  <span>Reviewer Operator ID / Authorization Name *</span>
                </label>
                <input
                  id="reviewerId"
                  type="text"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="e.g. rev_operator_01"
                  className="w-full px-3 py-2 rounded-lg bg-white border border-[#E5EAF1] text-xs text-[#0B1F3A] font-mono font-bold focus:outline-none focus:border-[#2F5BFF]/50"
                />
              </div>

              <div>
                <label htmlFor="reviewerNotes" className="block text-xs font-bold text-[#0B1F3A] mb-1 flex items-center space-x-1">
                  <FileText className="w-3.5 h-3.5 text-[#7A8799]" />
                  <span>Decision Rationale / Audit Notes</span>
                </label>
                <textarea
                  id="reviewerNotes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="State operational justification for override or termination..."
                  className="w-full px-3 py-2 rounded-lg bg-white border border-[#E5EAF1] text-xs text-[#0B1F3A] focus:outline-none focus:border-[#2F5BFF]/50 resize-none"
                />
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-[#F8FAFD] border border-[#E5EAF1] space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-[#53627A] font-bold">Current Status</span>
                <span className={`text-[11px] px-2.5 py-0.5 rounded font-bold border ${
                  item.status === 'APPROVED' ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20' :
                  item.status === 'REJECTED' ? 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20' :
                  'bg-[#F8FAFD] text-[#7A8799] border-[#E5EAF1]'
                }`}>
                  {item.status} ({item.decision})
                </span>
              </div>
              <div className="text-xs text-[#0B1F3A] font-numeric font-bold">
                <span className="text-[#7A8799] font-sans">Reviewer:</span> {item.reviewer_id || 'System'}
              </div>
              {item.notes && (
                <div className="text-xs text-[#0B1F3A] bg-white p-2 rounded border border-[#E5EAF1] mt-1">
                  <span className="text-[#7A8799] block text-[10px] uppercase font-bold">Notes:</span>
                  {item.notes}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Action Buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-[#E5EAF1] bg-white">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs font-bold text-[#53627A] hover:text-[#0B1F3A] bg-white hover:bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg transition-all cursor-pointer shadow-sm"
          >
            Close
          </button>

          {!isResolved && (
            <div className="flex items-center space-x-3">
              <button
                onClick={() => handleAction('REJECT_PERMANENT')}
                disabled={isSubmitting}
                className="flex items-center space-x-2 px-4 py-2 text-xs font-bold text-white bg-[#D6455D] hover:bg-[#B53449] disabled:opacity-50 rounded-lg transition-all shadow-sm cursor-pointer"
              >
                <XCircle className="w-4 h-4" />
                <span>{isSubmitting ? 'Processing...' : 'REJECT_PERMANENT (Terminate)'}</span>
              </button>

              <button
                onClick={() => handleAction('APPROVE_OVERRIDE')}
                disabled={isSubmitting}
                className="flex items-center space-x-2 px-4 py-2 text-xs font-bold text-white bg-[#16A36A] hover:bg-[#0D633F] disabled:opacity-50 rounded-lg transition-all shadow-sm cursor-pointer"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>{isSubmitting ? 'Processing...' : 'APPROVE_OVERRIDE (Force Execution)'}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
