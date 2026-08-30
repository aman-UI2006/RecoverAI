import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RevenueRiskPage } from '../pages/RevenueRisk';
import * as apiModule from '../services/api';

describe('Step 29: Revenue Risk Page Test Suite', () => {
  beforeEach(() => {
    apiModule.currentApiState.merchantId = 'm_alpha_123';
    apiModule.currentApiState.mode = 'SIMULATION';
    vi.restoreAllMocks();
  });

  it('1. Renders Revenue Risk Exposure header and summary cards', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'risk_001',
            transaction_id: 'pay_RF1001A',
            merchant_id: 'm_alpha_123',
            customer_email: 'priya.sharma@example.com',
            customer_name: 'Priya Sharma',
            amount_in_paise: 450000,
            currency: 'INR',
            status: 'DETECTED',
            scenario_type: 'PAYMENT_FAILURE',
            risk_level: 'CRITICAL',
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <BrowserRouter>
        <RevenueRiskPage />
      </BrowserRouter>
    );

    expect(screen.getByText('Revenue Risk Exposure')).toBeInTheDocument();
    expect(screen.getByText('Total Value At Risk')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('pay_RF1001A')).toBeInTheDocument();
      expect(screen.getByText('Priya Sharma')).toBeInTheDocument();
    });
  });

  it('2. Filters table when scenario tab is clicked', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'risk_001',
            transaction_id: 'pay_RF1001A',
            merchant_id: 'm_alpha_123',
            amount_in_paise: 450000,
            status: 'DETECTED',
            scenario_type: 'PAYMENT_FAILURE',
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <BrowserRouter>
        <RevenueRiskPage />
      </BrowserRouter>
    );

    const btn = screen.getByRole('button', { name: 'Payment Failure' });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(apiModule.api.get).toHaveBeenCalledWith('/api/v1/transactions', expect.objectContaining({
        params: expect.objectContaining({ scenario_type: 'PAYMENT_FAILURE' }),
      }));
    });
  });

  it('3. Filters transactions locally via real-time search query', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'risk_001',
            transaction_id: 'pay_RF1001A',
            merchant_id: 'm_alpha_123',
            customer_email: 'priya@example.com',
            amount_in_paise: 450000,
            status: 'DETECTED',
            scenario_type: 'PAYMENT_FAILURE',
            created_at: new Date().toISOString(),
          },
          {
            id: 'risk_002',
            transaction_id: 'pay_RF9999Z',
            merchant_id: 'm_alpha_123',
            customer_email: 'rahul@example.com',
            amount_in_paise: 200000,
            status: 'DETECTED',
            scenario_type: 'PAYMENT_FAILURE',
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <BrowserRouter>
        <RevenueRiskPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('pay_RF1001A')).toBeInTheDocument();
      expect(screen.getByText('pay_RF9999Z')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/Search Transaction ID or Email/i);
    fireEvent.change(searchInput, { target: { value: 'priya' } });

    expect(screen.getByText('pay_RF1001A')).toBeInTheDocument();
    expect(screen.queryByText('pay_RF9999Z')).not.toBeInTheDocument();
  });

  it('4. Renders informative empty state banner when no transactions match filter', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: { items: [] },
    });

    render(
      <BrowserRouter>
        <RevenueRiskPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No revenue currently at risk')).toBeInTheDocument();
    });
  });
});
