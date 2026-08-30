import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Layout } from '../components/Layout';
import * as apiModule from '../services/api';


describe('Step 27: Frontend Foundation Layout & Component Test Suite', () => {
  beforeEach(() => {
    apiModule.currentApiState.merchantId = 'm_alpha_123';
    apiModule.currentApiState.mode = 'SIMULATION';
    apiModule.currentApiState.apiKey = 'key_admin_secret_999';
    apiModule.currentApiState.token = null;

    vi.spyOn(apiModule, 'checkBackendHealth').mockResolvedValue({ status: 'ok' });
  });

  it('1. Renders RecoverAI logo and navigation sidebar with all 9 dashboard links', () => {
    render(
      <BrowserRouter>
        <Layout>
          <div>Test Children Content</div>
        </Layout>
      </BrowserRouter>
    );

    expect(screen.getAllByText('RecoverAI').length).toBeGreaterThan(0);
    expect(screen.getByText('Command Center')).toBeInTheDocument();
    expect(screen.getByText('Revenue Risk')).toBeInTheDocument();
    expect(screen.getByText('Recovery Queue')).toBeInTheDocument();
    expect(screen.getByText('Transaction Detail')).toBeInTheDocument();
    expect(screen.getByText('AI Decision Center')).toBeInTheDocument();
    expect(screen.getByText('Recovery Analytics')).toBeInTheDocument();
    expect(screen.getByText('Audit Center')).toBeInTheDocument();
    expect(screen.getByText('Policy Manager')).toBeInTheDocument();
    expect(screen.getByText('Human Review')).toBeInTheDocument();
  });

  it('2. Renders active execution mode badge and toggles between SIMULATION and REAL_TEST', () => {
    render(
      <BrowserRouter>
        <Layout>
          <div>Workspace Content</div>
        </Layout>
      </BrowserRouter>
    );

    const modeButton = screen.getByRole('button', { name: /SIMULATION/i });
    expect(modeButton).toBeInTheDocument();

    // Toggle mode
    fireEvent.click(modeButton);
    expect(screen.getByRole('button', { name: /REAL_TEST/i })).toBeInTheDocument();
    expect(apiModule.currentApiState.mode).toBe('REAL_TEST');

    // Toggle back
    fireEvent.click(screen.getByRole('button', { name: /REAL_TEST/i }));
    expect(screen.getByRole('button', { name: /SIMULATION/i })).toBeInTheDocument();
    expect(apiModule.currentApiState.mode).toBe('SIMULATION');
  });

  it('3. Renders merchant context selector and updates API state upon change', () => {
    render(
      <BrowserRouter>
        <Layout>
          <div>Workspace Content</div>
        </Layout>
      </BrowserRouter>
    );

    const select = screen.getByRole('combobox');
    expect(select).toHaveValue('m_alpha_123');

    fireEvent.change(select, { target: { value: 'm_beta_456' } });
    expect(select).toHaveValue('m_beta_456');
    expect(apiModule.currentApiState.merchantId).toBe('m_beta_456');
  });

  it('4. Renders child content cleanly within layout wrapper', () => {
    render(
      <BrowserRouter>
        <Layout>
          <div data-testid="custom-child">Child Component Content</div>
        </Layout>
      </BrowserRouter>
    );

    expect(screen.getByTestId('custom-child')).toBeInTheDocument();
    expect(screen.getByText('Child Component Content')).toBeInTheDocument();
  });

  it('5. Verifies API client instance configuration and headers', () => {
    expect(apiModule.api.defaults.baseURL).toBeTruthy();
    expect(apiModule.api.interceptors.request).toBeDefined();
  });
});
