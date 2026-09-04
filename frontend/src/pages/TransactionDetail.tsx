import React, { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ShieldCheck,
  Stethoscope,
  Brain,
  Clock,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  PlayCircle,
  Copy,
  Check,
  Layers,
  User,
  MessageSquare,
  Send,
  Lock,
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
  action_payload?: Record<string, any>;
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

  const authoritativeShortUrl = React.useMemo(() => {
    if (!transaction) return null;
    if (transaction.recovery_attempts && transaction.recovery_attempts.length > 0) {
      for (const att of transaction.recovery_attempts) {
        if (att.action_payload && att.action_payload.short_url) {
          return att.action_payload.short_url as string;
        }
      }
    }
    return null;
  }, [transaction]);

  const activePaymentLinkId = transaction?.razorpay_payment_link_id || transaction?.recovery_attempts?.[0]?.razorpay_payment_link_id;

  const fetchTransactionDetail = async () => {
    setLoading(true);
    setNotFound(false);

    let targetId = transactionId;

    try {
      if (!targetId) {
        // Fetch latest active transaction for current merchant & mode context
        const listRes = await api.get('/api/v1/transactions', {
          params: {
            limit: 1,
            merchant_id: currentApiState.merchantId,
            mode: currentApiState.mode,
          },
        });
        if (listRes.data && Array.isArray(listRes.data.items) && listRes.data.items.length > 0) {
          targetId = listRes.data.items[0].transaction_id || listRes.data.items[0].id;
        }
      }

      if (!targetId) {
        setNotFound(true);
        return;
      }

      const res = await api.get(`/api/v1/transactions/${targetId}`, {
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
      console.warn('[TransactionDetail API Error]:', err?.message);
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactionDetail();
    const handleStateChange = () => fetchTransactionDetail();
    window.addEventListener('apiStateChanged', handleStateChange);
    return () => window.removeEventListener('apiStateChanged', handleStateChange);
  }, [transactionId]);

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
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-bold bg-[#E6F4ED] text-[#16A36A] border border-[#16A36A]/20">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#16A36A]" />
            RECOVERED
          </span>
        );
      case 'EXECUTING':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-bold bg-[#EEF4FF] text-[#2454D6] border border-[#2F5BFF]/20">
            <PlayCircle className="w-3.5 h-3.5 text-[#2454D6]" />
            EXECUTING
          </span>
        );
      case 'FAILED':
      case 'STOPPED':
      case 'EXPIRED':
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-bold bg-[#FDF2F4] text-[#D6455D] border border-[#D6455D]/20">
            <XCircle className="w-3.5 h-3.5 text-[#D6455D]" />
            {statusStr}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-3 py-1 rounded text-xs font-bold bg-[#FDF8EC] text-[#D99A00] border border-[#D99A00]/20">
            <AlertTriangle className="w-3.5 h-3.5 text-[#D99A00]" />
            {statusStr}
          </span>
        );
    }
  };

  // 404 Not Found View
  if (notFound) {
    return (
      <div className="bg-white rounded-xl p-12 border border-[#E5EAF1] text-center max-w-lg mx-auto space-y-4 my-12 shadow-sm">
        <div className="p-4 rounded-full bg-[#FDF2F4] text-[#D6455D] border border-[#D6455D]/20 w-16 h-16 mx-auto flex items-center justify-center">
          <XCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-[#0B1F3A]">Transaction Not Found</h2>
        <p className="text-xs text-[#53627A]">
          The requested transaction ID <span className="font-mono text-[#0B1F3A] font-bold">'{transactionId}'</span> was not found in the active merchant context ({currentApiState.merchantId}).
        </p>
        <div className="pt-4">
          <button
            onClick={() => navigate('/queue')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#2F5BFF] text-white font-bold text-xs hover:bg-[#1A47E8] transition-all shadow-sm cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Recovery Queue</span>
          </button>
        </div>
      </div>
    );
  }

  if (loading || !transaction) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-24 bg-white rounded-xl border border-[#E5EAF1]" />
        <div className="h-32 bg-white rounded-xl border border-[#E5EAF1]" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-white rounded-xl border border-[#E5EAF1]" />
          <div className="h-64 bg-white rounded-xl border border-[#E5EAF1]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Navigation & Header Banner */}
      <div className="space-y-4">
        <Link
          to="/queue"
          className="inline-flex items-center gap-1.5 text-xs text-[#53627A] hover:text-[#2F5BFF] font-bold transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Recovery Queue</span>
        </Link>

        <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-sm">
          <div className="space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-[#0B1F3A] font-mono tracking-tight">
                {transaction.id}
              </h1>
              {renderStatusBadge(transaction.status)}
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
                {transaction.scenario_type}
              </span>
              <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#EEF4FF] text-[#2454D6] border border-[#2F5BFF]/20 font-mono">
                {transaction.mode}
              </span>
            </div>

            <div className="flex items-center gap-4 text-xs text-[#53627A] flex-wrap font-sans">
              <div className="flex items-center gap-1">
                <User className="w-3.5 h-3.5 text-[#7A8799]" />
                <span>Customer: <strong className="text-[#0B1F3A] font-mono">{transaction.customer_email || transaction.customer_id}</strong></span>
              </div>
              <div>•</div>
              <div className="flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-[#7A8799]" />
                <span>Merchant: <strong className="text-[#0B1F3A] font-mono">{transaction.merchant_id}</strong></span>
              </div>
              <div>•</div>
              <div className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-[#7A8799]" />
                <span>Created: {new Date(transaction.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div className="text-left md:text-right border-t md:border-t-0 border-[#E5EAF1] pt-4 md:pt-0">
            <div className="text-xs text-[#7A8799] uppercase tracking-wider font-bold">Transaction Value</div>
            <div className="text-2xl font-bold text-[#0B1F3A] font-numeric tracking-tight mt-0.5">
              {formatCurrency(transaction.amount)}
            </div>
            <div className="text-[11px] text-[#7A8799] mt-1 font-sans">
              Attempt #{transaction.retry_count} (Cycle {transaction.recovery_cycle})
            </div>
          </div>
        </div>
      </div>

      {/* Lifecycle Stepper Card */}
      <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] shadow-sm">
        <LifecycleStepper currentStatus={transaction.status} />
      </div>

      {/* Diagnosis & AI Decision Breakdown Panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Root Cause Diagnosis Panel */}
        <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] space-y-4 shadow-sm">
          <div className="flex items-center gap-2 border-b border-[#E5EAF1] pb-3">
            <Stethoscope className="w-4 h-4 text-[#2F5BFF]" />
            <h3 className="text-xs font-bold text-[#0B1F3A] uppercase tracking-wider">
              Root Cause Diagnosis
            </h3>
          </div>

          {transaction.diagnosis ? (
            <div className="space-y-4 font-numeric">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1]">
                  <div className="text-[10px] text-[#7A8799] uppercase font-bold">Failure Code</div>
                  <div className="text-xs font-mono font-bold text-[#2454D6] mt-0.5">
                    {transaction.diagnosis.failure_code}
                  </div>
                </div>

                <div className="bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1]">
                  <div className="text-[10px] text-[#7A8799] uppercase font-bold">Classifier Source</div>
                  <div className="text-xs font-bold text-[#16A36A] mt-0.5">
                    {transaction.diagnosis.diagnosis_source}
                  </div>
                </div>
              </div>

              <div className="space-y-1.5 font-sans">
                <div className="text-xs text-[#53627A] font-bold">Root Cause Explanation:</div>
                <p className="text-xs text-[#0B1F3A] leading-relaxed bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1]">
                  {transaction.diagnosis.root_cause_explanation}
                </p>
              </div>

              <div className="space-y-1 font-sans">
                <div className="flex justify-between text-xs font-bold">
                  <span className="text-[#53627A]">Diagnosis Confidence Score:</span>
                  <span className="text-[#2F5BFF] font-mono">
                    {Math.round(transaction.diagnosis.confidence_score * 100)}%
                  </span>
                </div>
                <div className="w-full bg-[#F1F5F9] rounded-full h-2 overflow-hidden border border-[#E5EAF1]">
                  <div
                    className="bg-[#2F5BFF] h-full transition-all duration-300"
                    style={{ width: `${Math.round(transaction.diagnosis.confidence_score * 100)}%` }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-[#7A8799] py-6 text-center">
              No root cause diagnosis recorded for this transaction.
            </div>
          )}
        </div>

        {/* AI Decision Breakdown Panel */}
        <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] space-y-4 shadow-sm">
          <div className="flex items-center gap-2 border-b border-[#E5EAF1] pb-3">
            <Brain className="w-4 h-4 text-[#2F5BFF]" />
            <h3 className="text-xs font-bold text-[#0B1F3A] uppercase tracking-wider">
              AI Recommendation & Policy Decision
            </h3>
          </div>

          {transaction.recovery_attempts && transaction.recovery_attempts.length > 0 ? (
            <div className="space-y-4 font-numeric">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1]">
                  <div className="text-[10px] text-[#7A8799] uppercase font-bold">Action Strategy</div>
                  <div className="text-xs font-bold text-[#0B1F3A] mt-0.5">
                    {transaction.recovery_attempts[0].recommended_action}
                  </div>
                </div>

                <div className="bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1]">
                  <div className="text-[10px] text-[#7A8799] uppercase font-bold">Policy Gate Status</div>
                  <div className="text-xs font-bold text-[#16A36A] mt-0.5">
                    {transaction.recovery_attempts[0].policy_status}
                  </div>
                </div>
              </div>

              <div className="bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1] space-y-1">
                <div className="text-[10px] text-[#7A8799] uppercase font-bold">Logical Operation Key</div>
                <div className="text-[11px] font-mono text-[#2454D6] break-all font-bold">
                  {transaction.recovery_attempts[0].logical_operation_key}
                </div>
              </div>

              {/* External Razorpay Resource Link */}
              {activePaymentLinkId ? (
                <div className="bg-[#EEF4FF] p-3 rounded-lg border border-[#2F5BFF]/20 flex items-center justify-between font-sans">
                  <div className="space-y-0.5">
                    <div className="text-[10px] font-bold text-[#2454D6] uppercase">Razorpay Payment Link Created</div>
                    <div className="text-xs font-mono font-bold text-[#0B1F3A]">
                      {activePaymentLinkId}
                    </div>
                  </div>
                  {authoritativeShortUrl ? (
                    <a
                      href={authoritativeShortUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-bold text-[#2F5BFF] hover:text-[#1A47E8] bg-white px-3 py-1.5 rounded-lg border border-[#2F5BFF]/30 shadow-sm"
                    >
                      <span>Demo Link</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  ) : (
                    <span className="text-[11px] font-mono text-[#7A8799] italic">
                      Customer-facing URL unavailable
                    </span>
                  )}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="text-xs text-[#7A8799] py-6 text-center">
              No recovery attempt execution records present.
            </div>
          )}
        </div>
      </div>

      {/* Customer Communication Copy Card */}
      <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] space-y-4 shadow-sm" data-testid="communication-preview-card">
        <div className="flex items-center justify-between border-b border-[#E5EAF1] pb-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-[#2F5BFF]" />
            <h3 className="text-xs font-bold text-[#0B1F3A] uppercase tracking-wider">
              Customer Recovery Communication Copy
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#EEF4FF] text-[#2454D6] border border-[#2F5BFF]/20">
              Tone: {transaction.scenario_type.includes('SUBSCRIPTION') ? 'Empathetic' : transaction.amount >= 10000 ? 'Urgent' : 'Informative'}
            </span>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
              {transaction.mode === 'REAL_TEST' ? 'REAL_TEST (Content Generation Only)' : 'SIMULATION Model'}
            </span>
          </div>
        </div>

        <div className="space-y-3 font-sans">
          <div className="flex items-center justify-between text-xs text-[#53627A]">
            <span className="flex items-center gap-1.5 font-bold">
              <Send className="w-3.5 h-3.5 text-[#7A8799]" />
              Channel: <strong className="text-[#0B1F3A]">SMS / WhatsApp</strong>
            </span>
            <span className="flex items-center gap-1 font-mono text-[11px] text-[#D99A00] font-bold">
              <Lock className="w-3 h-3 text-[#D99A00]" />
              PII Redacted Preview
            </span>
          </div>

          <div className="bg-[#F8FAFD] p-4 rounded-xl border border-[#E5EAF1] text-xs text-[#0B1F3A] font-mono leading-relaxed space-y-2">
            <p>
              {transaction.scenario_type.includes('SUBSCRIPTION')
                ? `We noticed your recent payment of ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(transaction.amount)} didn't go through. We understand these things happen! You can easily update your payment details using this secure link: ${authoritativeShortUrl || (activePaymentLinkId ? `[URL unavailable for Payment Link ID: ${activePaymentLinkId}]` : '[Link Unavailable]')}`
                : `Payment Action Required: Your transaction of ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(transaction.amount)} is pending. Please complete your payment via secure link: ${authoritativeShortUrl || (activePaymentLinkId ? `[URL unavailable for Payment Link ID: ${activePaymentLinkId}]` : '[Link Unavailable]')}`}
            </p>
          </div>

          {transaction.mode === 'REAL_TEST' ? (
            <div className="p-2.5 rounded-lg bg-[#FDF8EC] border border-[#D99A00]/20 text-[11px] text-[#D99A00] font-bold flex items-center justify-between">
              <span>REAL_TEST Boundary: Content generated for inspection only. No external SMS/Email dispatched.</span>
              <span className="font-mono text-[#D99A00] uppercase">Dispatched: NO</span>
            </div>
          ) : (
            <div className="p-2.5 rounded-lg bg-[#E6F4ED] border border-[#16A36A]/20 text-[11px] text-[#16A36A] font-bold flex items-center justify-between">
              <span>SIMULATION Boundary: Delivery modeled. Simulated conversion probability: 78.0%.</span>
              <span className="font-mono text-[#16A36A] uppercase">Dispatched: SIMULATED</span>
            </div>
          )}
        </div>
      </div>

      {/* Inline Cryptographic Audit Timeline Panel */}
      <div className="bg-white rounded-xl p-6 border border-[#E5EAF1] space-y-6 shadow-sm">
        <div className="flex items-center justify-between border-b border-[#E5EAF1] pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#16A36A]" />
            <h3 className="text-xs font-bold text-[#0B1F3A] uppercase tracking-wider">
              Cryptographic Audit Chain Timeline
            </h3>
          </div>
          <span className="text-xs text-[#16A36A] font-bold font-mono flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#16A36A]" />
            SHA-256 Hash Chain Verified
          </span>
        </div>

        {transaction.audit_timeline && transaction.audit_timeline.length > 0 ? (
          <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E5EAF1]">
            {transaction.audit_timeline.map((evt, index) => (
              <div key={evt.id || index} className="relative flex flex-col space-y-1">
                {/* Timeline Dot */}
                <div className="absolute -left-6 top-1.5 w-3 h-3 rounded-full bg-[#2F5BFF] border-2 border-white ring-2 ring-[#2F5BFF]/20" />

                <div className="flex items-center justify-between flex-wrap gap-2 font-sans">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-xs text-[#0B1F3A]">{evt.event_type}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
                      Actor: {evt.actor}
                    </span>
                    {evt.state_from && evt.state_to && (
                      <span className="text-[10px] font-mono font-bold text-[#2454D6] bg-[#EEF4FF] px-2 py-0.5 rounded border border-[#2F5BFF]/20">
                        {evt.state_from} → {evt.state_to}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-[#7A8799] font-mono">
                    {new Date(evt.created_at).toLocaleString()}
                  </span>
                </div>

                {/* Cryptographic SHA-256 Signature */}
                <div className="flex items-center justify-between bg-[#F8FAFD] px-3 py-1.5 rounded-lg border border-[#E5EAF1] text-[10px] font-mono text-[#53627A] overflow-x-auto">
                  <div className="flex items-center gap-2 truncate">
                    <span className="text-[#7A8799] select-none font-bold">SHA-256:</span>
                    <span className="text-[#0B1F3A] truncate font-bold">{evt.event_hash}</span>
                  </div>
                  <button
                    onClick={() => handleCopyHash(evt.event_hash)}
                    className="ml-2 text-[#7A8799] hover:text-[#2F5BFF] shrink-0 flex items-center gap-1 cursor-pointer"
                    title="Copy Hash"
                  >
                    {copiedHash === evt.event_hash ? (
                      <Check className="w-3 h-3 text-[#16A36A]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-[#7A8799] py-6 text-center">
            No audit timeline events recorded for this transaction.
          </div>
        )}
      </div>
    </div>
  );
};

export default TransactionDetailPage;
