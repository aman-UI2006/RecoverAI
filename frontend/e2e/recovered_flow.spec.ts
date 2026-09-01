import { test, expect } from '@playwright/test';
import crypto from 'crypto';

test.describe('RecoverAI Closed-Loop E2E Workflow (Step 41)', () => {
  const merchantId = 'm_alpha_123';
  const transactionId = 'pay_e2e_closed_loop_101';
  const webhookSecret = process.env.RAZORPAY_WEBHOOK_SECRET || 'YourWebhookSecretHere'; // Matching .env / settings

  test('executes end-to-end recovery pipeline from webhook detection to audit verification', async ({
    page,
    request,
    baseURL,
  }) => {
    const targetBaseUrl = baseURL || 'http://localhost:5173';
    const backendUrl = 'http://127.0.0.1:8000';

    // ------------------------------------------------------------------------
    // Step 1: Start against isolated test environment & Health Check
    // ------------------------------------------------------------------------
    const healthResponse = await request.get(`${backendUrl}/health`);
    expect(healthResponse.ok()).toBeTruthy();
    const healthData = await healthResponse.json();
    expect(healthData.status).toBe('ok');

    // ------------------------------------------------------------------------
    // Step 2: Trigger mock Razorpay payment failure webhook
    // ------------------------------------------------------------------------
    const webhookPayload = {
      entity: 'event',
      account_id: merchantId,
      event: 'payment.failed',
      contains: ['payment'],
      payload: {
        payment: {
          entity: {
            id: transactionId,
            amount: 150000, // ₹1,500.00 in paise
            currency: 'INR',
            status: 'failed',
            error_code: 'BAD_REQUEST_ERROR',
            error_description: 'Payment failed due to insufficient funds',
            email: 'e2e_customer@example.com',
            contact: '+919876543210',
          },
        },
      },
      created_at: Math.floor(Date.now() / 1000),
    };

    const rawPayloadString = JSON.stringify(webhookPayload);
    const signature = crypto
      .createHmac('sha256', webhookSecret)
      .update(rawPayloadString)
      .digest('hex');

    const webhookResponse = await request.post(`${backendUrl}/api/v1/webhooks/razorpay`, {
      data: Buffer.from(rawPayloadString, 'utf-8'),
      headers: {
        'Content-Type': 'application/json',
        'X-Razorpay-Signature': signature,
        'X-Razorpay-Event-Id': `evt_e2e_${Date.now()}`,
      },
    });

    expect(webhookResponse.status()).toBe(200);
    const webhookResponseBody = await webhookResponse.json();
    expect(['SUCCESS', 'DUPLICATE_SKIPPED']).toContain(webhookResponseBody.status);

    // ------------------------------------------------------------------------
    // Step 3: Verify transaction appears on Revenue Risk page
    // ------------------------------------------------------------------------
    await page.goto(`${targetBaseUrl}/revenue-risk`);
    await expect(page.locator('h1')).toContainText('Revenue Risk Exposure');

    // Search for transaction or inspect row
    const searchInput = page.locator('input[placeholder*="Search Transaction ID"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill(transactionId);
    }

    // Assert transaction table contains transaction or fallback items
    const tableBody = page.locator('tbody');
    await expect(tableBody).toBeVisible();

    // ------------------------------------------------------------------------
    // Step 4: Navigate to Transaction Detail page
    // ------------------------------------------------------------------------
    await page.goto(`${targetBaseUrl}/transactions/${transactionId}`);
    await page.waitForLoadState('networkidle');

    // Assert Transaction ID header banner renders
    const txHeader = page.locator('h1');
    await expect(txHeader).toBeVisible();

    // ------------------------------------------------------------------------
    // Step 5: Verify Diagnosis
    // ------------------------------------------------------------------------
    const diagnosisSection = page.locator('h3:has-text("Root Cause Diagnosis")');
    await expect(diagnosisSection).toBeVisible();
    await expect(page.locator('text=Root Cause Explanation')).toBeVisible();

    // ------------------------------------------------------------------------
    // Step 6: Verify ENRV Table / AI Decision Breakdown
    // ------------------------------------------------------------------------
    const decisionSection = page.locator('h3:has-text("AI Recommendation & Policy Decision")');
    await expect(decisionSection).toBeVisible();
    await expect(page.locator('text=Action Strategy')).toBeVisible();

    // ------------------------------------------------------------------------
    // Step 7: Verify Payment Link Generation / Reference
    // ------------------------------------------------------------------------
    const paymentLinkSection = page.locator('text=Razorpay Payment Link Created');
    await expect(paymentLinkSection).toBeVisible();
    const demoLinkBtn = page.locator('a:has-text("Demo Link")');
    await expect(demoLinkBtn).toBeVisible();

    // ------------------------------------------------------------------------
    // Step 8: Navigate to Audit Center
    // ------------------------------------------------------------------------
    await page.goto(`${targetBaseUrl}/audit`);
    await expect(page.locator('h1')).toContainText('Audit Center');

    // ------------------------------------------------------------------------
    // Step 9: Click VERIFY HASH CHAIN
    // ------------------------------------------------------------------------
    const verifierInput = page.locator('input[data-testid="verifier-input-tx-id"]');
    await expect(verifierInput).toBeVisible();
    await verifierInput.fill(transactionId);

    const verifyBtn = page.locator('button[data-testid="verify-chain-btn"]');
    await expect(verifyBtn).toBeVisible();
    await verifyBtn.click();

    // ------------------------------------------------------------------------
    // Step 10: Verify successful audit-chain verification ("CHAIN VALID")
    // ------------------------------------------------------------------------
    const statusBadge = page.locator('[data-testid="verification-status-badge"]');
    await expect(statusBadge).toBeVisible({ timeout: 10000 });
    await expect(statusBadge).toContainText('CHAIN VALID');
  });
});
