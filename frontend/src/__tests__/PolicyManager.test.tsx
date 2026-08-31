import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { PolicyManagerPage } from '../pages/PolicyManager';
import { api } from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

const mockPolicyData = {
  id: 'policy_test_123',
  merchant_id: 'mch_test_999',
  policy_version: 'v1.0',
  max_recovery_attempts: 3,
  max_auto_action_amount: 50000.0,
  min_recovery_probability: 0.15,
  cooldown_hours: 24,
  is_active: true,
  created_at: '2026-08-30T12:00:00Z',
};

describe('Step 35: Policy Manager Dashboard Test Suite', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. Renders Policy Manager header, version badge, KPI cards, and form inputs', async () => {
    (api.get as any).mockResolvedValue({ data: [mockPolicyData] });

    render(
      <BrowserRouter>
        <PolicyManagerPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Policy Manager & Safety Guardrails/i)).toBeInTheDocument();
    });

    expect(screen.getAllByText('v1.0').length).toBeGreaterThan(0);
    expect(screen.getByText(/3 Attempts/i)).toBeInTheDocument();
    expect(screen.getByText(/Merchant Policy Rules Editor/i)).toBeInTheDocument();
    expect(screen.getByText(/Global Safety Bounds/i)).toBeInTheDocument();
  });

  it('2. Displays client-side validation errors for invalid input values', async () => {
    (api.get as any).mockResolvedValue({ data: [mockPolicyData] });

    render(
      <BrowserRouter>
        <PolicyManagerPage />
      </BrowserRouter>
    );

    const attemptsInput = await screen.findByLabelText<HTMLInputElement>(/Max Recovery Attempts/i);
    await waitFor(() => {
      expect(attemptsInput.value).toBe('3');
    });

    fireEvent.change(attemptsInput, { target: { value: '0' } });

    const form = attemptsInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Max attempts must be an integer between 1 and 10/i)).toBeInTheDocument();
    });
  });

  it('3. Submits form successfully via PATCH endpoint and increments policy version', async () => {
    (api.get as any).mockResolvedValue({ data: [mockPolicyData] });
    (api.patch as any).mockResolvedValue({
      data: {
        ...mockPolicyData,
        max_recovery_attempts: 4,
        policy_version: 'v1.1',
      },
    });

    render(
      <BrowserRouter>
        <PolicyManagerPage />
      </BrowserRouter>
    );

    const attemptsInput = await screen.findByLabelText<HTMLInputElement>(/Max Recovery Attempts/i);
    await waitFor(() => {
      expect(attemptsInput.value).toBe('3');
    });

    fireEvent.change(attemptsInput, { target: { value: '4' } });

    const form = attemptsInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        '/policies/policy_test_123',
        expect.objectContaining({
          max_recovery_attempts: 4,
        })
      );
      expect(screen.getByText(/Policy version v1.1 deployed successfully/i)).toBeInTheDocument();
    });
  });

  it('4. Resets form fields back to currently active policy state', async () => {
    (api.get as any).mockResolvedValue({ data: [mockPolicyData] });

    render(
      <BrowserRouter>
        <PolicyManagerPage />
      </BrowserRouter>
    );

    const attemptsInput = await screen.findByLabelText<HTMLInputElement>(/Max Recovery Attempts/i);
    await waitFor(() => {
      expect(attemptsInput.value).toBe('3');
    });

    fireEvent.change(attemptsInput, { target: { value: '5' } });
    expect(attemptsInput.value).toBe('5');

    const resetBtn = screen.getByRole('button', { name: /Reset Fields/i });
    fireEvent.click(resetBtn);

    expect(attemptsInput.value).toBe('3');
  });

  it('5. Operates resiliently with offline fallback schema when API throws error', async () => {
    (api.get as any).mockRejectedValue(new Error('Network Error'));

    render(
      <BrowserRouter>
        <PolicyManagerPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Policy Manager & Safety Guardrails/i)).toBeInTheDocument();
      expect(screen.getAllByText('v1.0').length).toBeGreaterThan(0);
    });
  });
});
