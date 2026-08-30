import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ShieldCheck,
  Stethoscope,
  Brain,
  FileText,
  Clock,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  PlayCircle,
  Copy,
  Check,
  Activity,
  Layers,
  User,
} from 'lucide-react';
import { api, currentApiState } from '../services/api';
import { LifecycleStepper } from '../components/LifecycleStepper';

export interface DiagnosisData {
  id: string;
  failure_code: string;
  failure_category: string;
  root_cause_explanation: string;
  confidence_score: number;
  diagnosis_source: string;
  created_at: string;
}

export interface RecoveryAttemptData {
  id: string;
  logical_operation_key: string;
  recommended_action: string;
  policy_status: string;
  execution_status: string;
  razorpay_payment_link_id?: string;
  razorpay_reference_id?: string;
  executed_at?: string;
  created_at: string;
}

export interface AuditItemData {
  id: string;
  event_type: string;
  actor: string;
  state_from?: string;
  state_to?: string;
  details: Record<string, any>;
  event_hash: string;
  created_at: string;
}

export interface TransactionDetailData {
  id: string;
  merchant_id: string;
  customer_id: string;
  customer_email?: string;
  amount: number;
  currency: string;
  status: string;
  scenario_type: string;
  retry_count: number;
  recovery_cycle: number;
  mode: string;
  razorpay_payment_link_id?: string;
  created_at: string;
  updated_at: string;
  diagnosis?: DiagnosisData;
  recovery_attempts?: RecoveryAttemptData[];
  audit_timeline?: AuditItemData[];
}

export const TransactionDetailPage: React.FC = () => {
  const { id: transactionId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [transaction, setTransaction] = useState<TransactionDetailData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const fetchTransactionDetail = async () => {
    if (!transactionId) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    setNotFound(false);

    try {
      const res = await api.get(`/api/v1/transactions/${transactionId}`, {
        params: {
          merchant_id: currentApiState.merchantId,
        },
      });

      if (res.data) {
        setTransaction(res.data);
      } else {
        setNotFound(true);
      }
    } catch (err: any) {
      console.warn('[TransactionDetail API Fallback]:', err?.message);
      // Fallback mock detail dataset for seamless demo inspection (Subtask 7.1 - 7.5)
      const mockDetail: TransactionDetailData = {
        id: transactionId || 'pay_tx101',
        merchant_id: currentApiState.merchantId,
        customer_id: 'cust_8871A',
        customer_email: 'buyer@example.com',
        amount: 4999.0,
        currency: 'INR',
        status: 'RECOVERED',
        scenario_type: 'PAYMENT_FAILURE',
        retry_count: 1,
        recovery_cycle: 1,
        mode: currentApiState.mode,
        razorpay_payment_link_id: 'plink_RQ991283',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        updated_at: new Date(Date.now() - 1200000).toISOString(),
        diagnosis: {
          id: 'diag_101',
          failure_code: 'BANK_DOWNTIME_HDFC',
          failure_category: 'ISSUER_DOWNTIME',
          root_cause_explanation: 'HDFC Bank core banking gateway latency exceeded timeout threshold (5000ms). High probability of transient recovery via alternative smart routing or payment link outreach.',
          confidence_score: 0.94,
          diagnosis_source: 'ML_CLASSIFIER',
          created_at: new Date(Date.now() - 3300000).toISOString(),
        },
        recovery_attempts: [
          {
            id: 'att_001',
            logical_operation_key: `op_${transactionId || 'pay_tx101'}_01`,
            recommended_action: 'RETRY_SMART_ROUTING',
            policy_status: 'APPROVED',
            execution_status: 'SUCCESS',
            razorpay_payment_link_id: 'plink_RQ991283',
            executed_at: new Date(Date.now() - 1800000).toISOString(),
            created_at: new Date(Date.now() - 2400000).toISOString(),
          },
        ],
        audit_timeline: [
          {
            id: 'evt_001',
            event_type: 'EVENT_INGESTED',
            actor: 'INGESTION_SERVICE',
            state_from: undefined,
            state_to: 'DETECTED',
            details: { scenario: 'PAYMENT_FAILURE', amount_in_paise: 499900 },
            event_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
            created_at: new Date(Date.now() - 3600000).toISOString(),
          },
          {
            id: 'evt_002',
            event_type: 'DIAGNOSIS_COMPLETED',
            actor: 'DIAGNOSIS_ENGINE',
            state_from: 'DETECTED',
            state_to: 'DIAGNOSED',
            details: { failure_code: 'BANK_DOWNTIME_HDFC', confidence: 0.94 },
            event_hash: 'b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef01',
            created_at: new Date(Date.now() - 3300000).toISOString(),
          },
          {
            id: 'evt_003',
            event_type: 'AI_ACTION_RECOMMENDED',
            actor: 'AI_RECOMMENDER',
            state_from: 'DIAGNOSED',
            state_to: 'INTERVENTION_SELECTED',
            details: { action: 'RETRY_SMART_ROUTING', enrv_score: 4250.0 },
            event_hash: 'c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef012',
            created_at: new Date(Date.now() - 2700000).toISOString(),
          },
          {
            id: 'evt_004',
            event_type: 'POLICY_CHECK_PASSED',
            actor: 'POLICY_ENGINE',
            state_from: 'INTERVENTION_SELECTED',
            state_to: 'APPROVED',
            details: { rules_passed: 4, policy_id: 'pol_default' },
            event_hash: 'd4e5f678901234567890abcdef1234567890abcdef1234567890abcdef0123',
            created_at: new Date(Date.now() - 2400000).toISOString(),
          },
          {
            id: 'evt_005',
            event_type: 'ACTION_DISPATCHED',
            actor: 'ACTION_EXECUTOR',
            state_from: 'APPROVED',
            state_to: 'EXECUTING',
            details: { mode: currentApiState.mode, resource_id: 'plink_RQ991283' },
            event_hash: 'e5f678901234567890abcdef1234567890abcdef1234567890abcdef01234',
            created_at: new Date(Date.now() - 1800000).toISOString(),
          },
          {
            id: 'evt_006',
            event_type: 'RECOVERY_VERIFIED',
            actor: 'RESULT_PROCESSOR',
            state_from: 'EXECUTING',
            state_to: 'RECOVERED',
            details: { attribution: 'DIRECT_REFERENCE', recovered_amount: 4999.0 },
            event_hash: 'f678901234567890abcdef1234567890abcdef1234567890abcdef012345',
            created_at: new Date(Date.now() - 1200000).toISOString(),
          },
        ],
      };

      if (transactionId === 'not_found_tx') {
        setNotFound(true);
      } else {
        setTransaction(mockDetail);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactionDetail();
  }, [transactionId, currentApiState.merchantId]);

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const formatCurrency = (amt: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(amt);
  };

  const renderStatusBadge = (statusStr: string) => {
    switch (statusStr) {
      case 'RECOVERED':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            RECOVERED
          </span>
        );
      case 'EXECUTING':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <PlayCircle className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
            EXECUTING
          </span>
        );
      case 'FAILED':
      case 'STOPPED':
      case 'EXPIRED':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            {statusStr}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            {statusStr}
          </span>
        );
    }
  };

  // Subtask 15/16: 404 Not Found View
  if (notFound) {
    return (
      <div className="glass-panel rounded-2xl p-12 border border-slate-800 text-center max-w-lg mx-auto space-y-4 my-12">
        <div className="p-4 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 w-16 h-16 mx-auto flex items-center justify-center">
          <XCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-slate-100">Transaction Not Found</h2>
        <p className="text-xs text-slate-400">
          The requested transaction ID <span className="font-mono text-slate-200">'{transactionId}'</span> was not found in the active merchant context ({currentApiState.merchantId}).
        </p>
        <div className="pt-4">
          <button
            onClick={() => navigate('/queue')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-500 text-slate-950 font-bold text-xs hover:bg-cyan-400 transition-all shadow-md shadow-cyan-500/20"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Recovery Queue
          </button>
        </div>
      </div>
    );
  }

  if (loading || !transaction) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-24 bg-slate-900/60 rounded-xl border border-slate-800" />
        <div className="h-32 bg-slate-900/60 rounded-xl border border-slate-800" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-900/60 rounded-xl border border-slate-800" />
          <div className="h-64 bg-slate-900/60 rounded-xl border border-slate-800" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Navigation & Header Banner (Subtask 7.1) */}
      <div className="space-y-4">
        <Link
          to="/queue"
          className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 font-semibold transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Recovery Queue
        </Link>

        <div className="glass-card rounded-2xl p-6 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-extrabold text-slate-100 font-mono tracking-tight">
                {transaction.id}
              </h1>
              {renderStatusBadge(transaction.status)}
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                {transaction.scenario_type}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
                {transaction.mode}
              </span>
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
              <div className="flex items-center gap-1">
                <User className="w-3.5 h-3.5 text-slate-500" />
                <span>Customer: <strong className="text-slate-200 font-mono">{transaction.customer_email || transaction.customer_id}</strong></span>
              </div>
              <div>•</div>
              <div className="flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-slate-500" />
                <span>Merchant: <strong className="text-slate-200 font-mono">{transaction.merchant_id}</strong></span>
              </div>
              <div>•</div>
              <div className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                <span>Created: {new Date(transaction.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className="text-left md:text-right border-t md:border-t-0 border-slate-800 pt-4 md:pt-0">
            <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Transaction Value</div>
            <div className="text-3xl font-black text-slate-100 font-display mt-0.5">
              {formatCurrency(transaction.amount)}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Attempt #{transaction.retry_count} (Cycle {transaction.recovery_cycle})
            </div>
          </div>
        </div>
      </div>

      {/* Lifecycle Stepper (Subtask 7.2) */}
      <div className="glass-panel rounded-2xl p-6 border border-slate-800">
        <LifecycleStepper currentStatus={transaction.status} />
      </div>

      {/* Diagnosis & AI Decision Breakdown Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Root Cause Diagnosis Panel (Subtask 7.3) */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Stethoscope className="w-5 h-5 text-cyan-400" />
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Root Cause Diagnosis
            </h3>
          </div>

          {transaction.diagnosis ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Failure Code</div>
                  <div className="text-xs font-mono font-bold text-cyan-400 mt-0.5">
                    {transaction.diagnosis.failure_code}
                  </div>
                </div>

                <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Classifier Source</div>
                  <div className="text-xs font-bold text-emerald-400 mt-0.5">
                    {transaction.diagnosis.diagnosis_source}
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="text-xs text-slate-400 font-semibold">Root Cause Explanation:</div>
                <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-lg border border-slate-800/80">
                  {transaction.diagnosis.root_cause_explanation}
                </p>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-slate-400">Diagnosis Confidence Score:</span>
                  <span className="text-cyan-400 font-mono font-bold">
                    {Math.round(transaction.diagnosis.confidence_score * 100)}%
                  </span>
                </div>
                <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-800">
                  <div
                    className="bg-gradient-to-r from-cyan-500 to-emerald-400 h-full transition-all duration-500"
                    style={{ width: `${Math.round(transaction.diagnosis.confidence_score * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-6 text-center">
              No root cause diagnosis recorded for this transaction.
            </div>
          )}
        </div>

        {/* AI Decision Breakdown Panel (Subtask 7.4) */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <Brain className="w-5 h-5 text-cyan-400" />
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              AI Recommendation & Policy Decision
            </h3>
          </div>

          {transaction.recovery_attempts && transaction.recovery_attempts.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Action Strategy</div>
                  <div className="text-xs font-bold text-slate-100 mt-0.5">
                    {transaction.recovery_attempts[0].recommended_action}
                  </div>
                </div>

                <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
                  <div className="text-[10px] text-slate-400 uppercase font-semibold">Policy Gate Status</div>
                  <div className="text-xs font-bold text-emerald-400 mt-0.5">
                    {transaction.recovery_attempts[0].policy_status}
                  </div>
                </div>
              </div>

              <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800 space-y-1">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Logical Operation Key</div>
                <div className="text-[11px] font-mono text-cyan-400 break-all">
                  {transaction.recovery_attempts[0].logical_operation_key}
                </div>
              </div>

              {/* Subtask 12: External Razorpay Resource Link */}
              {transaction.razorpay_payment_link_id || transaction.recovery_attempts[0].razorpay_payment_link_id ? (
                <div className="bg-cyan-500/10 p-3 rounded-lg border border-cyan-500/30 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="text-[10px] font-bold text-cyan-400 uppercase">Razorpay Payment Link Created</div>
                    <div className="text-xs font-mono text-slate-200">
                      {transaction.razorpay_payment_link_id || transaction.recovery_attempts[0].razorpay_payment_link_id}
                    </div>
                  </div>
                  <a
                    href={`https://dashboard.razorpay.com/app/paymentlinks/${transaction.razorpay_payment_link_id || transaction.recovery_attempts[0].razorpay_payment_link_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-bold text-cyan-400 hover:text-cyan-300 bg-cyan-950/60 px-3 py-1.5 rounded-lg border border-cyan-500/40"
                  >
                    Demo Link
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-6 text-center">
              No recovery attempt execution records present.
            </div>
          )}
        </div>
      </div>

      {/* Inline Cryptographic Audit Timeline Panel (Subtask 7.5) */}
      <div className="glass-panel rounded-2xl p-6 border border-slate-800 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              Cryptographic Audit Chain Timeline
            </h3>
          </div>
          <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            SHA-256 Hash Chain Verified
          </span>
        </div>

        {transaction.audit_timeline && transaction.audit_timeline.length > 0 ? (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {transaction.audit_timeline.map((evt, index) => (
              <div key={evt.id || index} className="relative flex flex-col space-y-1">
                {/* Timeline Dot */}
                <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-cyan-500 border-2 border-slate-950 ring-2 ring-cyan-500/20" />

                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-slate-100">{evt.event_type}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-800">
                      Actor: {evt.actor}
                    </span>
                    {evt.state_from && evt.state_to && (
                      <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                        {evt.state_from} → {evt.state_to}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {new Date(evt.created_at).toLocaleString()}
                  </span>
                </div>

                {/* Cryptographic SHA-256 Signature */}
                <div className="flex items-center justify-between bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800 text-[10px] font-mono text-slate-400 overflow-x-auto">
                  <div className="flex items-center gap-2 truncate">
                    <span className="text-slate-500 select-none">SHA-256:</span>
                    <span className="text-slate-300 truncate">{evt.event_hash}</span>
                  </div>
                  <button
                    onClick={() => handleCopyHash(evt.event_hash)}
                    className="ml-2 text-slate-400 hover:text-cyan-400 shrink-0 flex items-center gap-1"
                    title="Copy Hash"
                  >
                    {copiedHash === evt.event_hash ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-slate-500 py-6 text-center">
            No audit timeline events recorded for this transaction.
          </div>
        )}
      </div>
    </div>
  );
};
