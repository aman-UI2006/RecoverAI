import React, { useState } from 'react';
import {
  X,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  User,
  FileText,
  Clock,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/80">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Inspect & Action Review</h2>
              <p className="text-xs text-slate-400">Authorization & Manual Decision Control</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {/* Error Alert Display */}
          {(errorAlert || validationError) && (
            <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 flex items-start space-x-3 text-red-400 text-sm">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Action Submission Error</p>
                <p className="text-xs text-red-300/80 mt-0.5">{errorAlert || validationError}</p>
              </div>
            </div>
          )}

          {/* Transaction Metadata Card */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-semibold text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-md border border-indigo-500/20">
                  Tx: {item.transaction_id}
                </span>
                <span className="text-xs font-medium text-slate-400">
                  Merchant: <span className="text-slate-200">{item.merchant_id}</span>
                </span>
              </div>
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                item.mode === 'REAL_TEST'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
              }`}>
                {item.mode}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-800/60 text-sm">
              <div>
                <span className="text-xs text-slate-400 block">Amount</span>
                <span className="text-base font-bold text-white font-mono">
                  ₹{item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-400 block">Scenario Type</span>
                <span className="text-xs font-medium text-amber-300 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20 inline-block mt-0.5">
                  {item.scenario_type}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-400 block">Escalated At</span>
                <span className="text-xs text-slate-300 font-mono">
                  {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          {/* Escalation Reason Box */}
          <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
            <div className="flex items-center space-x-2 text-amber-400 text-xs font-semibold uppercase tracking-wider">
              <Zap className="w-4 h-4" />
              <span>Escalation Reason Code</span>
            </div>
            <p className="text-sm font-medium text-amber-200 font-mono bg-slate-950/80 p-2.5 rounded-lg border border-amber-500/10">
              {item.reason}
            </p>
          </div>

          {/* Deep Inspection Links */}
          <div className="flex items-center space-x-4 text-xs">
            <Link
              to={`/transactions/${item.transaction_id}`}
              target="_blank"
              className="flex items-center space-x-1.5 text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>View Full Lifecycle Stepper</span>
            </Link>
            <Link
              to={`/ai-decision/${item.transaction_id}`}
              target="_blank"
              className="flex items-center space-x-1.5 text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Inspect AI Diagnosis & ENRV Rationale</span>
            </Link>
          </div>

          {/* Decision Form Controls (Only active if PENDING) */}
          {!isResolved ? (
            <div className="space-y-4 pt-2 border-t border-slate-800">
              <div>
                <label htmlFor="reviewerId" className="block text-xs font-medium text-slate-300 mb-1 flex items-center space-x-1">
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span>Reviewer Operator ID / Authorization Name *</span>
                </label>
                <input
                  id="reviewerId"
                  type="text"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                  placeholder="e.g. rev_operator_01"
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label htmlFor="reviewerNotes" className="block text-xs font-medium text-slate-300 mb-1 flex items-center space-x-1">
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  <span>Decision Rationale / Audit Notes</span>
                </label>
                <textarea
                  id="reviewerNotes"
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="State operational justification for override or termination..."
                  className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Current Status</span>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                  item.status === 'APPROVED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                  item.status === 'REJECTED' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                  'bg-slate-800 text-slate-400'
                }`}>
                  {item.status} ({item.decision})
                </span>
              </div>
              <div className="text-xs text-slate-300">
                <span className="text-slate-500">Reviewer:</span> {item.reviewer_id || 'System'}
              </div>
              {item.notes && (
                <div className="text-xs text-slate-300 bg-slate-900 p-2 rounded border border-slate-800 mt-1">
                  <span className="text-slate-500 block">Notes:</span>
                  {item.notes}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Action Buttons */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-slate-800 bg-slate-900/80">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white bg-slate-800/60 hover:bg-slate-800 rounded-lg transition-colors"
          >
            Close
          </button>

          {!isResolved && (
            <div className="flex items-center space-x-3">
              <button
                onClick={() => handleAction('REJECT_PERMANENT')}
                disabled={isSubmitting}
                className="flex items-center space-x-2 px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-500 active:bg-red-700 disabled:opacity-50 rounded-lg transition-colors shadow-lg shadow-red-600/20"
              >
                <XCircle className="w-4 h-4" />
                <span>{isSubmitting ? 'Processing...' : 'REJECT_PERMANENT (Terminate)'}</span>
              </button>

              <button
                onClick={() => handleAction('APPROVE_OVERRIDE')}
                disabled={isSubmitting}
                className="flex items-center space-x-2 px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 rounded-lg transition-colors shadow-lg shadow-emerald-600/20"
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
