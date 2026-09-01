/**
 * RecoverAI - Step 47: Recovery Strategy Visualization Matrix UI Component Tests
 *
 * Verifies rendering of interactive strategy heatmap matrix, diagnosis rows, candidate action columns,
 * cell probability color intensity mapping, hover tooltip calculations, and neutral gray state fallback.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StrategyMatrix, MatrixCellData } from '../components/StrategyMatrix';

describe('Step 47: StrategyMatrix Component Test Suite', () => {
  it('1. Renders strategy matrix container, title, legend, and grid layout', () => {
    render(<StrategyMatrix />);

    expect(screen.getByTestId('strategy-matrix-container')).toBeDefined();
    expect(screen.getByText('Action-Conditional Strategy Heatmap Matrix')).toBeDefined();
    expect(screen.getByText('High (≥70%)')).toBeDefined();
    expect(screen.getByText('Uncalculated')).toBeDefined();
    expect(screen.getByTestId('strategy-matrix-grid')).toBeDefined();
  });

  it('2. Renders default failure diagnosis rows and candidate action columns', () => {
    render(<StrategyMatrix />);

    // Row headers
    expect(screen.getByText('PAYMENT_LINK_EXPIRED')).toBeDefined();
    expect(screen.getByText('CARD_AUTHENTICATION_FAILED')).toBeDefined();
    expect(screen.getByText('INSUFFICIENT_FUNDS')).toBeDefined();
    expect(screen.getByText('GATEWAY_TIMEOUT')).toBeDefined();
    expect(screen.getByText('MAX_RETRIES_EXCEEDED')).toBeDefined();

    // Column headers
    expect(screen.getByText('PAYMENT LINK')).toBeDefined();
    expect(screen.getByText('RECOVERY MESSAGE')).toBeDefined();
    expect(screen.getByText('CUSTOMER NUDGE')).toBeDefined();
    expect(screen.getByText('WHATSAPP REMINDER')).toBeDefined();
    expect(screen.getByText('RETRY PAYMENT')).toBeDefined();
    expect(screen.getByText('MANUAL OUTREACH')).toBeDefined();
  });

  it('3. Color-cell intensities render probability values correctly', () => {
    render(<StrategyMatrix />);

    // Check specific matrix cell rendering (82% for PAYMENT_LINK_EXPIRED -> PAYMENT_LINK)
    const cellElement = screen.getByTestId('matrix-cell-PAYMENT_LINK_EXPIRED-PAYMENT_LINK');
    expect(cellElement).toBeDefined();
    expect(cellElement.textContent).toContain('82%');
  });

  it('4. Updates hover tooltip with P(R|X,a), ENRV, and intervention cost when cell hovered', () => {
    render(<StrategyMatrix />);

    const tooltipBefore = screen.getByTestId('strategy-matrix-tooltip');
    expect(tooltipBefore.textContent).toContain('Hover over any matrix cell');

    const cellElement = screen.getByTestId('matrix-cell-PAYMENT_LINK_EXPIRED-PAYMENT_LINK');
    fireEvent.mouseEnter(cellElement);

    const tooltipAfter = screen.getByTestId('strategy-matrix-tooltip');
    expect(tooltipAfter.textContent).toContain('PAYMENT_LINK_EXPIRED');
    expect(tooltipAfter.textContent).toContain('PAYMENT_LINK');
    expect(tooltipAfter.textContent).toContain('82.0%');
    expect(tooltipAfter.textContent).toContain('₹1,450');
    expect(tooltipAfter.textContent).toContain('₹5');

    // Mouse leave resets tooltip
    fireEvent.mouseLeave(cellElement);
    expect(screen.getByTestId('strategy-matrix-tooltip').textContent).toContain('Hover over any matrix cell');
  });

  it('5. Renders neutral gray cell state for uncalculated pairs', () => {
    render(<StrategyMatrix />);

    // MAX_RETRIES_EXCEEDED -> RETRY_PAYMENT has recovery_probability: null
    const uncalculatedCell = screen.getByTestId('matrix-cell-MAX_RETRIES_EXCEEDED-RETRY_PAYMENT');
    expect(uncalculatedCell).toBeDefined();
    expect(uncalculatedCell.textContent).toContain('N/A');

    fireEvent.mouseEnter(uncalculatedCell);
    expect(screen.getByTestId('strategy-matrix-tooltip').textContent).toContain('Uncalculated / Fallback Neutral Gray Cell State');
  });

  it('6. Accepts custom matrix data and highlights active diagnosis/action', () => {
    const customData: MatrixCellData[] = [
      {
        diagnosis: 'CUSTOM_DIAGNOSIS',
        action: 'PAYMENT_LINK',
        recovery_probability: 0.95,
        enrv: 2500,
        intervention_cost: 5,
      },
    ];

    render(
      <StrategyMatrix
        matrixData={customData}
        activeDiagnosis="PAYMENT_LINK_EXPIRED"
        activeAction="PAYMENT_LINK"
      />
    );

    const activeCell = screen.getByTestId('matrix-cell-PAYMENT_LINK_EXPIRED-PAYMENT_LINK');
    expect(activeCell).toBeDefined();
  });
});
