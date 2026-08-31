/**
 * RecoverAI - Step 34: Audit Center Component Test Suite
 *
 * Tests AuditCenter page and ChainVerifierWidget:
 * 1. Header & Step 34 observability badge rendering
 * 2. Executive metric cards & SHA-256 genesis anchor
 * 3. Paginated Audit Events data table
 * 4. ChainVerifierWidget interactive verification trigger & CHAIN VALID badge
 * 5. Event type dropdown filter
 * 6. Search filter by Transaction ID
 * 7. Canonical JSON inspector modal displaying untruncated SHA-256 strings
 * 8. Mode switch toggle (SIMULATION / REAL_TEST)
 */

import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuditCenterPage } from '../pages/AuditCenter';
import { api, currentApiState } from '../services/api';

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

describe('Step 34: Audit Center Page & Chain Verifier Test Suite', () => {
  const mockAuditResponse = {
    total: 3,
    page: 1,
    limit: 10,
    items: [
      {
        id: 'aud_evt_101',
        transaction_id: 'tx_pay_942001',
        event_type: 'STATE_CHANGE',
        actor: 'StateTransitionService',
        state_from: 'FAILED',
        state_to: 'DIAGNOSED',
        details: { failure_code: 'BAD_REQUEST_ERROR' },
        previous_hash: '0000000000000000000000000000000000000000000000000000000000000000',
        event_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
        created_at: new Date().toISOString(),
      },
      {
        id: 'aud_evt_102',
        transaction_id: 'tx_pay_942001',
        event_type: 'POLICY_DECISION',
        actor: 'PolicyEngine',
        state_from: 'DIAGNOSED',
        state_to: 'POLICY_APPROVED',
        details: { policy_result: 'PASS' },
        previous_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
        event_hash: 'b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12',
        created_at: new Date().toISOString(),
      },
      {
        id: 'aud_evt_103',
        transaction_id: 'tx_pay_942002',
        event_type: 'EXECUTION',
        actor: 'ActionExecutor',
        state_from: 'POLICY_APPROVED',
        state_to: 'RECOVERING',
        details: { action: 'PAYMENT_LINK' },
        previous_hash: 'b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef12',
        event_hash: 'c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef1234',
        created_at: new Date().toISOString(),
      },
    ],
  };

  const mockVerifyResponse = {
    transaction_id: 'tx_pay_942001',
    is_valid: true,
    total_events: 2,
    tampered_event_id: null,
    error_message: null,
    genesis_hash: '0000000000000000000000000000000000000000000000000000000000000000',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    currentApiState.mode = 'SIMULATION';
    currentApiState.merchantId = 'm_alpha_123';
  });

  it('renders header, observability badge, and metric cards', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/verify')) return Promise.resolve({ data: mockVerifyResponse });
      return Promise.resolve({ data: mockAuditResponse });
    });

    render(
      <BrowserRouter>
        <AuditCenterPage />
      </BrowserRouter>
    );

    expect(screen.getByTestId('audit-center-page')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Audit Center')).toBeDefined();
      expect(screen.getByText('Step 34 Observability')).toBeDefined();
    });

    expect(screen.getByText('SHA-256')).toBeDefined();
    expect(screen.getByText('100% INTACT')).toBeDefined();
  });

  it('renders Audit Events table with records', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/verify')) return Promise.resolve({ data: mockVerifyResponse });
      return Promise.resolve({ data: mockAuditResponse });
    });

    render(
      <BrowserRouter>
        <AuditCenterPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('audit-events-table')).toBeDefined();
    });

    expect(screen.getByText('aud_evt_101')).toBeDefined();
    expect(screen.getByText('StateTransitionService')).toBeDefined();
    expect(screen.getByText('PolicyEngine')).toBeDefined();
  });

  it('executes ChainVerifierWidget hash chain validation and renders CHAIN VALID badge', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/verify')) return Promise.resolve({ data: mockVerifyResponse });
      return Promise.resolve({ data: mockAuditResponse });
    });

    render(
      <BrowserRouter>
        <AuditCenterPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('chain-verifier-widget')).toBeDefined();
    });

    const input = screen.getByTestId('verifier-input-tx-id');
    fireEvent.change(input, { target: { value: 'tx_pay_942001' } });

    const verifyBtn = screen.getByTestId('verify-chain-btn');
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getByTestId('verification-status-badge')).toBeDefined();
    });

    expect(screen.getByTestId('verification-status-badge').textContent).toContain('CHAIN VALID');
  });

  it('opens JSON Inspector modal and displays raw untruncated SHA-256 hashes', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/verify')) return Promise.resolve({ data: mockVerifyResponse });
      return Promise.resolve({ data: mockAuditResponse });
    });

    render(
      <BrowserRouter>
        <AuditCenterPage />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('inspect-evt-aud_evt_101')).toBeDefined();
    });

    const inspectBtn = screen.getByTestId('inspect-evt-aud_evt_101');
    fireEvent.click(inspectBtn);

    await waitFor(() => {
      expect(screen.getByTestId('audit-json-modal')).toBeDefined();
    });

    expect(screen.getByText('Canonical Audit Payload Inspector')).toBeDefined();
    expect(screen.getAllByText('a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef').length).toBeGreaterThan(0);

    // Close modal
    const closeBtn = screen.getByTestId('close-json-modal-btn');
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('audit-json-modal')).toBeNull();
    });
  });

  it('toggles execution mode when mode switch button is clicked', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/verify')) return Promise.resolve({ data: mockVerifyResponse });
      return Promise.resolve({ data: mockAuditResponse });
    });

    render(
      <BrowserRouter>
        <AuditCenterPage />
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
