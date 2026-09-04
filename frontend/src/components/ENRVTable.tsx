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
      <div className="bg-white border border-[#E5EAF1] rounded-xl p-8 text-center shadow-sm font-sans" data-testid="enrv-empty-state">
        <AlertTriangle className="w-8 h-8 text-[#D99A00] mx-auto mb-3" />
        <h4 className="text-[#0B1F3A] font-bold text-base mb-1">No Candidate Action Scores Available</h4>
        <p className="text-[#53627A] text-sm max-w-md mx-auto">
          Decision context model scoring is pending or candidate actions were not evaluated for this transaction cycle.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-[#E5EAF1] bg-white shadow-sm font-sans font-numeric" data-testid="enrv-table-container">
      <table className="w-full text-left border-collapse" data-testid="enrv-table">
        <thead>
          <tr className="border-b border-[#E5EAF1] bg-[#F8FAFD] text-xs font-bold text-[#7A8799] uppercase tracking-wider font-sans">
            <th className="py-3.5 px-4 text-center w-16">Rank</th>
            <th className="py-3.5 px-4">Candidate Action</th>
            <th className="py-3.5 px-4 text-right">Recovery Probability P(R | X, a)</th>
            <th className="py-3.5 px-4 text-right">Gross Recovery (₹)</th>
            <th className="py-3.5 px-4 text-right">Intervention Cost (₹)</th>
            <th className="py-3.5 px-4 text-right font-bold text-[#0B1F3A]">Expected Net Recovery (ENRV)</th>
            <th className="py-3.5 px-4 text-center">Capability</th>
            <th className="py-3.5 px-4 text-center">Policy</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#E5EAF1] text-xs text-[#0B1F3A]">
          {actionScores.map((item) => {
            const isTop = item.rank === 1 || item.action === topAction;
            const isRecommended = item.action === recommendedAction;

            return (
              <tr
                key={item.id || item.action}
                data-testid={`enrv-row-${item.action}`}
                className={`transition-colors hover:bg-[#F8FAFD] ${
                  isRecommended ? 'bg-[#EEF4FF] font-bold' : isTop ? 'bg-[#E6F4ED]/50' : ''
                }`}
              >
                <td className="py-3.5 px-4 text-center font-sans">
                  <div className="flex items-center justify-center">
                    {item.rank === 1 ? (
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#E6F4ED] text-[#16A36A] border border-[#16A36A]/30 text-xs font-bold" title="Top ENRV Rank">
                        <Trophy className="w-3.5 h-3.5 text-[#16A36A]" />
                      </span>
                    ) : (
                      <span className="text-[#7A8799] text-xs font-mono font-bold">#{item.rank}</span>
                    )}
                  </div>
                </td>
                <td className="py-3.5 px-4 font-sans">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-[#0B1F3A] font-bold">{item.action}</span>
                    {isRecommended && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#2F5BFF] text-white" data-testid="badge-recommended">
                        <Sparkles className="w-3 h-3 mr-1 text-white" />
                        AI Recommended
                      </span>
                    )}
                    {isTop && !isRecommended && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-[#E6F4ED] text-[#16A36A] border border-[#16A36A]/20">
                        Top ENRV
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3.5 px-4 text-right font-mono font-bold text-[#16A36A]">
                  {formatPercent(item.recovery_probability)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono text-[#0B1F3A] font-bold">
                  {formatINR(item.expected_gross_recovery)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono text-[#D6455D] font-bold">
                  -{formatINR(item.intervention_cost)}
                </td>
                <td className="py-3.5 px-4 text-right font-mono font-bold text-[#2454D6] text-sm">
                  {formatINR(item.expected_net_recovery_value)}
                </td>
                <td className="py-3.5 px-4 text-center font-sans">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-bold border ${
                      item.capability_status === 'SUPPORTED'
                        ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20'
                        : 'bg-[#FDF8EC] text-[#D99A00] border-[#D99A00]/20'
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
                <td className="py-3.5 px-4 text-center font-sans">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-bold border ${
                      item.policy_status === 'APPROVED'
                        ? 'bg-[#E6F4ED] text-[#16A36A] border-[#16A36A]/20'
                        : 'bg-[#FDF2F4] text-[#D6455D] border-[#D6455D]/20'
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
