import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { CommandCenterPage } from '../pages/CommandCenter';
import * as apiModule from '../services/api';

// Mock ResizeObserver for Recharts compatibility in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

describe('Step 28: Command Center Page & Stat Cards Test Suite', () => {
  beforeEach(() => {
    apiModule.currentApiState.merchantId = 'm_alpha_123';
    apiModule.currentApiState.mode = 'SIMULATION';
    vi.restoreAllMocks();
  });

  it('1. Renders Command Center header and title', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        treatment_metrics: { total_eligible_amount: 100000, recovered_amount: 50000, recovery_rate: 0.5 },
        control_metrics: { total_eligible_amount: 100000, recovered_amount: 20000, recovery_rate: 0.2 },
        treatment_recovery_rate: 0.5,
        control_recovery_rate: 0.2,
        incremental_recovery_rate: 0.3,
        treatment_recovered_amount: 50000,
        control_recovered_amount: 20000,
        estimated_incremental_recovered_amount: 30000,
        net_incremental_revenue: 28000,
        mode: 'SIMULATION',
      },
    });

    render(
      <BrowserRouter>
        <CommandCenterPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Command Center')).toBeInTheDocument();
    expect(screen.getByText(/Live Telemetry/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Revenue at Risk')).toBeInTheDocument();
      expect(screen.getByText('Recovered Revenue')).toBeInTheDocument();
      expect(screen.getByText('Incremental Lift')).toBeInTheDocument();
      expect(screen.getByText('Net Recovery ROI')).toBeInTheDocument();
      expect(screen.getByText('Recovery Rate')).toBeInTheDocument();
    });
  });

  it('2. Reflects global mode changes when apiStateChanged is dispatched', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        treatment_metrics: { total_eligible_amount: 100000 },
        treatment_recovery_rate: 0.5,
        control_recovery_rate: 0.2,
        incremental_recovery_rate: 0.3,
        treatment_recovered_amount: 50000,
        control_recovered_amount: 20000,
        estimated_incremental_recovered_amount: 30000,
        net_incremental_revenue: 28000,
        mode: 'SIMULATION',
      },
    });

    render(
      <BrowserRouter>
        <CommandCenterPage />
      </BrowserRouter>
    );

    expect(screen.getByText(/SIMULATION MODE/i)).toBeInTheDocument();

    // Trigger global mode change via apiStateChanged event from Header
    apiModule.currentApiState.mode = 'REAL_TEST';
    window.dispatchEvent(new CustomEvent('apiStateChanged'));

    await waitFor(() => {
      expect(screen.getByText(/REAL_TEST MODE/i)).toBeInTheDocument();
    });
  });

  it('3. Renders fallback telemetry when API call encounters network error', async () => {
    vi.spyOn(apiModule.api, 'get').mockRejectedValue(new Error('Network error'));

    render(
      <BrowserRouter>
        <CommandCenterPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Command Center')).toBeInTheDocument();
      expect(screen.getByText('Revenue at Risk')).toBeInTheDocument();
      expect(screen.getByText('pay_L9x1K8z9A01')).toBeInTheDocument();
    });
  });
});
