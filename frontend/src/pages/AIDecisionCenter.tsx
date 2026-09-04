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
  Brain,
  Cpu,
  ShieldCheck,
  Stethoscope,
  Clock,
  Sparkles,
  AlertTriangle,
  Search,
  ExternalLink,
  Info,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Layers,
  FileCode,
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
    return () => {
      isMounted = false;
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
    <div className="space-y-6 pb-12" data-testid="ai-decision-center-page">
      {/* 1. TOP TITLE BANNER & SEARCH CONTROL */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
              <Cpu className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-bold text-slate-100">AI Decision Center</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Step 32 Observability
                </span>
              </div>
              <p className="text-slate-400 text-sm mt-0.5">
                Explainable model inference scores, ENRV calculations, and rule/LLM rationale
              </p>
            </div>
          </div>

          {/* Search Box */}
          <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Enter Transaction ID..."
                className="pl-9 pr-4 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-slate-200 text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-64"
                data-testid="input-search-tx"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition-colors flex items-center space-x-1.5 shadow-lg shadow-indigo-600/20"
              data-testid="btn-search-tx"
            >
              <span>Inspect</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* Air-gap execution safety disclaimer banner */}
        <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-2 text-indigo-300/90 font-mono">
            <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>
              <strong>Advisory Safety Boundary:</strong> AI Recommendation $\neq$ Financial Execution. Decision context is strictly read-only observability.
            </span>
          </div>
          <div className="flex items-center space-x-3 text-slate-400">
            <span>Mode: <strong className="text-slate-200">{currentApiState.mode}</strong></span>
            <span>Merchant: <strong className="text-slate-200">{currentApiState.merchantId.slice(0, 12)}...</strong></span>
          </div>
        </div>
      </div>

      {/* 2. LOADING SKELETON STATE */}
      {loading && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-12 text-center" data-testid="ai-decision-loading">
          <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin mx-auto mb-4" />
          <p className="text-slate-300 font-medium">Retrieving AI Decision Context from Backend...</p>
          <p className="text-slate-500 text-sm mt-1">Evaluating candidate action scores, ENRV metrics, and policy guardrails</p>
        </div>
      )}

      {/* 3. ERROR & 404 STATES */}
      {!loading && errorStatus && (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-8 text-center" data-testid="ai-decision-error">
          {errorStatus === 404 ? (
            <div data-testid="ai-decision-404">
              <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
              <h3 className="text-xl font-bold text-slate-200 mb-2">Decision Context Not Found (HTTP 404)</h3>
              <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">
                No decision context or transaction record was found for ID <code className="text-amber-300 font-mono">{explicitTxId || searchInput}</code>.
              </p>
            </div>
          ) : (
            <div>
              <XCircle className="w-12 h-12 text-rose-400 mx-auto mb-3" />
              <h3 className="text-xl font-bold text-slate-200 mb-2">API Error ({errorStatus})</h3>
              <p className="text-slate-400 text-sm max-w-md mx-auto mb-6">{errorMessage}</p>
            </div>
          )}
          <div className="flex items-center justify-center space-x-3">
            <button
              onClick={() => fetchAIDecision(explicitTxId || searchInput)}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-sm font-semibold transition-colors"
            >
              Retry Request
            </button>
            <Link
              to={`/transactions/${explicitTxId || searchInput}`}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition-colors"
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
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md" data-testid="decision-context-card">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Transaction ID</span>
                <Link
                  to={`/transactions/${decisionData.transaction_id}`}
                  className="font-mono text-base font-bold text-indigo-400 hover:underline flex items-center space-x-1 mt-1"
                  data-testid="link-transaction"
                >
                  <span>{decisionData.transaction_id}</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Decision Context ID</span>
                <span className="font-mono text-sm font-semibold text-slate-200 block mt-1 truncate" title={decisionData.decision_context_id || 'Pending'}>
                  {decisionData.decision_context_id || 'Pending'}
                </span>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Model & Feature Versions</span>
                <div className="flex items-center space-x-2 mt-1">
                  <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                    Model: {decisionData.model_version}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                    Feat: {decisionData.feature_version}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Timestamp</span>
                <span className="text-sm font-medium text-slate-300 flex items-center space-x-1 mt-1">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  <span>{formatDate(decisionData.created_at)}</span>
                </span>
              </div>
            </div>
          </div>

          {/* DIAGNOSIS & AI RECOMMENDATION SUMMARY GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* DIAGNOSIS PANEL */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md" data-testid="diagnosis-panel">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Stethoscope className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-lg font-semibold text-slate-100">Root Cause Diagnosis</h3>
                </div>
                {decisionData.diagnosis && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    Source: {decisionData.diagnosis.diagnosis_source}
                  </span>
                )}
              </div>

              {decisionData.diagnosis ? (
                <div className="space-y-4">
                  <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span className="font-semibold text-indigo-300 uppercase tracking-wider">
                        {decisionData.diagnosis.failure_category} / {decisionData.diagnosis.failure_code}
                      </span>
                      <span>Confidence: <strong className="text-emerald-400 font-mono">{(decisionData.diagnosis.confidence_score * 100).toFixed(0)}%</strong></span>
                    </div>
                    <p className="text-slate-200 text-sm font-medium leading-relaxed">
                      {decisionData.diagnosis.root_cause_explanation}
                    </p>
                  </div>
                  <div className="text-xs text-slate-400 flex items-center justify-between">
                    <span>Diagnosis ID: <code className="font-mono text-slate-300">{decisionData.diagnosis.id.slice(0, 8)}...</code></span>
                    <span>Diagnosed: {formatDate(decisionData.diagnosis.created_at)}</span>
                  </div>
                </div>
              ) : (
                <div className="p-6 bg-slate-950/40 rounded-xl text-center text-slate-400 text-sm" data-testid="diagnosis-missing">
                  <AlertTriangle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
                  No root cause diagnosis is currently recorded for this transaction.
                </div>
              )}
            </div>

            {/* RECOMMENDED ACTION & ENRV HIGHLIGHT CARD */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md" data-testid="recommendation-panel">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-lg font-semibold text-slate-100">AI Recommendation & ENRV</h3>
                </div>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  Advisory Output
                </span>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 p-4 bg-slate-950/80 border border-slate-800 rounded-xl">
                  <div>
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Recommended Strategy</span>
                    <span className="text-base font-bold font-mono text-emerald-400 mt-1 block" data-testid="recommended-action-title">
                      {decisionData.recommendation?.recommended_action || decisionData.top_action || 'PAYMENT_LINK'}
                    </span>
                  </div>
                  <div>
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Max Net Recovery (ENRV)</span>
                    <span className="text-base font-bold font-mono text-emerald-300 mt-1 block" data-testid="best-enrv-value">
                      {formatINR(decisionData.best_enrv_rupees)}
                    </span>
                  </div>
                </div>

                {decisionData.recommendation ? (
                  <div className="space-y-3">
                    <div>
                      <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">Diagnostic Rationale</span>
                      <p className="text-sm text-slate-300 bg-slate-950/50 p-3 rounded-lg border border-slate-800/60 leading-relaxed font-sans" data-testid="recommendation-rationale">
                        {decisionData.recommendation.rationale_text}
                      </p>
                    </div>

                    {decisionData.recommendation.customer_message_template && (
                      <div>
                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">Customer Nudge Message</span>
                        <p className="text-xs font-mono text-slate-400 bg-slate-950/80 p-2.5 rounded-lg border border-slate-800/80 italic">
                          "{decisionData.recommendation.customer_message_template}"
                        </p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 bg-slate-950/40 rounded-xl text-center text-slate-400 text-sm">
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
                <TrendingUp className="w-5 h-5 text-indigo-400" />
                <h3 className="text-lg font-semibold text-slate-100">Action-Conditional ML Scores & ENRV Ranking</h3>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                Formula: ENRV(a_i) = P(R | X, a_i) × Amount - InterventionCost
              </span>
            </div>

            <ENRVTable
              actionScores={decisionData.action_scores}
              topAction={decisionData.top_action}
              recommendedAction={decisionData.recommendation?.recommended_action}
            />
          </div>

          {/* RECOVERY STRATEGY VISUALIZATION MATRIX (Step 47) */}
          <StrategyMatrix
            activeDiagnosis={decisionData.diagnosis?.failure_code}
            activeAction={decisionData.recommendation?.recommended_action || decisionData.top_action || undefined}
          />

          {/* GUARDRAIL EVALUATION PANELS: CAPABILITY & POLICY */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* CAPABILITY EVALUATION PANEL */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md" data-testid="capability-panel">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <Layers className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-lg font-semibold text-slate-100">Capability Resolver</h3>
                </div>
                {decisionData.capability_evaluation && (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                      decisionData.capability_evaluation.is_executable
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}
                  >
                    {decisionData.capability_evaluation.status}
                  </span>
                )}
              </div>

              {decisionData.capability_evaluation ? (
                <div className="space-y-3 text-sm">
                  <div className="flex items-center justify-between p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400">Execution Mode:</span>
                    <span className="font-mono font-bold text-slate-200">{decisionData.capability_evaluation.execution_mode}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-950/80 rounded-xl border border-slate-800">
                    <span className="text-slate-400">Action Executable:</span>
                    <span className={`font-semibold flex items-center space-x-1 ${decisionData.capability_evaluation.is_executable ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {decisionData.capability_evaluation.is_executable ? <CheckCircle2 className="w-4 h-4 mr-1" /> : <AlertTriangle className="w-4 h-4 mr-1" />}
                      {decisionData.capability_evaluation.is_executable ? 'Executable' : 'Not Executable'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 bg-slate-950/50 p-3 rounded-lg border border-slate-800/60 leading-relaxed font-mono">
                    {decisionData.capability_evaluation.reason}
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-slate-950/40 rounded-xl text-center text-slate-400 text-sm">
                  Capability evaluation pending.
                </div>
              )}
            </div>

            {/* POLICY EVALUATION PANEL */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-lg backdrop-blur-md" data-testid="policy-panel">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-lg font-semibold text-slate-100">Policy Engine Evaluation</h3>
                </div>
                {decisionData.policy_evaluation && (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                      decisionData.policy_evaluation.policy_status === 'APPROVED'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}
                  >
                    {decisionData.policy_evaluation.policy_status}
                  </span>
                )}
              </div>

              {decisionData.policy_evaluation ? (
                <div className="space-y-3 text-sm">
                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800">
                      <span className="text-slate-400 block mb-0.5">Max Attempts</span>
                      <span className="font-mono font-bold text-slate-200">{decisionData.policy_evaluation.max_recovery_attempts}</span>
                    </div>
                    <div className="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800">
                      <span className="text-slate-400 block mb-0.5">Amount Cap</span>
                      <span className="font-mono font-bold text-slate-200">{formatINR(decisionData.policy_evaluation.max_auto_action_amount)}</span>
                    </div>
                    <div className="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800">
                      <span className="text-slate-400 block mb-0.5">Min P(R)</span>
                      <span className="font-mono font-bold text-emerald-400">{(decisionData.policy_evaluation.min_recovery_probability * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 bg-slate-950/50 p-3 rounded-lg border border-slate-800/60 leading-relaxed">
                    Rule Log: {decisionData.policy_evaluation.reason}
                  </p>
                </div>
              ) : (
                <div className="p-4 bg-slate-950/40 rounded-xl text-center text-slate-400 text-sm">
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
