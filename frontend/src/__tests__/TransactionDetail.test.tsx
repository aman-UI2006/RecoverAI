import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { TransactionDetailPage } from '../pages/TransactionDetail';
import * as apiModule from '../services/api';

describe('Step 31: Transaction Detail Page Test Suite', () => {
  beforeEach(() => {
    apiModule.currentApiState.merchantId = 'm_alpha_123';
    apiModule.currentApiState.mode = 'SIMULATION';
    vi.restoreAllMocks();
  });

  it('1. Renders transaction detail overview banner (ID, Customer, Amount, Status, Mode)', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        id: 'pay_tx101',
        merchant_id: 'm_alpha_123',
        customer_id: 'cust_8871A',
        customer_email: 'buyer@example.com',
        amount: 4999.0,
        currency: 'INR',
        status: 'RECOVERED',
        scenario_type: 'PAYMENT_FAILURE',
        retry_count: 1,
        recovery_cycle: 1,
        mode: 'SIMULATION',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/pay_tx101']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('pay_tx101')).toBeInTheDocument();
      expect(screen.getByText('RECOVERED')).toBeInTheDocument();
      expect(screen.getByText('PAYMENT_FAILURE')).toBeInTheDocument();
    });
  });

  it('2. Renders LifecycleStepper component highlighting current recovery state', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        id: 'pay_tx101',
        status: 'EXECUTING',
        amount: 1000.0,
        currency: 'INR',
        scenario_type: 'CHECKOUT_ABANDONMENT',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/pay_tx101']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('End-to-End Recovery Flow')).toBeInTheDocument();
      expect(screen.getByText('Current Status: EXECUTING')).toBeInTheDocument();
      expect(screen.getByText('1. Detect')).toBeInTheDocument();
      expect(screen.getByText('5. Execute')).toBeInTheDocument();
    });
  });

  it('3. Renders Root Cause Diagnosis panel with failure code and confidence score', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        id: 'pay_tx101',
        status: 'DIAGNOSED',
        amount: 2500.0,
        currency: 'INR',
        scenario_type: 'BANK_DOWNTIME',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        diagnosis: {
          id: 'diag_101',
          failure_code: 'BANK_DOWNTIME_HDFC',
          failure_category: 'ISSUER_DOWNTIME',
          root_cause_explanation: 'HDFC gateway latency timeout.',
          confidence_score: 0.94,
          diagnosis_source: 'ML_CLASSIFIER',
          created_at: new Date().toISOString(),
        },
      },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/pay_tx101']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('BANK_DOWNTIME_HDFC')).toBeInTheDocument();
      expect(screen.getByText('ML_CLASSIFIER')).toBeInTheDocument();
      expect(screen.getByText('94%')).toBeInTheDocument();
    });
  });

  it('4. Renders AI Recommendation & Policy Decision breakdown panel', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        id: 'pay_tx101',
        status: 'APPROVED',
        amount: 3000.0,
        currency: 'INR',
        scenario_type: 'PAYMENT_FAILURE',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        recovery_attempts: [
          {
            id: 'att_001',
            logical_operation_key: 'op_pay_tx101_01',
            recommended_action: 'RETRY_SMART_ROUTING',
            policy_status: 'APPROVED',
            execution_status: 'SUCCESS',
            razorpay_payment_link_id: 'plink_TEST123',
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/pay_tx101']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('RETRY_SMART_ROUTING')).toBeInTheDocument();
      expect(screen.getByText('op_pay_tx101_01')).toBeInTheDocument();
      expect(screen.getByText('plink_TEST123')).toBeInTheDocument();
    });
  });

  it('5. Renders Cryptographic Audit Timeline with SHA-256 hashes', async () => {
    vi.spyOn(apiModule.api, 'get').mockResolvedValue({
      data: {
        id: 'pay_tx101',
        status: 'RECOVERED',
        amount: 5000.0,
        currency: 'INR',
        scenario_type: 'PAYMENT_FAILURE',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        audit_timeline: [
          {
            id: 'evt_001',
            event_type: 'EVENT_INGESTED',
            actor: 'INGESTION_SERVICE',
            state_from: undefined,
            state_to: 'DETECTED',
            details: {},
            event_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
            created_at: new Date().toISOString(),
          },
        ],
      },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/pay_tx101']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('EVENT_INGESTED')).toBeInTheDocument();
      expect(screen.getByText('Actor: INGESTION_SERVICE')).toBeInTheDocument();
      expect(screen.getByText('a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef')).toBeInTheDocument();
    });
  });

  it('6. Displays Transaction Not Found error state when transaction ID returns 404', async () => {
    vi.spyOn(apiModule.api, 'get').mockRejectedValue({
      response: { status: 404, data: { detail: 'Transaction not found' } },
    });

    render(
      <MemoryRouter initialEntries={['/transactions/not_found_tx']}>
        <Routes>
          <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Transaction Not Found')).toBeInTheDocument();
      expect(screen.getByText(/not_found_tx/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Back to Recovery Queue/i })).toBeInTheDocument();
    });
  });
});
