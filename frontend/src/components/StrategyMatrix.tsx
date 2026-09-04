/**
 * RecoverAI - Step 47: Recovery Strategy Matrix Heat-map Component
 *
 * Interactive visual matrix mapping failure diagnoses (rows) to candidate recovery actions (columns).
 * Renders cell color intensities based on expected recovery probability P(R | X, a).
 * Features hover tooltips displaying calculated ENRV (Expected Net Recovery Value) and intervention cost.
 * Provides neutral gray cell fallback for uncalculated or empty diagnosis-action pairs.
 */

import React, { useState } from 'react';
import { Grid, Info, Sparkles } from 'lucide-react';

export interface MatrixCellData {
  diagnosis: string;
  action: string;
  recovery_probability: number | null;
  enrv: number | null;
  intervention_cost: number | null;
}

export interface StrategyMatrixProps {
  matrixData?: MatrixCellData[];
  activeDiagnosis?: string;
  activeAction?: string;
}

// Standard failure diagnoses (Rows)
const DEFAULT_DIAGNOSES = [
  'PAYMENT_LINK_EXPIRED',
  'CARD_AUTHENTICATION_FAILED',
  'INSUFFICIENT_FUNDS',
  'GATEWAY_TIMEOUT',
  'MAX_RETRIES_EXCEEDED',
];

// Standard candidate actions (Columns)
const DEFAULT_ACTIONS = [
  'PAYMENT_LINK',
  'RECOVERY_MESSAGE',
  'CUSTOMER_NUDGE',
  'WHATSAPP_REMINDER',
  'RETRY_PAYMENT',
  'MANUAL_OUTREACH',
];

// Fallback baseline matrix data for visual representation when live matrix API data is unpopulated
const DEFAULT_MATRIX_CELLS: MatrixCellData[] = [
  // PAYMENT_LINK_EXPIRED
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'PAYMENT_LINK', recovery_probability: 0.82, enrv: 1450.0, intervention_cost: 5.0 },
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'RECOVERY_MESSAGE', recovery_probability: 0.65, enrv: 1100.0, intervention_cost: 2.0 },
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'CUSTOMER_NUDGE', recovery_probability: 0.58, enrv: 950.0, intervention_cost: 1.0 },
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'WHATSAPP_REMINDER', recovery_probability: 0.76, enrv: 1320.0, intervention_cost: 3.5 },
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'RETRY_PAYMENT', recovery_probability: 0.25, enrv: 300.0, intervention_cost: 0.0 },
  { diagnosis: 'PAYMENT_LINK_EXPIRED', action: 'MANUAL_OUTREACH', recovery_probability: 0.70, enrv: 1050.0, intervention_cost: 50.0 },

  // CARD_AUTHENTICATION_FAILED
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'PAYMENT_LINK', recovery_probability: 0.74, enrv: 1280.0, intervention_cost: 5.0 },
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'RECOVERY_MESSAGE', recovery_probability: 0.52, enrv: 840.0, intervention_cost: 2.0 },
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'CUSTOMER_NUDGE', recovery_probability: 0.45, enrv: 710.0, intervention_cost: 1.0 },
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'WHATSAPP_REMINDER', recovery_probability: 0.68, enrv: 1150.0, intervention_cost: 3.5 },
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'RETRY_PAYMENT', recovery_probability: 0.38, enrv: 550.0, intervention_cost: 0.0 },
  { diagnosis: 'CARD_AUTHENTICATION_FAILED', action: 'MANUAL_OUTREACH', recovery_probability: 0.62, enrv: 920.0, intervention_cost: 50.0 },

  // INSUFFICIENT_FUNDS
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'PAYMENT_LINK', recovery_probability: 0.48, enrv: 750.0, intervention_cost: 5.0 },
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'RECOVERY_MESSAGE', recovery_probability: 0.35, enrv: 500.0, intervention_cost: 2.0 },
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'CUSTOMER_NUDGE', recovery_probability: 0.40, enrv: 620.0, intervention_cost: 1.0 },
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'WHATSAPP_REMINDER', recovery_probability: 0.55, enrv: 890.0, intervention_cost: 3.5 },
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'RETRY_PAYMENT', recovery_probability: 0.62, enrv: 1050.0, intervention_cost: 0.0 },
  { diagnosis: 'INSUFFICIENT_FUNDS', action: 'MANUAL_OUTREACH', recovery_probability: 0.42, enrv: 580.0, intervention_cost: 50.0 },

  // GATEWAY_TIMEOUT
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'PAYMENT_LINK', recovery_probability: 0.60, enrv: 980.0, intervention_cost: 5.0 },
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'RECOVERY_MESSAGE', recovery_probability: 0.40, enrv: 610.0, intervention_cost: 2.0 },
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'CUSTOMER_NUDGE', recovery_probability: 0.30, enrv: 420.0, intervention_cost: 1.0 },
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'WHATSAPP_REMINDER', recovery_probability: 0.50, enrv: 790.0, intervention_cost: 3.5 },
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'RETRY_PAYMENT', recovery_probability: 0.88, enrv: 1620.0, intervention_cost: 0.0 },
  { diagnosis: 'GATEWAY_TIMEOUT', action: 'MANUAL_OUTREACH', recovery_probability: 0.35, enrv: 450.0, intervention_cost: 50.0 },

  // MAX_RETRIES_EXCEEDED (uncalculated / fallback state example)
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'PAYMENT_LINK', recovery_probability: 0.15, enrv: 150.0, intervention_cost: 5.0 },
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'RECOVERY_MESSAGE', recovery_probability: 0.10, enrv: 80.0, intervention_cost: 2.0 },
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'CUSTOMER_NUDGE', recovery_probability: 0.08, enrv: 50.0, intervention_cost: 1.0 },
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'WHATSAPP_REMINDER', recovery_probability: 0.18, enrv: 210.0, intervention_cost: 3.5 },
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'RETRY_PAYMENT', recovery_probability: null, enrv: null, intervention_cost: null },
  { diagnosis: 'MAX_RETRIES_EXCEEDED', action: 'MANUAL_OUTREACH', recovery_probability: 0.28, enrv: 310.0, intervention_cost: 50.0 },
];

export const StrategyMatrix: React.FC<StrategyMatrixProps> = ({
  matrixData = DEFAULT_MATRIX_CELLS,
  activeDiagnosis,
  activeAction,
}) => {
  const [hoveredCell, setHoveredCell] = useState<{
    diagnosis: string;
    action: string;
    cellData?: MatrixCellData;
  } | null>(null);

  // Helper to lookup cell data for diagnosis + action pair
  const getCellData = (diagnosis: string, action: string): MatrixCellData | undefined => {
    return matrixData.find((item) => item.diagnosis === diagnosis && item.action === action);
  };

  // Helper to compute color intensity based on P(R | X, a)
  const getCellColorClass = (prob: number | null | undefined, isHighlighted: boolean) => {
    if (prob === undefined || prob === null) {
      return isHighlighted
        ? 'bg-[#F8FAFD] border-[#7A8799] text-[#7A8799] font-mono shadow-inner font-bold'
        : 'bg-[#F8FAFD] border-[#E5EAF1] text-[#7A8799] font-mono';
    }

    if (prob >= 0.7) {
      return isHighlighted
        ? 'bg-[#E6F4ED] border-[#16A36A] text-[#16A36A] font-bold shadow-md'
        : 'bg-[#E6F4ED]/80 border-[#16A36A]/40 text-[#16A36A] font-bold hover:bg-[#E6F4ED]';
    } else if (prob >= 0.5) {
      return isHighlighted
        ? 'bg-[#EEF4FF] border-[#2F5BFF] text-[#2454D6] font-bold shadow-md'
        : 'bg-[#EEF4FF]/80 border-[#2F5BFF]/30 text-[#2454D6] font-bold hover:bg-[#EEF4FF]';
    } else if (prob >= 0.3) {
      return isHighlighted
        ? 'bg-[#FDF8EC] border-[#D99A00] text-[#D99A00] font-bold shadow-md'
        : 'bg-[#FDF8EC]/80 border-[#D99A00]/30 text-[#D99A00] font-bold hover:bg-[#FDF8EC]';
    } else {
      return isHighlighted
        ? 'bg-[#FDF2F4] border-[#D6455D] text-[#D6455D] font-bold shadow-md'
        : 'bg-[#FDF2F4]/80 border-[#D6455D]/30 text-[#D6455D] font-bold hover:bg-[#FDF2F4]';
    }
  };

  const formatINR = (val: number | null | undefined) => {
    if (val === undefined || val === null) return 'N/A';
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div
      data-testid="strategy-matrix-container"
      className="bg-white border border-[#E5EAF1] rounded-xl p-6 shadow-sm font-sans space-y-4 font-numeric"
    >
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E5EAF1] pb-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-[#EEF4FF] border border-[#2F5BFF]/20 rounded-xl text-[#2F5BFF]">
            <Grid className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[#0B1F3A] flex items-center space-x-2">
              <span>Action-Conditional Strategy Heatmap Matrix</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#EEF4FF] text-[#2454D6] border border-[#2F5BFF]/20 uppercase tracking-wider font-mono">
                P(R | X, a) Mapping
              </span>
            </h3>
            <p className="text-xs text-[#53627A] mt-0.5">
              Visual grid mapping failure diagnoses (Rows) to candidate recovery probabilities and ENRV estimates (Columns)
            </p>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center space-x-3 text-[11px] font-mono font-bold text-[#53627A] bg-[#F8FAFD] px-3 py-1.5 rounded-lg border border-[#E5EAF1]">
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#E6F4ED] border border-[#16A36A]"></span>
            <span>High (&ge;70%)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#EEF4FF] border border-[#2F5BFF]"></span>
            <span>Med (&ge;50%)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#FDF8EC] border border-[#D99A00]"></span>
            <span>Low (&ge;30%)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-[#F8FAFD] border border-[#E5EAF1]"></span>
            <span>Uncalculated</span>
          </div>
        </div>
      </div>

      {/* Grid Container */}
      <div className="overflow-x-auto relative pt-2">
        <table className="w-full text-left text-xs border-collapse" data-testid="strategy-matrix-grid">
          <thead>
            <tr>
              <th className="py-2.5 px-3 bg-[#F8FAFD] text-[#7A8799] uppercase text-[10px] font-bold tracking-wider border-b border-r border-[#E5EAF1] w-48 font-sans">
                Diagnosis / Action Strategy
              </th>
              {DEFAULT_ACTIONS.map((action) => (
                <th
                  key={action}
                  className={`py-2.5 px-2 text-center text-[10px] font-mono font-bold uppercase tracking-wider border-b border-[#E5EAF1] ${
                    activeAction === action
                      ? 'bg-[#EEF4FF] text-[#2454D6] border-[#2F5BFF]/40'
                      : 'bg-[#F8FAFD] text-[#7A8799]'
                  }`}
                >
                  {action.replace('_', ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5EAF1]">
            {DEFAULT_DIAGNOSES.map((diag) => {
              const isDiagActive = activeDiagnosis === diag;
              return (
                <tr key={diag} className="hover:bg-[#F8FAFD]">
                  {/* Diagnosis Label (Row Header) */}
                  <td
                    className={`py-3 px-3 border-r border-[#E5EAF1] font-sans font-bold text-[11px] ${
                      isDiagActive
                        ? 'bg-[#EEF4FF] text-[#2454D6] border-l-2 border-l-[#2F5BFF]'
                        : 'text-[#0B1F3A]'
                    }`}
                  >
                    <div className="truncate max-w-[170px]" title={diag}>
                      {diag}
                    </div>
                  </td>

                  {/* Candidate Action Columns */}
                  {DEFAULT_ACTIONS.map((act) => {
                    const cell = getCellData(diag, act);
                    const isCellActive = isDiagActive && activeAction === act;
                    const prob = cell?.recovery_probability;

                    return (
                      <td key={act} className="p-1 text-center relative group">
                        <div
                          data-testid={`matrix-cell-${diag}-${act}`}
                          onMouseEnter={() => setHoveredCell({ diagnosis: diag, action: act, cellData: cell })}
                          onMouseLeave={() => setHoveredCell(null)}
                          className={`py-2 px-2 rounded-lg border text-xs transition-all cursor-pointer flex flex-col items-center justify-center min-h-[44px] ${getCellColorClass(
                            prob,
                            isCellActive
                          )}`}
                        >
                          {prob !== null && prob !== undefined ? (
                            <span className="font-mono text-xs font-bold">
                              {(prob * 100).toFixed(0)}%
                            </span>
                          ) : (
                            <span className="font-mono text-[10px] text-[#7A8799]">N/A</span>
                          )}

                          {cell?.enrv !== null && cell?.enrv !== undefined && (
                            <span className="text-[9px] font-mono opacity-80 mt-0.5">
                              {formatINR(cell.enrv)}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Hover Tooltip Details Panel */}
      <div
        data-testid="strategy-matrix-tooltip"
        className="mt-3 p-3 bg-[#F8FAFD] border border-[#E5EAF1] rounded-lg min-h-[52px] flex items-center justify-between text-xs font-sans"
      >
        {hoveredCell ? (
          <div className="flex items-center justify-between w-full font-mono">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-[#2F5BFF]" />
              <span className="text-[#0B1F3A] font-sans font-bold">
                {hoveredCell.diagnosis} &rarr; <span className="text-[#2454D6]">{hoveredCell.action}</span>
              </span>
            </div>
            {hoveredCell.cellData && hoveredCell.cellData.recovery_probability !== null ? (
              <div className="flex items-center space-x-4 font-numeric">
                <span>
                  P(R | X, a): <strong className="text-[#16A36A]">{(hoveredCell.cellData.recovery_probability! * 100).toFixed(1)}%</strong>
                </span>
                <span>
                  ENRV: <strong className="text-[#2454D6]">{formatINR(hoveredCell.cellData.enrv)}</strong>
                </span>
                <span>
                  Intervention Cost: <strong className="text-[#D99A00]">{formatINR(hoveredCell.cellData.intervention_cost)}</strong>
                </span>
              </div>
            ) : (
              <span className="text-[#7A8799] italic">Uncalculated / Fallback Neutral Gray Cell State</span>
            )}
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-[#53627A] italic">
            <Info className="w-4 h-4 text-[#7A8799]" />
            <span>Hover over any matrix cell to inspect expected recovery probability P(R | X, a), ENRV, and intervention cost details.</span>
          </div>
        )}
      </div>
    </div>
  );
};
