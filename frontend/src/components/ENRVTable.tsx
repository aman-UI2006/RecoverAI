/**
 * RecoverAI - Action-Conditional ENRV Scoring Table Component (Step 32)
 *
 * Renders candidate action scores, predicted recovery probabilities P(R | X, a_i),
 * intervention costs, expected net recovery values (ENRV), capability status,
 * and policy guardrail status. Highlights top-ranked ENRV action vs selected recommendation.
 */

import React from 'react';
import { ShieldCheck, AlertTriangle, Trophy, Sparkles, XCircle } from 'lucide-react';
import { ActionScoreItem } from '../pages/AIDecisionCenter';

export interface ENRVTableProps {
  actionScores: ActionScoreItem[];
  topAction?: string | null;
  recommendedAction?: string | null;
}

export const ENRVTable: React.FC<ENRVTableProps> = ({
  actionScores,
  topAction,
  recommendedAction,
}) => {
  const formatINR = (val: number) =>
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(val);

  const formatPercent = (prob: number) => `${(prob * 100).toFixed(1)}%`;

  if (!actionScores || actionScores.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-8 text-center" data-testid="enrv-empty-state">
        <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-3 animate-pulse" />
        <h4 className="text-slate-200 font-semibold text-base mb-1">No Candidate Action Scores Available</h4>
        <p className="text-slate-400 text-sm max-w-md mx-auto">
          Decision context model scoring is pending or candidate actions were not evaluated for this transaction cycle.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-md shadow-xl" data-testid="enrv-table-container">
      <table className="w-full text-left border-collapse" data-testid="enrv-table">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-950/80 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <th className="py-3.5 px-4 text-center w-16">Rank</th>
            <th className="py-3.5 px-4">Candidate Action</th>
            <th className="py-3.5 px-4 text-right">Recovery Probability $P(R \mid X, a)$</th>
            <th className="py-3.5 px-4 text-right">Gross Recovery (₹)</th>
            <th className="py-3.5 px-4 text-right">Intervention Cost (₹)</th>
            <th className="py-3.5 px-4 text-right font-bold text-slate-200">Expected Net Recovery (ENRV)</th>
            <th className="py-3.5 px-4 text-center">Capability</th>
            <th className="py-3.5 px-4 text-center">Policy</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 text-sm text-slate-300">
          {actionScores.map((item) => {
            const isTop = item.rank === 1 || item.action === topAction;
            const isRecommended = item.action === recommendedAction;

            return (
              <tr
                key={item.id || item.action}
                data-testid={`enrv-row-${item.action}`}
                className={`transition-colors hover:bg-slate-800/40 ${
                  isRecommended ? 'bg-indigo-950/30 font-medium' : isTop ? 'bg-emerald-950/20' : ''
                }`}
              >
                <td className="py-3.5 px-4 text-center">
                  <div className="flex items-center justify-center">
                    {item.rank === 1 ? (
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold" title="Top ENRV Rank">
                        <Trophy className="w-3.5 h-3.5" />
                      </span>
                    ) : (
                      <span className="text-slate-500 text-xs font-mono">#{item.rank}</span>
                    )}
                  </div>
                </td>
                <td className="py-3.5 px-4">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-slate-100 font-semibold">{item.action}</span>
                    {isRecommended && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30" data-testid="badge-recommended">
                        <Sparkles className="w-3 h-3 mr-1 text-indigo-400" />
                        AI Recommended
                      </span>
                    )}
                    {isTop && !isRecommended && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        Top ENRV
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3.5 px-4 text-right font-mono font-medium text-emerald-400">
                  {formatPercent(item.recovery_probability)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono text-slate-300">
                  {formatINR(item.expected_gross_recovery)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono text-rose-400/90">
                  -{formatINR(item.intervention_cost)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono font-bold text-emerald-300 text-base">
                  {formatINR(item.expected_net_recovery_value)}
                </td>
                <td className="py-3.5 px-4 text-center">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      item.capability_status === 'SUPPORTED'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}
                  >
                    {item.capability_status === 'SUPPORTED' ? (
                      <ShieldCheck className="w-3 h-3 mr-1" />
                    ) : (
                      <AlertTriangle className="w-3 h-3 mr-1" />
                    )}
                    {item.capability_status}
                  </span>
                </td>
                <td className="py-3.5 px-4 text-center">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      item.policy_status === 'APPROVED'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}
                  >
                    {item.policy_status === 'APPROVED' ? (
                      <ShieldCheck className="w-3 h-3 mr-1" />
                    ) : (
                      <XCircle className="w-3 h-3 mr-1" />
                    )}
                    {item.policy_status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
