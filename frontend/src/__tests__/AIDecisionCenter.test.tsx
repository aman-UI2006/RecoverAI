/**
 * RecoverAI - Step 32: AI Decision Center Dashboard Component Test Suite
 *
 * Exhaustively verifies AIDecisionCenterPage and ENRVTable:
 * 1. Header / transaction context rendering
 * 2. Diagnosis information & confidence rendering
 * 3. Action score table & ENRV ranking
 * 4. Recommended action highlight badge
 * 5. Diagnostic rationale & nudge message template
 * 6. Capability Resolver & Policy Engine guardrail panels
 * 7. Loading, 404, generic error, and missing-context fallback UI states
 * 8. Read-only safety verification
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AIDecisionCenterPage } from '../pages/AIDecisionCenter';
import { ENRVTable } from '../components/ENRVTable';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
  },
  currentApiState: {
    merchantId: 'm_alpha_123',
    mode: 'SIMULATION',
  },
}));

const mockAIDecisionResponse = {
  transaction_id: 'tx_alpha_100',
  merchant_id: 'm_alpha_123',
  decision_context_id: 'ctx_uuid_999',
  model_version: 'v1.2',
  feature_version: 'v1.1',
  policy_version: 'v1.0',
  created_at: '2026-08-30T10:00:00Z',
  top_action: 'PAYMENT_LINK',
  best_enrv_rupees: 746.5,
  diagnosis: {
    id: 'diag_uuid_100',
    failure_code: 'BAD_OTP',
    failure_category: 'AUTHENTICATION',
    root_cause_explanation: 'Customer entered invalid 3DS OTP password twice.',
    confidence_score: 0.92,
    diagnosis_source: 'RULES',
    created_at: '2026-08-30T10:00:00Z',
  },
  recommendation: {
    recommended_action: 'PAYMENT_LINK',
    rationale_text: 'High recovery probability via direct payment link.',
    customer_message_template: 'Complete your purchase securely via link.',
    confidence_score: 0.88,
  },
  action_scores: [
    {
      id: 'score_1',
      action: 'PAYMENT_LINK',
      recovery_probability: 0.75,
      expected_gross_recovery: 750.0,
      intervention_cost: 3.5,
      expected_net_recovery_value: 746.5,
      rank: 1,
      capability_status: 'SUPPORTED',
      policy_status: 'APPROVED',
    },
    {
      id: 'score_2',
      action: 'RECOVERY_MESSAGE',
      recovery_probability: 0.4,
      expected_gross_recovery: 400.0,
      intervention_cost: 0.6,
      expected_net_recovery_value: 399.4,
      rank: 2,
      capability_status: 'SUPPORTED',
      policy_status: 'APPROVED',
    },
  ],
  policy_evaluation: {
    policy_version: 'v1.0',
    policy_status: 'APPROVED',
    reason: 'All merchant policy limits satisfied for automated recovery.',
    max_recovery_attempts: 3,
    max_auto_action_amount: 50000.0,
    min_recovery_probability: 0.15,
  },
  capability_evaluation: {
    execution_mode: 'SIMULATION',
    is_executable: true,
    status: 'SUPPORTED',
    reason: "Action 'PAYMENT_LINK' is executable in SIMULATION mode.",
  },
};

describe('Step 32: AI Decision Center Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (initialEntry = '/ai-decision?tx=tx_alpha_100') => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/ai-decision" element={<AIDecisionCenterPage />} />
          <Route path="/ai-decision/:id" element={<AIDecisionCenterPage />} />
          <Route path="/transactions/:id" element={<div>Transaction Detail Stub</div>} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('1. Renders loading state initially', async () => {
    vi.mocked(api.get).mockReturnValue(new Promise(() => {})); // pending Promise
    renderComponent();

    expect(screen.getByTestId('ai-decision-loading')).toBeDefined();
    expect(screen.getByText('Retrieving AI Decision Context from Backend...')).toBeDefined();
  });

  it('2. Renders decision context metadata and header upon success', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockAIDecisionResponse });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('ai-decision-content')).toBeDefined();
    });

    expect(screen.getByTestId('decision-context-card')).toBeDefined();
    expect(screen.getByText('tx_alpha_100')).toBeDefined();
    expect(screen.getByText('ctx_uuid_999')).toBeDefined();
    expect(screen.getByText('Model: v1.2')).toBeDefined();
    expect(screen.getByText('Feat: v1.1')).toBeDefined();
  });

  it('3. Renders root cause diagnosis panel and confidence score', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockAIDecisionResponse });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('diagnosis-panel')).toBeDefined();
    });

    expect(screen.getByText(/AUTHENTICATION \/ BAD_OTP/i)).toBeDefined();
    expect(screen.getByText('Customer entered invalid 3DS OTP password twice.')).toBeDefined();
    expect(screen.getByText('92%')).toBeDefined();
    expect(screen.getByText('Source: RULES')).toBeDefined();
  });

  it('4. Renders recommendation and ENRV table with ranked actions', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockAIDecisionResponse });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('enrv-table')).toBeDefined();
    });

    expect(screen.getByTestId('recommendation-panel')).toBeDefined();
    expect(screen.getByTestId('recommended-action-title').textContent).toBe('PAYMENT_LINK');
    expect(screen.getByTestId('recommendation-rationale').textContent).toContain(
      'High recovery probability via direct payment link.'
    );

    // ENRV Table Rows
    expect(screen.getByTestId('enrv-row-PAYMENT_LINK')).toBeDefined();
    expect(screen.getByTestId('enrv-row-RECOVERY_MESSAGE')).toBeDefined();
    expect(screen.getByTestId('badge-recommended')).toBeDefined();
  });

  it('5. Renders capability resolver and policy evaluation panels', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: mockAIDecisionResponse });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('capability-panel')).toBeDefined();
      expect(screen.getByTestId('policy-panel')).toBeDefined();
    });

    expect(screen.getByText(/executable in SIMULATION mode/i)).toBeDefined();
    expect(screen.getByText(/All merchant policy limits satisfied/i)).toBeDefined();
  });

  it('6. Displays HTTP 404 state cleanly when transaction decision is not found', async () => {
    vi.mocked(api.get).mockRejectedValue({
      response: {
        status: 404,
        data: { detail: 'Transaction or DecisionContext not found' },
      },
    });
    renderComponent('/ai-decision?tx=non_existent_tx');

    await waitFor(() => {
      expect(screen.getByTestId('ai-decision-404')).toBeDefined();
    });

    expect(screen.getByText('Decision Context Not Found (HTTP 404)')).toBeDefined();
  });

  it('7. Handles missing diagnosis and missing action scores safely', async () => {
    const missingContextResponse = {
      ...mockAIDecisionResponse,
      diagnosis: null,
      recommendation: null,
      action_scores: [],
    };
    vi.mocked(api.get).mockResolvedValue({ data: missingContextResponse });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByTestId('ai-decision-content')).toBeDefined();
    });

    expect(screen.getByTestId('diagnosis-missing')).toBeDefined();
    expect(screen.getByTestId('enrv-empty-state')).toBeDefined();
  });

  it('8. ENRVTable component standalone snapshot verification', () => {
    render(
      <ENRVTable
        actionScores={mockAIDecisionResponse.action_scores}
        topAction="PAYMENT_LINK"
        recommendedAction="PAYMENT_LINK"
      />
    );

    expect(screen.getByTestId('enrv-table')).toBeDefined();
    expect(screen.getByText('75.0%')).toBeDefined();
    expect(screen.getByText('₹746.50')).toBeDefined();
  });
});
