/**
 * RecoverAI - AI Decision Center Dashboard Page (Step 32)
 *
 * Provides a detailed, transparent view of AI diagnosis, action-conditional ML scores,
 * ENRV calculations, LLM reasoning rationale, capability resolver status, and policy evaluation rules.
 * Consumes the GET /api/v1/ai-decisions/{transaction_id} backend REST API.
 *
 * AIR-GAPPED & READ-ONLY: Does NOT execute transactions, mutate payment state, or trigger Razorpay calls.
 */

import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  Cpu,
  ShieldCheck,
  Stethoscope,
  Clock,
  Sparkles,
  AlertTriangle,
  Search,
  ExternalLink,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Layers,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';

import { api, currentApiState } from '../services/api';
import { ENRVTable } from '../components/ENRVTable';
import { StrategyMatrix } from '../components/StrategyMatrix';

// TypeScript Interfaces matching backend Pydantic schemas
export interface ActionScoreItem {
  id?: string;
  action: string;
  recovery_probability: number;
  expected_gross_recovery: number;
  intervention_cost: number;
  expected_net_recovery_value: number;
  rank: number;
  capability_status: string;
  policy_status: string;
}

export interface AIDiagnosisSummary {
  id: string;
  failure_code: string;
  failure_category: string;
  root_cause_explanation: string;
  confidence_score: number;
  diagnosis_source: string;
  created_at: string;
}

export interface AIRecommendationSummary {
  recommended_action: string;
  rationale_text: string;
  customer_message_template: string;
  confidence_score: number;
}

export interface PolicyEvaluationSummary {
  policy_version: string;
  policy_status: string;
  reason: string;
  max_recovery_attempts: number;
  max_auto_action_amount: number;
  min_recovery_probability: number;
}

export interface CapabilityEvaluationSummary {
  execution_mode: string;
  is_executable: boolean;
  status: string;
  reason: string;
}

export interface AIDecisionResponse {
  transaction_id: string;
  merchant_id: string;
  decision_context_id?: string | null;
  model_version: string;
  feature_version: string;
  policy_version: string;
  created_at: string;
  top_action?: string | null;
  best_enrv_rupees?: number | null;
  diagnosis?: AIDiagnosisSummary | null;
  recommendation?: AIRecommendationSummary | null;
  action_scores: ActionScoreItem[];
  policy_evaluation?: PolicyEvaluationSummary | null;
  capability_evaluation?: CapabilityEvaluationSummary | null;
}

export const AIDecisionCenterPage: React.FC = () => {
  const { id: paramId } = useParams<{ id?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const explicitTxId = paramId || searchParams.get('tx') || searchParams.get('id');

  const [searchInput, setSearchInput] = useState<string>(explicitTxId || '');
  const [decisionData, setDecisionData] = useState<AIDecisionResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchAIDecision = async (txId: string) => {
    if (!txId.trim()) return;

    setLoading(true);
    setErrorStatus(null);
    setErrorMessage(null);

    try {
      const res = await api.get<AIDecisionResponse>(`/api/v1/ai-decisions/${txId.trim()}`, {
        params: {
          merchant_id: currentApiState.merchantId,
        },
      });
      setDecisionData(res.data);
    } catch (err: any) {
      console.warn('[AIDecisionCenter API Warning]:', err);
      const status = err.response?.status || 500;
      setErrorStatus(status);
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to retrieve AI Decision context from backend API.'
      );
      setDecisionData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const resolveAndFetch = async () => {
      let targetTxId = explicitTxId;

      if (!targetTxId) {
        try {
          const txRes = await api.get('/api/v1/transactions', {
            params: {
              merchant_id: currentApiState.merchantId,
              mode: currentApiState.mode,
              limit: 1,
            },
          });
          if (txRes.data?.items && txRes.data.items.length > 0) {
            targetTxId = txRes.data.items[0].transaction_id || txRes.data.items[0].id;
          }
        } catch (err) {
          console.warn('[AIDecisionCenter]: Failed to auto-resolve active transaction:', err);
        }
      }

      if (targetTxId) {
        if (isMounted) setSearchInput(targetTxId);
        await fetchAIDecision(targetTxId);
      } else {
        if (isMounted) {
          setLoading(false);
          setErrorStatus(404);
          setErrorMessage(`No transactions found for active merchant ${currentApiState.merchantId}.`);
          setDecisionData(null);
        }
      }
    };

    resolveAndFetch();
    const handleStateChange = () => {
      resolveAndFetch();
    };
    window.addEventListener('apiStateChanged', handleStateChange);
    return () => {
      isMounted = false;
      window.removeEventListener('apiStateChanged', handleStateChange);
    };
  }, [explicitTxId, currentApiState.merchantId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput.trim()) {
      navigate(`/ai-decision?tx=${encodeURIComponent(searchInput.trim())}`);
      fetchAIDecision(searchInput.trim());
    }
  };

  const formatINR = (val?: number | null) => {
    if (val === undefined || val === null) return '₹0.00';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(val);
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return 'N/A';
    try {
      return new Date(isoString).toLocaleString('en-IN', {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6 pb-12 font-sans" data-testid="ai-decision-center-page">
      {/* 1. TOP TITLE BANNER & SEARCH CONTROL */}
      <div className="fintech-card-hero p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-[#EEF6FF] border border-[#111827] rounded-xl text-[#2F66F5] shadow-xs">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-3xl font-extrabold text-[#0B1F44] tracking-tight">
                  <span className="text-gradient-highlight">AI Treatment</span> Decision Center
                </h1>
                <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#EEF6FF] text-[#2F66F5] border border-[#2F66F5]/20">
                  Step 32 Observability
                </span>
              </div>
              <p className="text-xs text-[#5E6B7E] mt-0.5 font-medium">
                Explainable model inference scores, ENRV calculations, and rule/LLM rationale
              </p>
            </div>
          </div>

          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2">
            <div className="relative">
              <Search className="w-4 h-4 text-[#5E6B7E] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Enter Transaction ID..."
                className="pl-9 pr-4 py-2 bg-white border border-[#111827] rounded-lg text-[#0B1F44] text-xs placeholder-[#5E6B7E] focus:outline-none focus:border-[#2F66F5] w-64 transition-all"
                data-testid="input-search-tx"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-[#2F66F5] hover:bg-[#1A47E8] text-white rounded-lg text-xs font-extrabold transition-all flex items-center space-x-1.5 shadow-sm cursor-pointer border border-[#111827]"
              data-testid="btn-search-tx"
            >
              <span>Inspect</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Air-gap execution safety disclaimer banner */}
        <div className="mt-4 pt-4 border-t border-[#E5EAF1] flex items-center justify-between text-xs text-[#53627A]">
          <div className="flex items-center space-x-2 text-[#0B1F3A] font-mono">
            <ShieldAlert className="w-4 h-4 text-[#D99A00] flex-shrink-0" />
            <span>
              <strong>Advisory Safety Boundary:</strong> AI Recommendation ≠ Financial Execution. Decision context is strictly read-only observability.
            </span>
          </div>
          <div className="flex items-center space-x-3 text-[#53627A]">
            <span>Mode: <strong className="text-[#0B1F3A]">{currentApiState.mode}</strong></span>
            <span>Merchant: <strong className="text-[#0B1F3A]">{currentApiState.merchantId.slice(0, 12)}...</strong></span>
          </div>
        </div>
      </div>

      {/* 2. LOADING SKELETON STATE */}
      {loading && (
        <div className="bg-white border border-[#E5EAF1] rounded-xl p-12 text-center" data-testid="ai-decision-loading">
          <RefreshCw className="w-8 h-8 text-[#2F5BFF] animate-spin mx-auto mb-4" />
          <p className="text-[#0B1F3A] font-bold">Retrieving AI Decision Context from Backend...</p>
          <p className="text-[#7A8799] text-xs mt-1">Evaluating candidate action scores, ENRV metrics, and policy guardrails</p>
        </div>
      )}

      {/* 3. ERROR & 404 STATES */}
      {!loading && errorStatus && (
        <div className="bg-white border border-[#E5EAF1] rounded-xl p-8 text-center shadow-sm" data-testid="ai-decision-error">
          {errorStatus === 404 ? (
            <div data-testid="ai-decision-404">
              <AlertTriangle className="w-12 h-12 text-[#D99A00] mx-auto mb-3" />
              <h3 className="text-lg font-bold text-[#0B1F3A] mb-2">Decision Context Not Found (HTTP 404)</h3>
              <p className="text-[#53627A] text-xs max-w-md mx-auto mb-6">
                No decision context or transaction record was found for ID <code className="text-[#D99A00] font-mono font-bold">{explicitTxId || searchInput}</code>.
              </p>
            </div>
          ) : (
            <div>
              <XCircle className="w-12 h-12 text-[#D6455D] mx-auto mb-3" />
              <h3 className="text-lg font-bold text-[#0B1F3A] mb-2">API Error ({errorStatus})</h3>
              <p className="text-[#53627A] text-xs max-w-md mx-auto mb-6">{errorMessage}</p>
            </div>
          )}
          <div className="flex items-center justify-center space-x-3">
            <button
              onClick={() => fetchAIDecision(explicitTxId || searchInput)}
              className="px-4 py-2 bg-white border border-[#E5EAF1] hover:bg-[#F8FAFD] text-[#0B1F3A] rounded-lg text-xs font-bold transition-colors cursor-pointer"
            >
              Retry Request
            </button>
            <Link
              to={`/transactions/${explicitTxId || searchInput}`}
              className="px-4 py-2 bg-[#2F5BFF] hover:bg-[#1A47E8] text-white rounded-lg text-xs font-bold transition-colors shadow-sm"
            >
              View Transaction Detail
            </Link>
          </div>
        </div>
      )}

      {/* 4. MAIN DECISION DASHBOARD CONTENT */}
      {!loading && decisionData && (
        <div className="space-y-6" data-testid="ai-decision-content">
          {/* HEADER / DECISION CONTEXT METADATA CARD */}
          <div className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm font-numeric" data-testid="decision-context-card">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Transaction ID</span>
                <Link
                  to={`/transactions/${decisionData.transaction_id}`}
                  className="font-mono text-sm font-bold text-[#2F5BFF] hover:underline flex items-center space-x-1 mt-1"
                  data-testid="link-transaction"
                >
                  <span>{decisionData.transaction_id}</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div>
                <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Decision Context ID</span>
                <span className="font-mono text-xs font-bold text-[#0B1F3A] block mt-1 truncate" title={decisionData.decision_context_id || 'Pending'}>
                  {decisionData.decision_context_id || 'Pending'}
                </span>
              </div>

              <div>
                <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Model & Feature Versions</span>
                <div className="flex items-center space-x-2 mt-1 font-sans">
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
                    Model: {decisionData.model_version}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-[#F8FAFD] text-[#53627A] border border-[#E5EAF1]">
                    Feat: {decisionData.feature_version}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Timestamp</span>
                <span className="text-xs font-semibold text-[#0B1F3A] flex items-center space-x-1 mt-1 font-sans">
                  <Clock className="w-3.5 h-3.5 text-[#7A8799]" />
                  <span>{formatDate(decisionData.created_at)}</span>
                </span>
              </div>
            </div>
          </div>

          {/* DIAGNOSIS & AI RECOMMENDATION SUMMARY GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* DIAGNOSIS PANEL */}
            <div className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm" data-testid="diagnosis-panel">
              <div className="flex items-center justify-between mb-4 border-b border-[#E5EAF1] pb-3">
                <div className="flex items-center space-x-2">
                  <Stethoscope className="w-4 h-4 text-[#2F5BFF]" />
                  <h3 className="text-base font-bold text-[#0B1F3A]">Root Cause Diagnosis</h3>
                </div>
                {decisionData.diagnosis && (
                  <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#EEF4FF] text-[#2454D6] border border-[#2F5BFF]/20">
                    Source: {decisionData.diagnosis.diagnosis_source}
                  </span>
                )}
              </div>

              {decisionData.diagnosis ? (
                <div className="space-y-4 font-numeric">
                  <div className="p-4 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg space-y-2">
                    <div className="flex items-center justify-between text-xs text-[#53627A]">
                      <span className="font-bold text-[#2454D6] uppercase tracking-wider">
                        {decisionData.diagnosis.failure_category} / {decisionData.diagnosis.failure_code}
                      </span>
                      <span>Confidence: <strong className="text-[#16A36A] font-mono font-bold">{(decisionData.diagnosis.confidence_score * 100).toFixed(0)}%</strong></span>
                    </div>
                    <p className="text-[#0B1F3A] text-xs leading-relaxed font-sans">
                      {decisionData.diagnosis.root_cause_explanation}
                    </p>
                  </div>
                  <div className="text-[11px] text-[#7A8799] flex items-center justify-between font-sans">
                    <span>Diagnosis ID: <code className="font-mono text-[#0B1F3A] font-bold">{decisionData.diagnosis.id.slice(0, 8)}...</code></span>
                    <span>Diagnosed: {formatDate(decisionData.diagnosis.created_at)}</span>
                  </div>
                </div>
              ) : (
                <div className="p-6 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg text-center text-[#7A8799] text-xs" data-testid="diagnosis-missing">
                  <AlertTriangle className="w-6 h-6 text-[#D99A00] mx-auto mb-2" />
                  No root cause diagnosis is currently recorded for this transaction.
                </div>
              )}
            </div>

            {/* RECOMMENDED ACTION & ENRV HIGHLIGHT CARD */}
            <div className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm" data-testid="recommendation-panel">
              <div className="flex items-center justify-between mb-4 border-b border-[#E5EAF1] pb-3">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-[#16A36A]" />
                  <h3 className="text-base font-bold text-[#0B1F3A]">AI Recommendation & ENRV</h3>
                </div>
                <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-[#E6F4ED] text-[#16A36A] border border-[#16A36A]/20">
                  Advisory Output
                </span>
              </div>

              <div className="space-y-4 font-numeric">
                <div className="grid grid-cols-2 gap-4 p-4 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg">
                  <div>
                    <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Recommended Strategy</span>
                    <span className="text-sm font-bold font-mono text-[#16A36A] mt-1 block" data-testid="recommended-action-title">
                      {decisionData.recommendation?.recommended_action || decisionData.top_action || 'PAYMENT_LINK'}
                    </span>
                  </div>
                  <div>
                    <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block">Max Net Recovery (ENRV)</span>
                    <span className="text-base font-bold text-[#16A36A] mt-1 block" data-testid="best-enrv-value">
                      {formatINR(decisionData.best_enrv_rupees)}
                    </span>
                  </div>
                </div>

                {decisionData.recommendation ? (
                  <div className="space-y-3 font-sans">
                    <div>
                      <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block mb-1">Diagnostic Rationale</span>
                      <p className="text-xs text-[#0B1F3A] bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1] leading-relaxed" data-testid="recommendation-rationale">
                        {decisionData.recommendation.rationale_text}
                      </p>
                    </div>

                    {decisionData.recommendation.customer_message_template && (
                      <div>
                        <span className="text-xs font-bold text-[#7A8799] uppercase tracking-wider block mb-1">Customer Nudge Message</span>
                        <p className="text-xs font-mono text-[#53627A] bg-[#F8FAFD] p-2.5 rounded-lg border border-[#E5EAF1] italic">
                          "{decisionData.recommendation.customer_message_template}"
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg text-center text-[#7A8799] text-xs">
                    Structured recommendation details pending. Primary ENRV rank optimization applies.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ACTION-CONDITIONAL ENRV SCORING TABLE */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <TrendingUp className="w-4 h-4 text-[#2F5BFF]" />
                <h3 className="text-base font-bold text-[#0B1F3A]">Action-Conditional ML Scores & ENRV Ranking</h3>
              </div>
              <span className="text-[11px] text-[#7A8799] font-mono">
                Formula: ENRV(a_i) = P(R | X, a_i) × Amount - InterventionCost
              </span>
            </div>

            <ENRVTable
              actionScores={decisionData.action_scores}
              topAction={decisionData.top_action}
              recommendedAction={decisionData.recommendation?.recommended_action}
            />
          </div>

          {/* RECOVERY STRATEGY VISUALIZATION MATRIX */}
          <StrategyMatrix
            activeDiagnosis={decisionData.diagnosis?.failure_code}
            activeAction={decisionData.recommendation?.recommended_action || decisionData.top_action || undefined}
          />

          {/* GUARDRAIL EVALUATION PANELS: CAPABILITY & POLICY */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* CAPABILITY EVALUATION PANEL */}
            <div className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm" data-testid="capability-panel">
              <div className="flex items-center justify-between mb-4 border-b border-[#E5EAF1] pb-3">
                <div className="flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-[#2F5BFF]" />
                  <h3 className="text-base font-bold text-[#0B1F3A]">Capability Resolver</h3>
                </div>
                {decisionData.capability_evaluation && (
                  <span
                    className={`px-2.5 py-0.5 rounded text-xs font-bold border ${
                      decisionData.capability_evaluation.is_executable
                        ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20'
                        : 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20'
                    }`}
                  >
                    {decisionData.capability_evaluation.status}
                  </span>
                )}
              </div>

              {decisionData.capability_evaluation ? (
                <div className="space-y-3 text-xs">
                  <div className="flex items-center justify-between p-3 bg-[#F8FAFD] rounded-lg border border-[#E5EAF1]">
                    <span className="text-[#53627A]">Execution Mode:</span>
                    <span className="font-mono font-bold text-[#0B1F3A]">{decisionData.capability_evaluation.execution_mode}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-[#F8FAFD] rounded-lg border border-[#E5EAF1]">
                    <span className="text-[#53627A]">Action Executable:</span>
                    <span className={`font-bold flex items-center space-x-1 ${decisionData.capability_evaluation.is_executable ? 'text-[#16A36A]' : 'text-[#D99A00]'}`}>
                      {decisionData.capability_evaluation.is_executable ? <CheckCircle2 className="w-4 h-4 mr-1 text-[#16A36A]" /> : <AlertTriangle className="w-4 h-4 mr-1 text-[#D99A00]" />}
                      {decisionData.capability_evaluation.is_executable ? 'Executable' : 'Not Executable'}
                    </span>
                  </div>
                  <p className="text-xs text-[#53627A] bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1] leading-relaxed font-mono">
                    {decisionData.capability_evaluation.reason}
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg text-center text-[#7A8799] text-xs">
                  Capability evaluation pending.
                </div>
              )}
            </div>

            {/* POLICY EVALUATION PANEL */}
            <div className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm" data-testid="policy-panel">
              <div className="flex items-center justify-between mb-4 border-b border-[#E5EAF1] pb-3">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-4 h-4 text-[#16A36A]" />
                  <h3 className="text-base font-bold text-[#0B1F3A]">Policy Engine Evaluation</h3>
                </div>
                {decisionData.policy_evaluation && (
                  <span
                    className={`px-2.5 py-0.5 rounded text-xs font-bold border ${
                      decisionData.policy_evaluation.policy_status === 'APPROVED'
                        ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20'
                        : 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20'
                    }`}
                  >
                    {decisionData.policy_evaluation.policy_status}
                  </span>
                )}
              </div>

              {decisionData.policy_evaluation ? (
                <div className="space-y-3 text-xs font-numeric">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2.5 bg-[#F8FAFD] rounded-lg border border-[#E5EAF1]">
                      <span className="text-[#7A8799] block mb-0.5 font-sans font-bold">Max Attempts</span>
                      <span className="font-mono font-bold text-[#0B1F3A]">{decisionData.policy_evaluation.max_recovery_attempts}</span>
                    </div>
                    <div className="p-2.5 bg-[#F8FAFD] rounded-lg border border-[#E5EAF1]">
                      <span className="text-[#7A8799] block mb-0.5 font-sans font-bold">Amount Cap</span>
                      <span className="font-mono font-bold text-[#0B1F3A]">{formatINR(decisionData.policy_evaluation.max_auto_action_amount)}</span>
                    </div>
                    <div className="p-2.5 bg-[#F8FAFD] rounded-lg border border-[#E5EAF1]">
                      <span className="text-[#7A8799] block mb-0.5 font-sans font-bold">Min P(R)</span>
                      <span className="font-mono font-bold text-[#16A36A]">{(decisionData.policy_evaluation.min_recovery_probability * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-[#53627A] bg-[#F8FAFD] p-3 rounded-lg border border-[#E5EAF1] leading-relaxed font-sans">
                    Rule Log: {decisionData.policy_evaluation.reason}
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg text-center text-[#7A8799] text-xs">
                  Policy evaluation pending.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIDecisionCenterPage;
