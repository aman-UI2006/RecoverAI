import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { HumanReviewPage } from '../pages/HumanReviewPage';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn()
  }
}));

const mockReviewItems = [
  {
    id: 'rev_901',
    transaction_id: 'tx_esc_001',
    merchant_id: 'm_alpha_123',
    status: 'PENDING',
    reason: 'HIGH_VALUE_AMOUNT_CAP_EXCEEDED',
    reviewer_id: null,
    decision: null,
    notes: null,
    reviewed_at: null,
    created_at: new Date().toISOString(),
    amount: 18500.0,
    currency: 'INR',
    scenario_type: 'PAYMENT_FAILURE',
    mode: 'SIMULATION'
  },
  {
    id: 'rev_902',
    transaction_id: 'tx_esc_002',
    merchant_id: 'm_alpha_123',
    status: 'APPROVED',
    reason: 'ML_PROBABILITY_BELOW_FLOOR',
    reviewer_id: 'rev_operator_admin',
    decision: 'APPROVE_OVERRIDE',
    notes: 'Approved after manual customer verification',
    reviewed_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    amount: 7200.0,
    currency: 'INR',
    scenario_type: 'CHECKOUT_ABANDONMENT',
    mode: 'REAL_TEST'
  }
];

const renderComponent = () =>
  render(
    <BrowserRouter>
      <HumanReviewPage />
    </BrowserRouter>
  );

describe('Step 36: Human Review Dashboard Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({
      data: {
        items: mockReviewItems,
        count: mockReviewItems.length
      }
    });
  });

  it('1. Renders Human Review Queue header, step indicator, and KPI cards', async () => {
    renderComponent();

    expect(screen.getByText('Human Review Queue')).toBeInTheDocument();
    expect(screen.getByText('STEP 36')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Pending Escalations')).toBeInTheDocument();
      expect(screen.getByText('High-Value Items (≥₹10k)')).toBeInTheDocument();
      expect(screen.getByText('Approved Overrides')).toBeInTheDocument();
      expect(screen.getByText('Terminated Actions')).toBeInTheDocument();
    });
  });

  it('2. Loads review queue items and renders transaction cards with escalation reason codes', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/tx_esc_001/i)).toBeInTheDocument();
    });

    const allTab = screen.getByRole('button', { name: 'ALL STATUSES' });
    fireEvent.click(allTab);

    expect(screen.getByText(/HIGH_VALUE_AMOUNT_CAP_EXCEEDED/i)).toBeInTheDocument();
    expect(screen.getByText(/tx_esc_002/i)).toBeInTheDocument();
    expect(screen.getByText(/ML_PROBABILITY_BELOW_FLOOR/i)).toBeInTheDocument();
  });

  it('3. Filters review items by status tabs and search query', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    });

    // Filter by PENDING status
    const pendingTab = screen.getByRole('button', { name: 'PENDING' });
    fireEvent.click(pendingTab);

    expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    expect(screen.queryByText('Tx: tx_esc_002')).not.toBeInTheDocument();

    // Filter by ALL status
    const allTab = screen.getByRole('button', { name: 'ALL STATUSES' });
    fireEvent.click(allTab);

    // Search filter
    const searchInput = screen.getByPlaceholderText('Search Tx ID or Escalation Code...');
    fireEvent.change(searchInput, { target: { value: 'tx_esc_002' } });

    expect(screen.queryByText('Tx: tx_esc_001')).not.toBeInTheDocument();
    expect(screen.getByText('Tx: tx_esc_002')).toBeInTheDocument();
  });

  it('4. Opens Inspect & Action modal upon clicking item button', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    });

    const actionButtons = screen.getAllByRole('button', { name: /INSPECT & ACTION/i });
    fireEvent.click(actionButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Inspect & Action Review')).toBeInTheDocument();
      expect(screen.getByText('APPROVE_OVERRIDE (Force Execution)')).toBeInTheDocument();
      expect(screen.getByText('REJECT_PERMANENT (Terminate)')).toBeInTheDocument();
    });
  });

  it('5. Submits APPROVE_OVERRIDE decision and updates item status dynamically', async () => {
    (api.post as any).mockResolvedValueOnce({
      data: {
        id: 'rev_901',
        status: 'APPROVED',
        decision: 'APPROVE_OVERRIDE'
      }
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    });

    const actionButtons = screen.getAllByRole('button', { name: /INSPECT & ACTION/i });
    fireEvent.click(actionButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Inspect & Action Review')).toBeInTheDocument();
    });

    const approveButton = screen.getByRole('button', { name: /APPROVE_OVERRIDE/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/api/v1/human-review/items/rev_901/decision',
        expect.objectContaining({
          decision: 'APPROVE_OVERRIDE',
          reviewer_id: 'rev_operator_01'
        })
      );
    });
  });

  it('6. Submits REJECT_PERMANENT decision and updates item status dynamically', async () => {
    (api.post as any).mockResolvedValueOnce({
      data: {
        id: 'rev_901',
        status: 'REJECTED',
        decision: 'REJECT_PERMANENT'
      }
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    });

    const actionButtons = screen.getAllByRole('button', { name: /INSPECT & ACTION/i });
    fireEvent.click(actionButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Inspect & Action Review')).toBeInTheDocument();
    });

    const rejectButton = screen.getByRole('button', { name: /REJECT_PERMANENT/i });
    fireEvent.click(rejectButton);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/api/v1/human-review/items/rev_901/decision',
        expect.objectContaining({
          decision: 'REJECT_PERMANENT',
          reviewer_id: 'rev_operator_01'
        })
      );
    });
  });

  it('7. Displays error alert in modal when backend API submission fails', async () => {
    (api.post as any).mockRejectedValueOnce({
      response: { data: { detail: 'Unauthorized reviewer role for transaction override' } }
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Tx: tx_esc_001')).toBeInTheDocument();
    });

    const actionButtons = screen.getAllByRole('button', { name: /INSPECT & ACTION/i });
    fireEvent.click(actionButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Inspect & Action Review')).toBeInTheDocument();
    });

    const approveButton = screen.getByRole('button', { name: /APPROVE_OVERRIDE/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(screen.getByText('Unauthorized reviewer role for transaction override')).toBeInTheDocument();
    });
  });

  it('8. Operates resiliently with offline mock fallback queue when backend API errors', async () => {
    (api.get as any).mockRejectedValueOnce(new Error('Network error'));

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Human Review Queue')).toBeInTheDocument();
      // Should fallback to mock data containing tx_alpha_998811
      expect(screen.getByText('Tx: tx_alpha_998811')).toBeInTheDocument();
    });
  });
});
