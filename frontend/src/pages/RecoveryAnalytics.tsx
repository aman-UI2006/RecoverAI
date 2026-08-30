import React from 'react';
import { BarChart3 } from 'lucide-react';
import { PagePlaceholder } from './PagePlaceholder';

export const RecoveryAnalyticsPage: React.FC = () => (
  <PagePlaceholder
    title="Recovery Analytics"
    subtitle="Control vs Treatment evaluation runs, recovery rates, and net financial lift"
    stepNumber={33}
    icon={BarChart3}
  />
);
