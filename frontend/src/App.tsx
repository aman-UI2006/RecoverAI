import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';

import { CommandCenterPage } from './pages/CommandCenter';
import { RevenueRiskPage } from './pages/RevenueRisk';
import { RecoveryQueuePage } from './pages/RecoveryQueue';
import { TransactionDetailPage } from './pages/TransactionDetail';
import { AIDecisionCenterPage } from './pages/AIDecisionCenter';
import { RecoveryAnalyticsPage } from './pages/RecoveryAnalytics';
import { AuditCenterPage } from './pages/AuditCenter';
import { PolicyManagerPage } from './pages/PolicyManager';
import { HumanReviewPage } from './pages/HumanReviewPage';

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<CommandCenterPage />} />
            <Route path="/revenue-risk" element={<RevenueRiskPage />} />
            <Route path="/recovery-queue" element={<RecoveryQueuePage />} />
            <Route path="/transactions/:id" element={<TransactionDetailPage />} />
            <Route path="/ai-decision" element={<AIDecisionCenterPage />} />
            <Route path="/ai-decision/:id" element={<AIDecisionCenterPage />} />
            <Route path="/analytics" element={<RecoveryAnalyticsPage />} />
            <Route path="/recovery-analytics" element={<RecoveryAnalyticsPage />} />
            <Route path="/audit" element={<AuditCenterPage />} />
            <Route path="/audit-center" element={<AuditCenterPage />} />
            <Route path="/policies" element={<PolicyManagerPage />} />
            <Route path="/human-review" element={<HumanReviewPage />} />
            {/* Fallback route */}
            <Route path="*" element={<CommandCenterPage />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ErrorBoundary>
  );
};

export default App;
