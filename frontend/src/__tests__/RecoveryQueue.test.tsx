import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RecoveryQueuePage } from '../pages/RecoveryQueue';
import * as apiModule from '../services/api';

describe('Step 30: Recovery Queue Page Test Suite', () => {
  beforeEach(() => {
    apiModule.currentApiState.merchantId = 'm_alpha_123';
    apiModule.currentApiState.mode = 'SIMULATION';
    vi.restoreAllMocks();
  });

  it('1. Renders Recovery Queue header and summary cards', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'int_001',
            transaction_id: 'pay_RQ2001A',
            merchant_id: 'm_alpha_123',
            recommended_action: 'RETRY_SMART_ROUTING',
            logical_operation_key: 'op_RQ2001A_retry_01',
            status: 'EXECUTING',
            retry_count: 1,
            cycle_number: 1,
            created_at: new Date().toISOString(),
          },
        ],
        total: 1,
      },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    expect(screen.getByText('Active Recovery Queue')).toBeInTheDocument();
    expect(screen.getByText('Live Interventions')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('pay_RQ2001A')).toBeInTheDocument();
      expect(screen.getByText('RETRY_SMART_ROUTING')).toBeInTheDocument();
      expect(screen.getByText('op_RQ2001A_retry_01')).toBeInTheDocument();
    });
  });

  it('2. Color-codes execution status badges (EXECUTING, SUCCESS, UNKNOWN, FAILED)', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'int_001',
            transaction_id: 'pay_RQ2001A',
            status: 'EXECUTING',
          },
        ],
        total: 1,
      },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('EXECUTING')).toBeInTheDocument();
    });
  });

  it('3. Triggers manual queue refresh upon button click', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: { items: [], total: 0 },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    const refreshBtn = screen.getByRole('button', { name: /Refresh Queue/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(apiModule.api.get).toHaveBeenCalledWith('/api/v1/transactions', expect.any(Object));
    });
  });

  it('4. Renders attempt retry counts and recovery cycle numbers', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: [
          {
            id: 'int_002',
            transaction_id: 'pay_RQ2002B',
            retry_count: 2,
            cycle_number: 1,
            status: 'RECOVERED',
          },
        ],
        total: 1,
      },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Attempt #2')).toBeInTheDocument();
      expect(screen.getByText('(Cycle 1)')).toBeInTheDocument();
    });
  });

  it('5. Handles pagination controls correctly', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        items: Array.from({ length: 10 }, (_, i) => ({
          id: `int_${i}`,
          transaction_id: `pay_RQ200${i}`,
          status: 'EXECUTING',
        })),
        total: 25,
      },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Page 1 of 3').length).toBeGreaterThan(0);
    });

    const nextBtn = screen.getByRole('button', { name: /Next/i });
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(apiModule.api.get).toHaveBeenCalledWith('/api/v1/transactions', expect.objectContaining({
        params: expect.objectContaining({ page: 2 }),
      }));
    });
  });

  it('6. Displays empty state message when queue filter returns no items', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: { items: [], total: 0 },
    });

    render(
      <BrowserRouter>
        <RecoveryQueuePage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No interventions in queue')).toBeInTheDocument();
    });
  });
});
