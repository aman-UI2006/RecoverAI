/**
 * RecoverAI - Step 33: Recovery Analytics Component Test Suite
 *
 * Exhaustively tests RecoveryAnalyticsPage:
 * 1. Header & step 33 observability rendering
 * 2. KPI metrics callouts (Gross, Rates, Lift, Net ROI)
 * 3. Refund-adjusted net revenue callout formula
 * 4. Recharts chart containers (Treatment vs Control, Trend line, Pie chart)
 * 5. Scenario and action category breakdown tables
 * 6. Execution mode toggle (SIMULATION / REAL_TEST)
 */

import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RecoveryAnalyticsPage } from '../pages/RecoveryAnalytics';
import { api, currentApiState } from '../services/api';

// Mock Recharts to avoid DOM measurement issues in happy-dom / jsdom environment
vi.mock('recharts', async () => {
  const original = await vi.importActual<any>('recharts');
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  };
});

// Mock API client
vi.mock('../services/api', async () => {
  const original = await vi.importActual<any>('../services/api');
  return {
    ...original,
    api: {
      get: vi.fn(),
    },
  };
});

describe('Step 33: Recovery Analytics Page', () => {
  const mockAnalyticsData = {
    run_name: 'analytics_summary_api',
    mode: 'SIMULATION',
    merchant_id: 'm_alpha_123',
    treatment_metrics: {
      total_eligible_count: 1250,
      total_eligible_amount: 1485000.0,
      recovered_count: 792,
      recovered_amount: 942000.0,
      recovery_rate: 0.6336,
      refunded_amount: 23600.0,
      intervention_cost: 17200.0,
    },
    control_metrics: {
      total_eligible_count: 1250,
      total_eligible_amount: 1485000.0,
      recovered_count: 400,
      recovered_amount: 475000.0,
      recovery_rate: 0.32,
      refunded_amount: 11800.0,
      intervention_cost: 0.0,
    },
    treatment_recovery_rate: 0.6336,
    control_recovery_rate: 0.32,
    incremental_recovery_rate: 0.3136,
    treatment_recovered_amount: 942000.0,
    control_recovered_amount: 475000.0,
    estimated_incremental_recovered_amount: 467000.0,
    net_incremental_revenue: 426200.0,
    created_at: new Date().toISOString(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    currentApiState.mode = 'SIMULATION';
    currentApiState.merchantId = 'm_alpha_123';
  });

  it('renders loading state initially and then analytics dashboard content', async () => {
    (api.get as any).mockResolvedValueOnce({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    expect(screen.getByTestId('recovery-analytics-page')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByTestId('analytics-content')).toBeDefined();
    });

    // Verify Title & Observability Badge
    expect(screen.getByText('Recovery Analytics')).toBeDefined();
    expect(screen.getByText('Step 33 Observability')).toBeDefined();
  });

  it('renders KPI metric callouts with correct financial values', async () => {
    (api.get as any).mockResolvedValueOnce({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('analytics-content')).toBeDefined();
    });

    // KPI Metrics Check
    expect(screen.getByTestId('kpi-treatment-rate').textContent).toContain('63.4%');
    expect(screen.getByTestId('kpi-control-rate').textContent).toContain('32.0%');
    expect(screen.getByTestId('kpi-incremental-lift').textContent).toContain('+31.4%');
    expect(screen.getByTestId('kpi-net-revenue').textContent).toContain('₹4,26,200');
  });

  it('renders refund-adjusted net revenue formula callout banner', async () => {
    (api.get as any).mockResolvedValueOnce({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('refund-adjustment-callout')).toBeDefined();
    });

    const callout = screen.getByTestId('refund-adjustment-callout');
    expect(callout.textContent).toContain('Refund-Adjusted Net Value');
    expect(callout.textContent).toContain('Gross: ₹9,42,000');
  });

  it('renders Treatment vs Control bar chart and trend chart containers', async () => {
    (api.get as any).mockResolvedValueOnce({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('chart-treatment-vs-control')).toBeDefined();
      expect(screen.getByTestId('chart-revenue-trend')).toBeDefined();
      expect(screen.getByTestId('chart-policy-rejections')).toBeDefined();
    });
  });

  it('renders failure scenario and recovery action breakdown tables', async () => {
    (api.get as any).mockResolvedValueOnce({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('table-scenario-breakdown')).toBeDefined();
      expect(screen.getByTestId('table-action-breakdown')).toBeDefined();
    });

    // Check Scenario Table Entries
    expect(screen.getByText('PAYMENT_FAILURE')).toBeDefined();
    expect(screen.getByText('CHECKOUT_ABANDONMENT')).toBeDefined();
    expect(screen.getByText('SUBSCRIPTION_LAPSE')).toBeDefined();

    // Check Action Table Entries
    expect(screen.getAllByText('PAYMENT_LINK').length).toBeGreaterThan(0);
    expect(screen.getByText('RECOVERY_MESSAGE')).toBeDefined();
    expect(screen.getByText('CUSTOMER_NUDGE')).toBeDefined();
  });

  it('toggles execution mode when mode switch button is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: mockAnalyticsData });

    render(
      <BrowserRouter>
        <RecoveryAnalyticsPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('SIMULATION MODE')).toBeDefined();
    });

    const modeBtn = screen.getByText('SIMULATION MODE');
    fireEvent.click(modeBtn);

    await waitFor(() => {
      expect(screen.getByText('REAL_TEST MODE')).toBeDefined();
    });
    expect(currentApiState.mode).toBe('REAL_TEST');
  });
});
